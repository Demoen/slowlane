# Certificates

Certificate commands use Apple's public App Store Connect API and require a **team API key**. Your key must have the role needed for Certificates, Identifiers & Profiles access.

## List and inspect

```bash
slowlane signing certs list
slowlane --json signing certs list --type development
```

Certificate IDs are public API resource IDs. Old Developer Portal identifiers should not be assumed interchangeable.

## Create from a CSR

Create a PEM certificate signing request with your own signing-key workflow, then pass the existing request to Slowlane:

```bash
slowlane signing certs create --type distribution --csr ./request.csr
```

| Alias | Apple certificate type |
| --- | --- |
| `development` | `DEVELOPMENT` |
| `distribution` | `DISTRIBUTION` |
| `mac_development` | `MAC_APP_DEVELOPMENT` |
| `mac_distribution` | `MAC_APP_DISTRIBUTION` |

The canonical types `IOS_DEVELOPMENT`, `IOS_DISTRIBUTION`, and `MAC_INSTALLER_DISTRIBUTION` are also accepted, alongside the canonical values above. Developer ID certificate creation is outside this release's scope.

The private key that produced the CSR remains your responsibility. Slowlane does not generate it, export it, install it into a keychain, or create a `.p12` archive.

## Download

```bash
slowlane signing certs download CERT_ID --output ./distribution.cer
```

The output file must not already exist. The downloaded certificate contains no private key; retain the matching private key for code signing.

## Revoke

```bash
slowlane signing certs revoke CERT_ID
```

Revocation is irreversible and can invalidate dependent provisioning profiles. Review the certificate ID and affected workflows before confirming. Use `--force` only in automation that has already approved that exact resource.

JSON mode and noninteractive processes require `--force`; without it, the command fails instead of prompting.

See Apple's [certificates API](https://developer.apple.com/documentation/appstoreconnectapi/certificates) for the upstream resource contract.
