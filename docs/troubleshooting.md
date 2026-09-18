# Troubleshooting

Start with local diagnostics:

```bash
slowlane doctor
slowlane --json doctor
```

Then make a read-only connection check:

```bash
slowlane doctor --online
```

The online check reaches an App Store Connect apps endpoint. It does not create resources, upload binaries, or establish permission for all other endpoints.

## Authentication failures

| Symptom | Check |
| --- | --- |
| Missing API credentials | Configure a key ID and exactly one private-key source; team keys also require an issuer |
| Individual key rejected | Set `ASC_KEY_TYPE=individual`; remove `ASC_ISSUER_ID` and file-based `issuer_id` |
| HTTP 401 | Check key ID, issuer/key type, matching `.p8` key, revoked keys, and system time |
| HTTP 403 | Check the key's role, user app access, and permission for the requested operation |
| Signing rejects an individual key | Switch to a team key with signing access |
| Configuration mentions retired options | Remove `[devportal]` and `auth.default_mode`; follow [migration](migration.md) |

Never paste private-key contents, bearer tokens, or raw session exports into bug reports.

## Signing failures

Use IDs from current public API list commands. A bundle identifier such as `com.example.app`, an App Store Connect app resource ID, and a device resource ID are different identifiers.

For a new profile, confirm the bundle identifier exists, the explicit certificate is compatible and unexpired, and the devices are registered and eligible. Development and ad hoc profiles require devices; App Store profiles must not include them.

Downloads refuse to overwrite files. Choose another output path or handle an existing file explicitly in your workflow.

## Upload failures

Uploads require macOS and a team API key. Confirm that Xcode or Transporter is installed and current. If needed, set `TRANSPORTER_PATH` to the supported executable.

Check the artifact's signing, bundle identifier, version/build numbers, and Apple's current [submission requirements](https://developer.apple.com/news/upcoming-requirements/). An upload tool's success does not imply that App Store Connect processing has finished.

After a timeout, inspect App Store Connect before uploading again. Do not assume that a client-side error means the transfer never reached Apple.

## Network errors and throttling

Read requests use bounded retries. Exhausted rate limits and network failures return nonzero exits. Wait for the server's indicated retry window when available and reduce concurrent requests.

Creates, invites, and other writes may have succeeded even if the response was lost. Slowlane avoids automatic replay; verify the remote state before retrying.

## Automation and bug reports

Place `--json` before the command. Capture stdout for results and stderr for errors; always check the process exit code.

Include the Slowlane version, operating system, sanitized command, exit code, and minimal redacted diagnostic output in an [issue](https://github.com/Demoen/slowlane/issues/new). Report possible credential exposure through the [security policy](https://github.com/Demoen/slowlane/blob/main/SECURITY.md).

Expected authentication, configuration, API, and upload failures produce concise errors, including with `--verbose`. Unexpected exceptions may include a verbose traceback. Review and redact diagnostic output before sharing it.
