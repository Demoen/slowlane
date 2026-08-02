# Configuration

Slowlane reads TOML configuration and then applies supported environment-variable and command-line overrides.

## Configuration file

The default path is platform-specific:

| Platform | Path |
| --- | --- |
| Linux and macOS | `$XDG_CONFIG_HOME/slowlane/config.toml`, or `~/.config/slowlane/config.toml` |
| Windows | `%APPDATA%\slowlane\config.toml` |

Use the global `--config` option to load another file:

```bash
slowlane --config /path/to/config.toml asc apps list
```

## Complete example

```toml
[auth]
key_id = "XXXXXXXXXX"
issuer_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
private_key_path = "/absolute/path/to/AuthKey_XXXXXXXXXX.p8"

[http]
timeout = 30
max_retries = 3
backoff_factor = 0.5

[output]
format = "text"
verbose = false

[devportal]
team_id = "TEAM_ID"
```

`team_id` selects an Apple Developer team when an account belongs to more than one team. The same value can be supplied per signing command with `--team-id`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `ASC_KEY_ID` | App Store Connect API key ID |
| `ASC_ISSUER_ID` | App Store Connect issuer ID |
| `ASC_PRIVATE_KEY` | Private-key contents |
| `ASC_PRIVATE_KEY_PATH` | Path to a `.p8` private-key file |
| `FASTLANE_SESSION` | Exported Slowlane session data |
| `SLOWLANE_JSON` | Set to `1` or `true` for JSON output |
| `SLOWLANE_VERBOSE` | Set to `1` or `true` for verbose output |
| `TRANSPORTER_PATH` | Explicit path to `iTMSTransporter` or `altool` |

The `--json` and `--verbose` global options override output settings for the current invocation:

```bash
slowlane --json --verbose asc apps list
```

## Credential handling

Prefer environment variables or a CI secret manager for credentials. If a private-key path is stored in the TOML file, keep the key itself outside the repository and restrict access to both files.
