"""Constants for the alulapy library."""

from enum import StrEnum

# Alula API base URL
API_BASE_URL = "https://api.alula.net"
OAUTH_TOKEN_URL = f"{API_BASE_URL}/oauth/token"

# Cove Connect iOS app OAuth2 client credentials (extracted from app binary).
# These are *app-level* credentials, not user secrets.
COVE_CLIENT_ID = "30d6c020-8b9d-11ed-a23f-9d00c9041c6e"
COVE_CLIENT_SECRET = (
    "a867fb60cbe5803a54bc2bd03b30031c30bc8088d11de59daa36669661d7b2bb"
)

# Token lifetime
TOKEN_EXPIRES_IN_DEFAULT = 900  # 15 minutes
TOKEN_REFRESH_BUFFER = 180  # refresh 3 minutes before expiry

# Rate limiting (from observed headers)
RATE_LIMIT_REQUESTS = 30  # per window
RATE_LIMIT_WINDOW = 60  # seconds

# Default pagination
DEFAULT_PAGE_SIZE = 200

# User agent
USER_AGENT = "alulapy/0.1.0"


class ArmingState(StrEnum):
    """Alarm panel arming states as returned by the Alula API."""

    DISARMED = "disarm"
    ARMED_STAY = "armstay"
    ARMED_AWAY = "armaway"
    ARMED_NIGHT = "armnight"
    UNKNOWN = "unknown"


class DeviceType(StrEnum):
    """Device types."""

    PANEL = "panel"
    CAMERA = "camera"
    UNKNOWN = "unknown"
