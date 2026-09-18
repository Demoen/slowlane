# Configuration

Slowlane reads a TOML configuration file, then applies environment settings and global CLI output options.

## File location

| Platform | Default path |
| --- | --- |
| Linux and macOS | `$XDG_CONFIG_HOME/slowlane/config.toml`, or `~/.config/slowlane/config.toml` |
| Windows | `%APPDATA%\slowlane\config.toml` |

Select another file with the global `--config` option:

```bash
slowlane --config /path/to/config.toml asc apps list
```

## Team-key example

```toml
[auth]
key_type = "team"
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
```

For an individual key, use `key_type = "individual"` and omit `issuer_id`. The default key type is `team`. A team key selects its own Apple account, so `[devportal]` and `auth.default_mode` are retired settings and produce a migration error.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `ASC_KEY_TYPE` | `team` (default) or `individual` |
| `ASC_KEY_ID` | API key ID |
| `ASC_ISSUER_ID` | Issuer ID; required for team keys and forbidden for individual keys |
| `ASC_PRIVATE_KEY` | PEM private-key contents from a secret manager |
| `ASC_PRIVATE_KEY_PATH` | Path to a protected `.p8` key file |
| `SLOWLANE_JSON` | Set to `1` or `true` for JSON output |
| `SLOWLANE_VERBOSE` | Set to `1` or `true` for verbose diagnostics |
| `TRANSPORTER_PATH` | Explicit path to a supported Apple upload executable |

Environment credentials override their file-based equivalents. Configure only one private-key source. Command-line `--json` and `--verbose` take precedence for that invocation:

```bash
slowlane --json --verbose asc apps list
```

## HTTP settings

`timeout` is a positive request timeout in seconds. `max_retries` is a nonnegative retry count; `backoff_factor` is a finite, nonnegative delay factor. Read retries are bounded and honor server throttling.

Slowlane does not automatically replay mutating API requests after uncertain network failures. Inspect the remote resource before retrying a create, invite, or delete operation.

## Output and secrets

JSON results go to stdout and diagnostics go to stderr. The global `--json` option must appear before the command. Keep private keys outside the repository and protect configuration files that reference them. See [troubleshooting](troubleshooting.md) for failures and [migration](migration.md) for retired options.
