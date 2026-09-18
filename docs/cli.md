# CLI reference

## Global syntax

```text
slowlane [GLOBAL OPTIONS] COMMAND [ARGS]
```

| Option | Purpose |
| --- | --- |
| `--verbose`, `-v` | Enable diagnostics on stderr |
| `--json` | Emit structured results on stdout and structured errors on stderr |
| `--config PATH`, `-c PATH` | Load a specific TOML configuration file |
| `--version`, `-V` | Show the installed version |
| `--help` | Show contextual help |

Global options must precede the command:

```bash
slowlane --json asc apps list
```

## Diagnostics

| Command | Behavior |
| --- | --- |
| `version` | Show the installed version |
| `doctor` | Inspect local API-key configuration and upload tooling without contacting Apple |
| `doctor --online` | Also make a read-only App Store Connect API request |

An online apps check does not prove permission for every endpoint. Incomplete or invalid credentials must be corrected before network workflows can run.

## App Store Connect

| Command | Arguments and options |
| --- | --- |
| `asc apps list` | `--limit NUMBER` |
| `asc apps get APP_ID_OR_BUNDLE_ID` | App resource ID or reverse-DNS bundle identifier |
| `asc builds list` | `--app APP_ID`, `--limit NUMBER` |
| `asc builds latest APP_ID` | App resource ID |
| `asc testflight testers` | `--app APP_ID`, `--limit NUMBER` |
| `asc testflight groups` | `--app APP_ID` |
| `asc testflight invite EMAIL` | Required `--group GROUP_ID`; optional `--first-name`, `--last-name` |

Team and individual keys can use eligible endpoints, subject to the role and account permissions.

TestFlight invitations support external groups only. Existing testers are reused, and email delivery depends on Apple's build readiness and notification settings.

## Signing

All signing commands require a **team key**. The key's issuer selects the account.

| Command | Arguments and options |
| --- | --- |
| `signing certs list` | Optional `--type TYPE` |
| `signing certs create` | Required `--type TYPE`, `--csr PATH` |
| `signing certs download CERT_ID` | Required `--output PATH`; refuses existing files |
| `signing certs revoke CERT_ID` | Optional `--force` |
| `signing profiles list` | Optional `--type TYPE`, `--app BUNDLE_ID` |
| `signing profiles create` | Required `--name`, `--type`, `--bundle-id`, `--cert`; repeatable `--device` |
| `signing profiles download PROFILE_ID` | Required `--output PATH`; refuses existing files |
| `signing profiles delete PROFILE_ID` | Optional `--force` |
| `signing devices list` | List registered device resource IDs |

See [certificates](usage/certificates.md) and [profiles](usage/profiles.md) for supported types. There is no automatic certificate selection. Development and ad hoc profiles require devices; App Store profiles reject devices.

JSON signing resources use Apple's public API shape: `id`, `type`, `attributes`, and relationships when returned by Apple.

Certificate revocation and profile deletion require `--force` in JSON mode or a noninteractive process. An interactive text-mode invocation prompts for confirmation. Approve the exact target before using `--force` in automation.

## Uploads

| Command | Arguments and options |
| --- | --- |
| `upload ipa PATH` | `--validate-only` or `--skip-validation` |
| `upload pkg PATH` | `--validate-only` or `--skip-validation`; macOS App Store package |

Uploads require macOS, supported Apple upload tools, and a team key. The two validation flags are mutually exclusive. Non-iOS IPA platforms require Transporter; the `altool` fallback supports iOS device IPAs and macOS PKGs.

## CI helpers

| Command | Arguments and options |
| --- | --- |
| `env print` | `--platform github\|gitlab\|azure\|generic` |
| `env setup` | `--platform github\|gitlab\|azure` |

Templates help wire API credentials into a CI secret store. They do not configure your CI provider or export session cookies.

## Automation

A successful command exits with code `0`. Failures use nonzero codes; inspect the JSON error object on stderr when using `--json`. Do not treat an empty stdout stream as success.

```bash
slowlane --json signing profiles list > profiles.json
```

Use `slowlane COMMAND --help` as the authoritative option list for the installed version. The [migration guide](migration.md) covers removed commands and changed signing output.
