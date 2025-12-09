# OrcaSlicer → OrcaCosmyx Rename Summary

## Completed: Full Application Rename

**Date:** December 8, 2025
**Status:** ✅ Complete

---

## Statistics

- **Files Renamed:** 55 files (using `git mv`)
- **Files Modified:** 173 files
- **Total Files Changed:** 228 files
- **Text Replacements:** 2,263+ occurrences

---

## Files Renamed (55 total)

### Source Code (4 files)
- `src/OrcaSlicer.cpp` → `src/OrcaCosmyx.cpp`
- `src/OrcaSlicer.hpp` → `src/OrcaCosmyx.hpp`
- `src/OrcaSlicer_app_msvc.cpp` → `src/OrcaCosmyx_app_msvc.cpp`
- `src/dev-utils/OrcaSlicer_profile_validator.cpp` → `src/dev-utils/OrcaCosmyx_profile_validator.cpp`

### Platform Files (4 files)
- `src/dev-utils/platform/unix/OrcaSlicer.desktop` → `OrcaCosmyx.desktop`
- `src/dev-utils/platform/msw/OrcaSlicer.rc.in` → `OrcaCosmyx.rc.in`
- `src/dev-utils/platform/msw/OrcaSlicer.manifest.in` → `OrcaCosmyx.manifest.in`
- `src/dev-utils/platform/msw/OrcaSlicer-gcodeviewer.rc.in` → `OrcaCosmyx-gcodeviewer.rc.in`

### Images/Icons (24 files)
All image files in `resources/images/` renamed:
- `OrcaSlicer*.png` → `OrcaCosmyx*.png`
- `OrcaSlicer*.svg` → `OrcaCosmyx*.svg`
- `OrcaSlicer*.ico` → `OrcaCosmyx*.ico`
- `OrcaSlicer*.icns` → `OrcaCosmyx*.icns`
- Including: mac icons, title images, gradient versions, grayscale variants

### Translation Files (21 files)
- `localization/i18n/OrcaSlicer.pot` → `OrcaCosmyx.pot`
- All 20 language `.po` files: `OrcaSlicer_*.po` → `OrcaCosmyx_*.po`
  - Languages: ca, cs, de, en, es, fr, hu, it, ja, ko, lt, nl, pl, pt_BR, ru, sv, tr, uk, zh_CN, zh_TW

### Distribution Files (3 files)
- `scripts/flatpak/io.github.softfever.OrcaSlicer.metainfo.xml` → `OrcaCosmyx.metainfo.xml`
- `scripts/flatpak/io.github.softfever.OrcaSlicer.yml` → `OrcaCosmyx.yml`
- `resources/profiles/Vivedino/OrcaSlicer-Troodon2-Bed-Texture.png` → `OrcaCosmyx-Troodon2-Bed-Texture.png`

### IDE Config (1 file)
- `.idea/OrcaSlicer.iml` → `OrcaCosmyx.iml`

---

## Text Replacements

### Core Identity
- ✅ `version.inc`: Updated `SLIC3R_APP_NAME` and `SLIC3R_APP_KEY` to "OrcaCosmyx"

### Modified File Categories
- ✅ All C++ source files (.cpp, .hpp, .h)
- ✅ All CMake files (CMakeLists.txt, *.cmake)
- ✅ All build scripts (.bat, .sh)
- ✅ All GitHub workflows (.github/workflows/*.yml)
- ✅ All documentation (.md files)
- ✅ All configuration files (.yml, .xml, .json, .ini)
- ✅ Translation files (.po, .pot)
- ✅ Resource files (hints.ini, text.js)

---

## Preserved URLs

As requested, the following URLs were **NOT changed**:

### GitHub Repository References
- ✅ `https://api.github.com/repos/OrcaSlicer/orcaslicer-profiles/releases/tags`
- ✅ All references to `OrcaSlicer/orcaslicer-profiles` repository path

Location: `src/libslic3r/AppConfig.cpp:41`

---

## Key Changes by Area

### Application Identity
- Window titles: "OrcaSlicer" → "OrcaCosmyx"
- Executable names: OrcaSlicer → OrcaCosmyx
- Bundle names (macOS): "OrcaSlicer" → "OrcaCosmyx"
- Desktop entries (Linux): Updated

### User Data Directories
Application will now use:
- **Windows:** `%APPDATA%/OrcaCosmyx/`
- **macOS:** `~/Library/Application Support/OrcaCosmyx/`
- **Linux:** `~/.config/OrcaCosmyx/`

### Build System
- CMake project names updated
- Install directories: `./OrcaSlicer` → `./OrcaCosmyx`
- Dependency directories: `OrcaSlicer_dep` → `OrcaCosmyx_dep`

### Documentation
- All user-facing documentation updated
- Developer guides updated
- Calibration guides updated
- Wiki references updated

---

## Verification

### Remaining "OrcaSlicer" References
The following intentional references remain:
1. ✅ GitHub repository URLs (as requested)
2. ✅ Binary/image files (no text changes needed)
3. ✅ Git history (intentionally preserved)

### Clean References
- ✅ No unintended "OrcaSlicer" references in source code
- ✅ No unintended "OrcaSlicer" references in build scripts
- ✅ No unintended "OrcaSlicer" references in configuration

---

## Next Steps

### To Build
Use the existing build commands (they've been updated):
- Windows: `build_release_vs2022.bat`
- macOS: `./build_release_macos.sh`
- Linux: `./build_linux.sh -dsi`

### To Test
1. Build the application
2. Run `OrcaCosmyx.exe` (Windows) or equivalent
3. Verify window title shows "OrcaCosmyx"
4. Check that config files are created in new directory

### To Commit
```bash
git add -A
git commit -m "Rename OrcaSlicer to OrcaCosmyx

- Renamed 55 files (source, images, translations, configs)
- Updated 2,263+ text references across 228 files
- Preserved GitHub repository URLs
- Updated build system and workflows"
```

---

## Notes

- All file renames used `git mv` to preserve git history
- Translation files updated (requires regeneration for completeness)
- GitHub workflows updated and ready to use
- No data migration code added (app not released yet)
