#include "GoldenScript.hpp"

#include <algorithm>
#include <cmath>
#include <exception>
#include <regex>
#include <set>
#include <sstream>

#include <nlohmann/json.hpp>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {
namespace Golden {

namespace {

using json = nlohmann::json;

const char* const capture_names[] = {"main", "dialog", "auto", "menu", "menubar", "none"};

bool read_rect(const json& value, Rect& rect)
{
    if (!value.is_array() || value.size() != 4)
        return false;
    for (const json& item : value)
        if (!item.is_number_integer())
            return false;
    rect = {value[0].get<int>(), value[1].get<int>(), value[2].get<int>(), value[3].get<int>()};
    return rect.w > 0 && rect.h > 0;
}

bool read_string_list(const json& value, std::vector<std::string>& out)
{
    if (!value.is_array())
        return false;
    for (const json& item : value) {
        if (!item.is_string())
            return false;
        out.push_back(item.get<std::string>());
    }
    return true;
}

// {"tab": "home"} or {"command": "go_to_layer", "param": "50"}.
bool read_action(const json& value, Action& action, std::string& error)
{
    if (!value.is_object()) {
        error = "an action must be an object";
        return false;
    }
    for (auto it = value.begin(); it != value.end(); ++it) {
        if (it.key() == "param") {
            if (!it.value().is_string()) {
                error = "\"param\" must be a string";
                return false;
            }
            action.param = it.value().get<std::string>();
            continue;
        }
        const std::vector<std::string>& kinds = action_kinds();
        if (std::find(kinds.begin(), kinds.end(), it.key()) == kinds.end()) {
            error = "unknown action \"" + it.key() + "\"";
            return false;
        }
        if (!action.kind.empty()) {
            error = "an action names one kind only";
            return false;
        }
        action.kind = it.key();
        if (it.value().is_string())
            action.arg = it.value().get<std::string>();
        else if (it.value().is_number_integer())
            action.arg = std::to_string(it.value().get<long long>());
        else {
            error = "the value of \"" + it.key() + "\" must be a string or an integer";
            return false;
        }
    }
    if (action.kind.empty()) {
        error = "an action names no kind";
        return false;
    }
    return true;
}

bool read_actions(const json& value, std::vector<Action>& out, std::string& error)
{
    if (!value.is_array()) {
        error = "actions must be a list";
        return false;
    }
    for (const json& item : value) {
        Action action;
        if (!read_action(item, action, error))
            return false;
        out.push_back(action);
    }
    return true;
}

const std::set<std::string>& known_os()
{
    static const std::set<std::string> names{"windows", "macos", "linux"};
    return names;
}

const std::set<std::string>& known_asserts()
{
    static const std::set<std::string> names{"canvas_ready", "slice_valid"};
    return names;
}

void read_step(const json& value, const std::string& where, Step& step, std::vector<std::string>& errors)
{
    static const std::set<std::string> fields{"id", "do", "capture", "close", "mask", "assert", "os", "skip", "settle_ms", "after"};
    for (auto it = value.begin(); it != value.end(); ++it)
        if (fields.count(it.key()) == 0)
            errors.push_back(where + ": unknown field \"" + it.key() + "\"");

    if (!value.contains("id") || !value["id"].is_string())
        errors.push_back(where + ": \"id\" is missing");
    else
        step.id = value["id"].get<std::string>();
    const std::string at = step.id.empty() ? where : step.id;

    std::string error;
    if (value.contains("do") && !read_actions(value["do"], step.actions, error))
        errors.push_back(at + ": " + error);
    if (value.contains("after") && !read_actions(value["after"], step.after, error))
        errors.push_back(at + ": " + error);
    if (value.contains("capture")) {
        if (!value["capture"].is_string() || !parse_capture_kind(value["capture"].get<std::string>(), step.capture))
            errors.push_back(at + ": unknown capture kind");
    }
    if (value.contains("close")) {
        if (value["close"].is_boolean())
            step.close = value["close"].get<bool>();
        else
            errors.push_back(at + ": \"close\" must be true or false");
    }
    if (value.contains("mask")) {
        bool ok = value["mask"].is_array();
        if (ok)
            for (const json& item : value["mask"]) {
                Rect rect;
                ok = ok && read_rect(item, rect);
                step.masks.push_back(rect);
            }
        if (!ok)
            errors.push_back(at + ": \"mask\" must be a list of [x, y, w, h] with w and h above 0");
    }
    if (value.contains("assert")) {
        if (!read_string_list(value["assert"], step.asserts))
            errors.push_back(at + ": \"assert\" must be a list of names");
        for (const std::string& name : step.asserts)
            if (known_asserts().count(name) == 0)
                errors.push_back(at + ": unknown assert \"" + name + "\"");
    }
    if (value.contains("os")) {
        if (!read_string_list(value["os"], step.os))
            errors.push_back(at + ": \"os\" must be a list of names");
        for (const std::string& name : step.os)
            if (known_os().count(name) == 0)
                errors.push_back(at + ": unknown OS \"" + name + "\"");
    }
    if (value.contains("skip")) {
        if (!value["skip"].is_string() || value["skip"].get<std::string>().empty())
            errors.push_back(at + ": \"skip\" must give a reason");
        else
            step.skip = value["skip"].get<std::string>();
    }
    if (value.contains("settle_ms")) {
        if (!value["settle_ms"].is_number_integer() || value["settle_ms"].get<int>() < 0)
            errors.push_back(at + ": \"settle_ms\" must be a positive integer");
        else
            step.settle_ms = value["settle_ms"].get<int>();
    }
}

void read_rule(const std::string& key, const json& value, CommandRule& rule, std::vector<std::string>& errors)
{
    static const std::set<std::string> fields{"class", "reason", "section", "param", "revert", "restore", "settle_ms"};
    rule.key = key;
    const std::string at = "menu_items." + key;
    if (!value.is_object()) {
        errors.push_back(at + ": must be an object");
        return;
    }
    for (auto it = value.begin(); it != value.end(); ++it)
        if (fields.count(it.key()) == 0)
            errors.push_back(at + ": unknown field \"" + it.key() + "\"");
    auto text = [&](const char* name, std::string& out) {
        if (!value.contains(name))
            return;
        if (value[name].is_string())
            out = value[name].get<std::string>();
        else
            errors.push_back(at + ": \"" + name + "\" must be a string");
    };
    text("class", rule.cls);
    text("reason", rule.reason);
    text("section", rule.section);
    text("param", rule.param);
    text("revert", rule.revert);
    if (value.contains("restore")) {
        if (value["restore"].is_boolean())
            rule.restore = value["restore"].get<bool>();
        else
            errors.push_back(at + ": \"restore\" must be true or false");
    }
    if (value.contains("settle_ms")) {
        if (value["settle_ms"].is_number_integer() && value["settle_ms"].get<int>() >= 0)
            rule.settle_ms = value["settle_ms"].get<int>();
        else
            errors.push_back(at + ": \"settle_ms\" must be a positive integer");
    }

    const std::vector<std::string>& classes = command_classes();
    if (std::find(classes.begin(), classes.end(), rule.cls) == classes.end())
        errors.push_back(at + ": \"class\" must be one of dialog, view, toggle, any, skip");
    if (rule.cls == "skip" && rule.reason.empty())
        errors.push_back(at + ": a skipped command must give a reason");
    if (rule.cls != "skip" && !std::regex_match(rule.section, std::regex("[0-9]{2}")))
        errors.push_back(at + ": \"section\" must be two digits");
}

std::string json_line(const json& value) { return value.dump(-1, ' ', false, json::error_handler_t::replace); }

json rect_json(const Rect& rect) { return json::array({rect.x, rect.y, rect.w, rect.h}); }

// Rounded to three decimals so the events stay byte-stable across runs.
double rounded(double value) { return std::round(value * 1000.0) / 1000.0; }

std::string rule_step_id(const CommandRule& rule) { return rule.section + "-" + slug(rule.key); }

Step rule_step(const CommandRule& rule, const std::map<std::string, std::string>& fixtures)
{
    Step step;
    step.id = rule_step_id(rule);
    if (rule.cls == "skip") {
        step.skip = rule.reason;
        step.capture = CaptureKind::None;
        return step;
    }
    step.actions.push_back({"command", rule.key, rule.param});
    step.settle_ms = rule.settle_ms;
    step.capture = rule.cls == "dialog" ? CaptureKind::Dialog : rule.cls == "any" ? CaptureKind::Auto : CaptureKind::Main;
    if (rule.cls == "toggle")
        step.after.push_back({"command", rule.key, rule.param});
    if (!rule.revert.empty())
        step.after.push_back({"command", rule.revert, ""});
    if (rule.restore) {
        step.after.push_back({"reset", "", ""});
        if (fixtures.count("model") != 0)
            step.after.push_back({"load", "model", ""});
        step.after.push_back({"select_all", "", ""});
    }
    return step;
}

bool runs_on(const Step& step, const std::string& os)
{
    return step.os.empty() || std::find(step.os.begin(), step.os.end(), os) != step.os.end();
}

// "&File" -> "File", "Save && Close" -> "Save & Close", "Undo\tCtrl+Z" -> "Undo Ctrl+Z".
std::string clean_label(const std::string& label)
{
    std::string out;
    for (std::size_t i = 0; i < label.size(); ++i) {
        const char c = label[i];
        if (c == '&') {
            if (i + 1 < label.size() && label[i + 1] == '&') {
                out += '&';
                ++i;
            }
            continue;
        }
        out += c == '\t' ? ' ' : c;
    }
    while (!out.empty() && out.back() == ' ')
        out.pop_back();
    return out;
}

void menu_lines(const std::vector<MenuNode>& items, int depth, std::ostringstream& out)
{
    const std::string indent(static_cast<std::size_t>(depth) * 2, ' ');
    for (const MenuNode& item : items) {
        out << indent;
        if (item.kind == MenuNode::Kind::Separator) {
            out << "---\n";
            continue;
        }
        if (item.kind == MenuNode::Kind::Check || item.kind == MenuNode::Kind::Radio)
            out << (item.checked ? "[x] " : "[ ] ");
        out << clean_label(item.label);
        if (item.kind == MenuNode::Kind::Submenu)
            out << " >";
        if (!item.enabled)
            out << " (disabled)";
        out << '\n';
        if (item.kind == MenuNode::Kind::Submenu)
            menu_lines(item.children, depth + 1, out);
    }
}

} // namespace

std::string to_string(CaptureKind kind) { return capture_names[static_cast<int>(kind)]; }

bool parse_capture_kind(const std::string& text, CaptureKind& kind)
{
    for (int i = 0; i < 6; ++i)
        if (text == capture_names[i]) {
            kind = static_cast<CaptureKind>(i);
            return true;
        }
    return false;
}

const std::vector<std::string>& action_kinds()
{
    static const std::vector<std::string> kinds{"tab",  "command", "prefs_tab", "settings", "load",       "reset",     "select_all",
                                                "context_menu", "menu", "wait", "slice", "copy_gcode", "close_tips"};
    return kinds;
}

const std::vector<std::string>& command_classes()
{
    static const std::vector<std::string> classes{"dialog", "view", "toggle", "any", "skip"};
    return classes;
}

const std::vector<std::string>& preferences_tabs()
{
    static const std::vector<std::string> tabs{"general", "files", "behaviour", "control", "graphics", "online"};
    return tabs;
}

bool parse_script(const std::string& text, Script& script, std::vector<std::string>& errors)
{
    const std::size_t errors_before = errors.size();
    json root;
    try {
        root = json::parse(text);
    } catch (const std::exception& error) {
        errors.push_back(std::string("script.json is not valid JSON: ") + error.what());
        return false;
    }
    if (!root.is_object()) {
        errors.push_back("script.json must hold an object");
        return false;
    }
    static const std::set<std::string> fields{"protocol", "window",    "language", "settle_ms", "step_timeout_s",
                                              "fixtures", "steps",     "menu_items", "exclude", "comment"};
    for (auto it = root.begin(); it != root.end(); ++it)
        if (fields.count(it.key()) == 0)
            errors.push_back("unknown field \"" + it.key() + "\"");

    if (root.contains("protocol") && root["protocol"].is_number_integer())
        script.protocol = root["protocol"].get<int>();
    if (script.protocol != protocol_version)
        errors.push_back("\"protocol\" must be " + std::to_string(protocol_version));

    const json& size = root.contains("window") && root["window"].is_object() && root["window"].contains("client_size") ?
                           root["window"]["client_size"] : json();
    if (size.is_array() && size.size() == 2 && size[0].is_number_integer() && size[1].is_number_integer() && size[0].get<int>() > 0 &&
        size[1].get<int>() > 0) {
        script.client_width  = size[0].get<int>();
        script.client_height = size[1].get<int>();
    } else
        errors.push_back("\"window.client_size\" must be [width, height]");

    if (root.contains("language") && root["language"].is_string())
        script.language = root["language"].get<std::string>();
    if (script.language.empty())
        errors.push_back("\"language\" is missing");

    if (root.contains("settle_ms")) {
        if (root["settle_ms"].is_number_integer() && root["settle_ms"].get<int>() >= 0)
            script.settle_ms = root["settle_ms"].get<int>();
        else
            errors.push_back("\"settle_ms\" must be a positive integer");
    }
    if (root.contains("step_timeout_s")) {
        if (root["step_timeout_s"].is_number_integer() && root["step_timeout_s"].get<int>() > 0)
            script.step_timeout_s = root["step_timeout_s"].get<int>();
        else
            errors.push_back("\"step_timeout_s\" must be above 0");
    }

    if (root.contains("fixtures")) {
        if (!root["fixtures"].is_object())
            errors.push_back("\"fixtures\" must be an object");
        else
            for (auto it = root["fixtures"].begin(); it != root["fixtures"].end(); ++it) {
                if (it.value().is_string())
                    script.fixtures[it.key()] = it.value().get<std::string>();
                else
                    errors.push_back("fixture \"" + it.key() + "\" must be a path");
            }
    }

    if (!root.contains("steps") || !root["steps"].is_array())
        errors.push_back("\"steps\" must be a list");
    else {
        int index = 0;
        for (const json& item : root["steps"]) {
            const std::string where = "steps[" + std::to_string(index++) + "]";
            Entry entry;
            if (!item.is_object()) {
                errors.push_back(where + ": must be an object");
                continue;
            }
            if (item.contains("generate")) {
                entry.is_generator = true;
                if (item["generate"].is_string())
                    entry.generator.kind = item["generate"].get<std::string>();
                if (item.contains("section") && item["section"].is_string())
                    entry.generator.section = item["section"].get<std::string>();
                static const std::set<std::string> generators{"menus", "prefs", "settings", "commands"};
                if (generators.count(entry.generator.kind) == 0)
                    errors.push_back(where + ": unknown generator");
                if (entry.generator.kind == "commands" && !std::regex_match(entry.generator.section, std::regex("[0-9]{2}")))
                    errors.push_back(where + ": a commands generator needs a two-digit \"section\"");
                for (auto it = item.begin(); it != item.end(); ++it)
                    if (it.key() != "generate" && it.key() != "section")
                        errors.push_back(where + ": unknown field \"" + it.key() + "\"");
            } else
                read_step(item, where, entry.step, errors);
            script.entries.push_back(entry);
        }
    }

    if (root.contains("menu_items")) {
        if (!root["menu_items"].is_object())
            errors.push_back("\"menu_items\" must be an object");
        else
            for (auto it = root["menu_items"].begin(); it != root["menu_items"].end(); ++it) {
                CommandRule rule;
                read_rule(it.key(), it.value(), rule, errors);
                script.rules.push_back(rule);
            }
        std::sort(script.rules.begin(), script.rules.end(), [](const CommandRule& a, const CommandRule& b) { return a.key < b.key; });
        for (const CommandRule& rule : script.rules)
            if (!rule.revert.empty() &&
                std::none_of(script.rules.begin(), script.rules.end(), [&](const CommandRule& other) { return other.key == rule.revert; }))
                errors.push_back("menu_items." + rule.key + ": \"revert\" names no classified command");
    }

    if (root.contains("exclude")) {
        bool ok = root["exclude"].is_array();
        if (ok)
            for (const json& item : root["exclude"]) {
                if (!item.is_object() || !item.contains("surface") || !item["surface"].is_string() || !item.contains("reason") ||
                    !item["reason"].is_string() || item["reason"].get<std::string>().empty()) {
                    ok = false;
                    break;
                }
                script.excludes.push_back({item["surface"].get<std::string>(), item["reason"].get<std::string>()});
            }
        if (!ok)
            errors.push_back("\"exclude\" must be a list of {\"surface\", \"reason\"}");
    }
    return errors.size() == errors_before;
}

std::string slug(const std::string& text)
{
    std::string out;
    bool        pending_dash = false;
    for (const char raw : text) {
        const unsigned char c = static_cast<unsigned char>(raw);
        const bool alnum = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
        if (!alnum) {
            pending_dash = !out.empty();
            continue;
        }
        if (pending_dash)
            out += '-';
        pending_dash = false;
        out += static_cast<char>(c >= 'A' && c <= 'Z' ? c - 'A' + 'a' : c);
    }
    return out;
}

bool is_valid_surface_id(const std::string& id)
{
    static const std::regex pattern("[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*");
    return std::regex_match(id, pattern);
}

std::vector<std::string> classification_errors(const std::vector<CommandRule>& rules, const std::vector<std::string>& catalog_keys)
{
    std::vector<std::string> errors;
    std::set<std::string>    classified;
    for (const CommandRule& rule : rules)
        classified.insert(rule.key);
    const std::set<std::string> catalog(catalog_keys.begin(), catalog_keys.end());
    for (const std::string& key : catalog_keys)
        if (classified.count(key) == 0)
            errors.push_back("command \"" + key + "\" is not classified in script.json menu_items");
    for (const std::string& key : classified)
        if (catalog.count(key) == 0)
            errors.push_back("menu_items." + key + " names no command of the catalog");
    return errors;
}

std::vector<Step> expand(const Script& script, const Inventory& inventory, std::vector<std::string>& errors)
{
    std::vector<Step> steps;
    std::vector<std::string> classification = classification_errors(script.rules, inventory.command_keys);
    errors.insert(errors.end(), classification.begin(), classification.end());

    for (const Entry& entry : script.entries) {
        if (!entry.is_generator) {
            if (runs_on(entry.step, inventory.os))
                steps.push_back(entry.step);
            continue;
        }
        const std::string& kind = entry.generator.kind;
        if (kind == "menus") {
            for (const MenuTarget& menu : inventory.menus) {
                Step step;
                step.id = "20-menu-" + menu.slug;
                // On macOS the harness opens the menu bar title itself, so the
                // action only carries the label for the capture event.
                step.capture = inventory.menubar ? CaptureKind::Menubar : CaptureKind::Menu;
                step.actions.push_back({"menu", menu.slug, menu.label});
                steps.push_back(step);
            }
            Step tree;
            tree.id      = "20-menu-tree";
            tree.capture = CaptureKind::None;
            steps.push_back(tree);
        } else if (kind == "prefs") {
            for (const std::string& tab : preferences_tabs()) {
                Step step;
                step.id      = "40-preferences-" + tab;
                step.capture = CaptureKind::Dialog;
                step.actions.push_back({"prefs_tab", tab, ""});
                steps.push_back(step);
            }
        } else if (kind == "settings") {
            for (const SettingsPage& page : inventory.settings_pages) {
                Step step;
                step.id      = "50-settings-" + slug(page.tab) + "-" + slug(page.page);
                step.capture = CaptureKind::Auto;
                step.actions.push_back({"settings", page.tab, page.page});
                steps.push_back(step);
            }
        } else if (kind == "commands") {
            // Catalog order, so a new upstream command lands next to its group.
            for (const std::string& key : inventory.command_keys) {
                auto rule = std::find_if(script.rules.begin(), script.rules.end(), [&](const CommandRule& r) { return r.key == key; });
                if (rule == script.rules.end() || rule->section != entry.generator.section)
                    continue;
                steps.push_back(rule_step(*rule, script.fixtures));
            }
        }
    }
    // Skipped rules without a section are listed once, at the end, so every
    // catalog key shows up in surfaces.txt.
    for (const std::string& key : inventory.command_keys) {
        auto rule = std::find_if(script.rules.begin(), script.rules.end(), [&](const CommandRule& r) { return r.key == key; });
        if (rule != script.rules.end() && rule->cls == "skip" && rule->section.empty()) {
            Step step;
            step.id      = "99-" + slug(rule->key);
            step.skip    = rule->reason;
            step.capture = CaptureKind::None;
            steps.push_back(step);
        }
    }

    std::set<std::string> seen;
    for (const Step& step : steps) {
        if (!is_valid_surface_id(step.id))
            errors.push_back("invalid surface id \"" + step.id + "\"");
        if (!seen.insert(step.id).second)
            errors.push_back("duplicate surface id \"" + step.id + "\"");
    }
    return steps;
}

std::string surfaces_text(const std::vector<Step>& steps, const std::vector<Exclusion>& excludes)
{
    std::ostringstream out;
    for (const Step& step : steps) {
        if (!step.skip.empty())
            out << step.id << " skip " << step.skip << '\n';
        else
            out << step.id << ' ' << to_string(step.capture) << '\n';
    }
    for (const Exclusion& exclusion : excludes)
        out << "exclude " << exclusion.surface << ' ' << exclusion.reason << '\n';
    return out.str();
}

std::string menu_tree_text(const std::string& title, const std::vector<MenuNode>& items)
{
    std::ostringstream out;
    out << clean_label(title) << '\n';
    menu_lines(items, 1, out);
    return out.str();
}

std::string hello_event(int seq, const std::string& app_version, const std::string& gl_renderer, const std::string& gl_version,
                        const std::string& display, double scale, const std::string& os)
{
    return json_line({{"seq", seq},
                      {"event", "hello"},
                      {"protocol", protocol_version},
                      {"version", app_version},
                      {"GL_RENDERER", gl_renderer},
                      {"GL_VERSION", gl_version},
                      {"display", display},
                      {"scale", rounded(scale)},
                      {"os", os}});
}

std::string capture_event(int seq, const std::string& id, const Rect& rect_px, CaptureKind kind, const std::vector<Rect>& masks,
                          const std::vector<Rect>& webviews, double scale, const std::string& title, const std::string& menu)
{
    json mask_list = json::array();
    for (const Rect& mask : masks)
        mask_list.push_back(rect_json(mask));
    json webview_list = json::array();
    for (const Rect& webview : webviews)
        webview_list.push_back(rect_json(webview));
    return json_line({{"seq", seq},
                      {"event", "capture"},
                      {"id", id},
                      {"kind", to_string(kind)},
                      {"rect_px", rect_json(rect_px)},
                      {"scale", rounded(scale)},
                      {"masks", mask_list},
                      {"webviews", webview_list},
                      {"title", title},
                      {"menu", menu}});
}

std::string text_event(int seq, const std::string& id, const std::string& content)
{
    return json_line({{"seq", seq}, {"event", "text"}, {"id", id}, {"content", content}});
}

std::string fail_event(int seq, const std::string& id, const std::string& reason)
{
    return json_line({{"seq", seq}, {"event", "fail"}, {"id", id}, {"reason", reason}});
}

std::string done_event(int seq, int errors) { return json_line({{"seq", seq}, {"event", "done"}, {"errors", errors}}); }

std::string ack_file_name(int seq) { return "ack-" + std::to_string(seq); }

} // namespace Golden
} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
