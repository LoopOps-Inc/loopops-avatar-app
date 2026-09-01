"""The validated request context. ``client_id`` comes from the token subject and
nowhere else; every tool call and every graph run receives it from here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RequestContext:
    client_id: str
    #: DPoP key thumbprint (``cnf.jkt``) when the token is sender-constrained.
    jkt: str | None
    device_id: str | None
    roles: frozenset[str] = field(default_factory=frozenset)
    token_issued_at: datetime | None = None
    token_id: str | None = None
    locale: str = "es-MX"
    #: Set when attestation failed or the device lacks hardware key storage:
    #: read-only, no transactional forms (ADR-0017 fallback).
    restricted: bool = False
    actor: str = "client"

    def has_role(self, role: str) -> bool:
        return role in self.roles


#: Roles carried in the ``roles`` claim (docs/05-security/03 §3).
ROLE_COMPLIANCE = "compliance"
ROLE_RISK = "risk"
ROLE_SECURITY = "security"
ROLE_SRE = "sre"
