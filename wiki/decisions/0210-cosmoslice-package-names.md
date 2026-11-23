# 0210. Every package a user sees is named CosmoSlice

## Status

Accepted. Amends decisions 0132 (the `.exe`, `.app` and AppImage names and the
`OrcaSlicer_` artifact prefix no longer stay), 0133 (the AppImage desktop
entry is rewired again, together with its file), 0134 (`OrcaSlicer.app` and
`OrcaSlicer.AppImage` in a text follow the new names), 0182 (the executable
is no longer `orca-slicer.exe`), 0062 (the artifacts named after `env.ver`
carry the CosmoSlice prefix) and 0154 (the DMG is rebuilt from
`CosmoSlice.app`). Those three live on other branches: their status line is
updated when they meet this one.

## Context

The product-name stage (decision 0132) renamed every visible text but kept
the package names: the Windows executable `orca-slicer.exe`, the installer,
portable, MSIX, DMG, AppImage and Flatpak file names, `OrcaSlicer.app`, and
every CI artifact `OrcaSlicer_...`. The user wants all of them to say
CosmoSlice. Nothing has been shipped to users yet, so no migration is needed.
Two constraints hold: no upstream line is edited in git (zero conflict), and
what the build or the CI reads by name keeps working.

## Decision

- Renamed (visible): the Windows executable `CosmoSlice.exe` (portable,
  installer and MSIX), the MSIX command alias `cosmoslice.exe`, the installer
  file `CosmoSlice_Windows_Installer_V<version>_<arch>.exe`, `CosmoSlice.app`,
  the DMG `CosmoSlice_Mac_universal_<ver>.dmg` and its volume `CosmoSlice`,
  the AppImage file and its launcher name, the MSIX file, the Flatpak bundle,
  and every CI artifact (`CosmoSlice_...`, `CosmoSlice-Linux-flatpak_...`).
- Kept: the data folder and `SLIC3R_APP_KEY`, `OrcaSlicer.conf`, the macOS
  bundle id and `CFBundleExecutable`, the G-code header, the Linux binary
  `orca-slicer` inside the AppImage and the Flatpak, the Flatpak app id,
  `OrcaSlicer.dll`, the portable build folder `build/OrcaSlicer`,
  `CPACK_PACKAGE_NAME`, and the intermediate names the upstream scripts move
  (`APP_IMAGE`, the `build_linux_image.sh.in` move).
- What the build names is renamed before the build, by rows of
  `cosmyx-src/branding/product-name/patches.json` (the existing stage): the
  Windows `OUTPUT_NAME`, the version resource `OriginalFilename`,
  `CPACK_PACKAGE_FILE_NAME`, `CPACK_NSIS_INSTALLED_ICON_NAME`,
  `CPACK_PACKAGE_EXECUTABLES`, `CPACK_CREATE_DESKTOP_LINKS`, the MSIX
  manifest `Executable` and alias, the executable check of `build_msix.ps1`,
  the two runtime lookups (`Process.cpp` now starts the running executable by
  its own file name; `BBLNetworkPlugin.cpp` looks for `CosmoSlice.exe` with the
  same "name plus one" length upstream used), and the AppImage desktop
  `Name=` together with the `mv` of the file appimagetool names after it.
  `build_win.bat` is never patched: an upstream test asserts its text.
- What only the workflow names (upload steps, read by GitHub before the
  checkout, so the branding cannot patch them) is renamed by one Cosmyx
  composite action, `.github/actions/cosmyx-package-names`, which runs
  `scripts/cosmyx/package_names.py` (standard library). Its names come from
  `cosmyx-src/branding/product-name/packages.json`: templates rendered with
  `{product}` or `{upstream}` and the job's `ver`, arch suffix and Ubuntu
  version. Five `# Cosmyx` hook steps, each only `name`, `uses` and
  `with: stage:`, call it:
  - `mac-app` in build_orca.yml after "Create DMG without notary", before the
    Cosmyx macOS signing: renames the universal app, drops the validator app
    and DMG and the unsigned `OrcaSlicer_` DMG, builds the CosmoSlice DMG with
    upstream's `scripts/create_dmg.sh`. The signing signs every app of the
    folder and rebuilds the DMG under the app's name, so the rename must come
    first.
  - `mac-upload` after "Upload OrcaSlicer_profile_validator DMG mac".
  - `windows` after "Build MSIX Store package Win", before "Upload artifacts
    Win MSIX": renames the MSIX, uploads the portable folder, the installer
    and the MSIX, deletes the upstream portable and installer artifacts.
  - `linux` before "Upload artifacts Ubuntu": renames the AppImage and
    uploads it.
  - `flatpak` in build_flatpak.yml (the Flatpak job of build_all.yml lives
    there on this base) before "Upload artifacts Flatpak": renames the bundle
    and uploads it, keeping the upstream name format.
  An upstream upload step that runs after a stage finds no file and only
  warns; an upstream artifact uploaded before a stage is deleted by it
  (`geekyeggo/delete-artifact`, already used upstream).
- Guards (G8): `PACKAGING_PINS` drops the installer name and the AppImage
  desktop name, pins the Linux binary `OUTPUT_NAME`, and keeps the AppImage
  intermediate names, `CPACK_PACKAGE_NAME` and the Flatpak id. A new check
  requires the AppImage desktop `Name=` and the file its script moves to name
  the same thing, before and after apply.

## Consequences

- A user sees CosmoSlice on every file they download, install or run, and in
  every CI artifact. The Linux binary and the data folder still say
  OrcaSlicer, where only tools read them.
- The CI uploads the Windows portable folder twice (upstream's, then
  deleted) because the upstream step uploads it before the MSIX is built.
- The other Cosmyx branches that look for packages by name accept both
  prefixes (artifact checks, Windows signing verification, GUI goldens,
  exec smoke), so merge order does not matter.
- Removing it: drop the rows listed above from `patches.json`, the five hook
  steps, the action, `package_names.py` and `packages.json`; the packages are
  named OrcaSlicer again.
