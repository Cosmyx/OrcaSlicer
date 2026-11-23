# Decision register

Every decision taken for the Cosmyx fork is recorded here, one file per
decision, so that parallel branches never edit the same file.

## Files

- Name: `NNNN-short-slug.md`, with a four-digit number and a lowercase,
  hyphenated slug (no spaces, safe on every OS).
- Numbers are reserved in ranges of ten per planned task, so two branches never
  take the same number:

  | Task | Range     |
  |------|-----------|
  | T0   | 0001-0009 |
  | T1   | 0010-0019 |
  | T2   | 0020-0029 |
  | T3   | 0030-0039 |
  | T4   | 0040-0049 |
  | T5   | 0050-0059 |
  | T6   | 0060-0069 |
  | T7   | 0070-0079 |
  | T8   | 0080-0089 |
  | T9   | 0090-0099 |
  | T10  | 0100-0109 |

  Later tasks take the next free range of ten (0110-0119, and so on) and note
  it in the coordination register before using it.
- There is no index file to update: `just decisions` lists the register.

## Content

Each file starts with a title line `# NNNN. Title`, then these sections:

- **Status**: accepted, superseded by NNNN, or reverted.
- **Context**: the problem and the constraints.
- **Decision**: what was chosen.
- **Consequences**: what it costs, and what removing it would take.

A decision is never rewritten once merged. A new decision supersedes it and the
old file only gets its status changed.
