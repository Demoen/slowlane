# CLI reference

## Global syntax

```text
slowlane [GLOBAL OPTIONS] COMMAND [ARGS]
```

| Option | Purpose |
| --- | --- |
| `--verbose`, `-v` | Enable verbose output |
| `--json` | Request JSON output from commands that support structured results |
| `--config PATH`, `-c PATH` | Load a specific TOML configuration file |
| `--version`, `-V` | Show the installed version and exit |
| `--help` | Show contextual help |

Global options must precede the command:

```bash
slowlane --json asc apps list
```

The `slowlane version` command provides the same version information.

## Session authentication

| Command | Key arguments and options |
| --- | --- |
| `spaceauth login` | `--email EMAIL`, `--service SERVICE`, `--headless` |
| `spaceauth export` | `--email EMAIL` |
| `spaceauth verify` | `--email EMAIL` |
| `spaceauth revoke` | Delete the local stored copy; required `--email EMAIL`, optional `--force` |
| `spaceauth doctor` | No command-specific options |

Interactive login requires the `interactive` package extra and an installed Chromium browser.
Deleting a local session does not invalidate exported copies or the session at Apple.

## App Store Connect

| Command | Key arguments and options |
| --- | --- |
| `asc apps list` | `--limit NUMBER` |
| `asc apps get APP_ID_OR_BUNDLE_ID` | App Store Connect app resource ID or bundle ID |
| `asc builds list` | `--app APP_ID`, `--limit NUMBER` |
| `asc builds latest APP_ID` | App Store Connect app resource ID |
| `asc testflight testers` | `--app APP_ID`, `--limit NUMBER` |
| `asc testflight groups` | `--app APP_ID` |
| `asc testflight invite EMAIL` | Required `--group GROUP_ID`; optional `--first-name`, `--last-name` |

## Certificates and provisioning profiles

Developer Portal commands require session authentication. Use `--team-id TEAM_ID` when the Apple ID belongs to more than one team.

| Command | Key arguments and options |
| --- | --- |
| `signing certs list` | `--type TYPE`, `--team-id TEAM_ID` |
| `signing certs create` | Required `--type TYPE` and `--csr PATH`; optional `--team-id TEAM_ID` |
| `signing certs revoke CERT_ID` | `--force`, `--team-id TEAM_ID` |
| `signing profiles list` | `--type TYPE`, `--app BUNDLE_ID`, `--team-id TEAM_ID` |
| `signing profiles create` | Required `--name`, `--type`, `--bundle-id`; repeatable `--device` for development and ad hoc; optional `--cert`, `--team-id` |
| `signing profiles delete PROFILE_ID` | `--force`, `--team-id TEAM_ID` |

## Uploads

| Command | Key arguments and options |
| --- | --- |
| `upload ipa PATH` | `--validate-only`, `--skip-validation` |
| `upload pkg PATH` | Upload a macOS package through the same Transporter flow |

Uploads require API-key authentication and Apple Transporter or `altool`.

## CI environment helpers

| Command | Key arguments and options |
| --- | --- |
| `env print` | `--platform github|gitlab|azure|generic`, `--include-session` |
| `env setup` | `--platform github|gitlab|azure` |

Use `slowlane COMMAND --help` for the authoritative option list installed with a particular release.
