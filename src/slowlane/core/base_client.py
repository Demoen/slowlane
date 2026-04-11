"""Shared base class for Apple API clients."""

from __future__ import annotations

from typing import Any, Self

from slowlane.core.config import SlowlaneConfig
from slowlane.core.http import AppleHTTPClient


class BaseAppleClient:
    def __init__(self, config: SlowlaneConfig | None = None) -> None:
        self._config = config or SlowlaneConfig.load()
        self._http = AppleHTTPClient(config=self._config.http)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
