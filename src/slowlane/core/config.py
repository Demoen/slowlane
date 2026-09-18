"""Configuration management with TOML support."""

from __future__ import annotations

import math
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

    key_type: str = "team"
    key_id: str | None = None
    issuer_id: str | None = None
    private_key_path: str | None = None


@dataclass
class HttpConfig:
    """HTTP client configuration."""

    timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 0.5

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if type(self.timeout) is not int or self.timeout <= 0:
            raise ConfigError("http.timeout must be a positive integer")
        if type(self.max_retries) is not int or self.max_retries < 0:
            raise ConfigError("http.max_retries must be a non-negative integer")
        if (
            isinstance(self.backoff_factor, bool)
            or not isinstance(self.backoff_factor, int | float)
            or not math.isfinite(self.backoff_factor)
            or self.backoff_factor < 0
        ):
            raise ConfigError("http.backoff_factor must be a finite non-negative number")


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
        explicit_path = path is not None
        if path is None:
            path = get_config_dir() / "config.toml"

        config = cls(_path=path)

        if explicit_path and not path.exists():
            raise ConfigError("Configuration file does not exist", path=str(path))

        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = tomllib.load(f)
                config._apply_dict(data)
                config.validate()
            except Exception as e:
                raise ConfigError(f"Failed to load config: {e}", path=str(path)) from e

        return config

    def _apply_dict(self, data: dict[str, Any]) -> None:
        """Apply dictionary values to config."""
        if "devportal" in data:
            raise ConfigError(
                "[devportal] is no longer supported; use a team API key for signing. See the migration guide."
            )
        sections: dict[str, AuthConfig | HttpConfig | OutputConfig] = {
            "auth": self.auth,
            "http": self.http,
            "output": self.output,
        }
        for name, values in data.items():
            if name not in sections:
                raise ConfigError(f"Unknown configuration section: {name}")
            if not isinstance(values, dict):
                raise ConfigError(f"{name} must be a TOML table")
            for key in values:
                if name == "auth" and key == "default_mode":
                    raise ConfigError(
                        "auth.default_mode has been removed; use auth.key_type = 'team' or 'individual'. See the migration guide."
                    )
                if key not in sections[name].__dataclass_fields__:
                    raise ConfigError(f"Unknown configuration option: {name}.{key}")
        if "auth" in data:
            auth = data["auth"]
            self.auth.key_type = auth.get("key_type", self.auth.key_type)
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
            "auth": _filter_none(
                {
                    "key_type": self.auth.key_type,
                    "key_id": self.auth.key_id,
                    "issuer_id": self.auth.issuer_id,
                    "private_key_path": self.auth.private_key_path,
                }
            ),
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

    def validate(self) -> None:
        if self.auth.key_type not in ("team", "individual"):
            raise ConfigError("auth.key_type must be 'team' or 'individual'")
        for name, value in (
            ("auth.key_id", self.auth.key_id),
            ("auth.issuer_id", self.auth.issuer_id),
            ("auth.private_key_path", self.auth.private_key_path),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ConfigError(f"{name} must be a non-empty string")
        self.http.validate()
        if self.output.format not in ("text", "json"):
            raise ConfigError("output.format must be 'text' or 'json'")
        if type(self.output.verbose) is not bool:
            raise ConfigError("output.verbose must be a boolean")

    def save(self, path: Path | None = None) -> None:
        """Save configuration to TOML file."""
        path = path or self._path
        if path is None:
            path = get_config_dir() / "config.toml"

        try:
            self.validate()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                tomli_w.dump(self.to_dict(), f)
        except Exception as e:
            raise ConfigError(f"Failed to save config: {e}", path=str(path)) from e

    def apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        for variable, attribute in (
            ("ASC_KEY_TYPE", "key_type"),
            ("ASC_KEY_ID", "key_id"),
            ("ASC_ISSUER_ID", "issuer_id"),
            ("ASC_PRIVATE_KEY_PATH", "private_key_path"),
        ):
            if variable in os.environ:
                setattr(self.auth, attribute, os.environ[variable].strip())

        # Output overrides
        if os.environ.get("SLOWLANE_JSON", "").lower() in ("1", "true"):
            self.output.format = "json"
        if os.environ.get("SLOWLANE_VERBOSE", "").lower() in ("1", "true"):
            self.output.verbose = True

        self.validate()
