# Managing Apps

Interact with your apps on App Store Connect.

## List Apps

List all apps associated with your credentials:

```bash
slowlane asc apps list
```

**Options:**
- `--limit <number>`: Limit the number of results.
- `--platform <platform>`: Filter by platform (e.g., `IOS`).

## Get App Details

Get details for a specific app by its Bundle ID or Apple ID:

```bash
slowlane asc apps get com.example.my-app
# OR
slowlane asc apps get 1234567890
```

## Create App

*Currently, creating apps is done via the web interface to ensure all metadata is correctly properly set up initially.*
