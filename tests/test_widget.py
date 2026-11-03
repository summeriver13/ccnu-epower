from epower.tray import ICON_SIZE, autostart_target, build_image
from epower.widget import (
    COLOR_ERROR,
    COLOR_LOW,
    COLOR_OK,
    DEFAULT_REFRESH_MINUTES,
    REFRESH_ENV,
    balance_value,
    icon_color,
    icon_text,
    refresh_minutes,
    tray_title,
)


def report(money=74.39, usage=9.62, errors=None):
    return {
        "query_time": "2026-11-04T00:01:36+08:00",
        "balance": {"remain_money": money, "yesterday_usage_kwh": usage},
        "errors": errors or [],
    }


def test_balance_value_reads_remain_money():
    assert balance_value(report()) == 74.39


def test_balance_value_returns_none_for_bad_payloads():
    assert balance_value(None) is None
    assert balance_value({}) is None
    assert balance_value({"balance": {"remain_money": "74"}}) is None


def test_icon_text_keeps_two_digits():
    assert icon_text(report(74.39)) == "74"


def test_icon_text_has_one_decimal_below_ten():
    assert icon_text(report(5.25)) == "5.2"


def test_icon_text_without_data():
    assert icon_text(None) == "?"


def test_icon_color_tracks_state():
    assert icon_color(report(74.39)) == COLOR_OK
    assert icon_color(report(5.0)) == COLOR_LOW
    assert icon_color(report(74.39, errors=["boom"])) == COLOR_ERROR
    assert icon_color(None) == COLOR_ERROR


def test_tray_title_lists_balance_usage_and_time():
    title = tray_title(report())
    assert "剩余 ¥74.39" in title
    assert "昨日 9.62 度" in title
    assert "2026-11-04T00:01" in title


def test_tray_title_reports_failed_endpoints():
    assert "接口失败 2 项" in tray_title(report(errors=["a", "b"]))


def test_tray_title_without_report():
    assert "尚未取到数据" in tray_title(None)


def test_refresh_minutes_default_and_override():
    assert refresh_minutes({}) == DEFAULT_REFRESH_MINUTES
    assert refresh_minutes({REFRESH_ENV: "15"}) == 15
    assert refresh_minutes({REFRESH_ENV: "0"}) == 1
    assert refresh_minutes({REFRESH_ENV: "soon"}) == DEFAULT_REFRESH_MINUTES


def test_build_image_returns_a_square_icon():
    image = build_image("74", COLOR_OK)
    assert image.size == (ICON_SIZE, ICON_SIZE)
    assert image.mode == "RGBA"


def test_autostart_target_uses_pythonw():
    assert "pythonw.exe" in autostart_target().lower()
    assert "-m epower.tray" in autostart_target()


def test_uninstall_without_key_is_not_an_error(monkeypatch):
    import winreg

    from epower import tray

    def missing(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(winreg, "OpenKey", missing)
    assert tray.uninstall_autostart() is False
