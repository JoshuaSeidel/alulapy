"""Exceptions for the alulapy library."""


class AlulaError(Exception):
    """Base exception for alulapy."""


class AlulaAuthError(AlulaError):
    """Raised when authentication fails (bad credentials, expired refresh token)."""


class AlulaApiError(AlulaError):
    """Raised when an API call returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AlulaConnectionError(AlulaError):
    """Raised when unable to connect to the Alula API."""
