# Apps

App commands use App Store Connect API-key authentication.

## List apps

```bash
slowlane asc apps list
```

Limit the number of returned records:

```bash
slowlane asc apps list --limit 25
```

Request structured output with the global option:

```bash
slowlane --json asc apps list
```

## Get an app

Pass the App Store Connect resource ID returned by `apps list`, or a bundle ID:

```bash
slowlane asc apps get APP_RESOURCE_ID
slowlane asc apps get com.example.app
```

The command displays the app name, resource ID, bundle ID, SKU, and primary locale when those values are present in the API response.
