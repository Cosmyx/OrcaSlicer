# 0141. Trusted scripts, data from the built commit, fork builds never run

## Status

Accepted.

## Context

`workflow_run` runs with the base repository's token and secrets, also for
builds of pull requests from forks. A build's artifacts and its commit are
untrusted input.

## Decision

- The check scripts and `data/allowlist.json` always come from the workflow's
  own commit (`tools/`). The built commit (`subject/`) is a sparse checkout of
  data files only: `version.inc`, `CosmyxVersion.hpp`, `localization/cosmyx/`
  and `resources/cosmyx/`. Nothing from it is executed; Python runs with `-I`.
- Least privilege: `contents: read` and `actions: read` for the workflow,
  `statuses: write` only for the two jobs that post the status; checkouts never
  keep credentials. The signing secrets only reach the script as presence
  flags (`secrets.X != ''`), never as values.
- A build whose head repository is not this repository is never executed: no
  `--appimage-extract` (the AppImage is unpacked with `unsquashfs` at its
  runtime's end instead), no smoke run, no slice. Those checks are skipped by
  design.

## Consequences

- A change to the scripts or the allowlist takes effect only once merged on
  DEV, which is what makes them trustworthy.
- Removing the fork rule would let a fork pull request run code with the
  repository's token.
