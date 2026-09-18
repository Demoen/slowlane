# Migrating from 0.3 to 0.4

Version 0.4 removes Apple ID sessions and private Developer Portal integrations. Signing now uses Apple's public App Store Connect API. Review automation before upgrading.

The cryptography security update also changes platform requirements: use Apple Silicon macOS, x64 Windows, or x64 Linux. Intel macOS and 32-bit Windows are unsupported. Migrate affected runners before upgrading; retaining a vulnerable dependency is not a supported workaround.

## What changed

| Previous workflow | Replacement |
| --- | --- |
| `spaceauth login/export/verify/revoke` | Configure an App Store Connect API key |
| `spaceauth doctor` | `slowlane doctor`; add `--online` for a read-only API check |
| `slowlane[interactive]` and Chromium | Install `slowlane`; browser dependencies are unnecessary |
| `FASTLANE_SESSION` | `ASC_KEY_TYPE`, `ASC_KEY_ID`, team issuer, and private-key source |
| `env print --include-session` | Remove `--include-session` and use the API-key CI templates |
| `[devportal].team_id` or `--team-id` | Use the team key for the intended Apple account |
| `[auth].default_mode` | `[auth].key_type = "team"` or `"individual"` |
| Profile certificate auto-selection | Required explicit `--cert CERT_ID` |
| Private Developer Portal response fields | Public API resources with `id` and `attributes` |

`[devportal]` and `auth.default_mode` in configuration cause a migration error. Remove them; environment overrides do not make retired file settings valid.

## Move authentication

1. Create a team API key with the roles your workflows require.
2. Configure `ASC_KEY_ID`, `ASC_ISSUER_ID`, and `ASC_PRIVATE_KEY_PATH` or `ASC_PRIVATE_KEY`.
3. Remove session-login steps and the interactive dependency extra from your CI configuration.
4. Run `slowlane doctor`, then `slowlane doctor --online`.
5. Exercise read-only app and signing commands before enabling writes.

Individual keys are available for eligible App Store Connect REST operations. Explicitly set `ASC_KEY_TYPE=individual` and remove all issuer settings. Signing and uploads require team keys in Slowlane.

## Update signing scripts

Re-list resources with the new API before using their IDs:

```bash
slowlane signing certs list
slowlane signing profiles list
slowlane signing devices list
```

Pass a certificate ID explicitly:

```bash
slowlane signing profiles create \
  --name "App Store com.example.app" \
  --type appstore \
  --bundle-id com.example.app \
  --cert CERT_ID
```

For development and ad hoc profiles, supply device **resource IDs**, not hardware UDIDs. Update JSON consumers to read `resource["id"]` and `resource["attributes"]` instead of legacy fields such as `certificateId` and `provisioningProfileId`.

## Existing session data

Slowlane no longer reads `FASTLANE_SESSION` or saved Apple ID sessions. Upgrading does **not** delete stored session data or invalidate exported cookies. Remove obsolete CI secrets and local saved-session entries through your existing credential-management process. If you need to invalidate a session at Apple, use Apple's account security controls.

## Uploads and retries

Uploads are explicitly limited to macOS with supported Apple tooling and team API keys. Individual-key uploads, Linux/Windows upload execution, notarization, and private-endpoint fallbacks are unsupported.

Mutating API calls are not automatically retried after uncertain failures. If a create or invite fails after a network interruption, list the relevant resources before deciding whether to repeat it.

See [troubleshooting](troubleshooting.md) and the [release verification checklist](release-verification.md) for verification steps.
