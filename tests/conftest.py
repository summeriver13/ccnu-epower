"""Shared fixtures: a duck-typed stand-in for the network client."""

from __future__ import annotations

from typing import Any

import pytest

from epower.errors import NetworkError


class FakeAPI:
    def __init__(self) -> None:
        self.balance: dict[str, Any] = {}
        self.daily: list[dict[str, Any]] = []
        self.monthly: list[dict[str, Any]] = []
        self.orders: list[dict[str, Any]] = []
        self.areas: list[dict[str, Any]] = []
        self.buildings: list[dict[str, Any]] = []
        self.rooms: list[dict[str, Any]] = []
        self.room_meter: dict[str, Any] = {"meterList": []}
        self.fail_on: set[str] = set()
        self.calls: list[str] = []

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if name in self.fail_on:
            raise NetworkError(f"{name} failed")

    def get_balance(self, meter_id: str) -> dict[str, Any]:
        self._record("balance")
        return self.balance

    def get_daily_usage(
        self, meter_id: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        self._record("daily")
        return self.daily

    def get_monthly_bill(
        self, meter_id: str, start_month: str, end_month: str
    ) -> list[dict[str, Any]]:
        self._record("monthly")
        return self.monthly

    def get_recharge_history(self, meter_id: str) -> list[dict[str, Any]]:
        self._record("orders")
        return self.orders

    def get_area_list(self) -> list[dict[str, Any]]:
        self._record("areas")
        return self.areas

    def get_building_list(self, area_id: str) -> list[dict[str, Any]]:
        self._record("buildings")
        return self.buildings

    def get_room_list(self, building_id: str, floor: int) -> list[dict[str, Any]]:
        self._record("rooms")
        return self.rooms

    def get_room_meter_info(self, room_id: str) -> dict[str, Any]:
        self._record("meter")
        return self.room_meter


@pytest.fixture()
def api() -> FakeAPI:
    return FakeAPI()
