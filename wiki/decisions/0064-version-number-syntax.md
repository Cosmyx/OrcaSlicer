# 0064. Version number syntax

## Status

Accepted.

## Context

`scripts/cosmyx/cosmyx_version.py` reads the Cosmyx patch from
`src/slic3r/GUI/Cosmyx/logic/CosmyxVersion.hpp` and `SoftFever_VERSION` from
`version.inc` (decision 0062). It must read the same numbers as the C++
compiler and CMake, or the CI build names disagree with the version the app
shows. Two cases did not agree:

- A leading zero makes a C++ integer literal octal: `patch_version = 010;` is
  8 in the app, while Python's `int("010")` gives 10.
- Python's `\d` matches every Unicode decimal digit, so a fullwidth or
  Arabic-Indic digit passed the checks although CMake and the compiler do not
  read it as a number.

## Decision

- `patch_version` must be an ASCII decimal literal without a leading zero
  (`0` or `[1-9][0-9]*`). Anything else, octal, hexadecimal, binary, digit
  separators or non-ASCII digits, is a `VersionError`; the script never tries
  to evaluate C++ literal syntax.
- `SoftFever_VERSION` digits are ASCII only (`[0-9]`, `re.ASCII`).

## Consequences

- The C++ header is not changed: a plain decimal patch number is what it
  already holds.
- Removing it: go back to `\d+` and `int()`, and accept that a leading zero
  or a non-ASCII digit can name the artifacts after another version than the
  app's.
