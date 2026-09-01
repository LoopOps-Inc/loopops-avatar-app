"""Form Spec signing and construction (ADR-0009).

HMAC-SHA256 over the canonical JSON of the spec with ``client_id`` bound in, a
10-minute TTL and a single-use ``form_id``. The renderer trusts nothing; the
executor re-derives every limit from the product master.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import orjson

from actinver_agent.graph.state import (
    FormDisclosure,
    FormExecution,
    FormField,
    FormProduct,
    FormSpec,
    Money,
    Operation,
)


def _canonical(spec: FormSpec) -> bytes:
    body = spec.model_dump(mode="json", exclude={"signature"})
    return orjson.dumps(body, option=orjson.OPT_SORT_KEYS)


def sign_form_spec(spec: FormSpec, key: bytes) -> str:
    return hmac.new(key, _canonical(spec), hashlib.sha256).hexdigest()


def verify_form_spec(spec: FormSpec, key: bytes) -> bool:
    if not spec.signature:
        return False
    return hmac.compare_digest(sign_form_spec(spec, key), spec.signature)


def amount_hash(money: Money) -> str:
    """Binds a step-up challenge to the declared amount (ADR-0017)."""
    normalised = f"{Decimal(money.amount).quantize(Decimal('0.01')):f}|{money.currency}"
    return hashlib.sha256(normalised.encode()).hexdigest()


def new_form_id() -> str:
    return f"fs_{secrets.token_hex(13)}"


def build_form_spec(
    *,
    requirements: dict[str, Any],
    client_id: str,
    thread_id: str,
    turn_id: str,
    suitability_verdict_id: str | None,
    approved_amount: Money | None,
    disclosure_texts: dict[str, tuple[str, str]],
    key: bytes,
    key_version: int = 1,
    ttl_s: int = 600,
    now: datetime | None = None,
) -> FormSpec:
    """Assemble a signed spec from ``get_transaction_requirements`` output.

    ``requirements`` shape (tool contract): ``operation``, ``product`` {id, name,
    risk_level, currency}, optional ``target_product``, ``fields`` [FormField
    dicts], ``disclosure_ids`` [str] with optional ``ack_ids`` [str],
    ``execution`` {cutoff_local, timezone, settlement, valuation}.
    """
    now = now or datetime.now(UTC)
    ack_ids = set(requirements.get("ack_ids", []))
    disclosures = [
        FormDisclosure(id=d_id, version=version, text=text, ack=d_id in ack_ids)
        for d_id, (text, version) in disclosure_texts.items()
    ]
    spec = FormSpec(
        form_id=new_form_id(),
        client_id=client_id,
        thread_id=thread_id,
        turn_id=turn_id,
        operation=_operation(requirements["operation"]),
        product=FormProduct.model_validate(requirements["product"]),
        target_product=(
            FormProduct.model_validate(requirements["target_product"])
            if requirements.get("target_product")
            else None
        ),
        suitability_verdict_id=suitability_verdict_id,
        approved_amount=approved_amount,
        fields=[FormField.model_validate(f) for f in requirements["fields"]],
        disclosures=disclosures,
        execution=FormExecution.model_validate(requirements["execution"]),
        issued_at=now,
        expires_at=now + timedelta(seconds=ttl_s),
        signing_key_version=key_version,
    )
    return spec.model_copy(update={"signature": sign_form_spec(spec, key)})


def _operation(value: str) -> Operation:
    allowed = ("BUY", "SELL", "SWITCH", "REDEEM", "RECURRING")
    if value not in allowed:
        raise ValueError(f"unsupported operation {value!r}")
    return value  # type: ignore[return-value]


def is_expired(spec: FormSpec, *, now: datetime | None = None) -> bool:
    return spec.expires_at <= (now or datetime.now(UTC))
