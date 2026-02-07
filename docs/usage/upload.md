# Uploading to App Store

Upload your binary (`.ipa` or `.pkg`) to App Store Connect.

Slowlane uses the **iTMSTransporter** tool (on macOS) or the native API where possible to robustly upload builds.

## Upload IPA

```bash
slowlane upload ipa ./path/to/MyApp.ipa
```

### Options
- `--validate-only`: detailed validation without uploading.
- `--platform`: specific platform (default: `ios`).

## Prerequisites
- **On macOS**: Requires Xcode or the Transporter app installed.
- **On Linux/Windows**: Upload capabilities are limited by Apple's tooling availability. Most users perform uploads from a macOS runner in CI.

## Troubleshooting Uploads
If you encounter `iTMSTransporter` errors, ensure:
1. You have accepted the latest agreements in App Store Connect.
2. Your firewall allows connections to Apple's transporter servers.
3. The IPA is correctly signed for **App Store Distribution** (not Development or Ad Hoc).
