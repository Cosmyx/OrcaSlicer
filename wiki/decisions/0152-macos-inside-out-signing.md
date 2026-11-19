# 0152. Inside-out signing of every Mach-O file, without --deep

## Status

Accepted.

## Context

`codesign --deep` is deprecated and cannot sign the Python runtime that
`build_release_macos.sh` relocates to `Contents/Resources/python` (with a
symbolic link left at `Contents/MacOS/python`). Notarisation requires a
hardened-runtime signature with a secure timestamp on every Mach-O file.
Upstream finds Mach-O files with `file --mime-type`.

## Decision

- Mach-O files are found by their magic bytes, with the artifact checks'
  `binfmt.py`, so names and `file` versions do not matter. Symbolic links are
  never followed or signed. An app without any Mach-O file is an error
  (detection is broken).
- Nested bundles (`.app`, `.framework`, `.bundle`, `.plugin`, `.xpc`,
  `.appex` folders with an `Info.plist` or a `Versions` folder) are signed as
  bundles. The order is deepest path first, files before bundles at the same
  depth, the app last, so a bundle is always sealed after everything inside it.
- Every item is signed with `codesign --force --options runtime --timestamp
  --entitlements scripts/disable_validation.entitlements --sign
  <MACOS_CERTIFICATE_ID> --keychain <temporary keychain>`: the same
  entitlements file as upstream (library validation off for the plug-ins,
  unsigned executable memory for the Bambu network plug-in).
- Mach-O object files (`MH_OBJECT`) are not loadable code and codesign cannot
  sign them; they are logged and left out.
- After signing, `codesign --verify --deep --strict` must pass on the app.

## Consequences

- A Python extension or plug-in Apple rejects shows up in the notary log
  (decision 0153), not as a silent gap.
- Removing it: `sign.py` and `discover.py`.
