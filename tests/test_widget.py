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
    balance_value,
    band_text,
    refresh_minutes,
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
    assert band_text(report()) == "\u00a574.39"


def test_band_text_without_data():
    assert band_text(None) == "获取中…"
    assert band_text({"balance": {}}) == "取数失败"


def test_text_colour_follows_the_balance():
    assert text_color(report(), light_taskbar=False) == COLOR_OK_DARK
    assert text_color(report(), light_taskbar=True) == COLOR_OK_LIGHT
    low = report(LOW_BALANCE_THRESHOLD_RMB - 1)
    assert text_color(low, light_taskbar=False) == COLOR_LOW


def test_text_colour_on_failure():
    assert text_color(report(errors=["boom"]), light_taskbar=False) == COLOR_ERROR
    assert text_color(None, light_taskbar=False) == COLOR_OK_DARK


def test_refresh_minutes_default_and_override():
    assert refresh_minutes({}) == DEFAULT_REFRESH_MINUTES
    assert refresh_minutes({REFRESH_ENV: "15"}) == 15
    assert refresh_minutes({REFRESH_ENV: "0"}) == 1
    assert refresh_minutes({REFRESH_ENV: "soon"}) == DEFAULT_REFRESH_MINUTES


def test_taskbar_theme_is_dark_off_windows():
    if sys.platform != "win32":
        assert taskbar_is_light() is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_autostart_target_uses_pythonw():
    command = autostart_target()
    assert "pythonw.exe" in command.lower()
    assert "-m epower.taskbar" in command


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_autostart_round_trip():
    from epower.taskbar import install_autostart, uninstall_autostart

    install_autostart()
    assert uninstall_autostart() is True
    assert uninstall_autostart() is False
