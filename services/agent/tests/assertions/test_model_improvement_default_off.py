"""Control DP-03: model-improvement use of conversations is opt-in and off by
default; it is a separate consent from voice recording (docs/06-compliance/04 §3).
"""

from __future__ import annotations

from actinver_agent.graph.state import (
    DISCLOSURE_PUBLIC_ID,
    FIRST_TURN_CONSENTS,
    ConsentType,
)


def test_model_improvement_is_not_required_for_service() -> None:
    assert ConsentType.MODEL_IMPROVEMENT not in FIRST_TURN_CONSENTS


def test_voice_and_model_improvement_are_separate_consents() -> None:
    assert ConsentType.VOICE_RECORDING is not ConsentType.MODEL_IMPROVEMENT
    assert ConsentType.VOICE_RECORDING not in FIRST_TURN_CONSENTS, (
        "voice consent gates voice only; chat must stay available without it"
    )


def test_first_turn_gates_guide_privacy_and_ai_disclosure() -> None:
    assert set(FIRST_TURN_CONSENTS) == {
        ConsentType.PRIVACY_NOTICE,
        ConsentType.SERVICES_GUIDE,
        ConsentType.AI_ASSISTANT,
    }


def test_every_consent_has_a_public_disclosure_id() -> None:
    assert set(DISCLOSURE_PUBLIC_ID) == set(ConsentType)
