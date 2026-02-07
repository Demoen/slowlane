# CLI Reference

## Global Options

- `--verbose / --no-verbose`: Enable verbose logging.
- `--format [text|json]`: set output format.
- `--help`: Show help message.

## `slowlane spaceauth`

Manage authentication sessions.

- `login`: Interactive login to generate session.
  - `--email`: Apple ID email.
  - `--service`: Target service (`appstoreconnect` or `developer`).
- `export`: Export session for CI use.
- `doctor`: Check authentication status.
- `revoke`: Revoke and clear local session.

## `slowlane asc`

App Store Connect operations.

### `apps`
- `list`: List all apps.
- `get`: Get details for a specific app.

### `builds`
- `list`: List builds for an app.
- `latest`: Get the latest build number.

### `testflight`
- `testers list`: List beta testers.
- `invite`: Invite a tester.
- `groups list`: List beta groups.

## `slowlane signing`

Developer Portal operations.

### `certs`
- `list`: List certificates.
- `create`: Create a certificate.
- `revoke`: Revoke a certificate.

### `profiles`
- `list`: List provisioning profiles.
- `create`: Create a profile.
- `delete`: Delete a profile.

## `slowlane upload`

Upload operations.

### `ipa`
- `path`: Path to the IPA file.
- `--validate-only`: Validate without uploading.
- `--platform`: Target platform.
