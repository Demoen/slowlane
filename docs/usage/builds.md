# Builds & TestFlight

Manage your builds and TestFlight beta testing.

## Builds

### List Builds
List all builds for a specific app:

```bash
slowlane asc builds list com.example.my-app
```

### Get Latest Build
Find the latest build number for a specific version or the latest overall:

```bash
slowlane asc builds latest com.example.my-app
```

## TestFlight

### Testers
List all beta testers:

```bash
slowlane asc testflight testers list
```

Invite a tester to a group:

```bash
slowlane asc testflight invite \
  --email new.tester@example.com \
  --first-name John \
  --last-name Doe \
  --group "External Testers"
```

### Groups
List TestFlight groups:

```bash
slowlane asc testflight groups list
```
