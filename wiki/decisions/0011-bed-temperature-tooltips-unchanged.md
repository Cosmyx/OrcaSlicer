# 0011. Bed temperature tooltips stay upstream's

## Status

Accepted.

## Context

The upstream tooltips of the bed temperature options explain only the value 0.
Mentioning -1 would mean editing twelve upstream strings, each a merge conflict
risk and a change to every upstream translation.

## Decision

The tooltips are left as upstream wrote them. The meaning of -1 is documented
in decision 0010 and the changelog.

## Consequences

- Users discover -1 from Cosmyx documentation, not from the tooltip.
- The test checks the upstream tooltip is still there, so a Cosmyx change that
  rewrites it is noticed.
- Revisiting this means adding the text through the Cosmyx translation catalogue
  (T8) rather than editing the upstream strings.
