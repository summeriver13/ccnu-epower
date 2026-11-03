"""Runtime configuration from environment variables and CLI arguments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from .errors import ConfigError

API_BASE = "https://jnb.ccnu.edu.cn/ICBS_V2_Server"

SYS_ID_ENV = "CCNU_SYS_ID"
ACCOUNT_ID_ENV = "CCNU_ACCOUNT_ID"
ACCOUNT_PASS_ENV = "CCNU_ACCOUNT_PASS"
AREA_ENV = "CCNU_AREA"
BUILDING_ENV = "CCNU_BUILDING"
FLOOR_ENV = "CCNU_FLOOR"
ROOM_ENV = "CCNU_ROOM"
METER_ID_ENV = "CCNU_METER_ID"
LOG_LEVEL_ENV = "CCNU_LOG_LEVEL"

DEFAULT_SYS_ID = "999"
DEFAULT_LOG_LEVEL = "WARNING"

REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 1.0
DEFAULT_RETRY_AFTER_SECONDS = 5.0
RATE_LIMIT_MIN_INTERVAL_SECONDS = 0.5


@dataclass(frozen=True)
class Credentials:
    """Platform account used by the SM2 login handshake."""

    sys_id: str
    account_id: str
    account_pass: str


@dataclass(frozen=True)
class Target:
    """Room to query, or a bare meter ID when ``meter_id`` is set."""

    meter_id: str = ""
    area_id: str = ""
    building_name: str = ""
    floor: int = 0
    room_name: str = ""

    @property
    def uses_meter_id(self) -> bool:
        return bool(self.meter_id)


@dataclass(frozen=True)
class CliOptions:
    """Raw command line values before environment fallback."""

    meter_id: Optional[str] = None
    area: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[int] = None
    room: Optional[str] = None


def _source(env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    return os.environ if env is None else env


def credentials_from_env(env: Optional[Mapping[str, str]] = None) -> Credentials:
    """Read the platform account from the environment.

    Raises:
        ConfigError: When the account ID or password is missing.
    """
    source = _source(env)
    account_id = source.get(ACCOUNT_ID_ENV, "").strip()
    account_pass = source.get(ACCOUNT_PASS_ENV, "").strip()
    if not account_id or not account_pass:
        raise ConfigError(
            f"缺少平台账号：请设置 {ACCOUNT_ID_ENV} 和 {ACCOUNT_PASS_ENV} 环境变量"
        )
    return Credentials(
        sys_id=source.get(SYS_ID_ENV, "").strip() or DEFAULT_SYS_ID,
        account_id=account_id,
        account_pass=account_pass,
    )


def parse_floor(raw: str) -> int:
    """Convert a floor string to int, or raise ConfigError."""
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{FLOOR_ENV} 不是有效整数：'{raw}'") from exc


def resolve_target(
    options: CliOptions, env: Optional[Mapping[str, str]] = None
) -> Optional[Target]:
    """Combine CLI options and environment variables into one target.

    CLI values win over environment values. Returns None when the caller
    supplied no usable target.
    """
    source = _source(env)
    meter_id = (options.meter_id or "").strip() or source.get(METER_ID_ENV, "").strip()
    if meter_id:
        return Target(meter_id=meter_id)

    cli_ready = (
        options.area and options.building and options.room and options.floor is not None
    )
    if cli_ready:
        return Target(
            area_id=(options.area or "").strip(),
            building_name=(options.building or "").strip(),
            floor=options.floor or 0,
            room_name=(options.room or "").strip(),
        )

    area = source.get(AREA_ENV, "").strip()
    building = source.get(BUILDING_ENV, "").strip()
    floor_raw = source.get(FLOOR_ENV, "").strip()
    room = source.get(ROOM_ENV, "").strip()
    if area and building and floor_raw and room:
        return Target(
            area_id=area,
            building_name=building,
            floor=parse_floor(floor_raw),
            room_name=room,
        )
    return None
