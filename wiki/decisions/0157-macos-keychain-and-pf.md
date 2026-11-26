# 0157. Temporary keychain and a pf token, always cleaned up

## Status

Accepted.

## Context

codesign needs the certificate in an unlocked keychain it can use without a
prompt. Upstream's step makes its keychain the default and never restores the
search list, and its pf rule stays enabled, which is harmless only on
throw-away runners. Self-hosted macOS runners (`SELF_HOSTED`) keep state.

## Decision

- The certificate is decoded to `$RUNNER_TEMP`, imported into
  `$RUNNER_TEMP/cosmyx-signing.keychain-db` (`set-keychain-settings -lut
  21600`, `import -A -t cert -f pkcs12`, `set-key-partition-list -S
  apple-tool:,apple:,codesign:` with the keychain password), and deleted. The
  user's keychain search list and default keychain are saved, the temporary
  keychain is put first in both, and codesign also gets `--keychain`.
- `security find-identity -v -p codesigning` must list a `Developer ID
  Application:` identity that `MACOS_CERTIFICATE_ID` matches; otherwise the
  step fails before signing.
- On GitHub-hosted runners (`SELF_HOSTED` empty) UDP 443 is blocked with pf so
  stapler falls back to TCP, as upstream does; `pfctl -E` returns a token
  that the cleanup releases with `pfctl -X`.
- The cleanup step runs with `always()`: it restores the search list and the
  default keychain, deletes the keychain and releases the pf token.

## Consequences

- On a self-hosted runner, stapler may need TCP to work on its own.
- Removing it: the keychain, pf and cleanup steps of the action.
