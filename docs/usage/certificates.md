# Certificates

Certificate commands use an Apple ID session and Apple's Developer Portal services. Include `--team-id TEAM_ID` when the account belongs to more than one team.

## List certificates

```bash
slowlane signing certs list
```

Filter by certificate type:

```bash
slowlane signing certs list --type development
```

## Create a certificate

Create a certificate from an existing PEM-encoded certificate signing request:

```bash
slowlane signing certs create --type distribution --csr ./request.csr
```

## Revoke a certificate

The certificate ID is positional:

```bash
slowlane signing certs revoke CERT_ID
```

Add `--force` only when a non-interactive workflow has already confirmed the target. Revoking a certificate can invalidate provisioning profiles that depend on it and cannot be undone.
