"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from slowlane.auth.jwt_auth import JWTAuth
from slowlane.core.config import SlowlaneConfig


@pytest.fixture(autouse=True)
def isolated_user_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ASC_KEY_TYPE",
        "ASC_KEY_ID",
        "ASC_ISSUER_ID",
        "ASC_PRIVATE_KEY",
        "ASC_PRIVATE_KEY_PATH",
        "SLOWLANE_JSON",
        "SLOWLANE_VERBOSE",
        "TRANSPORTER_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    for name in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))


@pytest.fixture
def mock_config() -> SlowlaneConfig:
    return SlowlaneConfig()


@pytest.fixture
def mock_jwt_auth() -> MagicMock:
    auth = MagicMock(spec=JWTAuth)
    auth.get_token.return_value = "mock.jwt.token"
    auth.key_type = "team"
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
