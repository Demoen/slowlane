# Uploads

Slowlane validates and uploads IPA and PKG files through Apple Transporter or `altool`. Uploads require App Store Connect API-key authentication and Apple tooling that is normally available only on macOS.

## Prerequisites

1. Install Xcode or the Transporter app.
2. Configure `ASC_KEY_ID`, `ASC_ISSUER_ID`, and either `ASC_PRIVATE_KEY_PATH` or `ASC_PRIVATE_KEY`.
3. Accept current agreements in App Store Connect.
4. Confirm that the binary is signed for its intended distribution channel.

Use `TRANSPORTER_PATH` if automatic tool discovery does not find the correct executable.

## Upload an IPA

```bash
slowlane upload ipa ./path/to/MyApp.ipa
```

Validate without uploading:

```bash
slowlane upload ipa ./path/to/MyApp.ipa --validate-only
```

By default, Slowlane validates before upload. Skip that separate validation pass only when another trusted step has already validated the artifact:

```bash
slowlane upload ipa ./path/to/MyApp.ipa --skip-validation
```

## Upload a PKG

```bash
slowlane upload pkg ./path/to/MyApp.pkg
```

## Troubleshooting

- Run `slowlane spaceauth doctor` to inspect local authentication and dependency configuration.
- Confirm that the API key role permits the requested operation.
- Check that Xcode or Transporter is current and accessible to the CI runner.
- Re-run with the global `--verbose` option before the upload command to collect diagnostic output without exposing credentials.
