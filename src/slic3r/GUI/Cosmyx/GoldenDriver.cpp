#include "GoldenDriver.hpp"

#include "logic/CosmyxVersion.hpp"
#include "logic/GoldenScript.hpp"

#include "libslic3r/Format/ProjectStrategy.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/Utils.hpp"
#include "slic3r/GUI/BBLTopbar.hpp"
#include "slic3r/GUI/DailyTips.hpp"
#include "slic3r/GUI/Event.hpp"
#include "slic3r/GUI/GLCanvas3D.hpp"
#include "slic3r/GUI/GUI.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/MainFrame.hpp"
#include "slic3r/GUI/NativeCommands.hpp"
#include "slic3r/GUI/NotificationManager.hpp"
#include "slic3r/GUI/OpenGLManager.hpp"
#include "slic3r/GUI/ParamsDialog.hpp"
#include "slic3r/GUI/ParamsPanel.hpp"
#include "slic3r/GUI/PartPlate.hpp"
#include "slic3r/GUI/Plater.hpp"
#include "slic3r/GUI/Preferences.hpp"
#include "slic3r/GUI/Tab.hpp"

#include <boost/filesystem.hpp>
#include <boost/log/trivial.hpp>
#include <boost/nowide/fstream.hpp>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <functional>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <wx/aui/auibar.h>
#include <wx/dialog.h>
#include <wx/eventfilter.h>
#include <wx/gdicmn.h>
#include <wx/glcanvas.h>
#include <wx/menu.h>
#include <wx/timer.h>
#include <wx/toplevel.h>
#include <wx/utils.h>
#include <wx/webview.h>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

namespace fs = boost::filesystem;
using namespace Golden;
using Clock = std::chrono::steady_clock;

constexpr int tick_ms          = 50;
constexpr int ready_timeout_s  = 180;
constexpr int slice_timeout_s  = 300;
constexpr int close_timeout_s  = 10;
constexpr int script_timeout_s = 5;

std::string env(const char* name)
{
    wxString value;
    return wxGetEnv(name, &value) ? into_u8(value) : std::string();
}

std::string tab_slug(Preset::Type type)
{
    switch (type) {
    case Preset::TYPE_PRINT: return "process";
    case Preset::TYPE_FILAMENT: return "filament";
    case Preset::TYPE_PRINTER: return "printer";
    default: return {};
    }
}

std::vector<MenuNode> menu_nodes(wxMenu* menu)
{
    std::vector<MenuNode> nodes;
    if (menu == nullptr)
        return nodes;
    for (wxMenuItem* item : menu->GetMenuItems()) {
        MenuNode node;
        if (item->IsSeparator()) {
            node.kind = MenuNode::Kind::Separator;
        } else {
            node.label   = into_u8(item->GetItemLabel());
            node.enabled = item->IsEnabled();
            if (item->IsSubMenu()) {
                node.kind     = MenuNode::Kind::Submenu;
                node.children = menu_nodes(item->GetSubMenu());
            } else if (item->IsCheckable()) {
                node.kind    = item->IsRadio() ? MenuNode::Kind::Radio : MenuNode::Kind::Check;
                node.checked = item->IsChecked();
            }
        }
        nodes.push_back(std::move(node));
    }
    return nodes;
}

void collect_webviews(wxWindow* window, std::vector<wxWebView*>& out)
{
    if (auto* view = dynamic_cast<wxWebView*>(window); view != nullptr && view->IsShownOnScreen()) {
        out.push_back(view);
        return;
    }
    for (wxWindow* child : window->GetChildren())
        collect_webviews(child, out);
}

// Walks the application through the script. Every step goes through the same
// phases, driven by a 50 ms timer; the timer keeps firing inside the nested
// event loops of modal dialogs and popup menus (MSW, GTK and OSX alike), so a
// step can open one through CallAfter, capture it, and close it again.
class Driver : public wxEvtHandler, public wxEventFilter
{
public:
    explicit Driver(const fs::path& dir) : m_dir(dir), m_timer(this)
    {
        m_os = env("COSMYX_GUI_DRIVER_OS");
        const std::string script = env("COSMYX_GUI_DRIVER_SCRIPT");
        m_script_path = script.empty() ? m_dir / "script.json" : fs::path(script);
        m_events.open((m_dir / "events.jsonl").string(), std::ios::out | std::ios::trunc | std::ios::binary);
        wxEvtHandler::AddFilter(this);
        Bind(wxEVT_TIMER, &Driver::on_timer, this);
        m_phase_start = Clock::now();
        m_timer.Start(tick_ms);
    }

    ~Driver() override { wxEvtHandler::RemoveFilter(this); }

    int FilterEvent(wxEvent& event) override
    {
        const wxEventType type = event.GetEventType();
        if (type == wxEVT_MENU_OPEN) {
            if (wxMenu* menu = static_cast<wxMenuEvent&>(event).GetMenu(); menu != nullptr && m_open_menu == nullptr)
                m_open_menu = menu;
        } else if (type == wxEVT_MENU_CLOSE) {
            if (static_cast<wxMenuEvent&>(event).GetMenu() == m_open_menu)
                m_open_menu = nullptr;
        }
        return Event_Skip;
    }

private:
    enum class Phase { WaitApp, Ready, Begin, Act, WaitAct, Settle, Capture, WaitAck, Scripts, Close, WaitClose, Finished };

    // ---- plumbing --------------------------------------------------------

    void emit(const std::string& line)
    {
        m_events << line << '\n';
        m_events.flush();
    }

    int next_seq() { return ++m_seq; }

    void fail(const std::string& id, const std::string& reason)
    {
        ++m_errors;
        BOOST_LOG_TRIVIAL(error) << "Cosmyx goldens: " << id << ": " << reason;
        emit(fail_event(next_seq(), id, reason));
    }

    void go(Phase phase)
    {
        m_phase       = phase;
        m_phase_start = Clock::now();
    }

    double elapsed_ms() const { return std::chrono::duration<double, std::milli>(Clock::now() - m_phase_start).count(); }

    const Step& step() const { return m_steps[m_index]; }

    int settle_ms() const { return step().settle_ms >= 0 ? step().settle_ms : m_script.settle_ms; }

    double step_timeout_ms() const { return m_script.step_timeout_s * 1000.0; }

    // Runs `body` from the main loop, so that a modal dialog or a popup menu
    // it opens runs its own nested loop while this driver keeps ticking.
    void call_after(std::function<void()> body)
    {
        m_call_running = false;
        m_call_done    = false;
        wxGetApp().CallAfter([this, body]() {
            m_call_running = true;
            body();
            m_call_running = false;
            m_call_done    = true;
        });
    }

    // Shown top-level windows other than the main frame.
    std::vector<wxTopLevelWindow*> shown_windows() const
    {
        std::vector<wxTopLevelWindow*> windows;
        MainFrame* main = wxGetApp().mainframe;
        for (wxWindowList::compatibility_iterator node = wxTopLevelWindows.GetFirst(); node; node = node->GetNext()) {
            auto* window = dynamic_cast<wxTopLevelWindow*>(node->GetData());
            if (window != nullptr && window != main && window->IsShown() && !window->IsBeingDeleted())
                windows.push_back(window);
        }
        return windows;
    }

    std::vector<wxTopLevelWindow*> new_windows() const
    {
        std::vector<wxTopLevelWindow*> windows;
        for (wxTopLevelWindow* window : shown_windows())
            if (m_baseline.count(window) == 0)
                windows.push_back(window);
        return windows;
    }

    static void close_window(wxTopLevelWindow* window)
    {
        if (auto* dialog = dynamic_cast<wxDialog*>(window); dialog != nullptr && dialog->IsModal())
            dialog->EndModal(wxID_CANCEL);
        else
            window->Close();
    }

    void close_new_windows()
    {
        for (wxTopLevelWindow* window : new_windows())
            close_window(window);
    }

    // ---- start -----------------------------------------------------------

    bool app_ready() const
    {
        GUI_App& app = wxGetApp();
        return app.mainframe != nullptr && app.mainframe->IsShown() && app.plater() != nullptr && app.plater()->canvas3D() != nullptr &&
               app.plater()->canvas3D()->is_initialized();
    }

    Inventory inventory() const
    {
        Inventory inv;
        inv.os = m_os;
        for (const NativeCommand& command : NativeCommands::catalog())
            inv.command_keys.push_back(command.key);

        MainFrame* main = wxGetApp().mainframe;
        if (main->topbar() != nullptr) {
            // Windows and Linux: the custom top bar pops these up.
            inv.menus = {{"file", "File"}, {"main", "Main"}, {"calibration", "Calibration"}};
        } else if (wxMenuBar* bar = main->GetMenuBar(); bar != nullptr) {
            inv.menubar = true;
            for (size_t i = 0; i < bar->GetMenuCount(); ++i) {
                const std::string label = into_u8(bar->GetMenuLabelText(i));
                inv.menus.push_back({slug(label), label});
            }
        }

        Plater* plater = wxGetApp().plater();
        for (Tab* tab : wxGetApp().tabs_list) {
            if (tab == nullptr || !tab->supports_printer_technology(plater->printer_technology()))
                continue;
            const std::string name = tab_slug(tab->type());
            if (name.empty())
                continue;
            for (const PageShp& page : tab->pages())
                if (page && page->get_show())
                    inv.settings_pages.push_back({name, into_u8(page->title())});
        }
        return inv;
    }

    void start()
    {
        MainFrame* main = wxGetApp().mainframe;
        main->Maximize(false);
        main->Move(wxPoint(16, 48));
        main->SetClientSize(wxSize(m_script.client_width, m_script.client_height));
        main->Raise();

        const OpenGLManager::GLInfo& gl = OpenGLManager::get_gl_info();
        const bool detected = gl.is_detected();
        const wxSize display = wxGetDisplaySize();
        emit(hello_event(next_seq(), display_version(), detected ? gl.get_renderer() : std::string(),
                         detected ? gl.get_version() : std::string(),
                         std::to_string(display.GetWidth()) + "x" + std::to_string(display.GetHeight()), main->GetContentScaleFactor(),
                         m_os));

        std::vector<std::string> errors;
        m_steps = expand(m_script, inventory(), errors);
        for (const std::string& error : errors)
            fail("script", error);
        emit(text_event(next_seq(), "surfaces", surfaces_text(m_steps, m_script.excludes)));

        if (wxMenuBar* bar = main->GetMenuBar(); bar != nullptr && main->topbar() == nullptr)
            for (size_t i = 0; i < bar->GetMenuCount(); ++i)
                m_menu_tree += menu_tree_text(into_u8(bar->GetMenuLabel(i)), menu_nodes(bar->GetMenu(i)));
        m_index = 0;
        go(Phase::Begin);
    }

    // ---- actions ---------------------------------------------------------

    fs::path fixture_path(const std::string& name) const
    {
        auto it = m_script.fixtures.find(name);
        const std::string value = it == m_script.fixtures.end() ? name : it->second;
        static const std::string resources = "resources:";
        if (value.rfind(resources, 0) == 0)
            return fs::path(resources_dir()) / value.substr(resources.size());
        fs::path path(value);
        return path.is_absolute() ? path : m_dir / path;
    }

    // Starts one action. Returns false (and reports) when it cannot run.
    bool start_action(const Action& action)
    {
        GUI_App&   app    = wxGetApp();
        Plater*    plater = app.plater();
        MainFrame* main   = app.mainframe;
        m_slice_wait      = false;
        m_wait_ms         = 0;
        const std::string& kind = action.kind;

        if (kind == "wait") {
            m_wait_ms = std::max(0, std::atoi(action.arg.c_str()));
            m_call_running = false;
            m_call_done    = true;
            return true;
        }
        if (kind == "copy_gcode") {
            m_call_running = false;
            m_call_done    = true;
            PartPlate* plate = plater->get_partplate_list().get_curr_plate();
            const std::string source = plate != nullptr ? plate->get_tmp_gcode_path() : std::string();
            fs::path target = m_dir / "gcode" / (action.arg.empty() ? std::string("plate_1.gcode") : action.arg);
            boost::system::error_code ec;
            fs::create_directories(target.parent_path(), ec);
            std::string error;
            if (source.empty() || !fs::exists(source) || copy_file(source, target.string(), error) != CopyFileResult::SUCCESS) {
                fail(step().id, "the sliced G-code could not be copied: " + (error.empty() ? source : error));
                return false;
            }
            return true;
        }
        if (kind == "tab") {
            call_after([main, id = action.arg]() { main->select_tab(wxString::FromUTF8(id)); });
            return true;
        }
        if (kind == "command") {
            call_after([key = action.arg, param = action.param]() { NativeCommands::run(key, param); });
            return true;
        }
        if (kind == "slice") {
            m_slice_wait  = true;
            m_slice_count = 0;
            call_after([]() { NativeCommands::run("slice_and_preview"); });
            return true;
        }
        if (kind == "prefs_tab") {
            const std::vector<std::string>& tabs = preferences_tabs();
            auto it = std::find(tabs.begin(), tabs.end(), action.arg);
            if (it == tabs.end()) {
                fail(step().id, "unknown Preferences tab \"" + action.arg + "\"");
                return false;
            }
            const auto tab = static_cast<PreferencesTab>(it - tabs.begin());
            call_after([tab]() { wxGetApp().open_preferences(tab); });
            return true;
        }
        if (kind == "settings") {
            Tab* target = nullptr;
            for (Tab* tab : app.tabs_list)
                if (tab != nullptr && tab_slug(tab->type()) == action.arg)
                    target = tab;
            if (target == nullptr) {
                fail(step().id, "no settings tab \"" + action.arg + "\"");
                return false;
            }
            call_after([target, page = action.param]() {
                // Printer and filament tabs live in the settings dialog, which
                // shows one tab at a time.
                if (ParamsDialog* dialog = wxGetApp().params_dialog(); dialog != nullptr && target->GetParent() == dialog->panel())
                    dialog->panel()->set_active_tab(target);
                target->activate_option("", wxString::FromUTF8(page));
            });
            return true;
        }
        if (kind == "load") {
            const fs::path path = fixture_path(action.arg);
            if (!fs::exists(path)) {
                fail(step().id, "fixture not found: " + path.string());
                return false;
            }
            call_after([plater, path]() { plater->load_files(std::vector<fs::path>{path}, LoadStrategy::LoadModel); });
            return true;
        }
        if (kind == "reset") {
            call_after([plater]() { plater->delete_all_objects_from_model(); });
            return true;
        }
        if (kind == "select_all") {
            call_after([plater]() { plater->select_all(); });
            return true;
        }
        if (kind == "close_tips") {
            call_after([plater]() {
                if (DailyTipsWindow* tips = plater->get_dailytips(); tips != nullptr)
                    tips->close();
            });
            return true;
        }
        if (kind == "context_menu") {
            call_after([plater]() {
                GLCanvas3D* canvas = plater->canvas3D();
                const Size  size   = canvas->get_canvas_size();
                // Same event a right click on the selected object sends; the
                // plater shows the matching context menu (a popup, so this
                // call returns only once the harness closed it).
                RBtnEvent event(EVT_GLCANVAS_RIGHT_CLICK,
                                std::pair<Vec2d, bool>(Vec2d(size.get_width() / 2.0, size.get_height() / 2.0), false));
                canvas->get_wxglcanvas()->GetEventHandler()->ProcessEvent(event);
            });
            return true;
        }
        if (kind == "menu") {
            BBLTopbar* topbar = main->topbar();
            if (topbar == nullptr) {
                // macOS: the harness opens the native menu bar title itself.
                m_call_running = false;
                m_call_done    = true;
                return true;
            }
            const std::string which = action.arg;
            call_after([topbar, which]() {
                wxAuiToolBarEvent event(wxEVT_AUITOOLBAR_TOOL_DROPDOWN, wxID_ANY);
                event.SetEventObject(topbar);
                if (which == "file")
                    topbar->OnFileToolItem(event);
                else if (which == "main")
                    topbar->OnDropdownToolItem(event);
                else if (which == "calibration")
                    topbar->OnCalibToolItem(event);
            });
            return true;
        }
        fail(step().id, "unknown action \"" + kind + "\"");
        return false;
    }

    bool slice_finished() const
    {
        Plater* plater = wxGetApp().plater();
        if (plater == nullptr || plater->is_background_process_slicing())
            return false;
        PartPlate* plate = plater->get_partplate_list().get_curr_plate();
        return plate != nullptr && plate->is_slice_result_valid();
    }

    // ---- phases ----------------------------------------------------------

    void begin_step()
    {
        if (m_index >= m_steps.size()) {
            emit(done_event(next_seq(), m_errors));
            m_timer.Stop();
            go(Phase::Finished);
            return;
        }
        const Step& current = step();
        if (!current.skip.empty()) {
            ++m_index;
            return;
        }
        m_baseline.clear();
        for (wxTopLevelWindow* window : shown_windows())
            m_baseline.insert(window);
        m_open_menu = nullptr;
        m_actions   = &current.actions;
        m_action    = 0;
        m_in_after  = false;
        m_target    = nullptr;
        go(Phase::Act);
    }

    void act()
    {
        if (m_action >= m_actions->size()) {
            if (m_in_after) {
                // A window left open by the undo actions is an error too.
                if (!new_windows().empty()) {
                    fail(step().id, "a window is still open after the step");
                    close_new_windows();
                }
                ++m_index;
                go(Phase::Begin);
            } else
                enter_settle();
            return;
        }
        if (!start_action((*m_actions)[m_action])) {
            abort_step();
            return;
        }
        go(Phase::WaitAct);
    }

    void wait_act()
    {
        const bool last_action = !m_in_after && m_action + 1 == m_actions->size();
        const bool opened      = m_call_running && elapsed_ms() >= tick_ms * 2;
        if (opened && last_action) {
            // A modal dialog or a popup menu now runs its own loop.
            enter_settle();
            return;
        }
        if (m_call_done && elapsed_ms() >= m_wait_ms) {
            if (m_slice_wait) {
                m_slice_count = slice_finished() ? m_slice_count + 1 : 0;
                if (m_slice_count < 3) {
                    if (elapsed_ms() > slice_timeout_s * 1000.0) {
                        fail(step().id, "slicing did not finish in " + std::to_string(slice_timeout_s) + " s");
                        abort_step();
                    }
                    return;
                }
            }
            ++m_action;
            go(Phase::Act);
            return;
        }
        if (elapsed_ms() > step_timeout_ms()) {
            fail(step().id, std::string("action \"") + (*m_actions)[m_action].kind + "\" did not finish");
            abort_step();
        }
    }

    // Notifications come and go with timers: none on a golden. The canvas is
    // marked dirty so the next frames paint the final state.
    void enter_settle()
    {
        if (Plater* plater = wxGetApp().plater()) {
            if (NotificationManager* notifications = plater->get_notification_manager())
                notifications->clear_all();
            if (GLCanvas3D* canvas = plater->get_current_canvas3D())
                canvas->set_as_dirty();
        }
        go(Phase::Settle);
    }

    void settle()
    {
        if (elapsed_ms() >= settle_ms())
            go(Phase::Capture);
    }

    // The label carried by the step's "menu" action (its slug when it has none).
    static std::string menu_label(const Step& current)
    {
        for (auto it = current.actions.rbegin(); it != current.actions.rend(); ++it)
            if (it->kind == "menu")
                return it->param.empty() ? it->arg : it->param;
        return current.id;
    }

    void capture()
    {
        const Step& current = step();
        MainFrame*  main    = wxGetApp().mainframe;
        const std::vector<wxTopLevelWindow*> opened = new_windows();
        CaptureKind kind   = current.capture;
        wxTopLevelWindow* target = main;
        std::string menu;

        for (const std::string& name : current.asserts) {
            if (name == "canvas_ready" && !app_ready())
                fail(current.id, "the 3D canvas is not initialized");
            if (name == "slice_valid" && !slice_finished())
                fail(current.id, "the plate has no valid slicing result");
        }

        switch (kind) {
        case CaptureKind::None:
            if (current.id == "20-menu-tree")
                emit(text_event(next_seq(), current.id, m_menu_tree));
            if (!opened.empty()) {
                fail(current.id, "unexpected window \"" + into_u8(opened.back()->GetTitle()) + "\"");
                close_new_windows();
            }
            go(Phase::Close);
            return;
        case CaptureKind::Main:
            if (!opened.empty()) {
                fail(current.id, "unexpected window \"" + into_u8(opened.back()->GetTitle()) + "\"");
                close_new_windows();
            }
            break;
        case CaptureKind::Dialog:
            if (opened.empty()) {
                fail(current.id, "no window opened");
                abort_step();
                return;
            }
            target = opened.back();
            break;
        case CaptureKind::Auto:
            if (!opened.empty()) {
                target = opened.back();
                kind   = CaptureKind::Dialog;
            } else
                kind = CaptureKind::Main;
            break;
        case CaptureKind::Menu:
            if (!m_call_running) {
                fail(current.id, "no popup menu opened");
                abort_step();
                return;
            }
            if (m_open_menu != nullptr)
                m_menu_tree += menu_tree_text(menu_label(current), menu_nodes(m_open_menu));
            break;
        case CaptureKind::Menubar:
            menu = menu_label(current);
            break;
        }

        m_target = target;
        if (target == main)
            main->Raise();
        const double scale  = target->GetContentScaleFactor();
        const wxRect screen = target->GetScreenRect();
        auto to_px = [scale](int value) { return static_cast<int>(value * scale + 0.5); };
        const Rect rect{to_px(screen.x), to_px(screen.y), to_px(screen.width), to_px(screen.height)};

        std::vector<Rect> webviews;
        m_webviews.clear();
        if (kind == CaptureKind::Main || kind == CaptureKind::Dialog) {
            collect_webviews(target, m_webviews);
            for (wxWebView* view : m_webviews) {
                const wxRect area = view->GetScreenRect();
                webviews.push_back({to_px(area.x - screen.x), to_px(area.y - screen.y), to_px(area.width), to_px(area.height)});
            }
        }
        m_capture_seq = next_seq();
        emit(capture_event(m_capture_seq, current.id, rect, kind, current.masks, webviews, scale, into_u8(target->GetTitle()), menu));
        go(Phase::WaitAck);
    }

    void wait_ack()
    {
        if (fs::exists(m_dir / ack_file_name(m_capture_seq))) {
            start_scripts();
            go(Phase::Scripts);
            return;
        }
        if (elapsed_ms() > step_timeout_ms()) {
            fail(step().id, "the harness did not acknowledge the capture");
            abort_step();
        }
    }

    // The text of each WebView is a text golden (its pixels are masked on
    // Windows and macOS, where the system engine renders them).
    void start_scripts()
    {
        m_script_results.assign(m_webviews.size(), std::string());
        m_scripts_pending = m_webviews.size();
        for (wxWebView* view : m_webviews) {
            view->Bind(wxEVT_WEBVIEW_SCRIPT_RESULT, &Driver::on_script_result, this);
            view->RunScriptAsync("document.body ? document.body.innerText : ''");
        }
    }

    void on_script_result(wxWebViewEvent& event)
    {
        event.Skip();
        auto it = std::find(m_webviews.begin(), m_webviews.end(), event.GetEventObject());
        if (it == m_webviews.end() || m_scripts_pending == 0)
            return;
        std::string& result = m_script_results[static_cast<size_t>(it - m_webviews.begin())];
        if (!result.empty())
            return;
        result = event.IsError() ? std::string("<script error>") : into_u8(event.GetString());
        --m_scripts_pending;
    }

    void scripts()
    {
        if (m_scripts_pending > 0 && elapsed_ms() < script_timeout_s * 1000.0)
            return;
        for (size_t i = 0; i < m_script_results.size(); ++i) {
            std::string id = step().id + "-webview" + (i == 0 ? std::string() : "-" + std::to_string(i + 1));
            emit(text_event(next_seq(), id, m_scripts_pending > 0 && m_script_results[i].empty() ? "<no result>" : m_script_results[i]));
        }
        for (wxWebView* view : m_webviews)
            view->Unbind(wxEVT_WEBVIEW_SCRIPT_RESULT, &Driver::on_script_result, this);
        m_webviews.clear();
        m_scripts_pending = 0;
        go(Phase::Close);
    }

    void close()
    {
        if (m_target != nullptr && m_target != wxGetApp().mainframe && step().close)
            close_window(m_target);
        m_target = nullptr;
        go(Phase::WaitClose);
    }

    void wait_close()
    {
        // The call that opened a dialog or a menu returns once it is closed.
        if (m_call_running && elapsed_ms() < close_timeout_s * 1000.0)
            return;
        if (m_call_running)
            fail(step().id, "the window or menu did not close");
        m_actions  = &step().after;
        m_action   = 0;
        m_in_after = true;
        go(Phase::Act);
    }

    // Closes what the step left open and moves on to the next step.
    void abort_step()
    {
        close_new_windows();
        m_target = nullptr;
        ++m_index;
        go(Phase::Begin);
    }

    void on_timer(wxTimerEvent&)
    {
        if (m_busy || wxGetApp().is_closing())
            return;
        m_busy = true;
        try {
            tick();
        } catch (const std::exception& error) {
            fail(m_index < m_steps.size() ? step().id : std::string("driver"), std::string("exception: ") + error.what());
            if (m_phase != Phase::Finished && m_index < m_steps.size())
                abort_step();
        }
        m_busy = false;
    }

    void tick()
    {
        switch (m_phase) {
        case Phase::WaitApp:
            if (app_ready()) {
                go(Phase::Ready);
            } else if (elapsed_ms() > ready_timeout_s * 1000.0) {
                fail("driver", "the main window or the 3D canvas never became ready");
                emit(done_event(next_seq(), m_errors));
                m_timer.Stop();
                go(Phase::Finished);
            }
            break;
        case Phase::Ready:
            // Lets the first frames paint before anything moves.
            if (elapsed_ms() >= 1500.0) {
                if (load_script())
                    start();
                else {
                    emit(done_event(next_seq(), m_errors));
                    m_timer.Stop();
                    go(Phase::Finished);
                }
            }
            break;
        case Phase::Begin: begin_step(); break;
        case Phase::Act: act(); break;
        case Phase::WaitAct: wait_act(); break;
        case Phase::Settle: settle(); break;
        case Phase::Capture: capture(); break;
        case Phase::WaitAck: wait_ack(); break;
        case Phase::Scripts: scripts(); break;
        case Phase::Close: close(); break;
        case Phase::WaitClose: wait_close(); break;
        case Phase::Finished: break;
        }
    }

    bool load_script()
    {
        boost::nowide::ifstream in(m_script_path.string(), std::ios::binary);
        if (!in) {
            emit(hello_event(next_seq(), display_version(), "", "", "", 1.0, m_os));
            fail("script", "cannot read " + m_script_path.string());
            return false;
        }
        std::ostringstream text;
        text << in.rdbuf();
        std::vector<std::string> errors;
        if (!parse_script(text.str(), m_script, errors)) {
            emit(hello_event(next_seq(), display_version(), "", "", "", 1.0, m_os));
            for (const std::string& error : errors)
                fail("script", error);
            return false;
        }
        return true;
    }

    fs::path                     m_dir;
    fs::path                     m_script_path;
    std::string                  m_os;
    boost::nowide::ofstream      m_events;
    wxTimer                      m_timer;
    Script                       m_script;
    std::vector<Step>            m_steps;
    size_t                       m_index{0};
    Phase                        m_phase{Phase::WaitApp};
    Clock::time_point            m_phase_start;
    const std::vector<Action>*   m_actions{nullptr};
    size_t                       m_action{0};
    bool                         m_in_after{false};
    bool                         m_busy{false};
    bool                         m_call_running{false};
    bool                         m_call_done{true};
    bool                         m_slice_wait{false};
    int                          m_slice_count{0};
    int                          m_wait_ms{0};
    int                          m_seq{0};
    int                          m_errors{0};
    int                          m_capture_seq{0};
    std::set<wxTopLevelWindow*>  m_baseline;
    wxTopLevelWindow*            m_target{nullptr};
    wxMenu*                      m_open_menu{nullptr};
    std::string                  m_menu_tree;
    std::vector<wxWebView*>      m_webviews;
    std::vector<std::string>     m_script_results;
    size_t                       m_scripts_pending{0};
};

} // namespace

void start_golden_driver_if_requested()
{
    // post_init() can run again on Linux (GH #5537 workaround in GUI_App), so
    // only the first call may start the driver.
    static bool started = false;
    if (started)
        return;
    started = true;
    const std::string dir = env("COSMYX_GUI_DRIVER_DIR");
    if (dir.empty())
        return;
    BOOST_LOG_TRIVIAL(info) << "Cosmyx goldens: driver started, folder " << dir;
    // Never deleted: the driver lives until the process ends (the harness
    // kills the application once it read the done event), and destroying a
    // timer after wxWidgets shut down would crash the exit.
    new Driver(fs::path(dir));
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
