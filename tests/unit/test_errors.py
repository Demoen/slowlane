"""Tests for error handling."""

import pytest

from slowlane.core.errors import (
    AuthExpiredError,
    ExitCode,
    SlowlaneError,
    NetworkError,
    RateLimitError,
)


class TestExitCode:
    """Tests for exit codes."""

    def test_exit_codes_are_unique(self) -> None:
        """Test that all exit codes are unique."""
        codes = [e.value for e in ExitCode]
        assert len(codes) == len(set(codes))

    def test_success_is_zero(self) -> None:
        """Test that SUCCESS is 0."""
        assert ExitCode.SUCCESS == 0


class TestSlowlaneError:
    """Tests for SlowlaneError."""

    def test_default_message(self) -> None:
        """Test default error message."""
        error = SlowlaneError()
        assert str(error) == "An error occurred"

    def test_custom_message(self) -> None:
        """Test custom error message."""
        error = SlowlaneError("Custom error")
        assert str(error) == "Custom error"

    def test_context(self) -> None:
        """Test error context."""
        error = SlowlaneError("Error", key="value", num=42)
        assert "key=value" in str(error)
        assert "num=42" in str(error)

    def test_exit_code(self) -> None:
        """Test exit code."""
        error = SlowlaneError()
        assert error.exit_code == ExitCode.GENERAL_ERROR


class TestAuthExpiredError:
    """Tests for AuthExpiredError."""

    def test_exit_code(self) -> None:
        """Test exit code is AUTH_EXPIRED."""
        error = AuthExpiredError()
        assert error.exit_code == ExitCode.AUTH_EXPIRED


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_retry_after(self) -> None:
        """Test retry_after value."""
        error = RateLimitError(retry_after=60)
        assert error.retry_after == 60
        assert "retry_after=60" in str(error)


class TestNetworkError:
    """Tests for NetworkError."""

    def test_exit_code(self) -> None:
        """Test exit code is NETWORK_ERROR."""
        error = NetworkError()
        assert error.exit_code == ExitCode.NETWORK_ERROR
