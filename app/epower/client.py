"""JSON REST API client with rate limiting, retries, and JWT refresh."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, TypeVar

import requests

from .auth import SM2Auth
from .config import (
    API_BASE,
    DEFAULT_RETRY_AFTER_SECONDS,
    MAX_RETRIES,
    RATE_LIMIT_MIN_INTERVAL_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_BASE_DELAY_SECONDS,
)
from .errors import APIError, AuthError, NetworkError, ParseError

logger = logging.getLogger("ccnu_epower")

T = TypeVar("T")


def retry_on_transient(
    func: Callable[[], T],
    max_retries: int = MAX_RETRIES,
    base_delay: float = RETRY_BASE_DELAY_SECONDS,
) -> T:
    """Call func with exponential backoff on transient network errors.

    Retries ConnectionError, Timeout, and NetworkError. All other
    CCNUEWError subclasses propagate immediately.
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except (requests.ConnectionError, requests.Timeout, NetworkError) as exc:
            if attempt >= max_retries:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "Transient error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                max_retries,
                delay,
                exc,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")


def parse_retry_after(response: Optional[Any]) -> float:
    """Read Retry-After from a response, falling back to five seconds."""
    if response is None:
        return DEFAULT_RETRY_AFTER_SECONDS
    try:
        return float(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER_SECONDS))
    except (ValueError, TypeError):
        return DEFAULT_RETRY_AFTER_SECONDS


class RateLimiter:
    """Keep a minimum interval between consecutive API calls."""

    def __init__(self, min_interval: float = RATE_LIMIT_MIN_INTERVAL_SECONDS) -> None:
        self._min_interval = min_interval
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()


class NewAPI:
    """JSON REST API client. All endpoints require a bearer token."""

    def __init__(
        self,
        session: requests.Session,
        auth: SM2Auth,
        limiter: Optional[RateLimiter] = None,
    ) -> None:
        self._session = session
        self._auth = auth
        self._limiter = limiter or RateLimiter()
        self._area_cache: Optional[list[dict[str, Any]]] = None

    def request(
        self, endpoint: str, params: dict[str, str], *, retry_auth: bool = True
    ) -> dict[str, Any]:
        return retry_on_transient(
            lambda: self._request_once(endpoint, params, retry_auth=retry_auth)
        )

    def _request_once(
        self, endpoint: str, params: dict[str, str], *, retry_auth: bool
    ) -> dict[str, Any]:
        self._limiter.wait()
        url = f"{API_BASE}/{endpoint}"
        try:
            response = self._session.get(
                url,
                params=params,
                headers=self._auth.get_auth_headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.HTTPError as exc:
            return self._handle_http_error(exc, endpoint, params, retry_auth=retry_auth)
        except requests.RequestException as exc:
            raise NetworkError(f"JSON API 网络错误 [{endpoint}]：{exc}") from exc
        except ValueError as exc:
            raise ParseError(f"JSON 解析失败 [{endpoint}]：{exc}") from exc
        return self._check_code(payload, endpoint)

    def _handle_http_error(
        self,
        error: requests.HTTPError,
        endpoint: str,
        params: dict[str, str],
        *,
        retry_auth: bool,
    ) -> dict[str, Any]:
        response = error.response
        status = response.status_code if response is not None else 0
        if status == 429:
            retry_after = parse_retry_after(response)
            logger.warning(
                "429 rate-limited on [%s], waiting %.1fs", endpoint, retry_after
            )
            time.sleep(retry_after)
            raise NetworkError(
                f"请求过于频繁 [{endpoint}]，已等待 {retry_after:.0f}s 后重试"
            ) from error
        if status == 401 and retry_auth:
            logger.info("Received 401, refreshing JWT and retrying once")
            self._auth.refresh_jwt()
            return self._request_once(endpoint, params, retry_auth=False)
        raise AuthError(f"JSON API 认证失败 [{endpoint}]：HTTP {status}") from error

    @staticmethod
    def _check_code(payload: dict[str, Any], endpoint: str) -> dict[str, Any]:
        code = payload.get("Code")
        if code != 0:
            raise APIError(
                f"API 返回错误 [{endpoint}]：Code={code}，{payload.get('Mess', '')}"
            )
        return payload

    def get_balance(self, meter_id: str) -> dict[str, Any]:
        payload = self.request("v3/XINTF/GetReserve", {"MeterID": meter_id})
        return payload.get("Data", {})

    def get_daily_usage(
        self, meter_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Query daily usage. Dates use the yyyy-M-d format, no leading zeros."""
        payload = self.request(
            "v3/XINTF/GetMeterDayValue",
            {"MeterID": meter_id, "startDate": start_date, "endDate": end_date},
        )
        values = payload.get("Data", {}).get("DayValues", [])
        return values if isinstance(values, list) else []

    def get_monthly_bill(
        self, meter_id: str, start_month: str, end_month: str
    ) -> list[dict[str, Any]]:
        """Query monthly bills. Months use the yyyyMM format."""
        payload = self.request(
            "v3/XINTF/GetMeterMonthValue",
            {"MeterID": meter_id, "startMonth": start_month, "endMonth": end_month},
        )
        values = payload.get("Data", {}).get("MonthValues", [])
        return values if isinstance(values, list) else []

    def get_recharge_history(self, meter_id: str) -> list[dict[str, Any]]:
        payload = self.request("v3/XINTF/GetMeterOrderHistory", {"MeterID": meter_id})
        values = payload.get("Data", {}).get("orderInfoList", [])
        return values if isinstance(values, list) else []

    def get_area_list(self) -> list[dict[str, Any]]:
        if self._area_cache is None:
            payload = self.request("v3/XINTF/GetAreaInfo", {})
            values = payload.get("Data", {}).get("areaInfoList", [])
            self._area_cache = values if isinstance(values, list) else []
        return self._area_cache

    def get_building_list(self, area_id: str) -> list[dict[str, Any]]:
        payload = self.request("v3/XINTF/GetArchitectureInfo", {"AreaID": area_id})
        values = payload.get("Data", {}).get("architectureInfoList", [])
        return values if isinstance(values, list) else []

    def get_room_list(self, building_id: str, floor: int) -> list[dict[str, Any]]:
        payload = self.request(
            "v3/XINTF/GetRoomInfo",
            {"ArchitectureID": building_id, "Floor": str(floor)},
        )
        values = payload.get("Data", {}).get("roomInfoList", [])
        return values if isinstance(values, list) else []

    def get_room_meter_info(self, room_id: str) -> dict[str, Any]:
        payload = self.request("v3/XINTF/GetRoomMeterInfo", {"RoomID": room_id})
        return payload.get("Data", {})
