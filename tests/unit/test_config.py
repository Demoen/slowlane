"""Tests for configuration management."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from slowlane.core.config import SlowlaneConfig, get_config_dir, get_data_dir


class TestConfigDirs:
    """Tests for config directory functions."""

    def test_get_config_dir_returns_path(self) -> None:
        """Test config dir returns a valid path containing slowlane."""
        config_dir = get_config_dir()
        assert isinstance(config_dir, Path)
        assert "slowlane" in str(config_dir).lower()

    def test_get_data_dir_returns_path(self) -> None:
        """Test data dir returns a valid path containing slowlane."""
        data_dir = get_data_dir()
        assert isinstance(data_dir, Path)
        assert "slowlane" in str(data_dir).lower()


class TestSlowlaneConfig:
    """Tests for SlowlaneConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SlowlaneConfig()
        assert config.auth.default_mode == "jwt"
        assert config.http.timeout == 30
        assert config.http.max_retries == 3
        assert config.output.format == "text"

    def test_load_nonexistent(self) -> None:
        """Test loading from nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.toml"
            config = SlowlaneConfig.load(path)
            # Should return default config
            assert config.auth.default_mode == "jwt"

    def test_load_and_save(self) -> None:
        """Test saving and loading config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"

            # Create and save config
            config = SlowlaneConfig()
            config.auth.key_id = "TEST123"
            config.http.timeout = 60
            config.save(path)

            # Load it back
            loaded = SlowlaneConfig.load(path)
            assert loaded.auth.key_id == "TEST123"
            assert loaded.http.timeout == 60

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        config = SlowlaneConfig()
        config.auth.key_id = "TEST123"

        d = config.to_dict()
        assert d["auth"]["key_id"] == "TEST123"
        assert d["http"]["timeout"] == 30
        assert d["output"]["format"] == "text"

    def test_apply_env_overrides(self) -> None:
        """Test environment variable overrides."""
        config = SlowlaneConfig()

        with patch.dict(
            "os.environ",
            {
                "ASC_KEY_ID": "ENV_KEY",
                "ASC_ISSUER_ID": "ENV_ISSUER",
                "SLOWLANE_JSON": "1",
            },
        ):
            config.apply_env_overrides()
            assert config.auth.key_id == "ENV_KEY"
            assert config.auth.issuer_id == "ENV_ISSUER"
            assert config.output.format == "json"
