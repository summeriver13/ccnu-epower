import sys

import pytest

from epower.taskbar import autostart_target, taskbar_is_light
from epower.widget import (
    COLOR_ERROR,
    COLOR_LOW,
    COLOR_OK_DARK,
    COLOR_OK_LIGHT,
    DEFAULT_REFRESH_MINUTES,
    LOW_BALANCE_THRESHOLD_RMB,
    REFRESH_ENV,
    RETRY_MINUTES,
    alert_cleared,
    alert_due,
    balance_value,
    band_text,
    band_text_variants,
    fitting_text,
    next_refresh_minutes,
    refresh_minutes,
    room_name,
    text_color,
)


def report(money=74.39, errors=None):
    return {"balance": {"remain_money": money}, "errors": errors or []}


def test_balance_value_reads_remain_money():
    assert balance_value(report()) == 74.39


def test_balance_value_returns_none_for_bad_payloads():
    assert balance_value(None) is None
    assert balance_value({}) is None
    assert balance_value({"balance": {"remain_money": "74"}}) is None


def test_band_text_formats_two_decimals():
    assert band_text(report()) == "电费 \u00a574.39"


def test_band_text_shows_the_room():
    payload = report()
    payload["location"] = {"room_name": "南4-316"}
    assert band_text(payload) == "电费 南4-316 \u00a574.39"


def test_band_text_without_data():
    assert band_text(None) == "电费 获取中…"
    assert band_text({"balance": {}}) == "电费 取数失败"
    payload = {"balance": {}, "location": {"room_name": "南4-316"}}
    assert band_text(payload) == "电费 南4-316 取数失败"


def test_band_text_variants_run_from_widest_to_narrowest():
    payload = report()
    payload["location"] = {"room_name": "南4-316"}
    assert band_text_variants(payload) == (
        "电费 南4-316 ¥74.39",
        "南4-316 ¥74.39",
        "电费 ¥74.39",
        "¥74.39",
    )


def test_band_text_variants_without_a_room():
    assert band_text_variants(report()) == ("电费 ¥74.39", "¥74.39")
    assert band_text_variants(None) == ("电费 获取中…", "获取中…")


def test_fitting_text_takes_the_widest_text_that_fits():
    assert fitting_text(("abcd", "abc", "ab"), len, 3) == "abc"
    assert fitting_text(("abcd", "abc"), len, 2) is None
    assert fitting_text((), len, 100) is None


def test_room_name_ignores_bad_payloads():
    assert room_name(None) == ""
    assert room_name({"location": {}}) == ""
    assert room_name({"location": {"room_name": 5}}) == ""


def test_text_colour_follows_the_balance():
    assert text_color(report(), light_taskbar=False) == COLOR_OK_DARK
    assert text_color(report(), light_taskbar=True) == COLOR_OK_LIGHT
    low = report(LOW_BALANCE_THRESHOLD_RMB - 1)
    assert text_color(low, light_taskbar=False) == COLOR_LOW


def test_text_colour_on_failure():
    assert text_color(report(money=None), light_taskbar=False) == COLOR_ERROR
    assert text_color(report(errors=["boom"]), light_taskbar=False) == COLOR_OK_DARK
    assert text_color(None, light_taskbar=False) == COLOR_OK_DARK


def test_refresh_minutes_default_and_override():
    assert refresh_minutes({}) == DEFAULT_REFRESH_MINUTES
    assert refresh_minutes({REFRESH_ENV: "15"}) == 15
    assert refresh_minutes({REFRESH_ENV: "0"}) == 1
    assert refresh_minutes({REFRESH_ENV: "soon"}) == DEFAULT_REFRESH_MINUTES


def test_next_refresh_minutes_retries_soon_after_a_failure():
    assert next_refresh_minutes(report()) == DEFAULT_REFRESH_MINUTES
    assert next_refresh_minutes(report(), {REFRESH_ENV: "15"}) == 15
    assert next_refresh_minutes(None) == RETRY_MINUTES
    assert next_refresh_minutes(report(errors=["boom"])) == RETRY_MINUTES


def test_taskbar_theme_is_dark_off_windows():
    if sys.platform != "win32":
        assert taskbar_is_light() is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_autostart_target_uses_pythonw():
    command = autostart_target()
    assert "pythonw.exe" in command.lower()
    assert "-m epower.taskbar" in command


def test_alert_due_only_once_per_drop():
    low = LOW_BALANCE_THRESHOLD_RMB - 0.01
    assert alert_due(low, False) is True
    assert alert_due(low, True) is False


def test_alert_due_ignores_safe_and_missing_values():
    assert alert_due(LOW_BALANCE_THRESHOLD_RMB, False) is False
    assert alert_due(LOW_BALANCE_THRESHOLD_RMB + 1.0, False) is False
    assert alert_due(None, False) is False


def test_alert_cleared_needs_a_value_at_or_above_the_threshold():
    assert alert_cleared(LOW_BALANCE_THRESHOLD_RMB) is True
    assert alert_cleared(LOW_BALANCE_THRESHOLD_RMB + 1.0) is True
    assert alert_cleared(LOW_BALANCE_THRESHOLD_RMB - 0.01) is False
    assert alert_cleared(None) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_autostart_round_trip(monkeypatch):
    import contextlib
    import winreg

    from epower import taskbar

    test_key = r"Software\ccnu-epower-test"
    monkeypatch.setattr(taskbar, "AUTOSTART_KEY", test_key)
    monkeypatch.setattr(taskbar, "AUTOSTART_NAME", "ccnu-epower-test")
    try:
        taskbar.install_autostart()
        assert taskbar.uninstall_autostart() is True
        assert taskbar.uninstall_autostart() is False
    finally:
        with contextlib.suppress(FileNotFoundError):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, test_key)
