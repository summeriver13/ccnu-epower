"""Collect balance, usage, bills, and recharge history for one room."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .client import NewAPI
from .config import Target
from .errors import CCNUEWError
from .room import RoomLocation, resolve_room

CST = timezone(timedelta(hours=8))
MONTHS_BACK = 2
UNKNOWN = "-"

BALANCE_KEYS = ("remainPower", "remainMoney", "remain", "balance")
YESTERDAY_USAGE_KEYS = (
    "yesterdayPower",
    "yesterdayUse",
    "yesterdayUsage",
    "freePower",
)
YESTERDAY_CHARGE_KEYS = (
    "yesterdayMoney",
    "yesterdayCharge",
    "yesterdayCost",
    "dayMoney",
)
METER_STATE_KEYS = ("state", "stateName", "statusName", "meterState")
METER_VALVE_KEYS = ("valve", "valveState")
LAST_READ_KEYS = ("readTime", "lastReadTime", "lastTime", "LastQueryDate")
DAY_VALUE_KEYS = ("dayValue", "power", "usePower", "value")
DAY_CHARGE_KEYS = ("dayUseMeony", "dayUseMoney", "money", "charge", "cost")


def extract_float(data: dict[str, Any], *keys: str) -> Optional[float]:
    """Return the first value that converts to float, else None."""
    for key in keys:
        raw = data.get(key)
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (ValueError, TypeError):
            continue
    return None


def extract_str(data: dict[str, Any], *keys: str) -> str:
    """Return the first non-empty value as string, else an empty string."""
    for key in keys:
        raw = data.get(key)
        if raw is not None and raw != "":
            return str(raw)
    return ""


def month_range(now: datetime, months_back: int = MONTHS_BACK) -> tuple[str, str]:
    """Return the yyyyMM strings for the first and last month to query."""
    total = now.year * 12 + now.month - 1 - months_back
    start_year, start_month = divmod(total, 12)
    return f"{start_year}{start_month + 1:02d}", now.strftime("%Y%m")


def collect_report(
    api: NewAPI, target: Target, now: Optional[datetime] = None
) -> dict[str, Any]:
    """Collect every available record for the target.

    Endpoint failures are recorded in the errors list, so a partial
    report is still returned.
    """
    current = now or datetime.now(CST)
    errors: list[str] = []
    location = _location(api, target)
    return {
        "query_time": current.strftime("%Y-%m-%d %H:%M:%S CST"),
        "query_time_iso": current.isoformat(),
        "location": asdict(location),
        "balance": _collect_balance(api, location.meter_id, current, errors),
        "daily_usage": _collect_daily(api, location.meter_id, current, errors),
        "monthly_bills": _collect_monthly(api, location.meter_id, current, errors),
        "recharge_history": _collect_recharge(api, location.meter_id, errors),
        "errors": errors,
    }


def _location(api: NewAPI, target: Target) -> RoomLocation:
    if not target.uses_meter_id:
        return resolve_room(api, target)
    return RoomLocation(
        meter_id=target.meter_id,
        area_name=UNKNOWN,
        area_id=UNKNOWN,
        building_name=UNKNOWN,
        floor=0,
        room_name=UNKNOWN,
        room_id=UNKNOWN,
    )


def _collect_balance(
    api: NewAPI, meter_id: str, now: datetime, errors: list[str]
) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    try:
        raw = api.get_balance(meter_id)
    except CCNUEWError as exc:
        errors.append(f"余额查询失败: {exc}")

    usage = extract_float(raw, *YESTERDAY_USAGE_KEYS)
    charge = extract_float(raw, *YESTERDAY_CHARGE_KEYS)
    fresh_usage, fresh_charge = _collect_yesterday(api, meter_id, now, errors)
    return {
        "remain_money": extract_float(raw, *BALANCE_KEYS),
        "yesterday_usage_kwh": fresh_usage if fresh_usage is not None else usage,
        "yesterday_charge": fresh_charge if fresh_charge is not None else charge,
        "meter_status": _meter_status(raw),
        "last_read_time": extract_str(raw, *LAST_READ_KEYS),
        "raw": raw,
    }


def _meter_status(raw: dict[str, Any]) -> str:
    state = extract_str(raw, *METER_STATE_KEYS)
    valve = extract_str(raw, *METER_VALVE_KEYS)
    return f"{state}--{valve}" if valve else state


def _collect_yesterday(
    api: NewAPI, meter_id: str, now: datetime, errors: list[str]
) -> tuple[Optional[float], Optional[float]]:
    yesterday = now - timedelta(days=1)
    day = f"{yesterday.year}-{yesterday.month}-{yesterday.day}"
    try:
        records = api.get_daily_usage(meter_id, day, day)
    except CCNUEWError as exc:
        errors.append(f"昨日数据查询失败: {exc}")
        return None, None
    if not records:
        return None, None
    record = records[0]
    return (
        extract_float(record, *DAY_VALUE_KEYS),
        extract_float(record, *DAY_CHARGE_KEYS),
    )


def _collect_daily(
    api: NewAPI, meter_id: str, now: datetime, errors: list[str]
) -> list[dict[str, Any]]:
    start = f"{now.year}-{now.month}-1"
    end = f"{now.year}-{now.month}-{now.day}"
    try:
        return api.get_daily_usage(meter_id, start, end)
    except CCNUEWError as exc:
        errors.append(f"每日用量查询失败: {exc}")
        return []


def _collect_monthly(
    api: NewAPI, meter_id: str, now: datetime, errors: list[str]
) -> list[dict[str, Any]]:
    start_month, end_month = month_range(now)
    try:
        return api.get_monthly_bill(meter_id, start_month, end_month)
    except CCNUEWError as exc:
        errors.append(f"月度账单查询失败: {exc}")
        return []


def _collect_recharge(
    api: NewAPI, meter_id: str, errors: list[str]
) -> list[dict[str, Any]]:
    try:
        return api.get_recharge_history(meter_id)
    except CCNUEWError as exc:
        errors.append(f"充值记录查询失败: {exc}")
        return []
