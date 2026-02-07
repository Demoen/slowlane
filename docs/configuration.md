# Configuration

Slowlane can be configured via a TOML file or environment variables.

## Config File

The configuration file is located at `~/.config/slowlane/config.toml` (Linux/macOS) or `%APPDATA%\slowlane\config.toml` (Windows).

### Example Configuration

```toml
[auth]
# Default authentication mode: "jwt" or "session"
default_mode = "jwt"

[http]
# Request timeout in seconds
timeout = 30
# Number of retries for failed requests
max_retries = 3

[output]
# Output format: "text" (default) or "json"
format = "text"
# Show verbose logs
verbose = false
```

## Environment Variables

Environment variables override config file settings.

| Variable | Description |
|----------|-------------|
| `ASC_KEY_ID` | App Store Connect Key ID |
| `ASC_ISSUER_ID` | App Store Connect Issuer ID |
| `ASC_PRIVATE_KEY` | Private Key content (PEM format) |
| `ASC_PRIVATE_KEY_PATH` | Path to Private Key file (.p8) |
| `FASTLANE_SESSION` | Base64 encoded session cookie |
| `SLOWLANE_FORMAT` | Output format (`text`, `json`) |
| `SLOWLANE_VERBOSE` | Set to `true` for debug logs |
