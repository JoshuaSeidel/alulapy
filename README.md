# alulapy

Python client library for the Alula security platform API. Works with **Cove Smart**, **Alula Connect+**, and other Alula-powered alarm systems.

## Features

- **OAuth2 authentication** with automatic token refresh
- **Device info** — panel name, serial number, online status, firmware
- **Arming state** — real-time armed/disarmed/armed-stay/armed-away status
- **Zone sensors** — door, window, motion, smoke, water sensor open/closed states
- **Trouble flags** — AC failure, low battery, comm failure, tamper, and more
- **Event log** — recent arm/disarm/alarm events with filtering
- **Arm/Disarm** — via `helix.command` RPC (requires dealer to enable interactive services)

## Installation

```bash
pip install -e /path/to/alulapy
```

## Quick Start

```python
import asyncio
import aiohttp
from alulapy import AlulaClient

async def main():
    async with aiohttp.ClientSession() as session:
        client = AlulaClient(session)
        await client.async_login("your_username", "your_pin")

        devices = await client.async_get_devices()
        for device in devices:
            if device.is_panel:
                print(f"{device.name}: {device.arming_state}")
                print(f"  Online: {device.online}, Trouble: {device.any_trouble}")

        zones = await client.async_get_zones()
        for zone in zones:
            status = "OPEN" if zone.is_open else "closed"
            print(f"  Zone {zone.zone_index}: {zone.zone_name} — {status}")

asyncio.run(main())
```

## Arm/Disarm

Arm/disarm uses the `helix.command` RPC method. This requires `interactiveEnabled: true` on the device, which must be enabled by the alarm dealer (e.g., Cove support).

```python
await client.async_arm_stay(device.id)
await client.async_arm_away(device.id)
await client.async_disarm(device.id)
```

If you get "Permission Denied" (error code 6), contact your alarm provider and ask them to enable interactive services on your device.

## License

MIT
