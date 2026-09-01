"""ADR-0015: every feature flag carries an expiry; an expired flag fails the build."""

from __future__ import annotations

from datetime import UTC, datetime

from actinver_agent import flags


def test_every_flag_is_unexpired() -> None:
    expired = flags.unexpired(datetime.now(UTC).date())
    assert not expired, "expired flags: " + ", ".join(f.name for f in expired)


def test_flag_inventory_matches_adr_0015() -> None:
    expected = {
        "advisor.enabled",
        "advisor.voice_mode",
        "advisor.avatar",
        "advisor.intent.advisory_recommend",
        "advisor.intent.transactional",
        "advisor.model.primary",
        "advisor.suitability.ruleset_version",
        "advisor.prompt.version",
        "advisor.kill_switch",
    }
    assert set(flags.FLAG_INDEX) == expected


def test_kill_switch_is_risk_owned_and_off_by_default() -> None:
    spec = flags.FLAG_INDEX["advisor.kill_switch"]
    assert spec.owner == "Risk"
    assert spec.default == "off"


def test_regulated_flags_are_compliance_owned() -> None:
    for name in (
        "advisor.intent.advisory_recommend",
        "advisor.intent.transactional",
        "advisor.suitability.ruleset_version",
        "advisor.prompt.version",
    ):
        assert flags.FLAG_INDEX[name].owner == "Compliance", name
