# 0151. macOS signing settings from the seven Apple secrets

## Status

Accepted.

## Context

The repository already holds the secrets upstream's step reads:
`BUILD_CERTIFICATE_BASE64`, `P12_PASSWORD`, `KEYCHAIN_PASSWORD`,
`MACOS_CERTIFICATE_ID`, `APPLE_DEV_ACCOUNT`, `APP_PWD` and `TEAM_ID`. The user
confirmed they hold a Developer ID Application certificate and an app-specific
password of the Cosmyx Apple team. A step's `if:` cannot read secrets.

## Decision

- The hook passes the seven secrets to the action as inputs, the pattern of
  decision 0098. The action's first step checks them: none set, signing is off
  (a notice, output `enabled=false`, the build ships unsigned as before); some
  set, the step fails and names the missing ones; all set, it signs.
- Notarisation uses the Apple ID and app-specific password (`notarytool
  --apple-id --team-id --password`), as upstream does, rather than an App Store
  Connect API key, which the repository does not have.
- The script reads its settings from environment variables, never from its
  command line, and redacts every secret value from its log lines, error
  messages, summary and saved notary logs.
- The bundle identifier stays upstream's until the branding work changes it.

## Consequences

- An expired app-specific password fails at the first `notarytool submit`
  with an authentication error; a certificate of another type fails the
  keychain step ("not a Developer ID Application certificate").
- Moving to an API key later means three new secrets and a change in
  `notarize.credentials`.
