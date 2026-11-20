# feat/cosmyx-logs (PR #97)

## Purpose

Gives Cosmyx code its own log channel and its own log file. Cosmyx code logs with `COSMYX_LOG(level)` instead of
`BOOST_LOG_TRIVIAL(level)`; those records go to `cosmyx_<same time and pid as Orca's debug file>.log.N` in the folder of
Orca's current debug log (`data_dir()/log`), and Orca's own file no longer receives them. Upstream log records and files
are unchanged. The earlier CosmoSlice fork did this by editing upstream `utils.cpp` and `GUI_App.cpp`; here the whole
feature lives in two Cosmyx-owned files and needs no upstream hook of its own (decisions 0110 and 0111). The PR body states
"Upstream files touched: None".

## Parent and dependencies

- Parent: `DEV`. The branch's own commit range `origin/DEV..origin/feat/cosmyx-logs` also contains the foundation commits
  of PR #86 (T0: `6cbd27d0fc`, `f3947e5550`, `ab1a545017`, `57866a96b9`, `5fbe728f6f`, `39c40f609f`), because the
  foundation is not merged into DEV yet. The feature commits are only `138e5591bf`, `8ae413b78c`, `f3d6a9d6e8`,
  `815eb444b0`, `1a54759bd4`. Once #86 is on DEV the foundation commits drop out of the range.
- Other Cosmyx branches: none. It is independent of stealth mode, cloud, branding.
- Upstream APIs it calls: Boost.Log (`severity_channel_logger_mt`, `text_file_backend`, `synchronous_sink`, expressions),
  `Slic3r::data_dir()` and `Slic3r::get_log_file_name()` (declared in `src/libslic3r/Utils.hpp`, defined in
  `src/libslic3r/utils.cpp`), and the non-header global `g_log_sink` of `utils.cpp`, which `CosmyxLog.cpp` declares with
  `extern boost::shared_ptr<boost::log::sinks::synchronous_sink<boost::log::sinks::text_file_backend>> g_log_sink;`
  (line 30 of `CosmyxLog.cpp`). It also reads Orca's global severity filter set by `set_logging_level()` (it only relies
  on it, nothing is replaced).

## Changes

| File | Kind | What it does |
|---|---|---|
| `src/libslic3r/Cosmyx/CosmyxLog.hpp` | Cosmyx-owned | Declares `Cosmyx::LogLogger`, `log_channel()` ("Cosmyx"), `logger()`, `init_log(folder, name, rotation)`, `shutdown_log()`, `log_active()`, `log_file_path()`, `flush_log()`, `paired_log_file_name()` and the macro `COSMYX_LOG(sev)` (a `BOOST_LOG_CHANNEL_SEV`). Rotation size 100 MB, same as Orca. |
| `src/libslic3r/Cosmyx/CosmyxLog.cpp` | Cosmyx-owned | Function-local statics (no static-init logger), lazy sink registration on the first `COSMYX_LOG` once `g_log_sink` exists, file name derived from `get_log_file_name()` (`debug_X.log.0` becomes `cosmyx_X.log`), channel filter on the Cosmyx sink, and `!channel` filter set on Orca's `g_log_sink` so each file holds one channel. |
| `tests/cosmyx/test_cosmyx_log.cpp` | test | Six Catch2 cases, all tagged `[cosmyx][CosmyxLog]` (see Verification). |
| `wiki/decisions/0110-cosmyx-log-channel.md`, `0111-cosmyx-log-lazy-registration.md` | data (docs) | Decision register entries. |
| `CHANGELOG.md` | data | One line under `<!-- cosmyx-slot: T12 -->` in the `### libslic3r` area (see Shared files). |
| `scripts/cosmyx/tests/test_foundation.py` | test | Registers the T12 changelog slot in the slot checks (`815eb444b0`). |
| Foundation files (inherited from #86, not feature work) | Cosmyx-owned / CI / upstream hook | `src/libslic3r/Cosmyx/*.cmake/BedTemperatureOff/ChtNozzle/ConfigDefExtensions/GCodeHooks/IroningTemperature`, `src/slic3r/GUI/Cosmyx/Cosmyx.cmake/Cosmyx.hpp`, `tests/cosmyx/CMakeLists.txt`, `cosmyx_tests.cpp`, `test_cosmyx_foundation.cpp`, `justfile`, `.github/workflows/cosmyx-checks.yml`, `scripts/cosmyx/decisions.py`, `run_script_tests.py`, decisions 0001-0004. See upstream hooks below. |

Upstream hooks present in this branch's range (all inherited from the foundation, none added by the log feature):

| Upstream file | Hook line(s) | Anchor |
|---|---|---|
| `src/libslic3r/CMakeLists.txt` | `include(Cosmyx/Cosmyx.cmake) # Cosmyx` | right after `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${lisbslic3r_sources})` that follows `add_library(libslic3r STATIC ...)` |
| `src/slic3r/CMakeLists.txt` | `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx` | right after `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${SLIC3R_GUI_SOURCES})`, before `encoding_check(libslic3r_gui)` |
| `src/libslic3r/GCode.cpp` | `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx` | line 2, directly after `#include "ArcFitter.hpp"` |
| `src/libslic3r/PrintConfig.cpp` | `#include "Cosmyx/ConfigDefExtensions.hpp" // Cosmyx` (line 2, after `#include "PrintConfig.hpp"`) and `Cosmyx::extend_print_config_def(*this); // Cosmyx` | in `PrintConfigDef::PrintConfigDef()`, after `this->init_extruder_option_keys();` and before `assign_printer_technology_to_unknown(this->options, ptFFF);` |
| `tests/CMakeLists.txt` | `add_subdirectory(cosmyx) # Cosmyx` | between `add_subdirectory(slic3rutils)` and `add_subdirectory(fff_print)` |

## Rebase risk zones

Differences are `git diff origin/DEV upstream/v2.5.1` (added/removed lines, direction DEV to tag) and the count of DEV
commits touching the file since 2026-01-01.

| Upstream file / symbol | DEV vs v2.5.1 | Upstream churn |
|---|---|---|
| `src/libslic3r/utils.cpp` (`g_log_sink`, `get_log_file_name()`, `set_log_path_and_level()`) | `g_log_sink` and `get_log_file_name()` exist in both tags (v2.5.1 lines 241, 534; DEV lines 245, 565); file differs by 0 added, 46 removed lines (DEV has more code), anchors identical | 31 commits |
| `src/libslic3r/Utils.hpp` (`get_log_file_name()`, `data_dir()`) | declaration present in both (line 230) | low |
| `src/libslic3r/CMakeLists.txt` | 7 / 24 lines differ | 127 |
| `src/slic3r/CMakeLists.txt` | 1 / 11 lines differ | 205 |
| `src/libslic3r/GCode.cpp` | 147 / 269 differ (include block at the top stays) | 342 |
| `src/libslic3r/PrintConfig.cpp` | 30 / 307 differ (constructor sequence `init_fff_params(); init_extruder_option_keys();` present in both) | 385 |
| `tests/CMakeLists.txt` | 3 / 5 differ | 9 |

The logger itself depends only on `g_log_sink` having external linkage with that exact type. In v2.5.1 `g_log_sink`
is still a non-static global of the same type, so the link works unchanged.

## Intent to preserve

- Cosmyx records go to their own file, and only Cosmyx records go there. Orca's file never contains them, and upstream
  records never reach the Cosmyx file.
- No upstream hook for logging: the sink registers itself on the first `COSMYX_LOG`, only once Orca's file sink
  exists. Before that (start-up, CLI, old macOS without file logging) Cosmyx records behave like upstream ones, because
  Boost.Log stops using its default console sink as soon as any sink exists.
- Nothing is built during static initialisation (function-local statics), the crash the CosmoSlice fork hit.
- Cosmyx records still pass Orca's global severity filter, so the preference log level applies to them.
- File layout: same time/pid pairing, 100 MB rotation, `.N` index from 0, auto flush.
- If upstream renames, makes `static`, or wraps `g_log_sink` (or sets its own filter on its file sink), do not patch
  `utils.cpp`: change the `extern` declaration or obtain the sink through a new public upstream accessor in
  `CosmyxLog.cpp`. `git grep set_filter` in `utils.cpp` after a rebase shows whether the sink filter is now
  overwritten (the core-wide `boost::log::core::get()->set_filter` in `set_logging_level()` is a different filter and is
  expected).
- If upstream moves logging to another mechanism, re-implement as a channel filter on whatever file sink upstream
  creates, still without editing the upstream file.

## Verification

- Catch2, binary `cosmyx_tests`, run with `ctest -C Release -R cosmyx` or `cosmyx_tests "[CosmyxLog]"`. Cases:
  "Cosmyx log sink is not registered while Orca has no log file", "Cosmyx records land in the Cosmyx file, upstream
  records do not", "Cosmyx log file rotates at its size limit", "Cosmyx log init fails cleanly on an unusable folder",
  "Cosmyx log file name is paired with Orca's", "Cosmyx log channel is named Cosmyx".
- Foundation Catch2 cases in `test_cosmyx_foundation.cpp` (tag `[cosmyx]`) prove the hooks link.
- Script tests: `just test-scripts` (workflow `.github/workflows/cosmyx-checks.yml`, Ubuntu, macOS, Windows) which includes
  `scripts/cosmyx/tests/test_foundation.py` (slot T12 must exist once); `just decisions` validates the register.
- Manual: launch the app, trigger a Cosmyx log call, check `data_dir()/log` holds `debug_*.log.0` without Cosmyx lines and
  `cosmyx_*.log.0` with them.
- C++ is built only in CI (`build_all.yml` started by `workflow_dispatch` on the branch, or the integration branch).

## Known pitfalls

- `1a54759bd4`: with Boost filesystem v3, `path("data/log") / ""` appends nothing, so the paired-name test failed. A
  folder is written with a trailing separator (file name "."); `paired_log_file_name` returns empty for "." and "..".
  The test was fixed, not the code.
- `815eb444b0`: the foundation script test counts changelog slots; adding the T12 line required registering the slot in
  `test_foundation.py`. A rebase that rewrites `CHANGELOG.md` must keep exactly one `<!-- cosmyx-slot: T12 -->` marker,
  with blank-line separation, in its area (the slot tests check count, blank-line separation, area order and the list in
  decision 0003).
- Because the foundation is stacked into the range, a rebase onto a new tag replays the foundation commits too; resolve
  them once and identically on every branch.

## Shared files with other branches

- `CHANGELOG.md`: every feature edits it, each under its own `cosmyx-slot` marker (T12 here). Conflicts are avoided by
  the slots, not by luck: never move markers.
- `wiki/decisions/0001-0004`, `wiki/decisions/README.md`, `scripts/cosmyx/tests/test_foundation.py`, `justfile`,
  `.github/workflows/cosmyx-checks.yml`: foundation files shared by every branch.
- `tests/cosmyx/CMakeLists.txt` globs `test_*.cpp`, so adding tests needs no shared edit.
- `src/libslic3r/Cosmyx/Cosmyx.cmake` globs `*.cpp`/`*.hpp`, no shared edit for new sources.
- No other feature touches `utils.cpp` or hooks logging.
