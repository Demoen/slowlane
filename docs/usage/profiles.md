# Provisioning profiles

Profiles use Apple's public App Store Connect API and a **team API key**. Register your bundle identifier in Apple's developer tools before creating a profile.

## List

```bash
slowlane signing profiles list
slowlane signing profiles list --type appstore
slowlane signing profiles list --app com.example.app
```

`--app` filters by the human-readable bundle identifier. The output contains public API profile IDs for downloads and deletion.

## Select a certificate

```bash
slowlane signing certs list
```

Every new profile requires one explicit `--cert CERT_ID`. Choose a compatible, unexpired certificate and retain its matching private key. Certificate auto-selection has been removed.

## Create an App Store profile

```bash
slowlane signing profiles create \
  --name "App Store com.example.app" \
  --type appstore \
  --bundle-id com.example.app \
  --cert CERT_ID
```

App Store profiles do not accept device IDs.

## Create a development or ad hoc profile

Get registered device resource IDs with `slowlane signing devices list`. Pass at least one `--device` for development and ad hoc profiles:

```bash
slowlane signing profiles create \
  --name "Development com.example.app" \
  --type development \
  --bundle-id com.example.app \
  --cert CERT_ID \
  --device DEVICE_RESOURCE_ID_1 \
  --device DEVICE_RESOURCE_ID_2
```

Use a development certificate for `development` and a distribution certificate for `adhoc`. Device resource IDs are different from hardware UDIDs.

| Profile alias | Apple profile type |
| --- | --- |
| `development` | `IOS_APP_DEVELOPMENT` |
| `appstore` | `IOS_APP_STORE` |
| `adhoc` | `IOS_APP_ADHOC` |

The canonical values are also accepted. This CLI supports creation of these iOS profile types; enterprise profiles and other platform profile creation are outside this release's scope.

## Download and delete

```bash
slowlane signing profiles download PROFILE_ID --output ./App.mobileprovision
slowlane signing profiles delete PROFILE_ID
```

Downloads refuse to overwrite an existing file. Deletion prompts for confirmation; `--force` skips that prompt for an already-approved automation action.

JSON mode and noninteractive processes require `--force` for deletion. Without it, the command fails instead of prompting.

Profile creation does not sign your application or install the profile. Use Xcode or your signing pipeline to consume the downloaded file. See Apple's [profiles API](https://developer.apple.com/documentation/appstoreconnectapi/profiles).
