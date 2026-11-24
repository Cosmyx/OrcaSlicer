"""Integration and rebase helpers for the Cosmyx branch stack.

- `resolve`: pure text resolutions of the known conflict kinds.
- `cli`: `integrate` (rebuild the throwaway integration branch) and
  `rebase-check` (dry-run replay of every branch onto an upstream tag).

The branch list and merge order live in `branches.json` next to this file.
"""
