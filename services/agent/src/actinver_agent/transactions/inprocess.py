"""TransactionPort implemented in-process over ``TransactionExecutor``."""

from __future__ import annotations

from typing import Any

from actinver_agent.graph.state import FormSpec
from actinver_agent.ports import OrderReceipt, StepUpChallenge
from actinver_agent.transactions.executor import TransactionExecutor


class InProcessTransactions:
    def __init__(self, executor: TransactionExecutor) -> None:
        self._executor = executor

    @property
    def executor(self) -> TransactionExecutor:
        return self._executor

    async def issue_challenge(
        self, *, client_id: str, form_id: str, amount_hash: str
    ) -> StepUpChallenge:
        return await self._executor.issue_challenge(
            client_id=client_id, form_id=form_id, amount_hash=amount_hash
        )

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
        return await self._executor.execute(
            client_id=client_id,
            form_spec=form_spec,
            values=values,
            acknowledgements=acknowledgements,
            step_up_assertion=step_up_assertion,
            challenge_id=challenge_id,
            idempotency_key=idempotency_key,
            suitability_verdict_id=suitability_verdict_id,
            jkt=jkt,
            device_id=device_id,
        )

    async def health(self) -> bool:
        return True
