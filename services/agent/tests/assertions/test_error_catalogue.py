"""docs/04-backend/04 §3: HTTP-level error codes and their statuses. Guardrail
refusals are in-stream 200s and therefore intentionally NOT in this table."""

from __future__ import annotations

from actinver_agent import errors

DOCUMENTED_HTTP = {
    "FORM_EXPIRED": 409,
    "FORM_SIGNATURE_INVALID": 400,
    "STEP_UP_REQUIRED": 401,
    "LIMIT_EXCEEDED": 422,
    "RATE_LIMITED": 429,
    "SERVICE_UNAVAILABLE": 503,
}

IN_STREAM_ONLY = {
    "BLOCKED_INPUT",
    "BLOCKED_OUTPUT",
    "NOT_ENTITLED_ADVISORY",
    "NOT_ENTITLED_EXECUTION",
    "PROFILE_EXPIRED",
    "NO_SUITABLE_PRODUCT",
    "LOW_CONFIDENCE",
}


def test_documented_http_codes_present_with_status() -> None:
    for code, status in DOCUMENTED_HTTP.items():
        assert code in errors.ERRORS, code
        assert errors.ERRORS[code][0] == status, (code, errors.ERRORS[code][0])


def test_in_stream_refusals_are_not_http_errors() -> None:
    leaked = IN_STREAM_ONLY & set(errors.ERRORS)
    assert not leaked, f"guardrail refusals must be in-stream 200s, not HTTP errors: {leaked}"


def test_every_message_is_spanish_and_displayable() -> None:
    for code, (status, message) in errors.ERRORS.items():
        assert 400 <= status <= 599, code
        assert message and message[0].isupper(), code
        assert "{" not in message and "}" not in message, f"{code}: unformatted placeholder"


def test_problem_details_shape() -> None:
    fields = set(errors.ProblemDetails.model_fields)
    assert {"type", "title", "status", "code", "message", "trace_id"} <= fields
