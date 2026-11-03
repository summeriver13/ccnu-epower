"""Resolve a room name to its meter ID through the campus hierarchy API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Sequence

from .client import NewAPI
from .config import Target
from .errors import NotFoundError

logger = logging.getLogger("ccnu_epower")

BUILDING_KEY = "ArchitectureName"
ROOM_KEY = "RoomName"


@dataclass(frozen=True)
class RoomLocation:
    meter_id: str
    area_name: str
    area_id: str
    building_name: str
    floor: int
    room_name: str
    room_id: str


def resolve_room(api: NewAPI, target: Target) -> RoomLocation:
    """Find the meter bound to a room.

    Matching is by substring, so partial names such as the building short
    name are accepted. Ambiguous matches raise NotFoundError.

    Raises:
        NotFoundError: When a building, room, or meter binding is missing.
    """
    area_name = _area_name(api, target.area_id)
    buildings = api.get_building_list(target.area_id)
    building = _select_unique(
        buildings,
        BUILDING_KEY,
        target.building_name,
        scope=f"在 {area_name} 中",
        label="建筑",
    )
    building_id = building["ArchitectureID"]
    building_name = building[BUILDING_KEY]
    logger.info("Matched building: %s (ID: %s)", building_name, building_id)

    rooms = api.get_room_list(building_id, target.floor)
    room = _select_unique(
        rooms,
        ROOM_KEY,
        target.room_name,
        scope=f"在 {building_name} 第 {target.floor} 层中",
        label="房间",
    )
    room_id = room["RoomNo"]
    room_name = room[ROOM_KEY]
    logger.info("Matched room: %s (ID: %s)", room_name, room_id)

    meter_id = _meter_id(api, room_name, room_id)
    return RoomLocation(
        meter_id=meter_id,
        area_name=area_name,
        area_id=target.area_id,
        building_name=building_name,
        floor=target.floor,
        room_name=room_name,
        room_id=room_id,
    )


def _area_name(api: NewAPI, area_id: str) -> str:
    for area in api.get_area_list():
        if area.get("AreaID") == area_id:
            return str(area.get("AreaName", area_id))
    return area_id


def _select_unique(
    items: Sequence[dict[str, Any]],
    key: str,
    needle: str,
    *,
    scope: str,
    label: str,
) -> dict[str, Any]:
    matched = [item for item in items if needle in str(item.get(key, ""))]
    if not matched:
        available = [item.get(key, "?") for item in items]
        raise NotFoundError(
            f"{scope}未找到匹配 '{needle}' 的{label}。可用：{available}"
        )
    if len(matched) > 1:
        names = [item.get(key, "?") for item in matched]
        raise NotFoundError(
            f"'{needle}' 匹配到多个{label}：{names}，请使用更精确的名称"
        )
    return matched[0]


def _meter_id(api: NewAPI, room_name: str, room_id: str) -> str:
    meter_info = api.get_room_meter_info(room_id)
    meters = meter_info.get("meterList", [])
    if not meters:
        raise NotFoundError(
            f"房间 {room_name} (ID: {room_id}) 未绑定电表，"
            f"请先在浏览器中绑定房间后再试。"
        )
    meter_id = str(meters[0].get("meterId", ""))
    if not meter_id:
        raise NotFoundError(f"房间 {room_name} 的电表 ID 为空")
    logger.info("Meter ID: %s", meter_id)
    return meter_id
