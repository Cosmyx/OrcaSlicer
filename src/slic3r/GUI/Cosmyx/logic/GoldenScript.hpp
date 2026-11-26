#ifndef slic3r_GUI_Cosmyx_GoldenScript_hpp_
#define slic3r_GUI_Cosmyx_GoldenScript_hpp_

// wxWidgets-free half of the GUI goldens driver (decisions 0162-0178,
// wiki/cosmyx/gui-goldens.md).
//
// The driver (GoldenDriver.cpp) walks the application through a script,
// tests/cosmyx/gui/script.json, and asks the external harness
// (scripts/cosmyx/gui_goldens) to capture each surface. Everything that does
// not need a live application lives here, so cosmyx_tests checks it:
//
// - parsing and validating the script;
// - expanding its generators (every menu, every Preferences tab, every
//   settings page, every catalog command) against what the running
//   application reports;
// - checking that every NativeCommands catalog key is classified;
// - surface ids (slugs), the menu tree text golden and the surfaces list;
// - the protocol v1 events the driver writes to events.jsonl.

#include <map>
#include <string>
#include <vector>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {
namespace Golden {

// Version of the script format and of the events.jsonl protocol. The harness
// refuses a driver that announces another one.
inline constexpr int protocol_version = 1;

// What a step captures once its actions ran.
// - Main: the main window; a window that opens is an error.
// - Dialog: the top-level window the actions opened; none is an error.
// - Auto: that window if one opened, else the main window.
// - Menu: the popup menu the actions opened (the harness finds it on screen
//   and closes it with Escape).
// - Menubar: one menu of the native menu bar (macOS), opened by the harness.
// - None: nothing to capture (state changes, the G-code copy, text goldens).
enum class CaptureKind { Main, Dialog, Auto, Menu, Menubar, None };

std::string to_string(CaptureKind kind);
bool        parse_capture_kind(const std::string& text, CaptureKind& kind);

// One thing the driver does. `kind` is one of action_kinds(); `arg` is its
// value in the script ({"tab": "home"} gives kind "tab", arg "home").
struct Action
{
    std::string kind;
    std::string arg;
    std::string param;

    bool operator==(const Action& other) const
    {
        return kind == other.kind && arg == other.arg && param == other.param;
    }
};

// The action kinds the driver understands, in a fixed order:
// tab, command, prefs_tab, settings, load, reset, select_all, context_menu,
// menu, wait, slice, copy_gcode, close_tips.
const std::vector<std::string>& action_kinds();

// A rectangle in pixels, relative to the captured image.
struct Rect
{
    int x{0};
    int y{0};
    int w{0};
    int h{0};

    bool operator==(const Rect& other) const { return x == other.x && y == other.y && w == other.w && h == other.h; }
};

struct Step
{
    std::string              id;
    std::vector<Action>      actions;
    CaptureKind              capture{CaptureKind::Main};
    bool                     close{true};
    std::vector<Rect>        masks;
    std::vector<std::string> asserts;
    std::vector<std::string> os;
    std::string              skip;
    int                      settle_ms{-1}; // -1: the script default
    std::vector<Action>      after;
};

// How a NativeCommands catalog command is covered.
// - dialog: running it opens a window, which is captured and closed.
// - view: running it changes the main window, which is captured.
// - toggle: like view, then the command runs again to undo itself.
// - any: a window is captured if one opens, else the main window.
// - skip: not run; `reason` says why (native file dialog, browser, network...).
struct CommandRule
{
    std::string key;
    std::string cls;
    std::string reason;
    std::string section;
    std::string param;
    std::string revert;  // command run after the capture to undo it
    bool        restore{false}; // reload the fixture after the capture
    int         settle_ms{-1};
};

const std::vector<std::string>& command_classes();

// One generator entry of the script, expanded at run time.
struct Generator
{
    std::string kind;    // menus, prefs, settings, commands
    std::string section; // commands only: the section whose rules it expands
};

struct Exclusion
{
    std::string surface;
    std::string reason;
};

// A script entry: a literal step or a generator, kept in script order.
struct Entry
{
    bool      is_generator{false};
    Step      step;
    Generator generator;
};

struct Script
{
    int                                protocol{0};
    int                                client_width{0};
    int                                client_height{0};
    std::string                        language;
    int                                settle_ms{800};
    int                                step_timeout_s{30};
    std::map<std::string, std::string> fixtures;
    std::vector<Entry>                 entries;
    std::vector<CommandRule>           rules; // the "menu_items" object, sorted by key
    std::vector<Exclusion>             excludes;
};

// Parses and validates script.json. On failure, returns false and fills
// `errors`, one message per problem.
bool parse_script(const std::string& text, Script& script, std::vector<std::string>& errors);

// A menu the driver can show: a popup of the custom top bar (Windows, Linux)
// or a title of the native menu bar (macOS).
struct MenuTarget
{
    std::string slug;
    std::string label;
};

// One page of one settings tab ("process", "filament", "printer").
struct SettingsPage
{
    std::string tab;
    std::string page;
};

// What the running application reports, so the generators expand to the
// surfaces it really has.
struct Inventory
{
    std::string               os; // windows, macos, linux
    std::vector<std::string>  command_keys; // NativeCommands::catalog() order
    std::vector<MenuTarget>   menus;
    bool                      menubar{false}; // menus are native menu bar titles
    std::vector<SettingsPage> settings_pages;
};

// The Preferences tabs, in PreferencesTab order.
const std::vector<std::string>& preferences_tabs();

// Lower-case ASCII slug: letters and digits kept, every other run of
// characters (spaces, punctuation, '_', non-ASCII bytes) becomes one '-',
// with no '-' at either end. "Basic information" gives "basic-information".
std::string slug(const std::string& text);

// Whether `id` is a valid surface id: two digits, '-', then a slug
// ("40-preferences-general").
bool is_valid_surface_id(const std::string& id);

// Catalog keys with no rule, and rules naming no catalog key. Both are
// errors: a new upstream command must be classified before it can ship, and
// a stale rule hides a removed one.
std::vector<std::string> classification_errors(const std::vector<CommandRule>& rules, const std::vector<std::string>& catalog_keys);

// The steps to run on this application: literal steps kept, generators
// expanded, steps for other OSes dropped. Fills `errors` with duplicate ids,
// invalid ids and classification errors.
std::vector<Step> expand(const Script& script, const Inventory& inventory, std::vector<std::string>& errors);

// surfaces.txt: one line per step, "<id> <capture kind>" or
// "<id> skip <reason>", then one "exclude <surface> <reason>" line per
// exclusion. Ends with a newline.
std::string surfaces_text(const std::vector<Step>& steps, const std::vector<Exclusion>& excludes);

// One menu item, as wxWidgets reports it.
struct MenuNode
{
    enum class Kind { Normal, Check, Radio, Separator, Submenu };

    Kind                  kind{Kind::Normal};
    std::string           label; // may hold '&' mnemonics and a "\t<accel>" suffix
    bool                  enabled{true};
    bool                  checked{false};
    std::vector<MenuNode> children;
};

// Text golden of one menu: its title, then one line per item, indented by two
// spaces per level. "---" is a separator; "[x] " / "[ ] " prefix check and
// radio items; " (disabled)" ends a disabled item; "\t<accel>" is kept as
// " <accel>" after the label. '&' mnemonics are removed ("&&" stays "&").
std::string menu_tree_text(const std::string& title, const std::vector<MenuNode>& items);

// Protocol v1 events, one JSON object per line (no trailing newline).
// rect_px is [x, y, w, h] in screen pixels; masks (from the script, always
// painted) and webviews (painted only where tolerance.json says so) are
// [x, y, w, h] relative to the captured image.
std::string hello_event(int seq, const std::string& app_version, const std::string& gl_renderer, const std::string& gl_version,
                        const std::string& display, double scale, const std::string& os);
std::string capture_event(int seq, const std::string& id, const Rect& rect_px, CaptureKind kind, const std::vector<Rect>& masks,
                          const std::vector<Rect>& webviews, double scale, const std::string& title, const std::string& menu);
std::string text_event(int seq, const std::string& id, const std::string& content);
std::string fail_event(int seq, const std::string& id, const std::string& reason);
std::string done_event(int seq, int errors);

// Name of the file the harness writes once it handled event `seq`.
std::string ack_file_name(int seq);

} // namespace Golden
} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_GoldenScript_hpp_
