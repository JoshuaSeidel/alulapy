"""Data models for the alulapy library."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import ArmingState, DeviceType


@dataclass
class TokenInfo:
    """OAuth2 token information."""

    access_token: str
    refresh_token: str
    expires_in: int = 900
    token_type: str = "bearer"
    scope: str = ""


@dataclass
class User:
    """An Alula user account."""

    id: str
    dealer_id: str
    user_type: str
    language: str = "en"
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> User:
        """Create from API response data."""
        attrs = data.get("attributes", {})
        return cls(
            id=data.get("id", ""),
            dealer_id=attrs.get("dealerId", ""),
            user_type=attrs.get("userType", ""),
            language=attrs.get("language", "en"),
            raw=data,
        )


@dataclass
class Device:
    """An Alula device (panel or camera)."""

    id: str
    name: str
    serial_number: str
    mac_address: str | None
    device_type: DeviceType
    connected_panel_type: str | None
    timezone: str
    online: bool
    online_timestamp: str | None

    # Arming (panels only)
    arming_state: ArmingState
    last_armed_at: str | None
    last_disarmed_at: str | None

    # Trouble flags
    any_trouble: bool
    ac_failure: bool
    low_battery: bool
    server_comm_fail: bool
    cs_comm_fail: bool
    low_battery_zones: bool
    tamper_zones: bool
    alarm_zones: bool
    trouble_zones: bool
    fire_trouble: bool
    arming_protest: bool

    # Features
    features: dict[str, bool] = field(default_factory=dict)

    # Full raw response for anything we haven't modeled
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_panel(self) -> bool:
        """Return True if this device is an alarm panel."""
        return self.device_type == DeviceType.PANEL

    @property
    def is_camera(self) -> bool:
        """Return True if this device is a camera."""
        return self.device_type == DeviceType.CAMERA

    @property
    def is_armed(self) -> bool:
        """Return True if the panel is armed in any mode."""
        return self.arming_state in (
            ArmingState.ARMED_STAY,
            ArmingState.ARMED_AWAY,
            ArmingState.ARMED_NIGHT,
        )

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Device:
        """Create from API response data."""
        attrs = data.get("attributes", {})

        # Determine device type
        if attrs.get("isPanel"):
            device_type = DeviceType.PANEL
        elif attrs.get("isCamera"):
            device_type = DeviceType.CAMERA
        else:
            device_type = DeviceType.UNKNOWN

        # Parse arming state
        raw_arming = attrs.get("armingLevel")
        try:
            arming_state = ArmingState(raw_arming) if raw_arming else ArmingState.UNKNOWN
        except ValueError:
            arming_state = ArmingState.UNKNOWN

        return cls(
            id=data.get("id", ""),
            name=attrs.get("friendlyName", "Unknown Device"),
            serial_number=attrs.get("sn", ""),
            mac_address=attrs.get("mac"),
            device_type=device_type,
            connected_panel_type=attrs.get("connectedPanel"),
            timezone=attrs.get("timezone", "UTC"),
            online=attrs.get("onlineStatus", False),
            online_timestamp=attrs.get("onlineStatusTimestamp"),
            arming_state=arming_state,
            last_armed_at=attrs.get("lastArmedAt"),
            last_disarmed_at=attrs.get("lastDisarmedAt"),
            any_trouble=attrs.get("anyTrouble", False),
            ac_failure=attrs.get("acFailure", False),
            low_battery=attrs.get("lowBattery", False),
            server_comm_fail=attrs.get("serverCommFail", False),
            cs_comm_fail=attrs.get("csCommFail", False),
            low_battery_zones=attrs.get("lowBatteryZones", False),
            tamper_zones=attrs.get("tamperZones", False),
            alarm_zones=attrs.get("alarmZones", False),
            trouble_zones=attrs.get("troubleZones", False),
            fire_trouble=attrs.get("fireTrouble", False),
            arming_protest=attrs.get("armingProtest", False),
            features=attrs.get("featuresSelected", {}),
            raw=data,
        )


@dataclass
class ZoneStatus:
    """Status of a zone sensor."""

    name: str  # e.g., "open"
    is_active: bool  # True = open/triggered

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ZoneStatus:
        return cls(
            name=data.get("name", "unknown"),
            is_active=data.get("on", False),
        )


@dataclass
class Zone:
    """A zone sensor (door, window, motion, etc.)."""

    id: str
    device_id: str
    zone_index: int
    status: ZoneStatus
    push_enabled: bool
    zone_name: str | None
    device_type_hint: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_open(self) -> bool:
        """Return True if the zone is open / triggered."""
        return self.status.is_active

    @classmethod
    def from_api(cls, data: dict[str, Any], device_id: str | None = None) -> Zone:
        """Create from API response data.

        Handles both the device zones endpoint format (direct zoneName /
        zoneType attributes) and the notification zones endpoint format
        (names embedded in pushOptions).

        Args:
            data: Raw JSON:API resource dict.
            device_id: Fallback device ID when the attribute is absent
                       (e.g. when fetched via a device relationship URL).
        """
        attrs = data.get("attributes", {})

        # ── Zone name ────────────────────────────────────────────────
        # Prefer direct attribute, fall back to notification template.
        zone_name: str | None = attrs.get("zoneName") or attrs.get("friendlyName")
        if not zone_name:
            push_opts = attrs.get("pushOptions", {})
            body_args = push_opts.get("bodyArgs", [])
            if body_args:
                candidate = body_args[0]
                if not candidate.startswith("{"):
                    zone_name = candidate

        # ── Device type hint ─────────────────────────────────────────
        device_type_hint: str | None = (
            attrs.get("zoneType") or attrs.get("deviceType")
        )
        if not device_type_hint:
            push_opts = attrs.get("pushOptions", {})
            push_data = push_opts.get("data", {})
            device_type_hint = push_data.get("deviceType")
        if isinstance(device_type_hint, str) and device_type_hint.startswith("{"):
            device_type_hint = None

        return cls(
            id=data.get("id", ""),
            device_id=attrs.get("deviceId", "") or device_id or "",
            zone_index=attrs.get("zoneIndex", 0),
            status=ZoneStatus.from_api(attrs.get("zoneStatus", {})),
            push_enabled=attrs.get("pushEnabled", False),
            zone_name=zone_name,
            device_type_hint=device_type_hint,
            raw=data,
        )


@dataclass
class EventLogEntry:
    """An entry from the device event log."""

    id: str
    device_id: str
    timestamp: str
    event_code: str
    event_qualifier: str
    description: str
    partition: str
    user_zone: str
    user_zone_type: str
    user_zone_alias: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_arming_event(self) -> bool:
        """Return True if this is an arm/disarm event."""
        return self.event_code in ("400", "401", "441", "403")

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> EventLogEntry:
        """Create from API response data."""
        attrs = data.get("attributes", {})
        return cls(
            id=data.get("id", ""),
            device_id=attrs.get("deviceId", ""),
            timestamp=attrs.get("dateEntered", ""),
            event_code=attrs.get("signalEventCode", ""),
            event_qualifier=attrs.get("signalEventQualifier", ""),
            description=attrs.get("signalEventDescription", ""),
            partition=attrs.get("signalPartition", ""),
            user_zone=attrs.get("signalUserZone", ""),
            user_zone_type=attrs.get("signalUserZoneType", ""),
            user_zone_alias=attrs.get("signalUserZoneAlias"),
            raw=data,
        )
