# Security Model

This document explains how slowlane handles sensitive data.

## Data Classification

| Data Type | Sensitivity | Storage |
|-----------|-------------|---------|
| API Private Key (.p8) | High | OS Keychain or encrypted file |
| Session Cookies | High | OS Keychain or encrypted file |
| API Key ID | Medium | Config file (plaintext) |
| Issuer ID | Medium | Config file (plaintext) |
| Email Address | Low | Stored as SHA-256 hash only |
| Passwords | Critical | Never stored |

## Storage Locations

### Configuration
- **Path**: `~/.config/slowlane/config.toml`
- **Contents**: Non-sensitive settings only (timeouts, output format, key IDs)
- **Permissions**: User-readable only (0600)

### Secrets (OS Keychain)
When available, secrets are stored in:
- **macOS**: Keychain
- **Windows**: Credential Manager
- **Linux**: Secret Service (GNOME Keyring, KWallet)

### Secrets (Encrypted Fallback)
When keychain is unavailable:
- **Path**: `~/.local/share/slowlane/secrets/`
- **Encryption**: Fernet (AES-128-CBC)
- **Key**: Randomly generated, stored in `.key` file

## Session Security

### What's Stored
- Cookies required for Apple authentication
- Creation timestamp
- Last verification timestamp
- Target service (appstoreconnect/developer)
- Email hash (SHA-256, first 16 chars)

### What's NOT Stored
- Plaintext passwords
- Full email addresses
- 2FA codes

### Session Expiration
- Sessions are considered stale after 7 days
- Use `spaceauth verify` to check validity
- Apple may invalidate sessions at any time

## Environment Variables

| Variable | Purpose | Security Note |
|----------|---------|---------------|
| `ASC_KEY_ID` | API Key ID | Can be logged |
| `ASC_ISSUER_ID` | Issuer ID | Can be logged |
| `ASC_PRIVATE_KEY` | Private key content | Never logged |
| `ASC_PRIVATE_KEY_PATH` | Path to .p8 file | Path only logged |
| `FASTLANE_SESSION` | Session cookie data | Never logged |

## Logging

- All secrets are automatically redacted from logs
- Patterns matched: JWT tokens, passwords, session IDs
- Use `--verbose` safely - secrets still redacted

## Best Practices

1. **In CI**: Use secrets management (GitHub Secrets, GitLab CI Variables, etc.)
2. **Locally**: Prefer keychain storage over environment variables
3. **API Keys**: Rotate regularly, use minimal permissions
4. **Sessions**: Re-authenticate periodically, revoke when done

## Reporting Security Issues

If you discover a security vulnerability, please report it responsibly.
