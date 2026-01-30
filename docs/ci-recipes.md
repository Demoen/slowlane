# CI Recipes

Ready-to-use CI configurations for popular platforms.

## GitHub Actions

### Basic Upload
```yaml
name: Deploy to App Store

on:
  push:
    tags:
      - 'v*'

jobs:
  upload:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install slowlane
        run: pip install slowlane

      - name: Build App
        run: |
          # Your build steps here
          xcodebuild archive ...

      - name: Upload to App Store
        env:
          ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
          ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}
        run: slowlane upload ipa ./build/App.ipa
```

### With TestFlight Distribution
```yaml
- name: Upload and Notify
  env:
    ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
    ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
    ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}
  run: |
    slowlane upload ipa ./App.ipa
    slowlane asc testflight invite \
      --email tester@example.com \
      --group $BETA_GROUP_ID
```

## GitLab CI

```yaml
stages:
  - build
  - deploy

variables:
  PYTHON_VERSION: "3.11"

deploy:
  stage: deploy
  image: python:${PYTHON_VERSION}
  script:
    - pip install slowlane
    - slowlane upload ipa ./App.ipa
  variables:
    ASC_KEY_ID: $ASC_KEY_ID
    ASC_ISSUER_ID: $ASC_ISSUER_ID
    ASC_PRIVATE_KEY: $ASC_PRIVATE_KEY
  rules:
    - if: $CI_COMMIT_TAG
```

## Azure DevOps

```yaml
trigger:
  tags:
    include:
      - v*

pool:
  vmImage: 'macos-latest'

variables:
  - group: AppStoreConnect

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: pip install slowlane
    displayName: 'Install slowlane'

  - script: slowlane upload ipa $(Build.ArtifactStagingDirectory)/App.ipa
    displayName: 'Upload to App Store'
    env:
      ASC_KEY_ID: $(ASC_KEY_ID)
      ASC_ISSUER_ID: $(ASC_ISSUER_ID)
      ASC_PRIVATE_KEY: $(ASC_PRIVATE_KEY)
```

## CircleCI

```yaml
version: 2.1

jobs:
  deploy:
    macos:
      xcode: "15.0"
    steps:
      - checkout
      - run:
          name: Install slowlane
          command: pip3 install slowlane
      - run:
          name: Upload to App Store
          command: slowlane upload ipa ./App.ipa

workflows:
  deploy:
    jobs:
      - deploy:
          context: appstore-connect
          filters:
            tags:
              only: /^v.*/
```

## Bitbucket Pipelines

```yaml
pipelines:
  tags:
    'v*':
      - step:
          name: Deploy to App Store
          image: python:3.11
          script:
            - pip install slowlane
            - slowlane upload ipa ./App.ipa
```

## Session-Based Auth in CI

For operations requiring session auth:

1. Generate session locally:
```bash
slowlane spaceauth login --email your@email.com
slowlane spaceauth export > session.txt
```

2. Add to CI secrets as `FASTLANE_SESSION`

3. Use in CI:
```yaml
env:
  FASTLANE_SESSION: ${{ secrets.FASTLANE_SESSION }}
run: slowlane signing profiles list
```

**Note**: Sessions expire. Re-generate monthly or when operations fail.
