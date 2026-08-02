# Authentication

Slowlane supports App Store Connect API keys and Apple ID sessions. Use API keys for App Store Connect REST API and upload workflows. Developer Portal signing commands require an Apple ID session.

## App Store Connect API key

Create a key in App Store Connect under **Users and Access > Integrations**, then record the issuer ID and key ID. The `.p8` private key can be downloaded only once.

Provide the credentials through environment variables:

```bash
export ASC_KEY_ID="XXXXXXXXXX"
export ASC_ISSUER_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export ASC_PRIVATE_KEY_PATH="/absolute/path/to/AuthKey_XXXXXXXXXX.p8"
```

Secret managers can supply the key contents directly instead:

```bash
export ASC_PRIVATE_KEY="$(cat AuthKey_XXXXXXXXXX.p8)"
```

Confirm access by listing apps:

```bash
slowlane asc apps list
```

## Apple ID session

Install the interactive-login extra and Chromium before starting a browser login:

```bash
python -m pip install "slowlane[interactive]"
python -m playwright install chromium
```

Include an email address so Slowlane can store and retrieve the session:

```bash
slowlane spaceauth login --service developer --email developer@example.com
```

The browser handles Apple ID credentials and two-factor authentication. Slowlane extracts the resulting session cookies after login; it does not store the Apple ID password.

### Verify a stored session

```bash
slowlane spaceauth verify --email developer@example.com
```

`spaceauth doctor` inspects local dependencies and authentication configuration. It does not replace remote session verification.

### Export a session for CI

```bash
slowlane spaceauth export --email developer@example.com
```

Store the emitted `FASTLANE_SESSION` value in the CI provider's secret store. The value contains authentication cookies and must be protected like a password.

### Remove a stored session

```bash
slowlane spaceauth revoke --email developer@example.com
```

This deletes only the local stored copy. Exported values and the session at Apple remain valid
until you invalidate them through the Apple account.

## Security guidance

- Never commit `.p8` files or exported sessions.
- Grant API keys only the roles required by the workflow.
- Rotate API keys and sessions according to your organization's credential policy.
- Avoid printing exported sessions in shared or retained CI logs.
- Revoke credentials immediately if exposure is suspected.
