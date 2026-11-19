# 0145. Reviewed allowlist of third-party binaries

## Status

Accepted.

## Context

The Windows build ships vendor binaries (runtime libraries, drivers) signed by
their publishers, and the macOS bundle may hold single-architecture helpers.

## Decision

- `scripts/cosmyx/artifact_checks/data/allowlist.json`, read from the trusted
  checkout only, version 1, entries with `os`, `kind` (`vendor`,
  `unsigned-ok`, `arch-exempt`), `glob` (POSIX path inside the artifact,
  case-insensitive, `*` crosses folders), `publisher_subject` (vendor only),
  `require_timestamp` (vendor only, default true), `reason` (required) and
  `expires` (optional, `YYYY-MM-DD`).
- An unknown key, a missing reason or an expired entry makes the whole list
  invalid, which fails the check.
- An entry that matched no file once every artifact of its OS was scanned is
  stale: a failure in enforce mode, a warning otherwise.
- `unsigned-ok` never covers a file the build signs by name (installer,
  uninstaller, the app and the validator).
- The list ships empty. It is filled from the report of the first signed DEV
  run, through a reviewed pull request.

## Consequences

- Until it is filled, every vendor file fails in enforce mode: the first
  signed DEV run is expected to be red and to produce the list.
- Removing it: delete the file and the `allowlist.py` module.
