"""Development key material helpers.

Pure functions used by ``scripts/dev_token.py``, the CLI and tests to mint
HS256 dev access tokens, ES256 device keys, DPoP proofs (RFC 9449) and step-up
assertions. Nothing here runs outside local development or tests.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from actinver_agent.auth.stepup import b64url_encode

DEV_ISSUER = "https://idp.local.actinver/"
DEV_AUDIENCE = "actinver-ai-advisor"


def jwk_thumbprint(public_jwk: dict[str, Any]) -> str:
    """RFC 7638 thumbprint for an EC key: sha256 over the canonical members."""
    members = {k: public_jwk[k] for k in ("crv", "kty", "x", "y")}
    canonical = json.dumps(members, separators=(",", ":"), sort_keys=True).encode()
    return b64url_encode(hashlib.sha256(canonical).digest())


def generate_device_key() -> tuple[str, dict[str, Any], str]:
    """Returns (private_key_pem, public_jwk, jkt)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    numbers = private_key.public_key().public_numbers()
    public_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": b64url_encode(numbers.x.to_bytes(32, "big")),
        "y": b64url_encode(numbers.y.to_bytes(32, "big")),
    }
    return pem, public_jwk, jwk_thumbprint(public_jwk)


def mint_dev_access_token(
    key: str,
    client_id: str,
    *,
    roles: list[str] | None = None,
    jkt: str | None = None,
    device_id: str | None = None,
    ttl_s: int = 86400,
    issuer: str = DEV_ISSUER,
    audience: str = DEV_AUDIENCE,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": client_id,
        "iat": now,
        "exp": now + ttl_s,
        "jti": uuid.uuid4().hex,
        "roles": roles or [],
    }
    if jkt:
        claims["cnf"] = {"jkt": jkt}
    if device_id:
        claims["device_id"] = device_id
    return jwt.encode(claims, key, algorithm="HS256")


def make_dpop_proof(
    private_pem: str,
    public_jwk: dict[str, Any],
    method: str,
    url: str,
    access_token: str | None = None,
    *,
    nonce: str | None = None,
) -> str:
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    claims: dict[str, Any] = {
        "jti": uuid.uuid4().hex,
        "htm": method.upper(),
        "htu": url.split("?", 1)[0].split("#", 1)[0],
        "iat": int(time.time()),
    }
    if access_token is not None:
        claims["ath"] = b64url_encode(hashlib.sha256(access_token.encode("ascii")).digest())
    if nonce is not None:
        claims["nonce"] = nonce
    return jwt.encode(
        claims,
        private_key,  # type: ignore[arg-type]
        algorithm="ES256",
        headers={"typ": "dpop+jwt", "jwk": public_jwk},
    )


def sign_challenge(private_pem: str, challenge_b64: str) -> str:
    """ES256 raw r||s signature over the challenge string bytes, base64url."""
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise ValueError("device key must be an EC key")
    # The signed message is the challenge string exactly as issued (ASCII bytes).
    challenge = challenge_b64.encode("ascii")
    der = private_key.sign(challenge, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return b64url_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def amount_hash(amount: str, currency: str) -> str:
    """The amount binding used by step-up challenges (ADR-0017 step 1)."""
    from decimal import Decimal

    normalised = f"{Decimal(str(amount)).quantize(Decimal('0.01')):f}|{currency}"
    return hashlib.sha256(normalised.encode()).hexdigest()
