"""Tests for hermes_cli.parent_death_watchdog (desktop serve orphan guard)."""

from __future__ import annotations

from unittest.mock import patch

import psutil
import pytest

from hermes_cli import parent_death_watchdog as pwd


def test_is_orphaned_true_when_ppid_changes():
    assert pwd.is_orphaned(1234, 1.0, getppid=lambda: 999999) is True


def test_is_orphaned_true_when_parent_create_time_mismatch():
    me = psutil.Process()
    assert pwd.is_orphaned(me.pid, 0.0, getppid=lambda: me.pid) is True


def test_is_orphaned_false_when_parent_alive_and_matches():
    me = psutil.Process()
    assert (
        pwd.is_orphaned(me.pid, me.create_time(), getppid=lambda: me.pid) is False
    )


def test_start_parent_death_watchdog_skips_when_ppid_is_init():
    assert pwd.start_parent_death_watchdog(getppid=lambda: 1) is False


def test_start_desktop_watchdog_requires_hermes_desktop_env(monkeypatch):
    monkeypatch.delenv("HERMES_DESKTOP", raising=False)
    assert pwd.start_desktop_parent_death_watchdog() is False


def test_start_desktop_watchdog_starts_under_hermes_desktop(monkeypatch):
    monkeypatch.setenv("HERMES_DESKTOP", "1")
    with patch.object(pwd, "start_parent_death_watchdog", return_value=True) as start:
        assert pwd.start_desktop_parent_death_watchdog() is True
        start.assert_called_once_with()


def test_cmd_dashboard_arms_desktop_watchdog_before_profile_routing(monkeypatch):
    """cmd_dashboard must arm the watchdog early for desktop-spawned backends."""
    import hermes_cli.main as main_mod
    import hermes_cli.parent_death_watchdog as pwd_mod

    calls: list[str] = []

    monkeypatch.setenv("HERMES_DESKTOP", "1")
    monkeypatch.setattr(
        pwd_mod,
        "start_desktop_parent_death_watchdog",
        lambda: calls.append("watchdog") or True,
    )

    # Next step after the watchdog hook is profile routing — stop there.
    def _stop_profile():
        calls.append("profile")
        raise SystemExit(0)

    monkeypatch.setattr(
        "hermes_cli.profiles.get_active_profile_name",
        _stop_profile,
    )

    args = type(
        "Args",
        (),
        {
            "status": False,
            "stop": False,
            "headless_backend": True,
            "isolated": False,
            "open_profile": "",
            "host": "127.0.0.1",
            "port": 0,
            "no_open": True,
            "insecure": False,
            "skip_build": True,
        },
    )()

    with pytest.raises(SystemExit) as exc:
        main_mod.cmd_dashboard(args)

    assert exc.value.code == 0
    assert calls == ["watchdog", "profile"]


def test_main_cmd_dashboard_source_wires_watchdog():
    """Regression: the desktop orphan fix must stay wired into cmd_dashboard."""
    import inspect

    import hermes_cli.main as main_mod

    src = inspect.getsource(main_mod.cmd_dashboard)
    assert "start_desktop_parent_death_watchdog" in src
    assert "HERMES_DESKTOP" in src or "parent_death_watchdog" in src