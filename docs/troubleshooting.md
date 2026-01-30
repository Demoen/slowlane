# Troubleshooting

Common issues and solutions.

## Authentication Issues

### "No authentication configured"

**Cause**: Neither JWT nor session credentials are set.

**Solution**:
1. For API key auth, set these environment variables:
   ```bash
   export ASC_KEY_ID="your_key_id"
   export ASC_ISSUER_ID="your_issuer_id"
   export ASC_PRIVATE_KEY="$(cat AuthKey.p8)"
   ```

2. Or run interactive login:
   ```bash
   slowlane spaceauth login
   ```

3. Check status:
   ```bash
   slowlane spaceauth doctor
   ```

### "Authentication expired"

**Cause**: Session cookies have expired (Apple sessions last ~7 days).

**Solution**:
```bash
slowlane spaceauth login --email your@email.com
```

### "JWT error: Invalid private key"

**Cause**: The private key format is incorrect or corrupted.

**Solution**:
1. Ensure the key starts with `-----BEGIN PRIVATE KEY-----`
2. Check for extra whitespace or line breaks
3. Try reading directly from file:
   ```bash
   export ASC_PRIVATE_KEY_PATH="/path/to/AuthKey.p8"
   ```

## Upload Issues

### "iTMSTransporter not found"

**Cause**: The transporter binary isn't in a known location.

**Solution (macOS)**:
1. Install Xcode from the App Store
2. Or install "Transporter" app from the App Store
3. Or set path manually:
   ```bash
   export TRANSPORTER_PATH="/path/to/iTMSTransporter"
   ```

**Solution (Linux/Windows)**:
Transporter is macOS-only. Use alternative methods or a macOS runner.

### "ITMS-90062: Invalid Bundle"

**Cause**: The IPA is malformed or missing required entitlements.

**Solution**:
1. Re-export from Xcode with correct signing
2. Validate before upload:
   ```bash
   slowlane upload ipa ./App.ipa --validate-only
   ```

### "ITMS-90161: Invalid provisioning profile"

**Cause**: Profile doesn't match the signing certificate or has expired.

**Solution**:
1. Check profile expiration in Developer Portal
2. Regenerate profile:
   ```bash
   slowlane signing profiles list
   slowlane signing profiles create --name "..." --type appstore --bundle-id com.example.app
   ```

## Network Issues

### "Rate limit exceeded"

**Cause**: Too many requests to Apple's API.

**Solution**:
- Wait and retry (automatic with exponential backoff)
- Reduce parallel operations
- Cache results where possible

### "Network error: Connection timeout"

**Cause**: Network connectivity issues or Apple services down.

**Solution**:
1. Check internet connection
2. Check [Apple System Status](https://developer.apple.com/system-status/)
3. Increase timeout in config:
   ```toml
   # ~/.config/slowlane/config.toml
   [http]
   timeout = 60
   max_retries = 5
   ```

## Developer Portal Issues

### "Session authentication required"

**Cause**: Developer Portal operations require Apple ID session, not API key.

**Solution**:
```bash
slowlane spaceauth login --service developer
```

### "No development teams found"

**Cause**: Your Apple ID isn't associated with any developer accounts.

**Solution**:
1. Accept invitation in [developer.apple.com](https://developer.apple.com)
2. Verify correct Apple ID is being used

## CLI Issues

### "Command not found: slowlane"

**Cause**: Package not installed or not in PATH.

**Solution**:
```bash
pip install slowlane
# Or if using pipx
pipx install slowlane
```

### "Playwright not installed"

**Cause**: Playwright is optional for interactive login.

**Solution**:
```bash
pip install playwright
playwright install chromium
```

## Getting Help

1. Run diagnostics:
   ```bash
   slowlane spaceauth doctor
   ```

2. Enable verbose output:
   ```bash
   slowlane --verbose <command>
   ```

3. Check exit code:
   | Code | Meaning |
   |------|---------|
   | 0 | Success |
   | 2 | Auth expired |
   | 3 | Rate limited |
   | 4 | Network error |
   | 5 | Apple flow changed |
