"""Configuration management with TOML support."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli
import tomli_w

from .errors import ConfigError


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    if os.name == "nt":
        # Windows: use APPDATA
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        # macOS/Linux: use XDG or ~/.config
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "slowlane"


def get_data_dir() -> Path:
    """Get the data directory path for sessions and cache."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "slowlane"


@dataclass
class AuthConfig:
    """Authentication configuration."""

    default_mode: str = "jwt"  # "jwt" or "session"
    key_id: str | None = None
    issuer_id: str | None = None
    private_key_path: str | None = None


@dataclass
class HttpConfig:
    """HTTP client configuration."""

    timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 0.5


@dataclass
class OutputConfig:
    """Output configuration."""

    format: str = "text"  # "text" or "json"
    verbose: bool = False


@dataclass
class SlowlaneConfig:
    """Main configuration container."""

    auth: AuthConfig = field(default_factory=AuthConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    _path: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> SlowlaneConfig:
        """Load configuration from TOML file."""
        if path is None:
            path = get_config_dir() / "config.toml"

        config = cls(_path=path)

        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = tomli.load(f)
                config._apply_dict(data)
            except Exception as e:
                raise ConfigError(f"Failed to load config: {e}", path=str(path)) from e

        return config

    def _apply_dict(self, data: dict[str, Any]) -> None:
        """Apply dictionary values to config."""
        if "auth" in data:
            auth = data["auth"]
            self.auth.default_mode = auth.get("default_mode", self.auth.default_mode)
            self.auth.key_id = auth.get("key_id", self.auth.key_id)
            self.auth.issuer_id = auth.get("issuer_id", self.auth.issuer_id)
            self.auth.private_key_path = auth.get("private_key_path", self.auth.private_key_path)

        if "http" in data:
            http = data["http"]
            self.http.timeout = http.get("timeout", self.http.timeout)
            self.http.max_retries = http.get("max_retries", self.http.max_retries)
            self.http.backoff_factor = http.get("backoff_factor", self.http.backoff_factor)

        if "output" in data:
            output = data["output"]
            self.output.format = output.get("format", self.output.format)
            self.output.verbose = output.get("verbose", self.output.verbose)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary (excludes None values for TOML compatibility)."""
        def _filter_none(d: dict[str, Any]) -> dict[str, Any]:
            return {k: v for k, v in d.items() if v is not None}

        return {
            "auth": _filter_none({
                "default_mode": self.auth.default_mode,
                "key_id": self.auth.key_id,
                "issuer_id": self.auth.issuer_id,
                "private_key_path": self.auth.private_key_path,
            }),
            "http": {
                "timeout": self.http.timeout,
                "max_retries": self.http.max_retries,
                "backoff_factor": self.http.backoff_factor,
            },
            "output": {
                "format": self.output.format,
                "verbose": self.output.verbose,
            },
        }

    def save(self, path: Path | None = None) -> None:
        """Save configuration to TOML file."""
        path = path or self._path
        if path is None:
            path = get_config_dir() / "config.toml"

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                tomli_w.dump(self.to_dict(), f)
        except Exception as e:
            raise ConfigError(f"Failed to save config: {e}", path=str(path)) from e

    def apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # Auth overrides from env
        if key_id := os.environ.get("ASC_KEY_ID"):
            self.auth.key_id = key_id
        if issuer_id := os.environ.get("ASC_ISSUER_ID"):
            self.auth.issuer_id = issuer_id
        if private_key_path := os.environ.get("ASC_PRIVATE_KEY_PATH"):
            self.auth.private_key_path = private_key_path

        # Output overrides
        if os.environ.get("SLOWLANE_JSON", "").lower() in ("1", "true"):
            self.output.format = "json"
        if os.environ.get("SLOWLANE_VERBOSE", "").lower() in ("1", "true"):
            self.output.verbose = True
