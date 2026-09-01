"""Access-token verification (docs/05-security/03 §1).

``dev`` mode: HS256 with a key resolved by reference (local only).
``oidc`` mode: asymmetric tokens verified against the IdP JWKS.

Revocation: ``revoked:{client_id}`` holds an epoch; tokens issued before it are
rejected (cohort revocation, docs/05-security/06 §3.1). ``revoked_jti:{jti}``
rejects a single token.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import jwt
import structlog

from actinver_agent.auth.context import RequestContext
from actinver_agent.config import Settings
from actinver_agent.ports import CachePort
from actinver_agent.secrets import SecretResolver

log = structlog.get_logger(__name__)


class TokenError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TokenVerifier:
    def __init__(self, settings: Settings, resolver: SecretResolver, cache: CachePort) -> None:
        self._settings = settings
        self._resolver = resolver
        self._cache = cache
        self._dev_key: str | None = None
        self._jwks_client: jwt.PyJWKClient | None = None

    async def _signing_key(self, token: str) -> tuple[Any, list[str]]:
        auth = self._settings.auth
        if auth.mode == "dev":
            if self._dev_key is None:
                self._dev_key = await self._resolver.resolve(auth.dev_signing_key_ref)
            return self._dev_key, ["HS256"]
        if self._jwks_client is None:
            if not auth.jwks_url:
                raise TokenError("jwks_url_not_configured")
            self._jwks_client = jwt.PyJWKClient(auth.jwks_url, cache_keys=True)
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        return signing_key.key, ["RS256", "ES256"]

    async def verify(self, token: str) -> RequestContext:
        auth = self._settings.auth
        try:
            key, algorithms = await self._signing_key(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=algorithms,
                audience=auth.audience,
                issuer=auth.issuer,
                options={"require": ["exp", "iat", "sub"]},
                leeway=auth.dpop_clock_skew_s,
            )
        except TokenError:
            raise
        except jwt.PyJWTError as exc:
            raise TokenError(type(exc).__name__) from exc

        iat = int(claims["iat"])
        exp = int(claims["exp"])
        if exp - iat > auth.access_token_max_ttl_s + auth.dpop_clock_skew_s:
            raise TokenError("token_ttl_too_long")

        client_id = str(claims["sub"])
        jti = claims.get("jti")
        await self._check_revocation(client_id, iat, jti)

        cnf = claims.get("cnf") or {}
        roles = claims.get("roles") or []
        return RequestContext(
            client_id=client_id,
            jkt=cnf.get("jkt"),
            device_id=claims.get("device_id"),
            roles=frozenset(str(r) for r in roles),
            token_issued_at=datetime.fromtimestamp(iat, tz=UTC),
            token_id=str(jti) if jti else None,
            locale=str(claims.get("locale", "es-MX")),
        )

    async def _check_revocation(self, client_id: str, iat: int, jti: Any) -> None:
        epoch = await self._cache.get(f"revoked:{client_id}")
        if epoch is not None:
            try:
                if iat <= int(epoch.decode()):
                    raise TokenError("token_revoked")
            except ValueError:
                raise TokenError("token_revoked") from None
        if jti and await self._cache.get(f"revoked_jti:{jti}") is not None:
            raise TokenError("token_revoked")


async def revoke_client(
    cache: CachePort, client_id: str, *, issued_before: datetime | None
) -> None:
    """Reject every token issued before ``issued_before`` (default: now)."""
    epoch = int((issued_before or datetime.now(UTC)).timestamp())
    await cache.set(f"revoked:{client_id}", str(epoch).encode(), ttl_s=30 * 24 * 3600)
