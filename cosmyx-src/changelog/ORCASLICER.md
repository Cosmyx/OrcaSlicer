# OrcaSlicer base changelog

CosmoSlice bundle 8 is rebased on OrcaSlicer 2.5.2. This file lists the major
OrcaSlicer changes from 2.0.0 to 2.5.2, taken from the OrcaSlicer release
notes and dated at the official release. Our own changes are in
[COSMYX.md](COSMYX.md).

Stable release notes only cover the changes since the last pre-release, so a
large feature is listed under the stable release it shipped in.

## Added

- **2026-11-21** — Per-filament prime volume for the Type 1 prime tower.
- **2026-11-14** — Per-nozzle settings can be copied to every tool of a toolchanger.
- **2026-11-14** — Keyboard shortcut for Reload from disk.
- **2026-11-07** — Python plugin system, with a Plugins window, permission prompts and a plugin hub.
- **2026-11-07** — Belt printer support.
- **2026-11-07** — Colour mixing with mixed filaments, Texture Displacement, and import of textured or coloured models.
- **2026-11-07** — Experimental Design tab (parametric CAD), and parallel printing on IDEX and IQEX printers.
- **2026-11-07** — Speed Dial launcher and assignable keyboard shortcuts.
- **2026-11-07** — Bambu Lab H2C and A2L, mixed nozzle sizes on H2D and X2D, extruder variants on every printer, AMS drying and gradient filaments.
- **2026-11-07** — Toolhead collision volumes, shorter travel planning, Precise Seam modifiers and new infill options.
- **2026-11-07** — X-Ray, Section and Focus views, centre-of-mass markers, translucent filament preview, and "Publish 3MF".
- **2026-11-07** — Linux ARM64 AppImage.
- **2026-11-07** — New printer vendors and models, and about 10 filament vendors.
- **2026-07-07** — `{first_object_name}` filename placeholder, wiki links in Preferences, and number-or-percent settings in custom G-code.
- **2026-07-07** — add:north filaments.
- **2026-06-28** — One-time "Profile syncing change" dialog explaining the move to Orca Cloud.
- **2026-06-28** — Native Windows ARM64 build.
- **2026-06-28** — Per-filament minimal chamber temperature; the existing value is relabelled "Target".
- **2026-06-28** — The plate index is sent with packaged `.gcode.3mf` uploads to OctoPrint and Moonraker.
- **2026-06-28** — Snapmaker U1 nozzles and Elegoo Centauri 2 profiles.
- **2026-06-20** — Orca Cloud, an optional account for profile sync, version history, shareable preset bundles and community subscriptions.
- **2026-06-20** — Cloud sync conflict resolution, offline login, update notices for subscribed presets, "Hide login side panel", and Bambu telemetry turned off before the plugin starts.
- **2026-06-20** — Z Anti-Aliasing (ZAA) contouring, fuzzy skin ripple mode, Optimized Gyroid, non-crossing tri-hexagon infill, combined brims and multiple dovetail cuts.
- **2026-06-20** — Machine Input Shaping settings, kinematics visualisation, Expert user mode, native Wayland on Linux, and CGAL "Fix Model" on Linux and macOS.
- **2026-06-20** — Realistic View (Phong shading, SSAO, shadows), Troubleshoot Center, and a bridging overhaul.
- **2026-06-20** — Expanded per-feature filament assignment, with a "Default" option.
- **2026-06-20** — Native Moonraker and 3DPrinterOS hosts, Creality K-series LAN discovery with CFS filament sync, and the Repetier G-code flavour.
- **2026-06-20** — Sliced jobs can be sent as a packaged 3MF, and a Microsoft Store (MSIX) channel.
- **2026-06-20** — Many printers (Bambu Lab X2D, Flashforge, Anycubic and others), and a Thai interface translation.
- **2026-03-23** — Printer-level wipe tower type setting (Type 2 recommended for MMU, cutter and toolchanger printers).
- **2026-03-23** — Official Flathub package.
- **2026-03-23** — New G-code preview ported from PrusaSlicer 2.8, with a redesigned tool position window.
- **2026-03-23** — Bambu Lab H2D and H2S support, part skip for Bambu printers, and a choice of network plugin version.
- **2026-03-23** — Modular printer-agent architecture, with filament sync for third-party AMS-style systems.
- **2026-03-23** — Per-feature flow ratio, brim following the elephant-foot compensation, auto-slice, instances, mesh subdivision and Draco (`.drc`) import.
- **2026-03-23** — Calibrations for input shaping (several firmwares) and cornering/jerk; temperature tower up to 500 °C.
- **2026-03-23** — About 15 new printer vendors and models, and several filament vendors.
- **2025-10-05** — New OrcaSlicer update system.
- **2025-10-05** — Extra solid infill layers, by interval or by a list of layers.
- **2025-10-05** — New infill rotation system, and infill line multiplier.
- **2025-10-05** — New infill patterns: lateral honeycomb, TPMS-FK and TPMS-D.
- **2025-10-05** — New calibrations: Input Shaping and Junction Deviation. The flow calibration is improved.
- **2025-10-05** — Fuzzy skin painting and extrusion mode.
- **2025-10-05** — New seam alignment: "Aligned back".
- **2025-10-05** — Resonance avoidance (ported from QIDI Slicer).
- **2025-10-05** — RIB walls for the wipe tower.
- **2025-10-05** — Ironing: in vase mode, on support interfaces, and with a fan speed setting.
- **2025-10-05** — Filament remapping for models that are already coloured.
- **2025-10-05** — STEP import dialog (ported from Bambu Studio).
- **2025-10-05** — Choice of coordinate system in the Move, Scale and Rotate gizmos, and new shortcuts.
- **2025-10-05** — Modernised interface: buttons, dialogs, icons, 2D plate, legend and G-code viewer.
- **2025-03-20** — Global filament library: a filament preset can be used on every printer.
- **2025-03-20** — Dependency setting (compatible printers) for filaments and processes.
- **2025-03-20** — User profiles are backed up at each OrcaSlicer update.
- **2025-03-20** — New infill patterns: 2D Lattice and Quartercubic.
- **2025-03-20** — New fuzzy skin styles (structured noise, Perlin).
- **2025-03-20** — Bridges: more settings, a fan speed for internal bridges, and a forced internal bridge angle.
- **2025-03-20** — Retraction on the last top layer, and Ironing Inset.
- **2025-03-20** — Brim painting, mouse ear brim, and vertical tree support painting.
- **2025-03-20** — Improved Measure and Assembly gizmos (ported from Bambu Studio).
- **2025-03-20** — Brim for objects placed inside the hole of another object.
- **2025-03-20** — PA pattern calibration in batch mode.
- **2025-03-20** — Optional automatic perspective on the orthogonal views.
- **2025-03-20** — Bambu Cool Plate SuperTack, and LAN support for Bambu printers.
- **2025-03-20** — `orcaslicer://` protocol, and an option not to load the printer and project settings from a 3MF.
- **2025-03-20** — Arachne algorithm updated (PrusaSlicer 2.9).
- **2025-03-20** — Flatpak package for Linux.
- **2024-10-28** — Multi-tool printers (toolchangers).
- **2024-10-28** — Adaptive Pressure Advance.
- **2024-10-28** — Flow calibration in YOLO mode.
- **2024-10-28** — Multi-material interlocking (ported from Cura).
- **2024-10-28** — Better support for MMUs with a filament cutter (ERCF v2, Filametrix…).
- **2024-10-28** — Per-object skirt and draft shield.
- **2024-10-28** — Filament shrinkage compensation in XY and in Z (ported from PrusaSlicer).
- **2024-10-28** — Pellet printers.
- **2024-10-28** — Travel slope (`travel_slope`) and MMU tool change time.
- **2024-10-28** — Textured Cool Plate.
- **2024-10-28** — Fuzzy skin with a modifier.
- **2024-10-28** — Duplicating a plate with its objects.
- **2024-10-28** — The `data_dir` folder next to the application is used when it exists.
- **2024-10-28** — Stealth mode choice in the setup wizard.
- **2024-10-28** — Hardened steel nozzle type (HSN).
- **2024-06-21** — New icons.
- **2024-06-21** — Models open directly from Printables, Thingiverse and MakerWorld (Windows).
- **2024-06-21** — Cross Hatch infill pattern, and an infill direction setting.
- **2024-06-21** — Precise Z Height.
- **2024-06-21** — ESP3D connection for wireless printing.
- **2024-06-21** — Several Bambu printers managed together, and less purging with AMS retraction.
- **2024-06-21** — Touchpad-friendly 3D navigation, and an improved 3D navigator.
- **2024-06-21** — Z offset in the Pressure Advance calibration.
- **2024-06-21** — `model_name` and `plate_number` placeholders.
- **2024-06-21** — Improved thumbnails.
- **2024-06-21** — Minimum skirt and draft shield length.
- **2024-03-30** — Scarf joint seam, with an overhang threshold.
- **2024-03-30** — Small area flow compensation.
- **2024-03-30** — Direct adaptive bed mesh (Marlin, Klipper, RRF).
- **2024-03-30** — 3D navigator.
- **2024-03-30** — Print order inside each layer, and wall direction.
- **2024-03-30** — Counterbore hole bridging (ported from SuperSlicer).
- **2024-03-30** — Setting for the amount of internal bridges.
- **2024-03-30** — Configurable short wall cleanup for Arachne.
- **2024-03-30** — Custom G-code editor (ported from PrusaSlicer).
- **2024-03-30** — Warning when the speed, acceleration or jerk exceeds the machine limits.
- **2024-03-30** — New 3D Honeycomb infill, rewritten.
- **2024-03-30** — Option to turn the Bambu network plugin on or off.
- **2024-03-30** — SimplyPrint, Obico and Flashforge 5M connections, and a custom IP camera.
- **2024-03-30** — Project info editor, and plate renaming.

## Changed

- **2026-11-21** — Prusa CORE One overhang slowdown, and the Snapmaker U1 rod clearance check, in the profiles.
- **2026-11-07** — Faster startup, slicing (up to twice as fast) and G-code export; the G-code is deterministic.
- **2026-11-07** — Orca Cloud is shown in the Home tab.
- **2026-11-07** — Bambu Lab printers default to 3MF output; each filament has one ID; the Orca Filament Library is updated over the air.
- **2026-11-07** — Profile updates between releases are back on (off in Stealth mode).
- **2026-06-20** — User profiles sync through Orca Cloud instead of Bambu Cloud; logging in migrates the existing presets. The Bambu Cloud login stays for devices.
- **2026-06-20** — Redesigned printer selection dialog, unified setup guide, and a skirt overhaul.
- **2026-06-20** — "Slow down for curled perimeters" is off by default.
- **2026-03-23** — Interface redesign: Preferences, compact printer selection, canvas menu, accordion main tabs and a dynamic title bar.
- **2026-03-23** — The wiki moved to orcaslicer.com/wiki.
- **2026-03-23** — Adaptive Volumetric Speed is hidden behind developer mode; "flow rate" is renamed "flow ratio" in the calibration.

## Fixed

- **2026-11-21** — Slicing crashes on some projects, an empty first layer with a prime tower, and an OpenGL start failure.
- **2026-11-21** — STEP imports missing faces, arrange of bed-wide parts, and Measure/Assemble on stretched objects.
- **2026-11-21** — Linux AppImage freezing on Wayland, cloud plugin updates on Windows, and building from source.
- **2026-11-14** — Security: AMF files freezing the app, plugin packages now installed over a trusted connection, and the HTTPS CA file for Bambu LAN printers honoured.
- **2026-11-14** — Bambu LAN printers saved before 2.5.0, Creality Upload and Print, the Moonraker port, and filament sync slots.
- **2026-11-14** — Object copies, height ranges, spiral vase with modifiers, and CLI crashes on multi-nozzle projects.
- **2026-11-14** — Crashes when editing an object's speed and in Measure; usability of the mixed filament dialog.
- **2026-11-07** — Release-candidate blockers: bridge speed, scarf seams, wipe tower stops, a Mesh Boolean crash and a Linux freeze.
- **2026-07-07** — Presets pointing at renamed or deleted system profiles are repaired.
- **2026-07-07** — Cloud sync issues: filament overrides, preset names in messages, and two copies logging each other out.
- **2026-07-07** — Bambu network plugin install and update loop.
- **2026-07-07** — Several crashes, the print time estimate, and STEP Reload from Disk.
- **2026-06-28** — Skirt and brim regression in by-object (sequential) mode.
- **2026-06-28** — Filaments missing from the selection dialog, duplicate setting IDs, ambiguous AMS matches and preset resolution.
- **2026-06-28** — Fuzzy skin regression, CrealityPrint host errors, and blank web views on Wayland.
- **2026-06-20** — Tree support, fan and support Z bugs, LAN print hangs, and Windows paths with non-ASCII characters.
- **2026-03-23** — Security: path traversal hole in the 3MF import.
- **2026-03-23** — CLI segmentation faults, a black screen at startup on Linux, the wipe tower placed outside the bed, and regressions of the multi-tool extruder tab.
- **2025-10-05** — Handling of the G-code for Z moves.
- **2025-10-05** — Wrong printer model for the Prusa MK3S and MINI.
- **2025-10-05** — Crash when importing, in geometry-only mode, a 3MF saved with 2.3.1-alpha.
- **2025-10-05** — The rectilinear infill generated unoptimised paths.
- **2025-10-05** — The "Printer Config Bundle" export was sometimes refused.
- **2025-10-05** — Many fixes: vase mode, skirt, infill anchoring, wall avoidance, wipe tower, brims, tree supports and interface scaling.
- **2025-10-05** — Security vulnerability CVE-2024-45492 (libexpat).
- **2025-03-20** — Slow upload of large files to Bambu printers.
- **2025-03-20** — Crash when resetting filament presets.
- **2025-03-20** — Wrong first layer temperature with ooze prevention in by-object printing.
- **2025-03-20** — Crash with a bottom support interface set to "same as top".
- **2024-10-28** — Nozzle hitting the walls during travels with the scarf joint seam.
- **2024-10-28** — Inner/Outer/Inner mode with Arachne in some edge cases.
- **2024-10-28** — Crash when loading a G-code file twice, and during the PA pattern calibration.
- **2024-10-28** — Various wipe tower bugs.
- **2024-06-26** — Small area flow compensation no longer worked.
- **2024-06-26** — Sometimes wrong slicing results for multi-material models on Mac.
- **2024-06-26** — Mirror operation.
- **2024-06-26** — Failed upload of large G-code files to PrusaLink.
- **2024-06-21** — Fuzzy skin is finally uniform and random (no more visible patterns along the Z axis).
- **2024-06-21** — A top surface was sometimes taken for a bridge.
- **2024-03-30** — Filament load and unload time ignored in the time estimate.
- **2024-03-30** — Top surface detection in edge cases.

## Removed

- **2026-06-20** — "Auto" wall direction option.
- **2025-10-05** — Sensitive data removed from 3MF files.
- **2025-10-05** — Old "classic" overhang speed code.
- **2025-10-05** — Bambu server error dialog, and the automatic connection to the default Bambu printer at startup.
- **2025-03-20** — Grid is no longer the default infill; Crosshatch replaces it.
- **2024-10-28** — `overhang_speed_classic` option deprecated. Slowing down for curled perimeters is on by default.
- **2024-03-30** — The scarf joint seam flow ratio is only shown in developer mode.
- **2024-03-30** — Encrypted Bambu network log removed. The default log level becomes "warning".
