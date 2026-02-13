"""alulapy — Python client library for the Alula security platform API.

Supports Cove Smart, Alula Connect+, and other Alula-powered alarm systems.

Usage:
    from alulapy import AlulaClient

    async with aiohttp.ClientSession() as session:
        client = AlulaClient(session)
        await client.async_login("username", "pin")
        devices = await client.async_get_devices()
        for device in devices:
            if device.is_panel:
                print(f"{device.name}: {device.arming_state}")
"""

from .client import AlulaClient
from .const import ArmingState
from .exceptions import AlulaApiError, AlulaAuthError, AlulaConnectionError
from .models import Device, EventLogEntry, User, Zone, ZoneStatus

__all__ = [
    "AlulaClient",
    "ArmingState",
    "AlulaAuthError",
    "AlulaApiError",
    "AlulaConnectionError",
    "Device",
    "Zone",
    "ZoneStatus",
    "EventLogEntry",
    "User",
]

__version__ = "0.1.0"
