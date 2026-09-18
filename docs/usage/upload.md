# Uploads

Upload signed IPA and PKG artifacts using Apple's tools on **macOS**. This release requires a **team API key** for uploads.

## Before uploading

1. Install a current Xcode or Apple Transporter version.
2. Configure a team key with `ASC_KEY_ID`, `ASC_ISSUER_ID`, and either `ASC_PRIVATE_KEY_PATH` or `ASC_PRIVATE_KEY`.
3. Confirm your API key has upload permissions and the app record exists in App Store Connect.
4. Check your signed artifact and the current [Apple submission requirements](https://developer.apple.com/news/upcoming-requirements/).

Slowlane discovers supported Apple upload tools locally. Set `TRANSPORTER_PATH` to the executable when automatic discovery cannot find it. Paths must point to the Apple binary, not the enclosing application bundle.

Transporter is required for IPA platforms other than iOS. The `altool` fallback supports iOS device IPAs and macOS PKGs only; simulator artifacts are not uploadable.

## IPA

```bash
slowlane upload ipa ./App.ipa
```

The default flow validates before uploading:

```bash
slowlane upload ipa ./App.ipa --validate-only
```

When your pipeline has already validated this exact artifact, skip the separate validation pass:

```bash
slowlane upload ipa ./App.ipa --skip-validation
```

`--validate-only` and `--skip-validation` are mutually exclusive.

## PKG

```bash
slowlane upload pkg ./App.pkg
```

PKG uploads also accept `--validate-only` and `--skip-validation`, with the same mutually exclusive behavior as IPA uploads.

This command uploads an App Store package for macOS. It does not perform Developer ID notarization. Use Apple's notarization tooling for that separate workflow.

## Know when it is done

An upload command reports the result of the upload tool. A successful transfer does **not** mean Apple has finished processing the build or approved it for distribution. Inspect [build processing state](builds.md) in a later step and check App Store Connect for any processing errors.

Do not blindly repeat an upload after a timeout: the artifact may already have reached Apple. Check App Store Connect first.

## Troubleshooting

Run `slowlane doctor` for local checks and `slowlane doctor --online` for read-only API connectivity. The online check does not prove upload permission or validate an artifact. Review [troubleshooting](../troubleshooting.md) for authentication, tool discovery, and network failures.
