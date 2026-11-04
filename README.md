<div align="center">

# ccnu-epower

Query the CCNU dormitory electricity balance, usage, and bills from the
terminal. Keep the balance on the Windows taskbar.

[![CI](https://github.com/summeriver13/ccnu-epower/actions/workflows/ci.yml/badge.svg)](https://github.com/summeriver13/ccnu-epower/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

> [!WARNING]
> This project is not affiliated with, endorsed by, or supported by Central
> China Normal University. It calls a private API that the university can
> change or close at any time. Use it only with your own account and at a low
> request rate. You are responsible for following the campus network and
> platform terms.

## What you get

```
$ uv run epower
🔍 正在查找 南湖04栋 南4-316 …
🔗 正在连接校园网 …

✅ 查询完成！

  📊 JSON 数据: output\latest.json

  💰 剩余金额: ¥73.64
  ⚡ 昨日用量: 9.62 度
  📅 昨日计费: ¥5.37
  🕐 最近抄表: 2026-11-04 04:03:57
```

```
          taskbar
   ┌──────────────────────┐
   │ 电费 南4-316 ¥74.39  │  ← epower-band
   └──────────────────────┘
```

| Entry point | What it does |
| --- | --- |
| `epower` | One query. Writes `output/latest.json`. |
| `epower-band` | Taskbar band. Timer refresh, low-balance alert, optional autostart. |

## Requirements

| Item | Detail |
| --- | --- |
| Python | 3.9 or newer |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Network | Campus network only. The API is not reachable from the internet. |
| Credentials | Your platform account, or the shared-account key (see [Shared account](#shared-account)) |

## Quick start

```bash
git clone https://github.com/summeriver13/ccnu-epower.git
cd ccnu-epower
uv sync
cp .env.example .env      # then fill it in
uv run epower
```

## Configuration

The tool reads `.env` from the working directory. CLI arguments override it.

### Target room

Set `CCNU_METER_ID` for a direct query, or the four room variables for
discovery. Building and room names match by substring.

```ini
CCNU_AREA=0004
CCNU_BUILDING=BUILDING-NAME
CCNU_FLOOR=1
CCNU_ROOM=ROOM-NAME
```

### Credentials

Set one pair. Without it the tool stops with a configuration error.

```ini
CCNU_ACCOUNT_ID=your-account-id
CCNU_ACCOUNT_PASS=your-account-password
```

### Shared account

The platform frontend logs in without a password. It reads an encrypted
account from `/v1/Authentication/GetAP` and decrypts it with an SM2 private
key that ships in the frontend bundle. The tool can do the same:

```ini
CCNU_APP_PRIVATE_KEY=<key from the frontend bundle>
```

Leave `CCNU_ACCOUNT_PASS` empty to use this path. The tool fetches and
decrypts the shared account on every run, so a password rotation does not
break it. The key stays out of this repository.

This path uses a campus-wide account. Check that your use follows the platform
terms.

### All variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `CCNU_ACCOUNT_ID` | none | Platform account name |
| `CCNU_ACCOUNT_PASS` | none | Platform account password |
| `CCNU_APP_PRIVATE_KEY` | none | SM2 key for the shared account |
| `CCNU_SYS_ID` | `999` | Platform system ID |
| `CCNU_METER_ID` | none | Meter ID. Skips room discovery |
| `CCNU_AREA` | none | Campus code |
| `CCNU_BUILDING` | none | Building name |
| `CCNU_FLOOR` | none | Floor number |
| `CCNU_ROOM` | none | Room name |
| `CCNU_LOG_LEVEL` | `WARNING` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `CCNU_REFRESH_MINUTES` | `60` | Band refresh interval |

## Usage

```bash
# Room discovery
uv run epower -a 0004 -b BUILDING-NAME -f 1 -r ROOM-NAME

# Meter ID. Fewer requests, no discovery.
uv run epower -m 1000.000000.1
```

| Flag | Meaning |
| --- | --- |
| `-a`, `--area` | Campus code, such as `0004` |
| `-b`, `--building` | Building name, substring match |
| `-f`, `--floor` | Floor number |
| `-r`, `--room` | Room name, substring match |
| `-m`, `--meter-id` | Meter ID, skips room discovery |

The report goes to `output/latest.json` and overwrites the previous file.

| Key | Meaning |
| --- | --- |
| `location` | Area, building, floor, room, meter ID |
| `balance.remain_money` | Remaining balance in CNY |
| `balance.yesterday_usage_kwh` | Yesterday usage in kWh |
| `balance.yesterday_charge` | Yesterday charge in CNY |
| `balance.meter_status` | Meter state reported by the platform |
| `daily_usage` | Usage per day for the current month |
| `monthly_bills` | Last three monthly bills |
| `recharge_history` | Recharge orders |
| `errors` | Endpoints that failed during this run |

The command prints a warning when the balance is below 20 CNY.

## Taskbar band

```bash
uv run epower-band
```

The band shows `电费 南4-316 ¥74.39` on the taskbar, to the left of the
notification area icons. Windows 11 has no supported taskbar plugin API and no
window handle for the clock, so the band is a borderless topmost window placed
next to the tray. The taskbar owns that window, so the taskbar never covers
it, and it follows theme changes.

| Balance | Band |
| --- | --- |
| 20 CNY or more | White text |
| Below 20 CNY | Amber text, one system notification |
| Last refresh failed | Red text |

- Left click opens `output/latest.json`.
- Right click refreshes, opens the report, or quits.
- The notification repeats only after the balance goes back above 20 CNY.
  Windows drops balloons from hidden icons, so a tray icon shows for 15
  seconds around the balloon and then goes away.
- A refresh runs every 60 minutes. Set `CCNU_REFRESH_MINUTES` to change it.

### Start at logon

```bash
uv run epower-band --install-autostart      # writes the HKCU Run key
uv run epower-band --uninstall-autostart
```

Fill `.env` before you install the autostart entry. The band runs without a
console, so a missing setting shows up in the band text.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Report written |
| 1 | Missing configuration, network failure, or authentication failure |

## Development

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## License

MIT. See `LICENSE`.
