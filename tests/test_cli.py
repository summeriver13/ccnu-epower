import json

from epower import cli
from epower.config import METER_ID_ENV, Credentials


def sample_report():
    return {
        "query_time": "2025-07-11 12:00:00 CST",
        "query_time_iso": "2025-07-11T12:00:00+08:00",
        "location": {"meter_id": "meter"},
        "balance": {
            "remain_money": 5.0,
            "yesterday_usage_kwh": None,
            "yesterday_charge": None,
            "meter_status": "",
            "last_read_time": "",
            "raw": {},
        },
        "daily_usage": [],
        "monthly_bills": [],
        "recharge_history": [],
        "errors": [],
    }


def test_missing_credentials_exits_with_one(monkeypatch):
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.delenv("CCNU_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CCNU_ACCOUNT_PASS", raising=False)
    assert cli.main([]) == 1


def test_missing_target_exits_with_one(monkeypatch):
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        cli, "credentials_from_env", lambda env=None: Credentials("999", "u", "p")
    )
    monkeypatch.delenv(METER_ID_ENV, raising=False)
    monkeypatch.delenv("CCNU_AREA", raising=False)
    assert cli.main([]) == 1


def test_success_writes_report(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        cli, "credentials_from_env", lambda env=None: Credentials("999", "u", "p")
    )
    monkeypatch.setattr(cli, "query", lambda credentials, target: sample_report())
    monkeypatch.setattr(cli, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv(METER_ID_ENV, "meter")

    assert cli.main([]) == 0
    payload = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert payload["location"]["meter_id"] == "meter"


def test_query_failure_exits_with_one(monkeypatch):
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        cli, "credentials_from_env", lambda env=None: Credentials("999", "u", "p")
    )

    def fail(credentials, target):
        raise cli.CCNUEWError("boom")

    monkeypatch.setattr(cli, "query", fail)
    monkeypatch.setenv(METER_ID_ENV, "meter")
    assert cli.main([]) == 1
