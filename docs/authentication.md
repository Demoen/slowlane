# Authentication

Slowlane supports two primary authentication methods for interacting with Apple's services: **API Key** (recommended for CI/CD) and **Session Authentication** (for interactive use or when API keys are insufficient).

## Method 1: App Store Connect API Key (Recommended)

This is the most robust method for CI/CD pipelines. It uses a JSON Web Token (JWT) signed with your private key to authenticate requests.

### 1. Generate an API Key
1. Go to [App Store Connect > Users and Access > Keys](https://appstoreconnect.apple.com/access/api).
2. Click **+** to generate a new key.
3. Give it a name and select a role (e.g., "App Manager" or "Developer").
4. Download the `.p8` private key file. **Store this securely.**
5. Note the **Key ID** and your **Issuer ID**.

### 2. Configure Environment Variables
Set the following environment variables in your local shell or CI configuration:

```bash
export ASC_KEY_ID="YOUR_KEY_ID"
export ASC_ISSUER_ID="YOUR_ISSUER_ID"
# Option A: Path to the .p8 file
export ASC_PRIVATE_KEY_PATH="/path/to/AuthKey_XXXXXXXXXX.p8"

# Option B: Content of the .p8 file (useful for some CI systems)
export ASC_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----"
```

## Method 2: Session Authentication

Some operations (like managing certificates or provisioning profiles on the Developer Portal) may require a session-based login if the App Store Connect API doesn't fully support them, or if you prefer interactive login.

### Interactive Login
Run the login command to open a browser window and log in with your Apple ID. This supports 2FA.

```bash
slowlane spaceauth login --email user@example.com
```

This will save a session cookie to your machine.

### Exporting Session for CI/CD
To use session authentication in a headless CI environment:

1. Log in interactively on your local machine.
2. Export the session:
   ```bash
   slowlane spaceauth export
   ```
   Output:
   ```bash
   export FASTLANE_SESSION="ey... (long string) ..."
   ```
3. Set the `FASTLANE_SESSION` environment variable in your CI system.

### Validating Session
Check if your session is still valid:

```bash
slowlane spaceauth doctor
```

## Security Best Practices
- **Never commit your `.p8` file or `FASTLANE_SESSION` to a public repository.**
- Use mechanism like GitHub Secrets or GitLab Variables to inject these values at runtime.
- API Keys are long-lived but should be rotated periodically.
- Sessions expire (usually after ~30 days) and must be refreshed manually.
