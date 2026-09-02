"""Sandbox accounts cap LiveAvatar at ~60 s. The watchdog must not treat that
like a 30-minute session (immediate 'expiring' speech + vendor refresh)."""

from actinver_agent.avatar.broker import (
    should_emit_duration_warning,
    should_recover_disconnected_vendor,
    should_refresh_vendor,
)


def test_sandbox_cap_does_not_warn_or_refresh() -> None:
    cap = 60.0
    refresh_at = cap * 0.8
    for elapsed in (0.0, 1.0, 48.0, 55.0):
        assert not should_emit_duration_warning(cap_s=cap, elapsed_s=elapsed, already=False)
        assert not should_refresh_vendor(
            cap_s=cap, elapsed_s=elapsed, refresh_at=refresh_at, already=False
        )
        assert not should_recover_disconnected_vendor(
            cap_s=cap, elapsed_s=elapsed, already=False
        )


def test_half_hour_cap_warns_in_the_last_minute() -> None:
    cap = 1800.0
    assert not should_emit_duration_warning(cap_s=cap, elapsed_s=1739.0, already=False)
    assert should_emit_duration_warning(cap_s=cap, elapsed_s=1740.0, already=False)
    assert not should_emit_duration_warning(cap_s=cap, elapsed_s=1740.0, already=True)


def test_half_hour_cap_refreshes_at_80_percent() -> None:
    cap = 1800.0
    refresh_at = cap * 0.8
    assert not should_refresh_vendor(
        cap_s=cap, elapsed_s=1439.0, refresh_at=refresh_at, already=False
    )
    assert should_refresh_vendor(cap_s=cap, elapsed_s=1440.0, refresh_at=refresh_at, already=False)
    assert not should_refresh_vendor(
        cap_s=cap, elapsed_s=1440.0, refresh_at=refresh_at, already=True
    )
    assert should_recover_disconnected_vendor(cap_s=cap, elapsed_s=10.0, already=False)
    assert not should_recover_disconnected_vendor(cap_s=cap, elapsed_s=1796.0, already=False)
