# Devices

List registered devices using a **team API key**:

```bash
slowlane signing devices list
slowlane --json signing devices list
```

Use each device's public API resource `id` with `signing profiles create --device`. A resource ID is not the hardware UDID.

Device registration and enabling or disabling devices remain in Apple's developer tools. Slowlane currently lists devices; it does not mutate device registrations.

Continue with [provisioning profiles](profiles.md). The upstream resource contract is Apple's [devices API](https://developer.apple.com/documentation/appstoreconnectapi/devices).
