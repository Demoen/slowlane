# Authentication

Every network workflow uses an App Store Connect API key. Choose a **team key** for signing and uploads; an **individual key** can access eligible App Store Connect endpoints with the permissions of its user.

| Workflow | Team key | Individual key |
| --- | --- | --- |
| Apps, builds, and TestFlight | Subject to key role | Subject to user role and app access |
| Certificates, profiles, and devices | Required | Unsupported |
| IPA and PKG uploads | Required by Slowlane | Unsupported by Slowlane |

Apple documents [API key management](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api/) and [JWT authentication](https://developer.apple.com/documentation/appstoreconnectapi/generating-tokens-for-api-requests). Slowlane generates short-lived tokens locally from your private key.

## Team key

Create a team key in App Store Connect under **Users and Access → Integrations → App Store Connect API**. Choose the role required by your workflow. Save the key ID, issuer ID, and downloaded `.p8` file; Apple offers the private-key download only once.

```bash
export ASC_KEY_TYPE="team"
export ASC_KEY_ID="XXXXXXXXXX"
export ASC_ISSUER_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export ASC_PRIVATE_KEY_PATH="/absolute/path/to/AuthKey_XXXXXXXXXX.p8"

slowlane doctor
slowlane doctor --online
slowlane asc apps list
```

`team` is the default key type. A team's issuer identifies the account for signing operations; there is no separate `--team-id`.

## Individual key

Generate an individual API key from your App Store Connect user profile if your account permits it. Set the key type explicitly and remove any team issuer from the environment **and** configuration file:

```bash
export ASC_KEY_TYPE="individual"
export ASC_KEY_ID="XXXXXXXXXX"
unset ASC_ISSUER_ID
export ASC_PRIVATE_KEY_PATH="/absolute/path/to/AuthKey_XXXXXXXXXX.p8"

slowlane doctor --online
slowlane asc apps list
```

An individual key must not have an `issuer_id` in `config.toml`. Slowlane rejects conflicting configuration instead of guessing which identity to use. Individual keys cannot manage signing resources; Slowlane also restricts uploads to team keys.

## CI and secret managers

Supply the private-key contents through `ASC_PRIVATE_KEY`, or use `ASC_PRIVATE_KEY_PATH` for a protected file. Keep one key source configured so the selected credential is clear.

```yaml
env:
  ASC_KEY_TYPE: team
  ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
  ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
  ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}
```

Use `slowlane env print --platform github` for a configuration template. Templates reference the secret store; they do not replace creating its secrets. Use a macOS runner for uploads.

For GitLab, use a protected **File** CI variable named `ASC_PRIVATE_KEY_PATH` containing the PEM key. GitLab exposes its temporary file path to the job; do not try to mask a raw multiline PEM value. In Azure, put secret references such as `ASC_PRIVATE_KEY: $(ASC_PRIVATE_KEY)` in the task's `env:` mapping.

## Credential handling

Keep private keys out of source control, command arguments, and shared logs. Grant the narrowest role your operations need. Revoke an exposed key in App Store Connect and replace it in each environment.

Apple ID login, browser cookies, and `FASTLANE_SESSION` are no longer authentication methods. Existing users should follow the [migration guide](migration.md).
