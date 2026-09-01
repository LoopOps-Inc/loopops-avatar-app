"""RFC 9457 problem details (docs/04-backend/04 §1, §3).

Every HTTP error carries ``code``, a Spanish ``message`` safe to display, and a
``trace_id``. Guardrail refusals are NOT HTTP errors: they are in-stream 200s.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from pydantic import BaseModel


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    message: str
    trace_id: str
    detail: str | None = None
    instance: str | None = None
    retry_after_s: int | None = None


class ApiError(Exception):
    """Raise from route handlers; the handler below renders it."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        message_es: str,
        detail: str | None = None,
        retry_after_s: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message_es = message_es
        self.detail = detail
        self.retry_after_s = retry_after_s
        self.headers = headers or {}


#: Error catalogue from docs/04-backend/04 §3 (HTTP-level ones) plus the
#: auth/consent codes the remaining docs require.
ERRORS: dict[str, tuple[int, str]] = {
    "FORM_EXPIRED": (409, "La operación caducó por seguridad. ¿La preparamos otra vez?"),
    "FORM_SIGNATURE_INVALID": (400, "No pude validar la operación. Por seguridad la cancelé."),
    "FORM_ALREADY_USED": (409, "Esta operación ya fue enviada."),
    "FORM_CLIENT_MISMATCH": (403, "Esta operación no corresponde a tu sesión."),
    "ACK_REQUIRED": (422, "Falta confirmar las advertencias obligatorias."),
    "STEP_UP_REQUIRED": (401, "Necesitas confirmar tu identidad para continuar."),
    "LIMIT_EXCEEDED": (422, "El monto está fuera de los límites permitidos."),
    "RATE_LIMITED": (429, "Demasiadas solicitudes. Intenta de nuevo en un momento."),
    "SERVICE_UNAVAILABLE": (503, "El servicio no está disponible por el momento."),
    "UNAUTHENTICATED": (401, "Tu sesión no es válida. Inicia sesión de nuevo."),
    "FORBIDDEN": (403, "No tienes permiso para realizar esta acción."),
    "NOT_FOUND": (404, "No encontré lo que buscas."),
    "CONSENT_REQUIRED": (403, "Antes de continuar necesitas aceptar los avisos pendientes."),
    "VOICE_CONSENT_REQUIRED": (
        403,
        "Para usar el modo de voz necesitas autorizar la grabación de la conversación.",
    ),
    "VOICE_UNAVAILABLE": (503, "El modo de voz no está disponible; puedes seguir por chat."),
    "AVATAR_CAPACITY": (
        503,
        "El avatar no está disponible en este momento; puedes seguir por chat.",
    ),
    "AVATAR_BUDGET_EXHAUSTED": (
        429,
        "Alcanzaste el tiempo de voz disponible por hoy; puedes continuar por chat.",
    ),
    "KILL_SWITCH": (503, "El asistente digital no está disponible por el momento."),
    "IDEMPOTENCY_KEY_REQUIRED": (400, "Falta el encabezado Idempotency-Key."),
    "IDEMPOTENCY_CONFLICT": (409, "Esta solicitud ya fue procesada con otros datos."),
    "THREAD_FROZEN": (423, "Esta conversación está en revisión y no admite mensajes nuevos."),
    "VALIDATION_ERROR": (422, "La solicitud no es válida."),
    "MESSAGE_TOO_LONG": (413, "El mensaje es demasiado largo."),
    "INTERNAL_ERROR": (500, "Ocurrió un problema técnico. Intenta de nuevo."),
}


def api_error(code: str, *, detail: str | None = None, **kwargs: Any) -> ApiError:
    status, message = ERRORS[code]
    return ApiError(status=status, code=code, message_es=message, detail=detail, **kwargs)


def current_trace_id() -> str:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.trace_id:
        return format(ctx.trace_id, "032x")
    return "00000000000000000000000000000000"


def problem_response(request: Request, exc: ApiError) -> JSONResponse:
    problem = ProblemDetails(
        title=exc.code.replace("_", " ").title(),
        status=exc.status,
        code=exc.code,
        message=exc.message_es,
        trace_id=current_trace_id(),
        detail=exc.detail,
        instance=str(request.url.path),
        retry_after_s=exc.retry_after_s,
    )
    headers = dict(exc.headers)
    if exc.retry_after_s is not None:
        headers["Retry-After"] = str(exc.retry_after_s)
    return JSONResponse(
        status_code=exc.status,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers=headers,
    )
