"""Error types and exit codes for deterministic CLI behavior."""

from enum import IntEnum
from typing import Any


class ExitCode(IntEnum):
    """Deterministic exit codes for CI integration."""

    SUCCESS = 0
    GENERAL_ERROR = 1
    AUTH_EXPIRED = 2
    RATE_LIMITED = 3
    NETWORK_ERROR = 4
    APPLE_FLOW_CHANGED = 5
    INVALID_ARGUMENTS = 10


class SlowlaneError(Exception):
    """Base exception for all slowlane errors."""

    exit_code: ExitCode = ExitCode.GENERAL_ERROR
    message: str = "An error occurred"

    def __init__(self, message: str | None = None, **context: Any) -> None:
        self.message = message or self.message
        self.context = context
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.context:
            ctx = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx})"
        return self.message


class AuthExpiredError(SlowlaneError):
    """Session or token has expired and needs to be refreshed."""

    exit_code = ExitCode.AUTH_EXPIRED
    message = "Authentication expired"


class RateLimitError(SlowlaneError):
    """Apple API rate limit exceeded."""

    exit_code = ExitCode.RATE_LIMITED
    message = "Rate limit exceeded"

    def __init__(
        self, message: str | None = None, retry_after: int | None = None, **context: Any
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, retry_after=retry_after, **context)


class NetworkError(SlowlaneError):
    """Network connectivity issue."""

    exit_code = ExitCode.NETWORK_ERROR
    message = "Network error"


class AppleFlowChangedError(SlowlaneError):
    """Apple changed their login flow or API structure."""

    exit_code = ExitCode.APPLE_FLOW_CHANGED
    message = "Apple flow has changed - please report this issue"


class InvalidArgumentsError(SlowlaneError):
    """Invalid command line arguments."""

    exit_code = ExitCode.INVALID_ARGUMENTS
    message = "Invalid arguments"


class ConfigError(SlowlaneError):
    """Configuration file error."""

    message = "Configuration error"


class SecretStorageError(SlowlaneError):
    """Failed to store or retrieve secrets."""

    message = "Secret storage error"


class JWTError(SlowlaneError):
    """JWT generation or validation error."""

    message = "JWT error"


class SessionError(SlowlaneError):
    """Session authentication error."""

    exit_code = ExitCode.AUTH_EXPIRED
    message = "Session error"


class TransporterError(SlowlaneError):
    """iTunes Transporter error."""

    message = "Transporter error"


class DeveloperPortalError(SlowlaneError):
    """Developer Portal API error."""

    message = "Developer Portal error"


class AppStoreConnectError(SlowlaneError):
    """App Store Connect API error."""

    message = "App Store Connect error"
