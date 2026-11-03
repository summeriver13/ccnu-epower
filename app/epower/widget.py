"""Pure helpers for the tray icon text and colours."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Tuple

REFRESH_ENV = "CCNU_REFRESH_MINUTES"
DEFAULT_REFRESH_MINUTES = 60
LOW_BALANCE_THRESHOLD_RMB = 20.0

COLOR_OK = (22, 163, 74)
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


def icon_text(report: Optional[Mapping[str, Any]]) -> str:
    """Return the short text drawn inside the tray icon."""
    value = balance_value(report)
    if value is None:
        return "?"
    if value >= 100:
        return f"{value:.0f}"
    return f"{value:.0f}" if value >= 10 else f"{value:.1f}"


def icon_color(report: Optional[Mapping[str, Any]]) -> Color:
    """Return the icon colour for the current report state."""
    if not report or report.get("errors"):
        return COLOR_ERROR
    value = balance_value(report)
    if value is None:
        return COLOR_ERROR
    if value < LOW_BALANCE_THRESHOLD_RMB:
        return COLOR_LOW
    return COLOR_OK


def tray_title(report: Optional[Mapping[str, Any]]) -> str:
    """Return the tooltip text for the tray icon."""
    if not report:
        return "ccnu-epower：尚未取到数据"
    balance = report.get("balance") or {}
    money = balance.get("remain_money")
    usage = balance.get("yesterday_usage_kwh")
    updated = str(report.get("query_time", ""))[:16]
    parts = []
    if isinstance(money, (int, float)):
        parts.append(f"剩余 ¥{money:.2f}")
    else:
        parts.append("剩余 -")
    if isinstance(usage, (int, float)):
        parts.append(f"昨日 {usage:.2f} 度")
    if updated:
        parts.append(updated)
    if report.get("errors"):
        parts.append(f"接口失败 {len(report['errors'])} 项")
    return " · ".join(parts)


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
