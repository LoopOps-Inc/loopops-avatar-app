"""Typed transaction errors. ``api_code`` maps onto ``errors.ERRORS``."""

from __future__ import annotations


class TransactionError(Exception):
    api_code = "INTERNAL_ERROR"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.api_code)
        self.detail = detail


class FormExpired(TransactionError):
    api_code = "FORM_EXPIRED"


class FormSignatureInvalid(TransactionError):
    api_code = "FORM_SIGNATURE_INVALID"


class FormAlreadyUsed(TransactionError):
    api_code = "FORM_ALREADY_USED"


class FormClientMismatch(TransactionError):
    api_code = "FORM_CLIENT_MISMATCH"


class AckRequired(TransactionError):
    api_code = "ACK_REQUIRED"


class StepUpRequired(TransactionError):
    api_code = "STEP_UP_REQUIRED"


class LimitExceeded(TransactionError):
    api_code = "LIMIT_EXCEEDED"


class IdempotencyConflict(TransactionError):
    api_code = "IDEMPOTENCY_CONFLICT"


class FormNotFound(TransactionError):
    api_code = "NOT_FOUND"


class ExecutionUnavailable(TransactionError):
    api_code = "SERVICE_UNAVAILABLE"


ERROR_BY_CODE: dict[str, type[TransactionError]] = {
    cls.api_code: cls
    for cls in (
        FormExpired,
        FormSignatureInvalid,
        FormAlreadyUsed,
        FormClientMismatch,
        AckRequired,
        StepUpRequired,
        LimitExceeded,
        IdempotencyConflict,
        FormNotFound,
        ExecutionUnavailable,
    )
}
