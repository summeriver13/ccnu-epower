# CCNU Electricity Watch

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
- Your own platform account

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
