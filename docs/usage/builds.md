# Builds and TestFlight

These commands use App Store Connect API-key authentication.

## Builds

List builds across accessible apps:

```bash
slowlane asc builds list
```

Filter by an App Store Connect app resource ID and limit the result count:

```bash
slowlane asc builds list --app APP_RESOURCE_ID --limit 25
```

Get the latest build returned for an app:

```bash
slowlane asc builds latest APP_RESOURCE_ID
```

## TestFlight testers

List testers, optionally filtered by app:

```bash
slowlane asc testflight testers
slowlane asc testflight testers --app APP_RESOURCE_ID --limit 50
```

Invite a tester to a beta group. The email address is positional, and `--group` expects the group's App Store Connect resource ID:

```bash
slowlane asc testflight invite new.tester@example.com \
  --group GROUP_RESOURCE_ID \
  --first-name Taylor \
  --last-name Example
```

## TestFlight groups

```bash
slowlane asc testflight groups
slowlane asc testflight groups --app APP_RESOURCE_ID
```

Use the ID shown by this command when inviting a tester.
