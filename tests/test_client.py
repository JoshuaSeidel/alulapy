"""Tests for alulapy client."""

import time
from unittest.mock import MagicMock

import pytest

from alulapy.client import AlulaClient
from alulapy.const import TOKEN_REFRESH_BUFFER
from alulapy.exceptions import AlulaAuthError


def _make_client() -> AlulaClient:
    session = MagicMock()
    return AlulaClient(session)


def test_client_defaults() -> None:
    client = _make_client()
    assert client.access_token is None
    assert client.refresh_token is None
    assert client.is_authenticated is False


def test_restore_tokens() -> None:
    client = _make_client()
    client.restore_tokens("access", "refresh", expires_in=600)
    assert client.access_token == "access"
    assert client.refresh_token == "refresh"
    assert client.is_authenticated is True


def test_restore_tokens_caps_expiry() -> None:
    client = _make_client()
    client.restore_tokens("access", "refresh", expires_in=9999)
    # Should cap to 300s, so expiry is at most time.time() + 300
    assert client.token_expiry <= time.time() + 301


def test_is_authenticated_expired() -> None:
    client = _make_client()
    client._access_token = "token"
    client._token_expiry = time.time() + TOKEN_REFRESH_BUFFER - 1
    assert client.is_authenticated is False


@pytest.mark.asyncio
async def test_async_refresh_no_token() -> None:
    client = _make_client()
    with pytest.raises(AlulaAuthError, match="No refresh token"):
        await client.async_refresh()
