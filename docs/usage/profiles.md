# Provisioning profiles

Provisioning-profile commands use an Apple ID session and Apple's Developer Portal services. Include `--team-id TEAM_ID` when the account belongs to more than one team.

## List profiles

```bash
slowlane signing profiles list
```

Filter by distribution type or bundle ID:

```bash
slowlane signing profiles list --type appstore
slowlane signing profiles list --app com.example.app
```

## Create a profile

Create an App Store profile:

```bash
slowlane signing profiles create \
  --name "App Store com.example.app" \
  --type appstore \
  --bundle-id com.example.app
```

When `--cert` is omitted, Slowlane selects a certificate only if exactly one active,
unexpired distribution certificate is compatible. Use `--cert CERT_ID` to resolve an
ambiguous selection. App Store profiles do not accept devices.

Development and ad hoc profiles require at least one device. Repeat `--device` to include
multiple registered device IDs:

```bash
slowlane signing profiles create \
  --name "Development com.example.app" \
  --type development \
  --bundle-id com.example.app \
  --cert CERT_ID \
  --device DEVICE_ID_1 \
  --device DEVICE_ID_2
```

Without `--cert`, development profiles use the same unambiguous-selection rule with active,
unexpired development certificates. Ad hoc profiles require distribution certificates.

## Delete a profile

The profile ID is positional:

```bash
slowlane signing profiles delete PROFILE_ID
```

Use `--force` to skip the interactive confirmation in a controlled automation workflow.
