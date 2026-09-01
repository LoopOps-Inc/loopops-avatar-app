"""Server-verified step-up (ADR-0017).

The client never asserts that authentication happened; it proves it by signing
a server-issued challenge with the biometric-gated, hardware-backed device key.
``verify_step_up_assertion`` is shared by the BFF and by ``transaction-service``.
"""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def public_key_from_jwk(jwk: dict[str, Any]) -> ec.EllipticCurvePublicKey:
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise ValueError("device keys must be EC P-256 (ES256)")
    x = int.from_bytes(b64url_decode(jwk["x"]), "big")
    y = int.from_bytes(b64url_decode(jwk["y"]), "big")
    numbers = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1())
    return numbers.public_key()


def verify_step_up_assertion(
    public_key_jwk: dict[str, Any], challenge_b64: str, assertion_b64url: str
) -> bool:
    """ES256 (raw r||s, 64 bytes) signature over the challenge string bytes.

    ``challenge_b64`` is the base64 nonce the server issued; ``assertion_b64url``
    is the base64url-encoded signature the device returned.
    """
    try:
        public_key = public_key_from_jwk(public_key_jwk)
        challenge = challenge_b64.encode("ascii")
        signature = b64url_decode(assertion_b64url)
        if len(signature) != 64:
            return False
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")
        der = encode_dss_signature(r, s)
        public_key.verify(der, challenge, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return False
    return True
