"""Render collected data as JSON and as human readable strings."""

from __future__ import annotations

import json
from typing import Any, Optional

LOW_BALANCE_THRESHOLD_RMB = 20.0
MISSING = "-"


def format_money(value: Optional[float]) -> str:
    return MISSING if value is None else f"¥{value:,.2f}"


def format_kwh(value: Optional[float]) -> str:
    return MISSING if value is None else f"{value:,.2f} 度"


def format_value(value: Any, default: str = MISSING) -> str:
    if value is None or value == "":
        return default
    return str(value)


def generate_json(report: dict[str, Any]) -> str:
    """Drop the raw balance payload and dump the report as indented JSON."""
    balance = report["balance"]
    output = {
        "query_time": report["query_time_iso"],
        "location": report["location"],
        "balance": {
            "remain_money": balance["remain_money"],
            "yesterday_usage_kwh": balance["yesterday_usage_kwh"],
            "yesterday_charge": balance["yesterday_charge"],
            "meter_status": balance["meter_status"],
            "last_read_time": balance["last_read_time"],
        },
        "daily_usage": report["daily_usage"],
        "monthly_bills": report["monthly_bills"],
        "recharge_history": report.get("recharge_history", []),
        "errors": report["errors"],
    }
    return json.dumps(output, ensure_ascii=False, indent=2)
