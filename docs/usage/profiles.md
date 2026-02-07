# Provisioning Profiles

Manage provisioning profiles (mobileprovision files) which link your app ID, certificates, and devices.

## List Profiles

```bash
slowlane signing profiles list
```

Filtered by type:
```bash
slowlane signing profiles list --type appstore
```

## Create a Profile

Create a new profile for App Store distribution:

```bash
slowlane signing profiles create \
  --name "Match AppStore com.example.app" \
  --bundle-id com.example.app \
  --type appstore \
  --certificate-id CERT_ID
```

For Ad Hoc distribution (requires registered devices):

```bash
slowlane signing profiles create \
  --name "Match AdHoc com.example.app" \
  --bundle-id com.example.app \
  --type adhoc \
  --certificate-id CERT_ID \
  --devices "device_id1,device_id2"
```

## Delete a Profile

```bash
slowlane signing profiles delete --id PROFILE_ID
```
