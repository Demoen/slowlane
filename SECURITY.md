# Security policy

## Supported releases

Security fixes are provided for the latest Slowlane release. Upgrade to the current release before requesting support for an older version.

## Reporting a vulnerability

Do not disclose a suspected vulnerability in a public issue, discussion, pull request, or log attachment.

Submit a private report through [GitHub Security Advisories](https://github.com/Demoen/slowlane/security/advisories/new). Include:

- the affected Slowlane version and platform;
- the vulnerable command, module, or workflow;
- reproduction steps or a minimal proof of concept;
- the potential impact;
- any suggested mitigation;
- whether credentials or user data may have been exposed.

Remove real Apple IDs, team IDs, API keys, private keys, session cookies, and application identifiers from the report unless a maintainer explicitly requests them through a secure channel.

## Scope

Relevant reports include credential exposure, unsafe secret storage, authentication bypass, command execution, path traversal, dependency or release-pipeline compromise, and unintended disclosure in logs or structured output.

Apple service availability, account-policy disputes, and vulnerabilities in Apple-operated systems should be reported to Apple through its security-reporting process.

## Coordinated disclosure

Allow maintainers time to reproduce, fix, and publish an update before public disclosure. Security advisories and release notes will credit reporters who request attribution when a report is confirmed.
