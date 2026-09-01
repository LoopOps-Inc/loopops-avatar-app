"""Consent and disclosure documents served to the client.

These are the acknowledgement artefacts from docs/06-compliance/04 §3 and
docs/06-compliance/02 §5. The wording below is a neutral placeholder and
REQUIRES LEGAL APPROVAL before any client-facing release; the versions come
from configuration so a wording change is a versioned, recorded event.
"""

from __future__ import annotations

from typing import Literal

from actinver_agent.config import Settings
from actinver_agent.graph.state import DISCLOSURE_PUBLIC_ID, ConsentType

RequiredFor = Literal["first_turn", "voice", "optional"]

CONSENT_REQUIRED_FOR: dict[ConsentType, RequiredFor] = {
    ConsentType.PRIVACY_NOTICE: "first_turn",
    ConsentType.SERVICES_GUIDE: "first_turn",
    ConsentType.AI_ASSISTANT: "first_turn",
    ConsentType.VOICE_RECORDING: "voice",
    ConsentType.MODEL_IMPROVEMENT: "optional",
}

_TEXTS: dict[ConsentType, str] = {
    ConsentType.PRIVACY_NOTICE: (
        "Aviso de privacidad. Actinver trata tus datos personales para prestarte el servicio "
        "de información de inversiones, cumplir obligaciones regulatorias y prevenir fraudes. "
        "Estás interactuando con un sistema automatizado. Las conversaciones se graban y se "
        "conservan cinco años conforme a la normativa aplicable a los servicios de inversión; "
        "esta conservación no está sujeta a cancelación. Puedes ejercer tus derechos ARCO a "
        "través del canal de privacidad. [TEXTO PENDIENTE DE APROBACIÓN LEGAL]"
    ),
    ConsentType.SERVICES_GUIDE: (
        "Guía de Servicios de Inversión. Describe los servicios de inversión que Actinver "
        "ofrece, sus diferencias, las comisiones aplicables, los riesgos de los productos y el "
        "procedimiento de reclamaciones ante la UNE y la CONDUSEF. Consulta la versión completa "
        "en la aplicación o solicítala a tu asesor. [TEXTO PENDIENTE DE APROBACIÓN LEGAL]"
    ),
    ConsentType.AI_ASSISTANT: (
        "Soy un asistente automatizado de Actinver. No soy un asesor humano y no lo sustituyo. "
        "Puedo equivocarme; verifica las cifras en pantalla. En cualquier momento puedes pedir "
        "hablar con tu asesor. [TEXTO PENDIENTE DE APROBACIÓN LEGAL]"
    ),
    ConsentType.VOICE_RECORDING: (
        "Autorizo que Actinver grabe y conserve mis conversaciones de voz con el asistente "
        "durante cinco años conforme a la normativa aplicable a los servicios de inversión. "
        "Puedo retirar esta autorización en cualquier momento; el modo de chat seguirá "
        "disponible. [TEXTO PENDIENTE DE APROBACIÓN LEGAL]"
    ),
    ConsentType.MODEL_IMPROVEMENT: (
        "Autorizo el uso de mis conversaciones, seudonimizadas, para mejorar la calidad del "
        "asistente durante un máximo de 90 días. Esta autorización es opcional, está "
        "desactivada por defecto y puedo retirarla en cualquier momento sin afectar el "
        "servicio. [TEXTO PENDIENTE DE APROBACIÓN LEGAL]"
    ),
}


def current_version(settings: Settings, consent: ConsentType) -> str:
    return {
        ConsentType.PRIVACY_NOTICE: settings.ai_disclosure_version,
        ConsentType.SERVICES_GUIDE: settings.service_guide_version,
        ConsentType.AI_ASSISTANT: settings.ai_disclosure_version,
        ConsentType.VOICE_RECORDING: settings.voice_recording_disclosure_version,
        ConsentType.MODEL_IMPROVEMENT: settings.ai_disclosure_version,
    }[consent]


def consent_text(consent: ConsentType) -> str:
    return _TEXTS[consent]


def public_id(consent: ConsentType) -> str:
    return DISCLOSURE_PUBLIC_ID[consent]
