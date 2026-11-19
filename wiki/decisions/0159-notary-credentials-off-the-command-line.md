# 0159. Notary credentials off the command line

## Status

Accepted. Amends decision 0151 on how the app-specific password reaches
`notarytool`.

## Context

Decision 0151 passed the Apple ID, team ID and app-specific password to every
`notarytool submit`, `wait` and `log` call as `--password <APP_PWD>`. A
command line is readable by every process of the runner (`ps`, `/proc`) for as
long as the call runs, up to 40 minutes for a `wait`, and the self-hosted macOS
runners decision 0157 supports keep other jobs and users around. cli.py
promises that no secret reaches a process listing.

`notarytool` has three ways to get the password: `--password` on the command
line, a keychain profile (`--keychain-profile`, made by `store-credentials`),
or a prompt when `store-credentials` is given the Apple ID and team ID but no
`--password`. With no controlling terminal, that prompt reads its answer from
stdin (checked with notarytool on macOS 26: the call waits on stdin until the
answer arrives).

## Decision

- Before the first submission, `notarize.store_profile` runs
  `xcrun notarytool store-credentials cosmyx-notary --apple-id <id> --team-id
  <team> --keychain <temporary keychain> --no-validate` and writes the password
  to its stdin, in a new session so that no terminal is ever used. The
  password is never an argument of any process.
- Every `submit`, `wait` and `log` call then uses `--keychain-profile
  cosmyx-notary --keychain <temporary keychain>`. The profile is stored once
  per run and reused by the DMG round.
- The profile lives only in the temporary keychain of decision 0157, which the
  action's clean-up step deletes whatever the outcome.
- Notarisation needs that keychain: without `COSMYX_MAC_KEYCHAIN` the script
  stops with an error instead of saving the password in a user's login
  keychain.
- `--no-validate` keeps the store step offline; a wrong password still fails
  at the first `submit`, as before.

## Consequences

- Remaining exposure: the Apple ID and team ID are still on the
  `store-credentials` command line for the moment it runs (they are not
  secret in themselves, and stay redacted from the logs); the password exists
  in the pipe to that one process and in the temporary keychain, which is
  locked by `KEYCHAIN_PASSWORD` and deleted at the end of the job. The
  environment of the script still holds the password, as for every secret
  GitHub passes to a step.
- The stdin answer relies on notarytool's prompt reading stdin without a
  terminal. If a later notarytool refuses that, `store-credentials` fails and
  the step stops with its error; nothing falls back to `--password`.
- Undoing this means restoring `--password` in `notarize.credentials` and
  dropping `store_profile`, which brings the password back into the process
  listing for the whole notarisation.
