import json

from epower.report import (
    format_kwh,
    format_money,
    format_value,
    generate_json,
)


def report():
    return {
        "query_time": "2025-07-11 12:00:00 CST",
        "query_time_iso": "2025-07-11T12:00:00+08:00",
        "location": {"meter_id": "m"},
        "balance": {
            "remain_money": 1.5,
            "yesterday_usage_kwh": 2.0,
            "yesterday_charge": 0.2,
            "meter_status": "online",
            "last_read_time": "2025-07-11 11:00:00",
            "raw": {"secret": "payload"},
        },
        "daily_usage": [{"dayValue": "1"}],
        "monthly_bills": [],
        "recharge_history": [],
        "errors": [],
    }


def test_generate_json_drops_raw_payload():
    payload = json.loads(generate_json(report()))
    assert "raw" not in payload["balance"]
    assert payload["balance"]["remain_money"] == 1.5
    assert payload["location"]["meter_id"] == "m"


def test_format_helpers():
    assert format_money(1.5) == "¥1.50"
    assert format_money(None) == "-"
    assert format_kwh(2) == "2.00 度"
    assert format_value("") == "-"
    assert format_value("x") == "x"
