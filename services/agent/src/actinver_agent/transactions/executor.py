"""transaction-service core: the only component that places orders (ADR-0010).

The agent's state is untrusted input here. Every constraint is re-derived from
the product master; the step-up assertion is a hardware signature over a
server-issued challenge (ADR-0017); submissions are idempotent.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import orjson
import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from actinver_agent.audit.record import new_evidence_id, retention_for
from actinver_agent.graph.state import FormSpec, Money
from actinver_agent.ports import (
    AuditPort,
    ChallengeRepository,
    CoreBankingPort,
    DeviceRepository,
    FormSpecRepository,
    IdempotencyRepository,
    OmsPort,
    OrderReceipt,
    StepUpChallenge,
)
from actinver_agent.transactions import errors as txerr
from actinver_agent.transactions.formspec import amount_hash, is_expired, verify_form_spec

log = structlog.get_logger(__name__)


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def verify_es256(public_jwk: dict[str, Any], message: bytes, signature_b64url: str) -> bool:
    """Verify a raw (r||s) or DER ES256 signature over ``message`` with a P-256 JWK."""
    try:
        x = int.from_bytes(_b64url_decode(public_jwk["x"]), "big")
        y = int.from_bytes(_b64url_decode(public_jwk["y"]), "big")
        public_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()
        signature = _b64url_decode(signature_b64url)
        if len(signature) == 64:
            r = int.from_bytes(signature[:32], "big")
            s = int.from_bytes(signature[32:], "big")
            signature = encode_dss_signature(r, s)
        public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, KeyError, ValueError, TypeError):
        return False


class TransactionExecutor:
    def __init__(
        self,
        *,
        core: CoreBankingPort,
        oms: OmsPort,
        form_specs: FormSpecRepository,
        idempotency: IdempotencyRepository,
        challenges: ChallengeRepository,
        devices: DeviceRepository,
        audit: AuditPort,
        form_key: bytes,
        form_key_version: int = 1,
        challenge_ttl_s: int = 120,
        idempotency_ttl_s: int = 86_400,
    ) -> None:
        self._core = core
        self._oms = oms
        self._form_specs = form_specs
        self._idempotency = idempotency
        self._challenges = challenges
        self._devices = devices
        self._audit = audit
        self._form_key = form_key
        self._form_key_version = form_key_version
        self._challenge_ttl = challenge_ttl_s
        self._idempotency_ttl = idempotency_ttl_s

    # ── Step-up ──────────────────────────────────────────────────────────────

    async def issue_challenge(
        self, *, client_id: str, form_id: str, amount_hash: str
    ) -> StepUpChallenge:
        nonce = _b64url_encode(secrets.token_bytes(32))
        challenge_id = f"ch_{secrets.token_hex(12)}"
        expires_at = datetime.now(UTC) + timedelta(seconds=self._challenge_ttl)
        await self._challenges.store(
            challenge_id=challenge_id,
            client_id=client_id,
            form_id=form_id,
            amount_hash=amount_hash,
            nonce=nonce,
            expires_at=expires_at,
        )
        log.info("stepup.challenge_issued", form_id=form_id)
        return StepUpChallenge(challenge_id=challenge_id, challenge=nonce, expires_at=expires_at)

    # ── Execution ────────────────────────────────────────────────────────────

    async def execute(
        self,
        *,
        client_id: str,
        form_spec: FormSpec,
        values: dict[str, Any],
        acknowledgements: list[str],
        step_up_assertion: str,
        challenge_id: str,
        idempotency_key: str,
        suitability_verdict_id: str | None,
        jkt: str | None = None,
        device_id: str | None = None,
    ) -> OrderReceipt:
        now = datetime.now(UTC)
        request_hash = hashlib.sha256(
            orjson.dumps(
                {"form_id": form_spec.form_id, "values": values, "acks": sorted(acknowledgements)},
                option=orjson.OPT_SORT_KEYS,
                default=str,
            )
        ).hexdigest()

        # Idempotency first: a retry of an already-executed submission returns
        # the stored receipt and never reaches the OMS twice.
        previous = await self._idempotency.get(idempotency_key)
        if previous is not None:
            stored_hash, response = previous
            if stored_hash != request_hash:
                raise txerr.IdempotencyConflict()
            return OrderReceipt(**response, idempotent_replay=True)

        # 1. Nothing in the request is trusted: signature, TTL, single-use, owner.
        if not verify_form_spec(form_spec, self._form_key):
            raise txerr.FormSignatureInvalid()
        if form_spec.client_id != client_id:
            raise txerr.FormClientMismatch()
        if is_expired(form_spec, now=now):
            raise txerr.FormExpired()
        stored = await self._form_specs.get(form_spec.form_id)
        if stored is None:
            raise txerr.FormNotFound("form not issued by this service")
        stored_spec, status = stored
        if status != "ISSUED":
            raise txerr.FormAlreadyUsed()
        if stored_spec.signature != form_spec.signature:
            raise txerr.FormSignatureInvalid("spec does not match the issued one")

        # 2. Mandatory acknowledgements, server-side.
        missing = [a for a in form_spec.required_acknowledgements() if a not in acknowledgements]
        if missing:
            raise txerr.AckRequired(",".join(missing))

        # 3. Values against re-derived limits (never the spec's own).
        money = _money_from_values(values, form_spec)
        requirements = await self._core.get_transaction_requirements(
            client_id=client_id,
            product_id=form_spec.product.id,
            operation=form_spec.operation,
            amount=money.decimal if money else None,
            target_product_id=form_spec.target_product.id if form_spec.target_product else None,
        )
        _validate_against(requirements, values, money)

        # 4. Step-up: signature over the server challenge bound to form + amount.
        challenge = await self._challenges.consume(challenge_id=challenge_id, client_id=client_id)
        if challenge is None:
            raise txerr.StepUpRequired("challenge unknown, used or expired")
        if challenge["form_id"] != form_spec.form_id:
            raise txerr.StepUpRequired("challenge bound to another form")
        if money is not None and challenge["amount_hash"] != amount_hash(money):
            raise txerr.StepUpRequired("challenge bound to another amount")
        if datetime.fromisoformat(str(challenge["expires_at"])) < now:
            raise txerr.StepUpRequired("challenge expired")
        public_jwk = await self._device_key(client_id=client_id, jkt=jkt, device_id=device_id)
        if public_jwk is None or not verify_es256(
            public_jwk, str(challenge["nonce"]).encode("ascii"), step_up_assertion
        ):
            raise txerr.StepUpRequired("assertion does not verify against the device key")

        # 5. Place the order. The idempotency key travels to the OMS.
        order_payload = {
            "operation": form_spec.operation,
            "product_id": form_spec.product.id,
            "target_product_id": form_spec.target_product.id if form_spec.target_product else None,
            "values": values,
            "suitability_verdict_id": suitability_verdict_id or form_spec.suitability_verdict_id,
            "form_id": form_spec.form_id,
        }
        try:
            oms_result = await self._oms.place_order(
                client_id=client_id, order=order_payload, idempotency_key=idempotency_key
            )
        except Exception as exc:
            log.error("transaction.oms_failed", error=type(exc).__name__)
            raise txerr.ExecutionUnavailable() from exc

        # 6. Execution evidence, fail-closed, then persist the submission.
        evidence = await self._audit.write(
            record=self._execution_record(
                client_id=client_id,
                form_spec=form_spec,
                values=values,
                acknowledgements=acknowledgements,
                challenge_id=challenge_id,
                oms_result=oms_result,
                now=now,
                idempotency_key=idempotency_key,
                suitability_verdict_id=(
                    str(order_payload["suitability_verdict_id"])
                    if order_payload.get("suitability_verdict_id")
                    else None
                ),
            ),
            fail_closed=True,
        )
        await self._form_specs.record_submission(
            form_id=form_spec.form_id,
            client_id=client_id,
            values=values,
            acknowledgements=acknowledgements,
            disclosure_versions={d.id: d.version for d in form_spec.disclosures},
            step_up_challenge_id=challenge_id,
            order_id=str(oms_result["order_id"]),
            idempotency_key=idempotency_key,
        )
        await self._form_specs.mark(form_spec.form_id, status="USED")

        receipt = OrderReceipt(
            order_id=str(oms_result["order_id"]),
            status=str(oms_result.get("status", "RECEIVED")),
            settlement_date=str(oms_result.get("settlement_date", "")),
            evidence_id=evidence.evidence_id,
        )
        await self._idempotency.put(
            idempotency_key,
            request_hash=request_hash,
            response={
                "order_id": receipt.order_id,
                "status": receipt.status,
                "settlement_date": receipt.settlement_date,
                "evidence_id": receipt.evidence_id,
            },
            ttl_s=self._idempotency_ttl,
        )
        log.info("transaction.executed", order_id=receipt.order_id, form_id=form_spec.form_id)
        return receipt

    async def _device_key(
        self, *, client_id: str, jkt: str | None, device_id: str | None
    ) -> dict[str, Any] | None:
        if jkt:
            binding = await self._devices.get(client_id=client_id, jkt=jkt)
            if binding is not None:
                return binding.public_key_jwk
        if device_id:
            pem_or_jwk = await self._core.get_device_public_key(
                client_id=client_id, device_id=device_id
            )
            if pem_or_jwk:
                try:
                    parsed: dict[str, Any] = orjson.loads(pem_or_jwk)
                    return parsed
                except orjson.JSONDecodeError:
                    return None
        return None

    def _execution_record(
        self,
        *,
        client_id: str,
        form_spec: FormSpec,
        values: dict[str, Any],
        acknowledgements: list[str],
        challenge_id: str,
        oms_result: dict[str, Any],
        now: datetime,
        idempotency_key: str,
        suitability_verdict_id: str | None,
    ) -> dict[str, Any]:
        return {
            "evidence_id": new_evidence_id(now),
            "schema_version": "1.0",
            "record_type": "execution",
            "thread_id": form_spec.thread_id,
            "turn_id": f"{form_spec.turn_id}:exec",
            "client_id": client_id,
            "created_at": now.isoformat(),
            "channel": "form",
            "service_type": "no_asesorado",
            "service_subtype": "ejecucion_de_operaciones",
            "intent": f"transact_{form_spec.operation.lower()}",
            "form_spec": form_spec.model_dump(mode="json"),
            "submission": {
                "values": values,
                "acknowledgements": acknowledgements,
                "disclosure_versions": {d.id: d.version for d in form_spec.disclosures},
                "step_up_challenge_id": challenge_id,
                "idempotency_key": idempotency_key,
            },
            "suitability_verdict_id": suitability_verdict_id,
            "receipt": oms_result,
            "response": {"speech": None, "ui_payload": [], "refused": False},
            "retention": retention_for(now),
        }


def _money_from_values(values: dict[str, Any], spec: FormSpec) -> Money | None:
    raw = values.get("amount")
    if raw is None:
        return None
    if isinstance(raw, dict):
        try:
            return Money.model_validate(raw)
        except ValueError as exc:
            raise txerr.LimitExceeded("amount must be {amount, currency}") from exc
    # A bare number is rejected: monetary values carry an explicit currency.
    raise txerr.LimitExceeded(f"amount must carry a currency ({spec.product.currency})")


def _validate_against(
    requirements: dict[str, Any], values: dict[str, Any], money: Money | None
) -> None:
    fields = {f["key"]: f for f in requirements.get("fields", [])}
    for key, field in fields.items():
        if field.get("required", True) and key not in values:
            raise txerr.LimitExceeded(f"missing field {key}")
    if money is not None and "amount" in fields:
        field = fields["amount"]
        if field.get("currency") and field["currency"] != money.currency:
            raise txerr.LimitExceeded("currency mismatch")
        try:
            amount = money.decimal
            if field.get("min") is not None and amount < Decimal(str(field["min"])):
                raise txerr.LimitExceeded(f"below minimum {field['min']}")
            if field.get("max") is not None and amount > Decimal(str(field["max"])):
                raise txerr.LimitExceeded(f"above maximum {field['max']}")
        except InvalidOperation as exc:
            raise txerr.LimitExceeded("invalid amount") from exc
    for key, field in fields.items():
        if field.get("type") == "select" and key in values and field.get("options"):
            allowed = {o.get("value") for o in field["options"]}
            if values[key] not in allowed:
                raise txerr.LimitExceeded(f"invalid option for {key}")
    buying_power = requirements.get("buying_power")
    if (
        money is not None
        and buying_power is not None
        and money.decimal > Decimal(str(buying_power))
    ):
        raise txerr.LimitExceeded("insufficient buying power")
