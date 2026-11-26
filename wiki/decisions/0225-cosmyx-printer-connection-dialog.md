# 0225. Cosmyx physical printer dialog

## Status

Accepted.

## Context

The "Connection" button of the printer title bar opens upstream's
`PhysicalPrinterDialog`, which shows every print host option (host type,
address, web UI, API key, certificates, user and password, ports, discovery
buttons). A Cosmyx machine needs three values only, the ones the customer
procedure gives: the machine address and its API key, plus the preset name.
The machine serves an OctoPrint-compatible API under `/octoprint/`, its web
interface under `/mission-control-viewer/`, and its own CosmOS API under
`/api/` (identity, profile, hot ends, camera).

The user's choices:

- Two tabs, "Setup" and "Machine information".
- The address is an IPv4 address or an RFC 1123 host name, with an optional
  port.
- OK writes only `host_type`, `print_host`, `print_host_webui` and
  `printhost_apikey`; every other print host key is left as it is.
- The address is prefilled only when `print_host` has the form this dialog
  writes; there is no migration and no note for other values.
- "Machine information" is enabled once the settings are saved and a
  connection test succeeded, manual or automatic: one runs in the background
  when the dialog opens on an already configured machine.

The only live entry point of the upstream dialog is the title bar button
handler in `Sidebar::Sidebar()` (Plater.cpp); the sidebar button that also
opened it is commented out upstream.

## Decision

- Upstream hook, `src/slic3r/GUI/Plater.cpp`, two lines tagged `// Cosmyx`
  (decision 0002 placement):
  - after `#include "Plater.hpp"` (line 1):
    `#include "Cosmyx/CosmyxPrinterConnectionDialog.hpp" // Cosmyx`
  - first statement of the `m_printer_connect` button handler:
    `if (Cosmyx::show_cosmyx_printer_dialog(this->GetParent())) return; // Cosmyx`
  `show_cosmyx_printer_dialog()` returns false without showing anything when
  `current_printer_is_cosmyx()` (decision 0222) is false, so upstream's dialog
  opens unchanged for every other printer.
- `src/slic3r/GUI/Cosmyx/logic/CosmyxPrinterConnection.{hpp,cpp}`
  (wxWidgets-free): `check_host()` trims the blanks around the value, refuses
  a scheme, a path, user info, inner blanks and IPv6, accepts four dotted
  numbers only as a valid IPv4 address (no leading zeros), otherwise an
  RFC 1123 host name (labels of 1-63 letters, digits and hyphens, not
  starting or ending with a hyphen, at most 253 characters, a top label that
  is not all digits), then an optional port 1-65535; the host name is
  lower-cased and the port loses its leading zeros. URL builders
  (`http://<host>/octoprint/`, `http://<host>/mission-control-viewer/`,
  `http://<host>/api/...`), the reverse parser of the OctoPrint URL (trailing
  slash optional, scheme case-insensitive, nothing else accepted), the four
  values written on save, the saved connection read from a preset
  (`host_type` octoprint and a parsable `print_host`), the unlock rule and
  the classification of failed requests (401, 403, 404, timeout, unreachable,
  other HTTP error, unreadable answer).
- The unlock rule compares values: the tab is enabled when the saved preset
  describes a connection and the last successful test checked that same host
  and key. Typing new values does not lock the tab; saving them does until
  they are tested, and a save starts that test in the background.
- `src/slic3r/GUI/Cosmyx/logic/CosmyxPrinterConnectionInfo.{hpp,cpp}`: readers
  of `GET /api/machine/device`, `/api/machine/profile`, `/api/machine/nozzles`
  and `/api/camera`, with nlohmann::json, tolerant to missing, null, wrongly
  typed and extra fields; only a body that is not a JSON object fails.
- `src/slic3r/GUI/Cosmyx/CosmyxPrinterConnectionDialog.{hpp,cpp}`: a
  `DPIDialog` with a two-button tab strip over a `wxSimplebook`. The tab
  strip is made of Orca `Button`s rather than `TabCtrl`, because `TabCtrl`
  cannot disable or veto a tab and the spec wants a greyed tab.
  - Setup: "Save as" uses upstream's default name (`<system name> - Copy`,
    the user preset name, or "Untitled") and `check_preset_name()`. Saving
    writes the four keys into the edited printer preset and calls
    `Tab::save_preset("", false, false, true, name)` like upstream's `OnOK`;
    the dialog stays open when the save does not happen. Bottom buttons are
    Apply (save, stay open, so the information tab can unlock in the same
    session), OK (save and close) and Cancel.
  - The connection test is upstream's `PrintHost::test()` of the OctoPrint
    host (`GET <print_host>api/version` with `X-Api-Key`), run on a copy of
    the edited config so testing never changes the preset, with upstream's
    success and failure messages.
  - Machine information: read-only rows, a Refresh button, one message per
    failed section. The key is sent as `X-Api-Key`. When the identity request
    cannot reach the machine or is refused, the other three are not sent.
    A 404 on the camera reads "No camera".
  - Every request runs on a detached `std::thread` (5 s connection timeout,
    10 s total for the CosmOS reads) and reports through
    `wxGetApp().CallAfter`, guarded by a shared alive flag and a generation
    counter, so closing the dialog or starting a newer request drops stale
    answers. The UI thread never blocks.
- Strings live in the `printer-connection` catalogue
  (`localization/cosmyx/printer-connection/`, extracted with
  `just i18n-extract`, decision 0080); French is translated, the other
  languages wait for the translation pass. Strings upstream already has
  ("Physical Printer", "Yes", "No", "Refresh", "Model", ...) keep upstream's
  translations.

## Consequences

- GUI goldens to add once the GUI golden suite (T16) can select a Cosmyx
  printer, all with a Cosmyx printer selected and mocked HTTP answers: Setup
  empty, Setup filled, Machine information greyed, Machine information filled
  (anonymised samples of the tests).
- `scripts/cosmyx/tests/test_printer_connection_hook.py` pins the two hook
  lines and checks the dialog source writes only the four keys and runs its
  requests off the UI thread; `tests/cosmyx/test_cosmyx_printer_connection*.cpp`
  cover the logic.
- Removing it: delete the two Plater.cpp lines, the dialog, the two logic
  files, their tests and `localization/cosmyx/printer-connection/`. Presets
  saved by the dialog stay valid OctoPrint presets.
