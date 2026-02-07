# Certificates

Manage your signing certificates for distribution and development.

## List Certificates

List all valid certificates:

```bash
slowlane signing certs list
```

## Creates a Certificate

Create a new distribution certificate (e.g., for the App Store):

```bash
slowlane signing certs create --type distribution
```

Create a development certificate:

```bash
slowlane signing certs create --type development
```

## Revoke a Certificate

Revoke a certificate by its Serial Number or ID:

```bash
slowlane signing certs revoke --id CERT_ID
```

> **Warning**: Revoking a distribution certificate will invalidate any provisioning profiles that use it. Ensure you really want to do this.
