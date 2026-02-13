"""Tests for alulapy exceptions."""

from alulapy.exceptions import (
    AlulaApiError,
    AlulaAuthError,
    AlulaConnectionError,
    AlulaError,
)


def test_exception_hierarchy() -> None:
    assert issubclass(AlulaAuthError, AlulaError)
    assert issubclass(AlulaApiError, AlulaError)
    assert issubclass(AlulaConnectionError, AlulaError)


def test_api_error_status_code() -> None:
    err = AlulaApiError("test error", status_code=6)
    assert err.status_code == 6
    assert str(err) == "test error"


def test_api_error_no_status_code() -> None:
    err = AlulaApiError("test error")
    assert err.status_code is None
