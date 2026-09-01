"""DPoP proof verification (RFC 9449, ADR-0017).

A stolen access token is useless without the device's private key: every
request carries a proof JWT signed by that key, binding method, URI, a
timestamp, a replay-protected ``jti`` and the access-token hash (``ath``). The
thumbprint of the embedded JWK must equal the token's ``cnf.jkt``.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from actinver_agent.auth.devkeys import jwk_thumbprint
from actinver_agent.auth.stepup import b64url_encode
from actinver_agent.config import Settings
from actinver_agent.ports import CachePort


class DpopError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def normalise_htu(url: str) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    default_port = {"http": ":80", "https": ":443"}.get(scheme)
    if default_port and netloc.endswith(default_port):
        netloc = netloc[: -len(default_port)]
    return urlunsplit((scheme, netloc, parts.path or "/", "", ""))


class DpopVerifier:
    def __init__(self, settings: Settings, cache: CachePort) -> None:
        self._settings = settings
        self._cache = cache

    async def verify(
        self,
        *,
        proof: str,
        method: str,
        url: str,
        access_token: str,
        expected_jkt: str | None,
    ) -> str:
        """Returns the proof key thumbprint. Raises DpopError on any mismatch."""
        try:
            header = jwt.get_unverified_header(proof)
        except jwt.PyJWTError as exc:
            raise DpopError("malformed_proof") from exc
        if header.get("typ") != "dpop+jwt":
            raise DpopError("wrong_typ")
        alg = header.get("alg")
        jwk = header.get("jwk")
        if alg not in ("ES256", "RS256") or not isinstance(jwk, dict):
            raise DpopError("unsupported_alg_or_missing_jwk")
        if jwk.get("d"):
            raise DpopError("private_key_in_proof")

        try:
            key = _public_key(alg, jwk)
            claims = jwt.decode(
                proof, key, algorithms=[alg], options={"require": ["jti", "htm", "htu", "iat"]}
            )
        except (jwt.PyJWTError, ValueError) as exc:
            raise DpopError("invalid_signature") from exc

        skew = self._settings.auth.dpop_clock_skew_s
        now = int(time.time())
        if abs(now - int(claims["iat"])) > skew:
            raise DpopError("iat_out_of_window")
        if str(claims["htm"]).upper() != method.upper():
            raise DpopError("htm_mismatch")
        if normalise_htu(str(claims["htu"])) != normalise_htu(url):
            raise DpopError("htu_mismatch")
        expected_ath = b64url_encode(hashlib.sha256(access_token.encode("ascii")).digest())
        if claims.get("ath") != expected_ath:
            raise DpopError("ath_mismatch")

        thumbprint = _thumbprint(alg, jwk)
        if expected_jkt is None or thumbprint != expected_jkt:
            raise DpopError("jkt_mismatch")

        replay_key = f"dpop_jti:{claims['jti']}"
        if await self._cache.get(replay_key) is not None:
            raise DpopError("replayed_jti")
        await self._cache.set(replay_key, b"1", ttl_s=self._settings.auth.dpop_nonce_ttl_s)
        return thumbprint


def _public_key(alg: str, jwk: dict[str, Any]) -> Any:
    if alg == "ES256":
        return ECAlgorithm.from_jwk(jwk)
    return RSAAlgorithm.from_jwk(jwk)


def _thumbprint(alg: str, jwk: dict[str, Any]) -> str:
    if alg == "ES256":
        return jwk_thumbprint(jwk)
    import json

    members = {k: jwk[k] for k in ("e", "kty", "n")}
    canonical = json.dumps(members, separators=(",", ":"), sort_keys=True).encode()
    return b64url_encode(hashlib.sha256(canonical).digest())
