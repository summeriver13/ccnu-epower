# ccnu-epower

Unofficial command line client for the CCNU dormitory electricity platform.
It queries the remaining balance, daily usage, monthly bills, and recharge
history, then writes one JSON report.

## Disclaimer

This project is not affiliated with, endorsed by, or supported by Central China
Normal University. It calls a private API that the university can change or
close at any time. Use it only with your own account and at a low request rate.
You are responsible for following the campus network and platform terms.

## Requirements

- Python 3.9 or newer
- [uv](https://docs.astral.sh/uv/)
- A campus network connection: the API is only reachable from inside CCNU
- A platform account, or the shared-account key that the platform frontend
  uses (see Configure)

## Install

```bash
uv sync
```

## Configure

Create `.env` from the template, then fill in your account and room:

```bash
cp .env.example .env
```

```ini
CCNU_ACCOUNT_ID=your-account-id
CCNU_ACCOUNT_PASS=your-account-password
CCNU_AREA=0004
CCNU_BUILDING=BUILDING-NAME
CCNU_FLOOR=1
CCNU_ROOM=ROOM-NAME
```

`.env` is ignored by Git. The account values have no default on purpose.

### Shared account

The platform frontend logs in without a password. It reads an encrypted
account from `/v1/Authentication/GetAP` and decrypts it with an SM2 private
key that ships in the frontend bundle. The tool can do the same:

```ini
CCNU_APP_PRIVATE_KEY=<key from the frontend bundle>
```

Leave `CCNU_ACCOUNT_PASS` empty to use this path. The tool then fetches and
decrypts the shared account on every run, so a password rotation does not
break it. The key stays out of this repository.

This path uses a campus-wide account. Check that your use follows the platform
terms.

## Usage

```bash
# Room discovery. Building and room names match by substring.
uv run epower -a 0004 -b BUILDING-NAME -f 1 -r ROOM-NAME

# Meter ID. Skips discovery and uses fewer requests.
uv run epower -m 1000.000000.1
```

CLI arguments override `.env`. With no arguments the tool reads `.env`.

The report goes to `output/latest.json` and overwrites the previous file.

| Key | Meaning |
| --- | --- |
| `location` | area, building, floor, room, meter ID |
| `balance.remain_money` | remaining balance in CNY |
| `balance.yesterday_usage_kwh` | yesterday usage in kWh |
| `balance.yesterday_charge` | yesterday charge in CNY |
| `balance.meter_status` | meter state reported by the platform |
| `daily_usage` | usage per day for the current month |
| `monthly_bills` | last three monthly bills |
| `recharge_history` | recharge orders |
| `errors` | endpoints that failed during this run |

The command prints a warning when the balance is below 20 CNY.

## Tray icon

`epower-tray` keeps the balance in the Windows notification area. Windows 11
no longer accepts third-party taskbar bands, so the tray icon is the closest
supported place.

```bash
uv run epower-tray
```

The icon shows the integer balance. Green means the balance is normal, amber
means below 20 CNY, and red means the last refresh failed. Hover for the full
tooltip. The menu refreshes on demand, opens `output/latest.json`, or quits.

A refresh runs every 60 minutes. Set `CCNU_REFRESH_MINUTES` to change it.

```bash
uv run epower-tray --install-autostart      # writes HKCU, Run key
uv run epower-tray --uninstall-autostart
```

Fill `.env` before you install the autostart entry. The tray runs without a
console, so a missing setting shows up only in the tooltip.

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
