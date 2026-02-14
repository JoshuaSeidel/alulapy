"""Alula API client."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    COVE_CLIENT_ID,
    COVE_CLIENT_SECRET,
    DEFAULT_PAGE_SIZE,
    TOKEN_EXPIRES_IN_DEFAULT,
    TOKEN_REFRESH_BUFFER,
    USER_AGENT,
)
from .exceptions import AlulaApiError, AlulaAuthError, AlulaConnectionError
from .models import Device, EventLogEntry, TokenInfo, User, Zone

_LOGGER = logging.getLogger(__name__)


class AlulaClient:
    """Async client for the Alula security platform API.

    Usage:
        async with aiohttp.ClientSession() as session:
            client = AlulaClient(session)
            await client.async_login("username", "pin")
            devices = await client.async_get_devices()
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        client_id: str = COVE_CLIENT_ID,
        client_secret: str = COVE_CLIENT_SECRET,
        base_url: str = API_BASE_URL,
    ) -> None:
        """Initialize the client.

        Args:
            session: aiohttp client session (caller manages lifecycle).
            client_id: OAuth2 client ID (defaults to Cove Connect app).
            client_secret: OAuth2 client secret (defaults to Cove Connect app).
            base_url: API base URL.
        """
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url
        self._oauth_url = f"{base_url}/oauth/token"

        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0.0
        self._token_lock = asyncio.Lock()

        # Cached user info
        self._user_id: str | None = None

    # ── Public properties ────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """Return True if we have a valid (non-expired) access token."""
        return (
            self._access_token is not None
            and time.time() < self._token_expiry - TOKEN_REFRESH_BUFFER
        )

    @property
    def access_token(self) -> str | None:
        """Current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Current refresh token (persist this for re-auth without password)."""
        return self._refresh_token

    @property
    def token_expiry(self) -> float:
        """Unix timestamp when the current access token expires."""
        return self._token_expiry

    # ── Authentication ───────────────────────────────────────────────

    async def async_login(self, username: str, password: str) -> TokenInfo:
        """Authenticate with username and password/PIN.

        Args:
            username: Cove/Alula username (e.g., "c445792").
            password: Panel PIN or account password (e.g., "17327").

        Returns:
            TokenInfo with access and refresh tokens.

        Raises:
            AlulaAuthError: If credentials are invalid.
            AlulaConnectionError: If unable to reach the API.
        """
        return await self._token_request(
            grant_type="password",
            username=username,
            password=password,
        )

    async def async_refresh(self, refresh_token: str | None = None) -> TokenInfo:
        """Refresh the access token.

        Args:
            refresh_token: Explicit refresh token. If None, uses the stored one.

        Returns:
            TokenInfo with new access and refresh tokens.

        Raises:
            AlulaAuthError: If the refresh token is invalid/expired.
        """
        token = refresh_token or self._refresh_token
        if not token:
            raise AlulaAuthError("No refresh token available")
        return await self._token_request(
            grant_type="refresh_token",
            refresh_token=token,
        )

    def restore_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int = TOKEN_EXPIRES_IN_DEFAULT,
    ) -> None:
        """Restore tokens from persistent storage (e.g., HA config entry).

        Args:
            access_token: Previously stored access token.
            refresh_token: Previously stored refresh token.
            expires_in: Seconds until the access token was set to expire.
        """
        self._access_token = access_token
        self._refresh_token = refresh_token
        # Be conservative — assume it's already partially expired
        self._token_expiry = time.time() + min(expires_in, 300)

    async def _token_request(self, **kwargs: str) -> TokenInfo:
        """Execute an OAuth2 token request."""
        data = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            **kwargs,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

        try:
            async with self._session.post(
                self._oauth_url, data=data, headers=headers
            ) as resp:
                body = await resp.json()
                if resp.status == 401:
                    raise AlulaAuthError(
                        body.get("error_description", "Invalid credentials")
                    )
                if resp.status == 400:
                    raise AlulaAuthError(
                        body.get("error_description", f"Auth error: {body}")
                    )
                resp.raise_for_status()
        except aiohttp.ClientError as err:
            raise AlulaConnectionError(f"Connection error during auth: {err}") from err

        token_info = TokenInfo(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_in=body.get("expires_in", TOKEN_EXPIRES_IN_DEFAULT),
            token_type=body.get("token_type", "bearer"),
            scope=body.get("scope", ""),
        )

        self._access_token = token_info.access_token
        self._refresh_token = token_info.refresh_token
        self._token_expiry = time.time() + token_info.expires_in

        _LOGGER.debug("Token acquired, expires in %ds", token_info.expires_in)
        return token_info

    async def _ensure_token(self) -> None:
        """Ensure we have a valid access token, refreshing if needed."""
        async with self._token_lock:
            if self.is_authenticated:
                return
            if self._refresh_token:
                _LOGGER.debug("Access token expired, refreshing")
                await self.async_refresh()
            else:
                raise AlulaAuthError(
                    "Access token expired and no refresh token available. "
                    "Call async_login() first."
                )

    # ── HTTP helpers ─────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request with automatic token refresh."""
        await self._ensure_token()
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if json_data is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with self._session.request(
                method, url, headers=headers, json=json_data, params=params
            ) as resp:
                if resp.status == 401:
                    _LOGGER.debug("Got 401, attempting token refresh and retry")
                    await self.async_refresh()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with self._session.request(
                        method, url, headers=headers, json=json_data, params=params
                    ) as retry:
                        if retry.status == 401:
                            raise AlulaAuthError("Authentication failed after refresh")
                        retry.raise_for_status()
                        result: dict[str, Any] = await retry.json()
                        return result
                resp.raise_for_status()
                result = await resp.json()
                return result
        except AlulaAuthError:
            raise
        except aiohttp.ClientError as err:
            raise AlulaConnectionError(
                f"Connection error: {method} {path}: {err}"
            ) from err

    async def _rpc(
        self,
        rpc_method: str,
        params: dict[str, Any] | None = None,
        *,
        path: str = "/rpc/v1",
    ) -> dict[str, Any]:
        """Make a JSON-RPC request.

        Args:
            rpc_method: The RPC method name (e.g., "events.notifications.renew").
            params: Method parameters.
            path: RPC endpoint path.

        Returns:
            The "result" field from the JSON-RPC response.
        """
        payload = {
            "id": str(uuid.uuid4()).upper(),
            "method": rpc_method,
            "params": params or {},
        }
        result = await self._request("POST", path, json_data=payload)
        if "error" in result:
            err = result["error"]
            raise AlulaApiError(
                f"RPC error ({rpc_method}): {err}",
                status_code=err.get("code"),
            )
        rpc_result: dict[str, Any] = result.get("result", {})
        return rpc_result

    # ── User ─────────────────────────────────────────────────────────

    async def async_get_user(self) -> User:
        """Get the current authenticated user."""
        result = await self._request(
            "GET", "/api/v1/self",
            params={"customOptions[omitRelationships]": "true"},
        )
        user = User.from_api(result.get("data", {}))
        self._user_id = user.id
        return user

    # ── Devices ──────────────────────────────────────────────────────

    async def async_get_devices(self) -> list[Device]:
        """Get all devices (panels and cameras) on the account.

        Returns:
            List of Device objects.
        """
        result = await self._request(
            "GET", "/api/v1/devices",
            params={
                "customOptions[omitRelationships]": "true",
                "page[size]": str(DEFAULT_PAGE_SIZE),
            },
        )
        return [Device.from_api(d) for d in result.get("data", [])]

    async def async_get_panels(self) -> list[Device]:
        """Get only panel devices."""
        devices = await self.async_get_devices()
        return [d for d in devices if d.is_panel]

    async def async_get_cameras(self) -> list[Device]:
        """Get only camera devices."""
        devices = await self.async_get_devices()
        return [d for d in devices if d.is_camera]

    # ── Zones ────────────────────────────────────────────────────────

    async def async_get_zones(self) -> list[Zone]:
        """Get zone notification subscriptions.

        NOTE: This endpoint only returns zones that have push notification
        subscriptions.  Use async_discover_zones() + async_ensure_zone_subscriptions()
        to discover and subscribe all zones first.

        Returns:
            List of Zone objects for subscribed zones.
        """
        result = await self._request(
            "GET", "/api/v1/events/notifications/zones",
            params={"page[size]": str(DEFAULT_PAGE_SIZE), "sort": "id"},
        )
        return [Zone.from_api(z) for z in result.get("data", [])]

    # ── Event Log ────────────────────────────────────────────────────

    async def async_get_event_log(
        self,
        device_id: str,
        *,
        limit: int = 10,
        since: str | None = None,
    ) -> list[EventLogEntry]:
        """Get recent event log entries for a device.

        Args:
            device_id: The device UUID.
            limit: Max number of entries to return.
            since: ISO 8601 timestamp to filter events after this time.

        Returns:
            List of EventLogEntry objects, newest first.
        """
        params: dict[str, str] = {
            "customOptions[omitRelationships]": "true",
            "page[size]": str(limit),
            "sort": "-dateEntered",
        }
        if since:
            params["filter[dateEntered][$gt]"] = since

        result = await self._request(
            "GET", f"/api/v1/devices/{device_id}/eventlog",
            params=params,
        )
        return [EventLogEntry.from_api(e) for e in result.get("data", [])]

    # ── Zone Discovery & Subscriptions ────────────────────────────────

    async def async_discover_zones(
        self, device_id: str
    ) -> dict[int, dict[str, str | None]]:
        """Discover zones by scanning the device event log.

        The Alula API has no standalone zones endpoint. Zone information
        (names, types) is only available in event log entries.

        Args:
            device_id: The panel device UUID.

        Returns:
            Dict mapping zone_index -> {"zone_name": str|None, "zone_type": str}.
        """
        result = await self._request(
            "GET",
            f"/api/v1/devices/{device_id}/eventlog",
            params={
                "customOptions[omitRelationships]": "true",
                "page[size]": "500",
                "sort": "-dateEntered",
            },
        )
        zones: dict[int, dict[str, str | None]] = {}
        for entry in result.get("data", []):
            attrs = entry.get("attributes", {})
            zone_str = attrs.get("signalUserZone", "")
            if not zone_str or not zone_str.isdigit():
                continue
            zone_idx = int(zone_str)
            if zone_idx == 0 or zone_idx in zones:
                continue
            zones[zone_idx] = {
                "zone_name": attrs.get("signalUserZoneAlias"),
                "zone_type": attrs.get("signalUserZoneType", ""),
            }
        _LOGGER.debug(
            "Discovered %d zones from event log for device %s", len(zones), device_id
        )
        return zones

    async def async_ensure_zone_subscriptions(
        self, device_id: str, zone_indices: list[int]
    ) -> int:
        """Create notification subscriptions for zones that don't already have them.

        Each zone needs two subscriptions: one for on=True (opened) and one
        for on=False (closed). The payload requires BOTH the nested
        ``zoneStatus`` object and the flat ``zoneStatusName``/``zoneStatusOn``
        fields.

        Args:
            device_id: The panel device UUID.
            zone_indices: List of zone index numbers to subscribe.

        Returns:
            Number of new subscriptions created.
        """
        existing = await self.async_get_zones()
        existing_keys: set[tuple[str, int, bool]] = {
            (z.device_id, z.zone_index, z.status.is_active) for z in existing
        }

        created = 0
        for zone_idx in zone_indices:
            for status_on in (True, False):
                if (device_id, zone_idx, status_on) in existing_keys:
                    continue
                payload = {
                    "data": {
                        "type": "events-notifications-zones",
                        "attributes": {
                            "deviceId": device_id,
                            "zoneIndex": zone_idx,
                            "zoneStatus": {"name": "open", "on": status_on},
                            "zoneStatusName": "open",
                            "zoneStatusOn": status_on,
                            "pushEnabled": True,
                            "pushOptions": {
                                "titleKey": "APP_NAME",
                                "bodyKey": (
                                    "OPEN_ACTIVE" if status_on else "OPEN_INACTIVE"
                                ),
                                "bodyArgs": [
                                    f"{{zoneConfiguration.{zone_idx}.zoneName:}}"
                                ],
                                "data": {
                                    "deviceId": device_id,
                                    "zoneIndex": zone_idx,
                                    "deviceType": (
                                        f"{{zoneConfiguration.{zone_idx}.deviceType}}"
                                    ),
                                },
                            },
                        },
                    }
                }
                try:
                    await self._request(
                        "POST",
                        "/api/v1/events/notifications/zones",
                        json_data=payload,
                    )
                    created += 1
                    _LOGGER.debug(
                        "Created zone subscription: zone %d (on=%s)",
                        zone_idx,
                        status_on,
                    )
                except Exception as err:  # noqa: BLE001
                    # 403 = already exists (unique constraint), which is fine
                    _LOGGER.debug(
                        "Zone subscription skipped: zone %d (on=%s): %s",
                        zone_idx,
                        status_on,
                        err,
                    )
        return created

    # ── Notifications ────────────────────────────────────────────────

    async def async_renew_notifications(self, ttl: int = 2419200) -> bool:
        """Renew push notification subscriptions.

        Args:
            ttl: Time-to-live in seconds (default 28 days).

        Returns:
            True if successful.
        """
        result = await self._rpc("events.notifications.renew", {"ttl": ttl})
        success: bool = result.get("success", False)
        return success

    # ── Arm / Disarm ─────────────────────────────────────────────────
    # Uses helix.command RPC. Requires interactiveEnabled=True on the
    # device, which must be enabled by the dealer (e.g., Cove support).
    # If you get "Permission Denied", call your alarm provider and ask
    # them to enable interactive services on your device.

    async def async_arm_stay(self, device_id: str) -> dict[str, Any]:
        """Arm the panel in Stay mode.

        Args:
            device_id: The panel device UUID.

        Returns:
            RPC result dict.

        Raises:
            AlulaApiError: If the command fails (code 6 = interactiveEnabled is off).
        """
        return await self._helix_command(device_id, "armStay")

    async def async_arm_away(self, device_id: str) -> dict[str, Any]:
        """Arm the panel in Away mode.

        Args:
            device_id: The panel device UUID.

        Returns:
            RPC result dict.

        Raises:
            AlulaApiError: If the command fails.
        """
        return await self._helix_command(device_id, "armAway")

    async def async_arm_night(self, device_id: str) -> dict[str, Any]:
        """Arm the panel in Night mode.

        Args:
            device_id: The panel device UUID.

        Returns:
            RPC result dict.

        Raises:
            AlulaApiError: If the command fails.
        """
        return await self._helix_command(device_id, "armNight")

    async def async_disarm(self, device_id: str) -> dict[str, Any]:
        """Disarm the panel.

        Args:
            device_id: The panel device UUID.

        Returns:
            RPC result dict.

        Raises:
            AlulaApiError: If the command fails.
        """
        return await self._helix_command(device_id, "disarm")

    async def _helix_command(self, device_id: str, data: str) -> dict[str, Any]:
        """Send a helix.command RPC call.

        Args:
            device_id: The panel device UUID.
            data: Command string ("armStay", "armAway", "disarm").

        Raises:
            AlulaApiError: With a helpful message when interactiveEnabled is off.
        """
        try:
            return await self._rpc(
                "helix.command",
                {"deviceId": device_id, "data": data},
            )
        except AlulaApiError as err:
            if err.status_code == 6:
                raise AlulaApiError(
                    f"Arm/disarm command denied: interactiveEnabled is off "
                    f"on device {device_id}. Contact your alarm provider "
                    f"(e.g., Cove support) and ask them to enable interactive "
                    f"services on your device.",
                    status_code=6,
                ) from err
            raise
