"""Pure helpers for the taskbar band."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Tuple

REFRESH_ENV = "CCNU_REFRESH_MINUTES"
DEFAULT_REFRESH_MINUTES = 60
RETRY_MINUTES = 5
LOW_BALANCE_THRESHOLD_RMB = 20.0
BAND_LABEL = "电费"
PENDING_TEXT = "获取中…"
FAILED_TEXT = "取数失败"

COLOR_OK_DARK = (255, 255, 255)
COLOR_OK_LIGHT = (32, 32, 32)
COLOR_LOW = (217, 119, 6)
COLOR_ERROR = (220, 38, 38)

Color = Tuple[int, int, int]


def balance_value(report: Optional[Mapping[str, Any]]) -> Optional[float]:
    """Return the remaining balance in CNY, or None when missing."""
    if not report:
        return None
    balance = report.get("balance")
    if not isinstance(balance, Mapping):
        return None
    value = balance.get("remain_money")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def room_name(report: Optional[Mapping[str, Any]]) -> str:
    """Return the room shown on the taskbar, or an empty string."""
    if not report:
        return ""
    location = report.get("location")
    if not isinstance(location, Mapping):
        return ""
    name = location.get("room_name")
    return name if isinstance(name, str) else ""


def band_text(report: Optional[Mapping[str, Any]]) -> str:
    """Return the text drawn on the taskbar, such as 电费 南4-316 \u00a574.39."""
    value = balance_value(report)
    parts = [BAND_LABEL]
    room = room_name(report)
    if room:
        parts.append(room)
    if report is None:
        parts.append(PENDING_TEXT)
    elif value is None:
        parts.append(FAILED_TEXT)
    else:
        parts.append(f"\u00a5{value:.2f}")
    return " ".join(parts)


def text_color(report: Optional[Mapping[str, Any]], light_taskbar: bool) -> Color:
    """Return the text colour for the current balance state."""
    normal = COLOR_OK_LIGHT if light_taskbar else COLOR_OK_DARK
    if report is None:
        return normal
    value = balance_value(report)
    if value is None:
        return COLOR_ERROR if not light_taskbar else (185, 28, 28)
    if value < LOW_BALANCE_THRESHOLD_RMB:
        return COLOR_LOW
    return normal


def alert_due(value: Optional[float], alerted: bool) -> bool:
    """Return True when the balance is low and no alert was sent yet."""
    return value is not None and value < LOW_BALANCE_THRESHOLD_RMB and not alerted


def alert_cleared(value: Optional[float]) -> bool:
    """Return True when the balance is back above the alert threshold."""
    return value is not None and value >= LOW_BALANCE_THRESHOLD_RMB


def refresh_minutes(env: Optional[Mapping[str, str]] = None) -> int:
    """Return the refresh interval in minutes, at least one."""
    source = os.environ if env is None else env
    raw = source.get(REFRESH_ENV, "").strip()
    if not raw:
        return DEFAULT_REFRESH_MINUTES
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_REFRESH_MINUTES


def next_refresh_minutes(
    report: Optional[Mapping[str, Any]], env: Optional[Mapping[str, str]] = None
) -> int:
    """Return the wait before the next fetch, short after a failed one."""
    if report is None or report.get("errors"):
        return RETRY_MINUTES
    return refresh_minutes(env)
