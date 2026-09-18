# Installation

## Requirements

| Workflow | Requirements |
| --- | --- |
| Apps, builds, TestFlight | Python 3.14+, an eligible App Store Connect API key, and network access to Apple |
| Certificates, profiles, devices | The above, with a **team** API key and suitable signing permissions |
| IPA and PKG uploads | **macOS**, a team API key, and current Xcode or Apple Transporter tooling |

REST API commands run on macOS, Linux, and Windows. Uploads require macOS and fail early on other operating systems.

Supported architectures are **Apple Silicon (arm64) on macOS**, **x64 Windows**, and **x64 Linux**. The current cryptography dependency no longer supports Intel macOS or 32-bit Windows; source builds on those platforms are not supported by Slowlane. See the [cryptography changelog](https://cryptography.io/en/latest/changelog/).

## Install

Use a Python 3.14 or newer virtual environment:

```bash
python -m pip install slowlane
slowlane version
slowlane --help
```

For a Poetry project:

```bash
poetry add slowlane
poetry run slowlane --help
```

No browser installation or optional interactive extra is required.

## Connect an API key

Follow [Authentication](authentication.md) to configure a team or individual API key. Then check the local setup and make a read-only API check:

```bash
slowlane doctor
slowlane doctor --online
slowlane asc apps list
```

The online check verifies access to an apps endpoint. Success does not establish permission for every signing, TestFlight, or upload operation.

## Upgrade

```bash
python -m pip install --upgrade slowlane
```

Read the [migration guide](migration.md) before upgrading from 0.3.x: Apple ID sessions, private Developer Portal endpoints, and automatic certificate selection have been removed.

## Apple tooling

Use a current supported Xcode installation for your target platform. Apple changes SDK submission requirements independently of Slowlane; consult [Apple’s upcoming requirements](https://developer.apple.com/news/upcoming-requirements/) when preparing a release. Slowlane uploads already-built artifacts; it does not build, sign, notarize, or submit an app for review.
