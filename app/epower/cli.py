"""Command line entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Optional, Sequence

import requests
from dotenv import load_dotenv

from .auth import SM2Auth
from .client import NewAPI
from .collect import collect_report
from .config import (
    DEFAULT_LOG_LEVEL,
    LOG_LEVEL_ENV,
    CliOptions,
    Credentials,
    Target,
    credentials_from_env,
    resolve_target,
)
from .errors import CCNUEWError, ConfigError, NetworkError
from .report import (
    LOW_BALANCE_THRESHOLD_RMB,
    format_kwh,
    format_money,
    format_value,
    generate_json,
)

OUTPUT_DIR = "output"
OUTPUT_FILE = "latest.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="华师电费查询工具 — 查询宿舍电费并输出 JSON 报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  epower -m 1000.000000.1                # 电表 ID 直连\n"
            "  epower -a AREA -b BUILDING -f 1 -r ROOM  # 房间发现\n\n"
            "环境变量 (.env):\n"
            "  CCNU_ACCOUNT_ID / CCNU_ACCOUNT_PASS 必填\n"
            "  CCNU_METER_ID 或 CCNU_AREA/CCNU_BUILDING/CCNU_FLOOR/CCNU_ROOM"
        ),
    )
    parser.add_argument("-a", "--area", help="校区代码 (e.g. 0004)")
    parser.add_argument("-b", "--building", help="建筑名称，支持模糊匹配")
    parser.add_argument("-f", "--floor", type=int, help="楼层号")
    parser.add_argument("-r", "--room", help="房间名，支持模糊匹配")
    parser.add_argument("-m", "--meter-id", help="直接指定电表 ID，跳过房间发现")
    return parser


def configure_stdout() -> None:
    """Force UTF-8 output on Windows consoles that default to a legacy code page."""
    if sys.platform != "win32":
        return
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")


def setup_logging() -> None:
    level_name = os.getenv(LOG_LEVEL_ENV, DEFAULT_LOG_LEVEL).upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.WARNING),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def write_report(report: dict[str, Any]) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(generate_json(report))
    return path


def print_summary(report: dict[str, Any], json_path: str) -> None:
    balance = report["balance"]
    print(
        f"""
✅ 查询完成！

  📊 JSON 数据: {json_path}

  💰 剩余金额: {format_money(balance["remain_money"])}
  ⚡ 昨日用量: {format_kwh(balance["yesterday_usage_kwh"])}
  📅 昨日计费: {format_money(balance["yesterday_charge"])}
  🕐 最近抄表: {format_value(balance["last_read_time"])}"""
    )
    remain_money = balance["remain_money"]
    if remain_money is not None and remain_money < LOW_BALANCE_THRESHOLD_RMB:
        print(f"\n  ⚠️ 余额不足！剩余仅 {format_money(remain_money)}，请及时充值！")
    elif remain_money is not None:
        print("\n  ✅ 余额正常。")

    errors = report["errors"]
    if errors:
        print(f"\n  ⚠️ 部分数据获取失败 ({len(errors)} 项):")
        for error in errors:
            print(f"     - {error}")


def print_usage(parser: argparse.ArgumentParser) -> None:
    parser.print_help()
    print("\n❌ 请通过以下方式之一指定目标：")
    print("   电表 ID:   -m 12345678  或  CCNU_METER_ID=12345678")
    print("   房间发现:  -a 0004 -b BUILDING -f 1 -r ROOM")
    print(
        "   环境变量:  CCNU_AREA=0004 CCNU_BUILDING=BUILDING"
        " CCNU_FLOOR=1 CCNU_ROOM=ROOM"
    )


def query(credentials: Credentials, target: Target) -> dict[str, Any]:
    session = build_session()
    auth = SM2Auth(session, credentials)
    api = NewAPI(session, auth)
    return collect_report(api, target)


def main(argv: Optional[Sequence[str]] = None) -> int:
    load_dotenv()
    configure_stdout()
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        credentials = credentials_from_env()
        options = CliOptions(
            meter_id=args.meter_id,
            area=args.area,
            building=args.building,
            floor=args.floor,
            room=args.room,
        )
        target = resolve_target(options)
    except ConfigError as exc:
        print(f"❌ {exc}")
        return 1

    if target is None:
        print_usage(parser)
        return 1

    if target.uses_meter_id:
        print(f"🔍 正在查询电表 {target.meter_id} …")
    else:
        print(f"🔍 正在查找 {target.building_name} {target.room_name} …")

    print("🔗 正在连接校园网 …")
    try:
        report = query(credentials, target)
    except CCNUEWError as exc:
        print(f"\n❌ {exc}")
        if isinstance(exc, NetworkError):
            print("   请确认已连接到 CCNU 校园网络后重试。")
        return 1

    json_path = write_report(report)
    print_summary(report, json_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
