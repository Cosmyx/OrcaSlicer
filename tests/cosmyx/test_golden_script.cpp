// Checks of the wxWidgets-free half of the GUI goldens driver: script parsing,
// generator expansion, command classification, surface ids, the menu tree text
// golden and the protocol v1 events (decisions 0162-0178).

#include <catch2/catch_test_macros.hpp>

#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "slic3r/GUI/Cosmyx/logic/GoldenScript.hpp"

using namespace Slic3r::GUI::Cosmyx::Golden;

namespace {

// Smallest valid script, extended by each test.
std::string script_text(const std::string& steps, const std::string& menu_items = "{}", const std::string& extra = "")
{
    return R"({"protocol": 1, "window": {"client_size": [1280, 800]}, "language": "en_US",)" + extra +
           R"( "fixtures": {"model": "resources:handy_models/OrcaCube_v2.drc"}, "steps": )" + steps +
           R"(, "menu_items": )" + menu_items + "}";
}

Script parsed(const std::string& text)
{
    Script                   script;
    std::vector<std::string> errors;
    const bool               ok = parse_script(text, script, errors);
    INFO((errors.empty() ? std::string() : errors.front()));
    REQUIRE(ok);
    return script;
}

std::vector<std::string> parse_errors(const std::string& text)
{
    Script                   script;
    std::vector<std::string> errors;
    CHECK_FALSE(parse_script(text, script, errors));
    return errors;
}

bool any_contains(const std::vector<std::string>& messages, const std::string& part)
{
    for (const std::string& message : messages)
        if (message.find(part) != std::string::npos)
            return true;
    return false;
}

const Step* find_step(const std::vector<Step>& steps, const std::string& id)
{
    for (const Step& step : steps)
        if (step.id == id)
            return &step;
    return nullptr;
}

} // namespace

TEST_CASE("Slugs are lower-case ASCII words joined by dashes", "[cosmyx][GoldenScript]")
{
    CHECK(slug("Basic information") == "basic-information");
    CHECK(slug("help_about") == "help-about");
    CHECK(slug("  Machine G-code  ") == "machine-g-code");
    CHECK(slug("Layers and perimeters") == "layers-and-perimeters");
    CHECK(slug("3DBenchy") == "3dbenchy");
    CHECK(slug("Caf\xC3\xA9 menu") == "caf-menu");
    CHECK(slug("---") == "");
}

TEST_CASE("Surface ids are two digits and a slug", "[cosmyx][GoldenScript]")
{
    CHECK(is_valid_surface_id("00-start"));
    CHECK(is_valid_surface_id("40-preferences-general"));
    CHECK_FALSE(is_valid_surface_id("0-start"));
    CHECK_FALSE(is_valid_surface_id("00-Start"));
    CHECK_FALSE(is_valid_surface_id("00-start-"));
    CHECK_FALSE(is_valid_surface_id("00--start"));
    CHECK_FALSE(is_valid_surface_id("00 start"));
}

TEST_CASE("Capture kinds round-trip through their names", "[cosmyx][GoldenScript]")
{
    for (CaptureKind kind : {CaptureKind::Main, CaptureKind::Dialog, CaptureKind::Auto, CaptureKind::Menu, CaptureKind::Menubar,
                             CaptureKind::None}) {
        CaptureKind parsed_kind = CaptureKind::None;
        REQUIRE(parse_capture_kind(to_string(kind), parsed_kind));
        CHECK(parsed_kind == kind);
    }
    CaptureKind unused = CaptureKind::Main;
    CHECK_FALSE(parse_capture_kind("window", unused));
}

TEST_CASE("A valid script parses with its defaults", "[cosmyx][GoldenScript]")
{
    const Script script = parsed(script_text(R"([{"id": "00-start", "assert": ["canvas_ready"]},
        {"id": "10-tab-home", "do": [{"tab": "home"}], "settle_ms": 1200},
        {"id": "90-slice-layer", "do": [{"command": "go_to_layer", "param": "50"}], "os": ["linux"]}])"));
    CHECK(script.protocol == 1);
    CHECK(script.client_width == 1280);
    CHECK(script.client_height == 800);
    CHECK(script.language == "en_US");
    CHECK(script.settle_ms == 800);
    CHECK(script.step_timeout_s == 30);
    REQUIRE(script.entries.size() == 3);
    CHECK(script.entries[0].step.capture == CaptureKind::Main);
    CHECK(script.entries[0].step.close);
    CHECK(script.entries[1].step.actions == std::vector<Action>{{"tab", "home", ""}});
    CHECK(script.entries[1].step.settle_ms == 1200);
    CHECK(script.entries[2].step.actions == std::vector<Action>{{"command", "go_to_layer", "50"}});
    CHECK(script.entries[2].step.os == std::vector<std::string>{"linux"});
}

TEST_CASE("Script errors are all reported", "[cosmyx][GoldenScript]")
{
    CHECK(any_contains(parse_errors("not json"), "not valid JSON"));
    CHECK(any_contains(parse_errors(R"({"protocol": 2, "window": {"client_size": [1, 1]}, "language": "en_US", "steps": []})"),
                       "\"protocol\" must be 1"));
    CHECK(any_contains(parse_errors(script_text(R"([{"id": "00-a", "do": [{"jump": "x"}]}])")), "unknown action \"jump\""));
    CHECK(any_contains(parse_errors(script_text(R"([{"id": "00-a", "do": [{"tab": "x", "command": "y"}]}])")), "one kind only"));
    CHECK(any_contains(parse_errors(script_text(R"([{"id": "00-a", "capture": "window"}])")), "unknown capture kind"));
    CHECK(any_contains(parse_errors(script_text(R"([{"id": "00-a", "skip": ""}])")), "must give a reason"));
    CHECK(any_contains(parse_errors(script_text(R"([{"id": "00-a", "os": ["beos"]}])")), "unknown OS"));
    CHECK(any_contains(parse_errors(script_text(R"([{"id": "00-a", "mask": [[0, 0, 0, 4]]}])")), "\"mask\""));
    CHECK(any_contains(parse_errors(script_text(R"([{"id": "00-a", "colour": 1}])")), "unknown field \"colour\""));
    CHECK(any_contains(parse_errors(script_text(R"([{"generate": "commands"}])")), "two-digit \"section\""));
    CHECK(any_contains(parse_errors(script_text("[]", R"({"x": {"class": "maybe", "section": "30"}})")), "\"class\" must be one of"));
    CHECK(any_contains(parse_errors(script_text("[]", R"({"x": {"class": "skip"}})")), "must give a reason"));
    CHECK(any_contains(parse_errors(script_text("[]", R"({"x": {"class": "view"}})")), "\"section\" must be two digits"));
    CHECK(any_contains(parse_errors(script_text("[]", R"({"x": {"class": "view", "section": "70", "revert": "y"}})")),
                       "\"revert\" names no classified command"));
}

TEST_CASE("Every catalog key needs a rule and every rule a catalog key", "[cosmyx][GoldenScript]")
{
    const Script script = parsed(script_text("[]", R"({"help_about": {"class": "dialog", "section": "30"},
        "old_command": {"class": "skip", "reason": "gone"}})"));
    const std::vector<std::string> errors = classification_errors(script.rules, {"help_about", "new_command"});
    REQUIRE(errors.size() == 2);
    CHECK(any_contains(errors, "command \"new_command\" is not classified"));
    CHECK(any_contains(errors, "menu_items.old_command names no command"));
    CHECK(classification_errors(script.rules, {"help_about", "old_command"}).empty());
}

TEST_CASE("Generators expand to the surfaces the application reports", "[cosmyx][GoldenScript]")
{
    const Script script = parsed(script_text(
        R"([{"id": "00-start"}, {"generate": "menus"}, {"generate": "commands", "section": "30"},
            {"generate": "prefs"}, {"generate": "settings"}, {"generate": "commands", "section": "70"},
            {"id": "80-linux-only", "os": ["linux"]}])",
        R"({"help_about": {"class": "dialog", "section": "30"},
            "export_stl": {"class": "skip", "reason": "native file dialog"},
            "view_top": {"class": "view", "section": "70"},
            "obj_mirror_x": {"class": "toggle", "section": "70"},
            "plate_add": {"class": "view", "section": "70", "revert": "plate_delete"},
            "plate_delete": {"class": "skip", "reason": "run as the revert of plate_add", "section": "70"},
            "obj_delete": {"class": "any", "section": "70", "restore": true, "settle_ms": 1500}})"));
    Inventory inventory;
    inventory.os           = "windows";
    inventory.command_keys = {"help_about", "export_stl", "view_top", "obj_mirror_x", "plate_add", "plate_delete", "obj_delete"};
    inventory.menus        = {{"file", "File"}, {"main", "Main"}};
    inventory.settings_pages = {{"process", "Quality"}, {"printer", "Machine G-code"}};

    std::vector<std::string> errors;
    const std::vector<Step>  steps = expand(script, inventory, errors);
    INFO((errors.empty() ? std::string() : errors.front()));
    CHECK(errors.empty());

    std::vector<std::string> ids;
    for (const Step& step : steps)
        ids.push_back(step.id);
    CHECK(ids == std::vector<std::string>{"00-start", "20-menu-file", "20-menu-main", "20-menu-tree", "30-help-about",
                                          "40-preferences-general", "40-preferences-files", "40-preferences-behaviour",
                                          "40-preferences-control", "40-preferences-graphics", "40-preferences-online",
                                          "50-settings-process-quality", "50-settings-printer-machine-g-code", "70-view-top",
                                          "70-obj-mirror-x", "70-plate-add", "70-plate-delete", "70-obj-delete", "99-export-stl"});

    CHECK(find_step(steps, "20-menu-file")->capture == CaptureKind::Menu);
    CHECK(find_step(steps, "20-menu-file")->actions == std::vector<Action>{{"menu", "file", "File"}});
    CHECK(find_step(steps, "20-menu-tree")->capture == CaptureKind::None);
    CHECK(find_step(steps, "30-help-about")->capture == CaptureKind::Dialog);
    CHECK(find_step(steps, "40-preferences-online")->actions == std::vector<Action>{{"prefs_tab", "online", ""}});
    CHECK(find_step(steps, "50-settings-printer-machine-g-code")->capture == CaptureKind::Auto);
    CHECK(find_step(steps, "50-settings-printer-machine-g-code")->actions ==
          std::vector<Action>{{"settings", "printer", "Machine G-code"}});
    CHECK(find_step(steps, "70-view-top")->after.empty());
    CHECK(find_step(steps, "70-obj-mirror-x")->after == std::vector<Action>{{"command", "obj_mirror_x", ""}});
    CHECK(find_step(steps, "70-plate-add")->after == std::vector<Action>{{"command", "plate_delete", ""}});
    CHECK(find_step(steps, "70-plate-delete")->skip == "run as the revert of plate_add");
    const Step* restored = find_step(steps, "70-obj-delete");
    CHECK(restored->capture == CaptureKind::Auto);
    CHECK(restored->settle_ms == 1500);
    CHECK(restored->after == std::vector<Action>{{"reset", "", ""}, {"load", "model", ""}, {"select_all", "", ""}});
    CHECK(find_step(steps, "99-export-stl")->skip == "native file dialog");
    CHECK(find_step(steps, "80-linux-only") == nullptr);
}

TEST_CASE("macOS menus are menu bar captures", "[cosmyx][GoldenScript]")
{
    const Script script = parsed(script_text(R"([{"generate": "menus"}])"));
    Inventory    inventory;
    inventory.os      = "macos";
    inventory.menubar = true;
    inventory.menus   = {{"file", "File"}, {"calibration", "Calibration"}};
    std::vector<std::string> errors;
    const std::vector<Step>  steps = expand(script, inventory, errors);
    CHECK(errors.empty());
    REQUIRE(steps.size() == 3);
    CHECK(steps[1].id == "20-menu-calibration");
    CHECK(steps[1].capture == CaptureKind::Menubar);
    CHECK(steps[1].actions == std::vector<Action>{{"menu", "calibration", "Calibration"}});
}

TEST_CASE("Expansion reports unclassified commands, duplicates and bad ids", "[cosmyx][GoldenScript]")
{
    const Script script = parsed(script_text(R"([{"id": "00-start"}, {"id": "00-start"}, {"id": "1-bad"}])"));
    Inventory    inventory;
    inventory.os           = "linux";
    inventory.command_keys = {"help_about"};
    std::vector<std::string> errors;
    expand(script, inventory, errors);
    CHECK(any_contains(errors, "command \"help_about\" is not classified"));
    CHECK(any_contains(errors, "duplicate surface id \"00-start\""));
    CHECK(any_contains(errors, "invalid surface id \"1-bad\""));
}

TEST_CASE("surfaces.txt lists every step and every exclusion", "[cosmyx][GoldenScript]")
{
    Step main;
    main.id = "00-start";
    Step dialog;
    dialog.id      = "30-help-about";
    dialog.capture = CaptureKind::Dialog;
    Step skipped;
    skipped.id   = "99-export-stl";
    skipped.skip = "native file dialog";
    CHECK(surfaces_text({main, dialog, skipped}, {{"tab-device", "needs a printer"}}) ==
          "00-start main\n30-help-about dialog\n99-export-stl skip native file dialog\nexclude tab-device needs a printer\n");
}

TEST_CASE("The menu tree text golden is stable and readable", "[cosmyx][GoldenScript]")
{
    MenuNode open;
    open.label = "&Open Project\tCtrl+O";
    MenuNode separator;
    separator.kind = MenuNode::Kind::Separator;
    MenuNode check;
    check.kind    = MenuNode::Kind::Check;
    check.label   = "Show &Labels";
    check.checked = true;
    MenuNode radio;
    radio.kind  = MenuNode::Kind::Radio;
    radio.label = "Save && Close";
    MenuNode disabled;
    disabled.label   = "Export";
    disabled.enabled = false;
    MenuNode recent;
    recent.kind     = MenuNode::Kind::Submenu;
    recent.label    = "Recent";
    recent.children = {disabled};
    CHECK(menu_tree_text("&File", {open, separator, check, radio, recent}) ==
          "File\n"
          "  Open Project Ctrl+O\n"
          "  ---\n"
          "  [x] Show Labels\n"
          "  [ ] Save & Close\n"
          "  Recent >\n"
          "    Export (disabled)\n");
}

TEST_CASE("Protocol events are one JSON object each", "[cosmyx][GoldenScript]")
{
    using nlohmann::json;
    const json hello = json::parse(hello_event(1, "2.6.0-8", "llvmpipe", "4.5", "1600x1000", 1.0, "linux"));
    CHECK(hello["seq"] == 1);
    CHECK(hello["event"] == "hello");
    CHECK(hello["protocol"] == protocol_version);
    CHECK(hello["GL_RENDERER"] == "llvmpipe");
    CHECK(hello["display"] == "1600x1000");

    const std::string line = capture_event(2, "30-help-about", {10, 20, 300, 200}, CaptureKind::Dialog, {{1, 2, 3, 4}}, {{5, 6, 7, 8}},
                                           2.0, "About", "");
    CHECK(line.find('\n') == std::string::npos);
    const json capture = json::parse(line);
    CHECK(capture["event"] == "capture");
    CHECK(capture["kind"] == "dialog");
    CHECK(capture["rect_px"] == json::array({10, 20, 300, 200}));
    CHECK(capture["masks"] == json::array({json::array({1, 2, 3, 4})}));
    CHECK(capture["webviews"] == json::array({json::array({5, 6, 7, 8})}));
    CHECK(capture["scale"] == 2.0);

    const json text = json::parse(text_event(3, "20-menu-tree", "File\n  Open\n"));
    CHECK(text["content"] == "File\n  Open\n");
    CHECK(json::parse(fail_event(4, "x", "why"))["reason"] == "why");
    CHECK(json::parse(done_event(5, 0))["errors"] == 0);
    CHECK(ack_file_name(7) == "ack-7");
    // The same inputs always give the same bytes.
    CHECK(capture_event(2, "a", {0, 0, 1, 1}, CaptureKind::Main, {}, {}, 1.0, "", "") ==
          capture_event(2, "a", {0, 0, 1, 1}, CaptureKind::Main, {}, {}, 1.0, "", ""));
}

TEST_CASE("The shipped golden script is valid", "[cosmyx][GoldenScript]")
{
    std::ifstream in(std::string(TEST_DATA_DIR) + "/../cosmyx/gui/script.json", std::ios::binary);
    REQUIRE(in.good());
    std::ostringstream text;
    text << in.rdbuf();
    Script                   script;
    std::vector<std::string> errors;
    const bool               ok = parse_script(text.str(), script, errors);
    INFO((errors.empty() ? std::string() : errors.front()));
    CHECK(ok);
    CHECK(script.language == "en_US");
    CHECK_FALSE(script.rules.empty());
}
