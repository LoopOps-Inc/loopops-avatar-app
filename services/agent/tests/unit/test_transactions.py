"""Form Spec signing and the independent executor (ADR-0009, ADR-0010, ADR-0017)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from actinver_agent.auth import devkeys
from actinver_agent.clients.synthetic import SyntheticCoreBanking, SyntheticOms
from actinver_agent.graph.state import Money
from actinver_agent.persistence.memory import (
    MemoryChainStore,
    MemoryChallengeRepository,
    MemoryDeviceRepository,
    MemoryEvidenceIndexRepository,
    MemoryFormSpecRepository,
    MemoryIdempotencyRepository,
    MemoryObjectStore,
    MemorySpool,
)
from actinver_agent.ports import DeviceBinding
from actinver_agent.transactions import errors as txerr
from actinver_agent.transactions.executor import TransactionExecutor
from actinver_agent.transactions.formspec import (
    amount_hash,
    build_form_spec,
    is_expired,
    sign_form_spec,
    verify_form_spec,
)

KEY = b"formspec-test-key"
CLIENT = "cl_demo_moderado"
TEXTS = {
    "PAST_PERF": ("Los rendimientos pasados no garantizan rendimientos futuros.", "2026-08"),
    "RISK_ACK": ("Entiendo que el valor de esta inversión puede disminuir.", "2026-08"),
    "COSTS": ("Consulta las comisiones aplicables.", "2026-08"),
    "SETTLEMENT": ("La operación se liquida conforme a la fecha valor del producto.", "2026-08"),
}


async def make_spec(core: SyntheticCoreBanking, amount: str = "100000") -> Any:
    requirements = await core.get_transaction_requirements(
        client_id=CLIENT, product_id="ACTIGOB-BF", operation="BUY"
    )
    requirements["ack_ids"] = [d["id"] for d in requirements["disclosures"] if d["ack"]]
    return build_form_spec(
        requirements=requirements,
        client_id=CLIENT,
        thread_id="th_1",
        turn_id="tn_1",
        suitability_verdict_id="sv_abc",
        approved_amount=Money.of(amount),
        disclosure_texts=TEXTS,
        key=KEY,
    )


async def test_signature_roundtrip_and_tamper() -> None:
    spec = await make_spec(SyntheticCoreBanking())
    assert verify_form_spec(spec, KEY)
    assert spec.client_id == CLIENT and spec.required_acknowledgements() == ["RISK_ACK"]
    tampered = spec.model_copy(update={"client_id": "cl_other"})
    assert not verify_form_spec(tampered, KEY), "client_id is bound into the signature"
    limit_tampered = spec.model_copy(
        update={"fields": [f.model_copy(update={"max": "999999999"}) for f in spec.fields]}
    )
    assert not verify_form_spec(limit_tampered, KEY)
    assert not verify_form_spec(spec, b"other-key")
    assert sign_form_spec(spec, KEY) == spec.signature
    assert not is_expired(spec)
    assert is_expired(spec, now=spec.expires_at + timedelta(seconds=1))
    assert spec.expires_at - spec.issued_at == timedelta(minutes=10)


def test_amount_hash_is_stable() -> None:
    assert amount_hash(Money.of("100000")) == amount_hash(Money.of("100000.00"))
    assert amount_hash(Money.of("100000")) != amount_hash(Money.of("100000", "USD"))


class Harness:
    def __init__(self) -> None:
        self.core = SyntheticCoreBanking()
        self.oms = SyntheticOms()
        self.form_specs = MemoryFormSpecRepository()
        self.idempotency = MemoryIdempotencyRepository()
        self.challenges = MemoryChallengeRepository()
        self.devices = MemoryDeviceRepository()
        from actinver_agent.audit.inprocess import InProcessAudit
        from actinver_agent.audit.sink import EvidenceWriter

        self.audit = InProcessAudit(
            EvidenceWriter(
                store=MemoryObjectStore(),
                chain=MemoryChainStore(),
                index=MemoryEvidenceIndexRepository(),
                spool=MemorySpool(),
            )
        )
        self.executor = TransactionExecutor(
            core=self.core,
            oms=self.oms,
            form_specs=self.form_specs,
            idempotency=self.idempotency,
            challenges=self.challenges,
            devices=self.devices,
            audit=self.audit,
            form_key=KEY,
        )
        self.private_pem, self.public_jwk, self.jkt = devkeys.generate_device_key()

    async def bind_device(self) -> None:
        await self.devices.register(
            DeviceBinding(
                client_id=CLIENT,
                device_id="dev-1",
                jkt=self.jkt,
                public_key_jwk=self.public_jwk,
                registered_at=datetime.now(UTC),
                attestation_verified=True,
            )
        )

    async def signed_challenge(self, spec: Any, amount: Money) -> tuple[str, str]:
        challenge = await self.executor.issue_challenge(
            client_id=CLIENT, form_id=spec.form_id, amount_hash=amount_hash(amount)
        )
        return challenge.challenge_id, devkeys.sign_challenge(self.private_pem, challenge.challenge)

    async def execute(
        self,
        spec: Any,
        *,
        amount: Money,
        acks: list[str] | None = None,
        assertion: str | None = None,
        challenge_id: str | None = None,
        key: str = "idem-1",
        jkt: str | None = None,
    ) -> Any:
        if challenge_id is None or assertion is None:
            challenge_id, assertion = await self.signed_challenge(spec, amount)
        return await self.executor.execute(
            client_id=CLIENT,
            form_spec=spec,
            values={"amount": amount.model_dump(), "account_id": "acc_001"},
            acknowledgements=["RISK_ACK"] if acks is None else acks,
            step_up_assertion=assertion,
            challenge_id=challenge_id,
            idempotency_key=key,
            suitability_verdict_id="sv_abc",
            jkt=jkt or self.jkt,
        )


@pytest.fixture
async def harness() -> Harness:
    h = Harness()
    await h.bind_device()
    return h


async def test_happy_path_places_one_order_and_records_evidence(harness: Harness) -> None:
    spec = await make_spec(harness.core)
    await harness.form_specs.store(spec, status="ISSUED")
    receipt = await harness.execute(spec, amount=Money.of("100000"))
    assert receipt.order_id and receipt.status == "RECEIVED" and receipt.evidence_id
    stored = await harness.form_specs.get(spec.form_id)
    assert stored is not None and stored[1] == "USED"


async def test_idempotent_replay_returns_same_order(harness: Harness) -> None:
    spec = await make_spec(harness.core)
    await harness.form_specs.store(spec, status="ISSUED")
    challenge_id, assertion = await harness.signed_challenge(spec, Money.of("100000"))
    first = await harness.execute(
        spec, amount=Money.of("100000"), challenge_id=challenge_id, assertion=assertion, key="k"
    )
    replay = await harness.execute(
        spec, amount=Money.of("100000"), challenge_id=challenge_id, assertion=assertion, key="k"
    )
    assert replay.order_id == first.order_id and replay.idempotent_replay


async def test_challenge_is_single_use(harness: Harness) -> None:
    spec = await make_spec(harness.core)
    await harness.form_specs.store(spec, status="ISSUED")
    challenge_id, assertion = await harness.signed_challenge(spec, Money.of("100000"))
    await harness.execute(
        spec, amount=Money.of("100000"), challenge_id=challenge_id, assertion=assertion, key="a"
    )
    await harness.form_specs.mark(
        spec.form_id, status="ISSUED"
    )  # simulate a second attempt on the same form
    with pytest.raises(txerr.StepUpRequired):
        await harness.execute(
            spec, amount=Money.of("100000"), challenge_id=challenge_id, assertion=assertion, key="b"
        )


async def test_wrong_device_signature_is_rejected(harness: Harness) -> None:
    spec = await make_spec(harness.core)
    await harness.form_specs.store(spec, status="ISSUED")
    other_pem, _, _ = devkeys.generate_device_key()
    challenge = await harness.executor.issue_challenge(
        client_id=CLIENT, form_id=spec.form_id, amount_hash=amount_hash(Money.of("100000"))
    )
    forged = devkeys.sign_challenge(other_pem, challenge.challenge)
    with pytest.raises(txerr.StepUpRequired):
        await harness.execute(
            spec, amount=Money.of("100000"), challenge_id=challenge.challenge_id, assertion=forged
        )


async def test_limits_are_rederived_not_trusted(harness: Harness) -> None:
    spec = await make_spec(harness.core, amount="5000000")
    # The client edits the spec's declared max; the executor ignores it and re-derives.
    inflated = spec.model_copy(
        update={
            "fields": [
                f.model_copy(update={"max": "999999999"}) if f.key == "amount" else f
                for f in spec.fields
            ]
        }
    )
    inflated = inflated.model_copy(update={"signature": sign_form_spec(inflated, KEY)})
    await harness.form_specs.store(inflated, status="ISSUED")
    with pytest.raises(txerr.LimitExceeded):
        await harness.execute(inflated, amount=Money.of("5000000"))


async def test_missing_acknowledgement_is_refused(harness: Harness) -> None:
    spec = await make_spec(harness.core)
    await harness.form_specs.store(spec, status="ISSUED")
    with pytest.raises(txerr.AckRequired):
        await harness.execute(spec, amount=Money.of("100000"), acks=[])


async def test_expired_and_tampered_forms_are_refused(harness: Harness) -> None:
    spec = await make_spec(harness.core)
    expired = spec.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(minutes=1)})
    expired = expired.model_copy(update={"signature": sign_form_spec(expired, KEY)})
    await harness.form_specs.store(expired, status="ISSUED")
    with pytest.raises(txerr.FormExpired):
        await harness.execute(expired, amount=Money.of("100000"))
    tampered = spec.model_copy(update={"signature": "00" * 32})
    await harness.form_specs.store(tampered, status="ISSUED")
    with pytest.raises(txerr.FormSignatureInvalid):
        await harness.execute(tampered, amount=Money.of("100000"))


async def test_every_typed_error_maps_to_an_api_code() -> None:
    from actinver_agent.errors import ERRORS

    for exc_type in (
        txerr.FormExpired,
        txerr.FormSignatureInvalid,
        txerr.FormAlreadyUsed,
        txerr.FormClientMismatch,
        txerr.AckRequired,
        txerr.StepUpRequired,
        txerr.LimitExceeded,
        txerr.IdempotencyConflict,
    ):
        assert exc_type.api_code in ERRORS, exc_type
