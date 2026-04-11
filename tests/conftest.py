"""Shared test fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from slowlane.auth.jwt_auth import JWTAuth
from slowlane.auth.session_auth import SessionAuth
from slowlane.core.config import SlowlaneConfig


@pytest.fixture
def mock_config() -> SlowlaneConfig:
    return SlowlaneConfig()


@pytest.fixture
def mock_jwt_auth() -> MagicMock:
    auth = MagicMock(spec=JWTAuth)
    auth.get_token.return_value = "mock.jwt.token"
    return auth


@pytest.fixture
def mock_session_auth() -> MagicMock:
    auth = MagicMock(spec=SessionAuth)
    auth.cookies = {"myacinfo": "abc123", "DSESSIONID": "xyz"}
    return auth


@pytest.fixture
def mock_http() -> MagicMock:
    """Reusable mock for AppleHTTPClient."""
    http = MagicMock()
    http.get_json.return_value = {}
    http.post_json.return_value = {}
    return http


@pytest.fixture
def asc_paginated_response() -> dict:
    """Single-page ASC paginated response."""
    return {"data": [], "links": {}}
