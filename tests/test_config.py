import pytest

from epower.config import (
    ACCOUNT_ID_ENV,
    ACCOUNT_PASS_ENV,
    AREA_ENV,
    BUILDING_ENV,
    DEFAULT_SYS_ID,
    FLOOR_ENV,
    METER_ID_ENV,
    ROOM_ENV,
    CliOptions,
    credentials_from_env,
    parse_floor,
    resolve_target,
)
from epower.errors import ConfigError


def test_credentials_require_account_and_password():
    with pytest.raises(ConfigError):
        credentials_from_env({})
    with pytest.raises(ConfigError):
        credentials_from_env({ACCOUNT_ID_ENV: "user"})


def test_credentials_default_sys_id():
    credentials = credentials_from_env(
        {ACCOUNT_ID_ENV: "user", ACCOUNT_PASS_ENV: "secret"}
    )
    assert credentials.sys_id == DEFAULT_SYS_ID
    assert credentials.account_id == "user"
    assert credentials.account_pass == "secret"


def test_meter_id_from_cli_wins_over_env():
    options = CliOptions(meter_id="cli-meter")
    target = resolve_target(options, {METER_ID_ENV: "env-meter"})
    assert target is not None
    assert target.meter_id == "cli-meter"
    assert target.uses_meter_id


def test_meter_id_from_env():
    target = resolve_target(CliOptions(), {METER_ID_ENV: "env-meter"})
    assert target is not None
    assert target.meter_id == "env-meter"


def test_room_needs_all_four_cli_values():
    partial = CliOptions(area="0004", building="B", floor=1)
    target = resolve_target(partial, {})
    assert target is None


def test_room_from_cli():
    options = CliOptions(area="0004", building="B", floor=2, room="R")
    target = resolve_target(options, {})
    assert target is not None
    assert (target.area_id, target.building_name, target.floor, target.room_name) == (
        "0004",
        "B",
        2,
        "R",
    )


def test_room_from_env():
    env = {
        AREA_ENV: "0004",
        BUILDING_ENV: "B",
        FLOOR_ENV: "3",
        ROOM_ENV: "R",
    }
    target = resolve_target(CliOptions(), env)
    assert target is not None
    assert target.floor == 3


def test_room_env_rejects_bad_floor():
    env = {
        AREA_ENV: "0004",
        BUILDING_ENV: "B",
        FLOOR_ENV: "three",
        ROOM_ENV: "R",
    }
    with pytest.raises(ConfigError):
        resolve_target(CliOptions(), env)


def test_no_target_returns_none():
    assert resolve_target(CliOptions(), {}) is None


def test_parse_floor_error_message():
    with pytest.raises(ConfigError):
        parse_floor("0x1")
