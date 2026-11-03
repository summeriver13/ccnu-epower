from datetime import datetime

from epower.collect import CST, UNKNOWN, collect_report, month_range
from epower.config import Target

NOW = datetime(2025, 7, 11, 12, 0, tzinfo=CST)


def test_meter_target_skips_discovery(api):
    api.balance = {"remainPower": "102.57", "state": "online", "valve": "closed"}
    report = collect_report(api, Target(meter_id="meter"), now=NOW)
    assert report["location"]["meter_id"] == "meter"
    assert report["location"]["area_name"] == UNKNOWN
    assert "buildings" not in api.calls


def test_balance_fields_and_status(api):
    api.balance = {"remainPower": "12.5", "state": "online", "valve": "closed"}
    report = collect_report(api, Target(meter_id="meter"), now=NOW)
    balance = report["balance"]
    assert balance["remain_money"] == 12.5
    assert balance["meter_status"] == "online--closed"
    assert balance["raw"] == api.balance


def test_day_value_overrides_balance_yesterday(api):
    api.balance = {"yesterdayPower": "1.0", "yesterdayMoney": "0.5"}
    api.daily = [{"dayValue": "5.5", "dayUseMeony": "3.3"}]
    balance = collect_report(api, Target(meter_id="meter"), now=NOW)["balance"]
    assert balance["yesterday_usage_kwh"] == 5.5
    assert balance["yesterday_charge"] == 3.3


def test_failures_are_collected(api):
    api.fail_on = {"balance", "daily", "monthly", "orders"}
    report = collect_report(api, Target(meter_id="meter"), now=NOW)
    assert len(report["errors"]) == 5
    assert report["daily_usage"] == []
    assert report["monthly_bills"] == []
    assert report["recharge_history"] == []


def test_room_target_uses_resolved_location(api):
    api.areas = [{"AreaID": "0004", "AreaName": "Campus"}]
    api.buildings = [{"ArchitectureID": "B1", "ArchitectureName": "Dorm 04"}]
    api.rooms = [{"RoomNo": "21943", "RoomName": "N4-316"}]
    api.room_meter = {"meterList": [{"meterId": "1000.000000.1"}]}
    target = Target(area_id="0004", building_name="Dorm", floor=3, room_name="316")
    location = collect_report(api, target, now=NOW)["location"]
    assert location["meter_id"] == "1000.000000.1"
    assert location["room_id"] == "21943"


def test_month_range_spans_three_months():
    assert month_range(NOW) == ("202505", "202507")


def test_month_range_crosses_year():
    january = datetime(2026, 1, 5, tzinfo=CST)
    assert month_range(january) == ("202511", "202601")
