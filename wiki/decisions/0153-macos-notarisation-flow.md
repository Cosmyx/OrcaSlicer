# 0153. Notarisation: submit all, wait, retry tool errors only, staple

## Status

Accepted.

## Context

Apple's notary service queues submissions; waits of tens of minutes happen.
Its tools fail sometimes for network reasons, and `stapler` fails with Error
68 when the ticket has not reached Apple's CDN yet or over HTTP/3.

## Decision

- Two rounds: the apps (each zipped with `ditto -c -k --keepParent`), then the
  DMGs. In each round every file is submitted first (`notarytool submit
  --no-wait --output-format json`), then waited for (`notarytool wait
  --timeout 40m`).
- A tool error (non-zero exit without an answer) is retried 3 times, 30 s
  apart. An answer of `Invalid` or `Rejected` is final and never retried; its
  log (`notarytool log`) is saved for the `cosmyx-notary-log-<version>`
  artifact and its issues are listed in the step summary.
- `stapler staple` is retried 5 times, 30 s apart, on the apps and then the
  DMGs. On GitHub-hosted runners UDP 443 is blocked first (decision 0157).

## Consequences

- A slow queue can reach the step's 90-minute timeout; rerunning the job
  resubmits.
- Removing it: `notarize.py`.
