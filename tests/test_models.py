"""Tests for alulapy data models."""

from alulapy.const import ArmingState, DeviceType
from alulapy.models import Device, EventLogEntry, TokenInfo, User, Zone, ZoneStatus


def test_token_info_defaults() -> None:
    token = TokenInfo(access_token="abc", refresh_token="def")
    assert token.expires_in == 900
    assert token.token_type == "bearer"
    assert token.scope == ""


def test_user_from_api() -> None:
    data = {
        "id": "user-123",
        "attributes": {
            "dealerId": "dealer-1",
            "userType": "customer",
            "language": "es",
        },
    }
    user = User.from_api(data)
    assert user.id == "user-123"
    assert user.dealer_id == "dealer-1"
    assert user.user_type == "customer"
    assert user.language == "es"


def test_user_from_api_defaults() -> None:
    user = User.from_api({})
    assert user.id == ""
    assert user.dealer_id == ""
    assert user.language == "en"


def test_device_from_api_panel() -> None:
    data = {
        "id": "dev-1",
        "attributes": {
            "friendlyName": "Front Panel",
            "sn": "SN123",
            "mac": "AA:BB:CC",
            "isPanel": True,
            "timezone": "America/Denver",
            "onlineStatus": True,
            "armingLevel": "disarm",
            "anyTrouble": False,
            "acFailure": False,
            "lowBattery": True,
            "serverCommFail": False,
            "csCommFail": False,
            "lowBatteryZones": False,
            "tamperZones": False,
            "alarmZones": False,
            "troubleZones": False,
            "fireTrouble": False,
            "armingProtest": False,
        },
    }
    device = Device.from_api(data)
    assert device.id == "dev-1"
    assert device.name == "Front Panel"
    assert device.serial_number == "SN123"
    assert device.mac_address == "AA:BB:CC"
    assert device.device_type == DeviceType.PANEL
    assert device.is_panel is True
    assert device.is_camera is False
    assert device.online is True
    assert device.arming_state == ArmingState.DISARMED
    assert device.is_armed is False
    assert device.low_battery is True


def test_device_from_api_camera() -> None:
    data = {
        "id": "cam-1",
        "attributes": {
            "isCamera": True,
            "onlineStatus": False,
        },
    }
    device = Device.from_api(data)
    assert device.device_type == DeviceType.CAMERA
    assert device.is_camera is True
    assert device.is_panel is False


def test_device_arming_states() -> None:
    for arming_val, expected_armed in [
        ("armstay", True),
        ("armaway", True),
        ("armnight", True),
        ("disarm", False),
    ]:
        data = {
            "id": "dev-1",
            "attributes": {"isPanel": True, "armingLevel": arming_val},
        }
        device = Device.from_api(data)
        assert device.is_armed is expected_armed, f"Failed for {arming_val}"


def test_device_unknown_arming_state() -> None:
    data = {
        "id": "dev-1",
        "attributes": {"isPanel": True, "armingLevel": "bogus_value"},
    }
    device = Device.from_api(data)
    assert device.arming_state == ArmingState.UNKNOWN


def test_zone_from_api() -> None:
    data = {
        "id": "zone-1",
        "attributes": {
            "deviceId": "dev-1",
            "zoneIndex": 3,
            "zoneStatus": {"name": "open", "on": True},
            "pushEnabled": True,
            "pushOptions": {
                "bodyArgs": ["Front Door"],
                "data": {"deviceType": "door"},
            },
        },
    }
    zone = Zone.from_api(data)
    assert zone.id == "zone-1"
    assert zone.device_id == "dev-1"
    assert zone.zone_index == 3
    assert zone.is_open is True
    assert zone.push_enabled is True
    assert zone.zone_name == "Front Door"
    assert zone.device_type_hint == "door"


def test_zone_status_from_api() -> None:
    status = ZoneStatus.from_api({"name": "open", "on": True})
    assert status.name == "open"
    assert status.is_active is True


def test_zone_template_strings_filtered() -> None:
    data = {
        "id": "zone-2",
        "attributes": {
            "deviceId": "dev-1",
            "zoneIndex": 1,
            "zoneStatus": {},
            "pushOptions": {
                "bodyArgs": ["{zoneName}"],
                "data": {"deviceType": "{deviceType}"},
            },
        },
    }
    zone = Zone.from_api(data)
    assert zone.zone_name is None
    assert zone.device_type_hint is None


def test_event_log_entry_from_api() -> None:
    data = {
        "id": "evt-1",
        "attributes": {
            "deviceId": "dev-1",
            "dateEntered": "2024-01-15T10:00:00Z",
            "signalEventCode": "401",
            "signalEventQualifier": "1",
            "signalEventDescription": "Disarm",
            "signalPartition": "01",
            "signalUserZone": "001",
            "signalUserZoneType": "user",
            "signalUserZoneAlias": "Master Code",
        },
    }
    entry = EventLogEntry.from_api(data)
    assert entry.id == "evt-1"
    assert entry.event_code == "401"
    assert entry.is_arming_event is True
    assert entry.description == "Disarm"
    assert entry.user_zone_alias == "Master Code"


def test_event_log_non_arming() -> None:
    data = {
        "id": "evt-2",
        "attributes": {
            "signalEventCode": "130",
        },
    }
    entry = EventLogEntry.from_api(data)
    assert entry.is_arming_event is False
