import pytest

from epower.config import Target
from epower.errors import NotFoundError
from epower.room import resolve_room


def populate(api):
    api.areas = [{"AreaID": "0004", "AreaName": "Campus"}]
    api.buildings = [{"ArchitectureID": "B1", "ArchitectureName": "Dorm 04"}]
    api.rooms = [{"RoomNo": "21943", "RoomName": "N4-316"}]
    api.room_meter = {"meterList": [{"meterId": "1000.000000.1"}]}
    return api


def target(**overrides):
    values = {
        "area_id": "0004",
        "building_name": "Dorm",
        "floor": 3,
        "room_name": "316",
    }
    values.update(overrides)
    return Target(**values)


def test_resolve_room_returns_location(api):
    location = resolve_room(populate(api), target())
    assert location.meter_id == "1000.000000.1"
    assert location.area_name == "Campus"
    assert location.room_id == "21943"
    assert location.building_name == "Dorm 04"


def test_missing_building_lists_candidates(api):
    with pytest.raises(NotFoundError) as excinfo:
        resolve_room(populate(api), target(building_name="Nonexistent"))
    assert "Dorm 04" in str(excinfo.value)


def test_ambiguous_building_is_rejected(api):
    populate(api)
    api.buildings.append({"ArchitectureID": "B2", "ArchitectureName": "Dorm 05"})
    with pytest.raises(NotFoundError):
        resolve_room(api, target(building_name="Dorm"))


def test_unbound_room_is_rejected(api):
    populate(api)
    api.room_meter = {"meterList": []}
    with pytest.raises(NotFoundError):
        resolve_room(api, target())
