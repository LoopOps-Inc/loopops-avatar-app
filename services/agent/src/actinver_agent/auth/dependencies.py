"""FastAPI dependencies: authentication, roles and idempotency.

``Authorization: DPoP <token>`` plus a ``DPoP`` proof header is the contract
(docs/04-backend/04 §1). In ``local`` a plain ``Bearer`` token is accepted so
curls work, but a present proof is always verified.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import jwt
import orjson
import structlog
from fastapi import Depends, Header, Request

from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dpop import DpopError, DpopVerifier
from actinver_agent.auth.jwt import TokenError, TokenVerifier
from actinver_agent.deps import Dependencies, get_current
from actinver_agent.errors import api_error
from actinver_agent.observability.setup import client_hash, get_metrics
from actinver_agent.ports import DeviceBinding

log = structlog.get_logger(__name__)

_VERIFIERS: dict[int, tuple[TokenVerifier, DpopVerifier]] = {}


def get_deps() -> Dependencies:
    return get_current()


def _verifiers(deps: Dependencies) -> tuple[TokenVerifier, DpopVerifier]:
    key = id(deps)
    if key not in _VERIFIERS:
        _VERIFIERS[key] = (
            TokenVerifier(deps.settings, deps.secrets, deps.cache),
            DpopVerifier(deps.settings, deps.cache),
        )
    return _VERIFIERS[key]


def _split_authorization(header: str | None) -> tuple[str, str]:
    if not header or " " not in header:
        raise api_error("UNAUTHENTICATED", detail="missing Authorization header")
    scheme, _, token = header.partition(" ")
    return scheme.strip().lower(), token.strip()


async def authenticate(
    deps: Dependencies,
    *,
    authorization: str | None,
    dpop: str | None,
    method: str,
    url: str,
) -> RequestContext:
    scheme, token = _split_authorization(authorization)
    if scheme not in {"dpop", "bearer"}:
        raise api_error("UNAUTHENTICATED", detail="unsupported auth scheme")
    token_verifier, dpop_verifier = _verifiers(deps)
    try:
        ctx = await token_verifier.verify(token)
    except TokenError as exc:
        get_metrics().auth_failures.add(1, {"reason": exc.reason})
        raise api_error("UNAUTHENTICATED", detail=exc.reason) from exc

    auth = deps.settings.auth
    if scheme == "bearer" and (auth.dpop_required or not deps.settings.is_local):
        get_metrics().auth_failures.add(1, {"reason": "dpop_required"})
        raise api_error("UNAUTHENTICATED", detail="DPoP-bound token required")
    if dpop is not None or scheme == "dpop":
        if dpop is None:
            get_metrics().auth_failures.add(1, {"reason": "missing_dpop_proof"})
            raise api_error("UNAUTHENTICATED", detail="missing DPoP proof")
        try:
            await dpop_verifier.verify(
                proof=dpop, method=method, url=url, access_token=token, expected_jkt=ctx.jkt
            )
        except DpopError as exc:
            get_metrics().auth_failures.add(1, {"reason": exc.reason})
            raise api_error("UNAUTHENTICATED", detail=f"dpop:{exc.reason}") from exc
        await _register_device(deps, ctx, dpop)
    elif ctx.jkt is not None and auth.dpop_required:
        raise api_error("UNAUTHENTICATED", detail="missing DPoP proof")

    structlog.contextvars.bind_contextvars(client_hash=client_hash(ctx.client_id))
    return ctx


def _public_url(request: Request) -> str:
    """Rebuild the URL the client signed, honouring proxy headers."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}{request.url.path}"


async def require_client(
    request: Request,
    authorization: str | None = Header(default=None),
    dpop: str | None = Header(default=None, alias="DPoP"),
    deps: Dependencies = Depends(get_deps),
) -> RequestContext:
    return await authenticate(
        deps,
        authorization=authorization,
        dpop=dpop,
        method=request.method,
        url=_public_url(request),
    )


def require_role(*roles: str) -> Callable[..., Awaitable[RequestContext]]:
    async def _dep(ctx: RequestContext = Depends(require_client)) -> RequestContext:
        if not any(ctx.has_role(r) for r in roles):
            raise api_error("FORBIDDEN", detail=f"requires one of: {', '.join(roles)}")
        return ctx

    return _dep


def idempotency_key(
    key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    if not key or len(key) > 128:
        raise api_error("IDEMPOTENCY_KEY_REQUIRED")
    return key


def request_hash(payload: Any) -> str:
    body = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS, default=str)
    return hashlib.sha256(body).hexdigest()


class IdempotencyGuard:
    """Replays the stored response for a repeated key; 409 on a different body."""

    def __init__(self, deps: Dependencies, *, key: str, client_id: str, payload: Any) -> None:
        self._deps = deps
        self._key = f"{client_id}:{key}"
        self._hash = request_hash(payload)

    async def replay(self) -> dict[str, Any] | None:
        stored = await self._deps.repos.idempotency.get(self._key)
        if stored is None:
            return None
        stored_hash, response = stored
        if stored_hash != self._hash:
            raise api_error("IDEMPOTENCY_CONFLICT")
        return response

    async def store(self, response: dict[str, Any]) -> None:
        await self._deps.repos.idempotency.put(
            self._key,
            request_hash=self._hash,
            response=response,
            ttl_s=self._deps.settings.limits.idempotency_ttl_s,
        )


async def _register_device(deps: Dependencies, ctx: RequestContext, proof: str) -> None:
    """A verified DPoP proof carries the device public key: register it against the
    client identity on first sight (ADR-0017)."""
    jwk = jwt.get_unverified_header(proof).get("jwk")
    if isinstance(jwk, dict):
        await register_device_key(deps, ctx, jwk)


async def register_device_key(deps: Dependencies, ctx: RequestContext, jwk: dict[str, Any]) -> bool:
    """Bind a device public key to the client. Only a key whose RFC 7638 thumbprint
    equals the token's ``cnf.jkt`` is accepted, so a bearer token alone cannot
    enrol an arbitrary key. Returns True when a binding exists afterwards."""
    if ctx.jkt is None or jwk.get("d"):
        return False
    try:
        from actinver_agent.auth.devkeys import jwk_thumbprint

        if jwk_thumbprint(jwk) != ctx.jkt:
            log.warning("device.jkt_mismatch", client_hash=client_hash(ctx.client_id))
            return False
        existing = await deps.repos.devices.get(client_id=ctx.client_id, jkt=ctx.jkt)
        if existing is not None:
            return True
        await deps.repos.devices.register(
            DeviceBinding(
                client_id=ctx.client_id,
                device_id=ctx.device_id or ctx.jkt,
                jkt=ctx.jkt,
                public_key_jwk={k: v for k, v in jwk.items() if k != "d"},
                registered_at=datetime.now(UTC),
                attestation_verified=False,
            )
        )
        log.info("device.registered", client_hash=client_hash(ctx.client_id))
        return True
    except Exception as exc:
        log.warning("device.registration_failed", reason=type(exc).__name__)
        return False
