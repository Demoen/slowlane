# Quickstart Guide

Get up and running with slowlane in minutes.

## Installation

```bash
pip install slowlane
```

For interactive login (browser-based 2FA):
```bash
playwright install chromium
```

## Authentication Options

### Option 1: API Key (Recommended for CI)

1. Create an API key in [App Store Connect](https://appstoreconnect.apple.com/access/api)
2. Download the `.p8` private key file
3. Set environment variables:

```bash
export ASC_KEY_ID="YOUR_KEY_ID"
export ASC_ISSUER_ID="YOUR_ISSUER_ID"
export ASC_PRIVATE_KEY="$(cat AuthKey_XXXXXX.p8)"
```

4. Test it:
```bash
slowlane asc apps list
```

### Option 2: Session Auth (For features requiring Apple ID)

1. Run interactive login:
```bash
slowlane spaceauth login --email your@email.com
```

2. Complete login in the browser window
3. Session is saved automatically

4. For CI, export the session:
```bash
slowlane spaceauth export
# Outputs: export FASTLANE_SESSION="..."
```

## Common Tasks

### List Apps
```bash
slowlane asc apps list
```

### Get Latest Build
```bash
slowlane asc builds latest APP_ID
```

### Upload IPA
```bash
slowlane upload ipa ./MyApp.ipa
```

### Check Auth Status
```bash
slowlane spaceauth doctor
```

## CI Configuration

### GitHub Actions
```yaml
- name: Upload to App Store
  env:
    ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
    ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
    ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}
  run: |
    pip install slowlane
    slowlane upload ipa ./app.ipa
```

See `slowlane env setup --platform github` for more details.

## Troubleshooting

### "Authentication expired"
Your session has expired. Run `spaceauth login` again.

### "iTMSTransporter not found"
Transporter is bundled with Xcode on macOS. On other platforms, use the API for alternative upload methods.

### "Rate limited"
Wait and retry. slowlane automatically backs off on rate limits.

## Next Steps

- Run `slowlane --help` for all commands
- Check `slowlane spaceauth doctor` for auth diagnostics
- See the full documentation in `docs/`
