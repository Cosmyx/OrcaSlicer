#include "CosmyxPrinterConnectionDialog.hpp"

#include <algorithm>
#include <atomic>
#include <cstddef>
#include <initializer_list>
#include <memory>
#include <optional>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <boost/format.hpp>
#include <boost/log/trivial.hpp>

#include <wx/colour.h>
#include <wx/dialog.h>
#include <wx/event.h>
#include <wx/font.h>
#include <wx/gdicmn.h>
#include <wx/panel.h>
#include <wx/scrolwin.h>
#include <wx/simplebook.h>
#include <wx/sizer.h>
#include <wx/string.h>
#include <wx/textctrl.h>
#include <wx/window.h>

#include "libslic3r/Config.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/PresetBundle.hpp"
#include "libslic3r/PrintConfig.hpp"

#include "slic3r/GUI/GUI.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/GUI_Utils.hpp"
#include "slic3r/GUI/I18N.hpp"
#include "slic3r/GUI/MainFrame.hpp"
#include "slic3r/GUI/SavePresetDialog.hpp"
#include "slic3r/GUI/Tab.hpp"
#include "slic3r/GUI/format.hpp"
#include "slic3r/GUI/Widgets/Button.hpp"
#include "slic3r/GUI/Widgets/DialogButtons.hpp"
#include "slic3r/GUI/Widgets/Label.hpp"
#include "slic3r/GUI/Widgets/StateColor.hpp"
#include "slic3r/GUI/Widgets/TextInput.hpp"
#include "slic3r/Utils/Http.hpp"
#include "slic3r/Utils/PrintHost.hpp"

#include "CosmyxMachineHook.hpp"
#include "logic/CosmyxPrinterConnection.hpp"
#include "logic/CosmyxPrinterConnectionInfo.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

// CosmOS API requests: the machine is on the local network, so a short
// connection timeout keeps a wrong address from hanging the tab.
const long k_connect_timeout_s = 5;
const long k_request_timeout_s = 10;

const int k_page_setup = 0;
const int k_page_info  = 1;

wxColour hint_colour() { return wxColour(255, 111, 0); }

// One finished GET request, as Orca's Http class reports it.
struct Reply
{
    bool        ok     = false;
    unsigned    status = 0;
    std::string body;
    std::string error;
};

// Runs on a worker thread only.
Reply http_get(const std::string& url, const std::string& api_key)
{
    Reply reply;
    auto  http = Http::get(url);
    if (!api_key.empty())
        http.header("X-Api-Key", api_key);
    http.timeout_connect(k_connect_timeout_s)
        .timeout_max(k_request_timeout_s)
        .on_complete([&reply](std::string body, unsigned status) {
            reply.ok     = true;
            reply.status = status;
            reply.body   = std::move(body);
        })
        .on_error([&reply](std::string body, std::string error, unsigned status) {
            reply.status = status;
            reply.body   = std::move(body);
            reply.error  = std::move(error);
        })
        .perform_sync();
    return reply;
}

// What one endpoint gave: a value, or why there is none.
template<class T> struct Fetched
{
    std::optional<T>           value;
    std::optional<HttpFailure> failure;
    unsigned                   status = 0;
};

template<class T, class Parser> Fetched<T> fetch(const ConnectionSettings& settings, const char* path, Parser parse)
{
    Fetched<T>  result;
    const Reply reply = http_get(cosmos_api_url(settings.host, path), settings.api_key);
    result.status     = reply.status;
    if (!reply.ok) {
        result.failure = classify_http_failure(reply.status, reply.error);
        return result;
    }
    result.value = parse(reply.body);
    if (!result.value)
        result.failure = HttpFailure::BadResponse;
    return result;
}

struct MachineInfo
{
    Fetched<DeviceInfo>          device;
    Fetched<InstalledOptions>    options;
    Fetched<std::vector<HotEnd>> hot_ends;
    Fetched<CameraInfo>          camera;
};

wxString failure_text(HttpFailure failure, unsigned status)
{
    switch (failure) {
    case HttpFailure::Unauthorized:
        return _L("The machine refused the API key (HTTP 401). Check the API key in the Setup tab.");
    case HttpFailure::Forbidden: return _L("The API key is not allowed to read this information (HTTP 403).");
    case HttpFailure::NotFound: return _L("The machine does not provide this information (HTTP 404).");
    case HttpFailure::Timeout:
        return _L("The machine did not answer in time. Check that it is switched on and connected to the network.");
    case HttpFailure::Unreachable: return _L("Could not reach the machine. Check the address and the network.");
    case HttpFailure::HttpError:
        // TRN %1% is an HTTP status code, for example 500.
        return format_wxstr(_L("The machine answered with an error (HTTP %1%)."), status);
    case HttpFailure::BadResponse: break;
    }
    return _L("The machine sent an answer that could not be read.");
}

wxString host_error_text(HostError error)
{
    switch (error) {
    case HostError::None: return {};
    case HostError::Empty: return _L("Enter the IP address or the host name of the machine.");
    case HostError::Whitespace: return _L("The address must not contain spaces.");
    case HostError::Scheme: return _L("Enter the address only, without http:// or https://.");
    case HostError::Path: return _L("Enter the address only, without a path after it.");
    case HostError::UserInfo: return _L("The address must not contain a user name.");
    case HostError::Port: return _L("The port must be a number from 1 to 65535.");
    case HostError::Ipv4: return _L("This IPv4 address is not valid.");
    case HostError::Hostname: return _L("This host name is not valid.");
    }
    return {};
}

wxString text_or_dash(const std::optional<std::string>& value) { return value && !value->empty() ? from_u8(*value) : wxString("-"); }

wxString yes_no(const std::optional<bool>& value)
{
    if (!value)
        return "-";
    return *value ? _L("Yes") : _L("No");
}

wxString number_with_unit(const std::optional<double>& value, const char* unit)
{
    if (!value)
        return "-";
    return from_u8(format_number(*value) + " " + unit);
}

std::string option_string(const DynamicPrintConfig& config, const char* key)
{
    const ConfigOption* option = config.option(key);
    return option != nullptr ? option->serialize() : std::string();
}

// The connection the saved printer preset describes.
std::optional<ConnectionSettings> saved_settings_of(const Preset& preset)
{
    return saved_connection(option_string(preset.config, "host_type"), option_string(preset.config, "print_host"),
                            option_string(preset.config, "printhost_apikey"));
}

class CosmyxPrinterConnectionDialog : public DPIDialog
{
public:
    explicit CosmyxPrinterConnectionDialog(wxWindow* parent);
    ~CosmyxPrinterConnectionDialog() override { m_alive->store(false); }

protected:
    void on_dpi_changed(const wxRect& suggested_rect) override;
    void on_sys_color_changed() override;

private:
    wxWindow* build_setup_page(wxWindow* parent);
    wxWindow* build_info_page(wxWindow* parent);
    void      add_field(wxWindow* parent, wxBoxSizer* sizer, const wxString& title, ::TextInput** input, Label** hint, const wxString& value);
    Label*    add_hint(wxWindow* parent);

    void select_page(int page);
    // Grows the dialog when shown hints or messages need more room, never shrinks it.
    void refit();
    void style_tabs();
    void update_setup();
    void update_lock();
    // The Setup values when all of them are valid.
    std::optional<ConnectionSettings> typed_settings() const;
    bool                              save();
    void                              start_test(const ConnectionSettings& settings, bool automatic);
    void                              on_test_done(int generation, ConnectionSettings settings, bool ok, wxString message, bool automatic);
    void                              start_fetch();
    void                              on_fetch_done(int generation, MachineInfo info);
    void                              show_info(const MachineInfo& info);
    void                              add_section(wxSizer* sizer, const wxString& title);
    void                              add_row(wxFlexGridSizer* grid, const wxString& label, const wxString& value);
    void                              add_failure(wxSizer* sizer, HttpFailure failure, unsigned status);

    std::shared_ptr<std::atomic<bool>> m_alive = std::make_shared<std::atomic<bool>>(true);

    PresetCollection* m_presets = nullptr;
    int               m_page    = k_page_setup;

    Button*        m_tab_setup = nullptr;
    Button*        m_tab_info  = nullptr;
    wxSimplebook*  m_book      = nullptr;
    DialogButtons* m_buttons   = nullptr;

    ::TextInput* m_name_input  = nullptr;
    Label*       m_name_hint   = nullptr;
    ::TextInput* m_host_input  = nullptr;
    Label*       m_host_hint   = nullptr;
    ::TextInput* m_key_input   = nullptr;
    Label*       m_key_hint    = nullptr;
    Button*      m_test_button = nullptr;
    Label*       m_test_status = nullptr;

    Label*            m_lock_hint      = nullptr;
    Button*           m_refresh_button = nullptr;
    Label*            m_info_status    = nullptr;
    wxScrolledWindow* m_info_panel     = nullptr;

    std::optional<ConnectionSettings> m_saved;
    std::optional<ConnectionSettings> m_last_successful_test;
    bool                              m_name_valid       = false;
    int                               m_test_generation  = 0;
    bool                              m_test_running     = false;
    int                               m_fetch_generation = 0;
    bool                              m_fetch_running    = false;
    bool                              m_info_loaded      = false;
};

CosmyxPrinterConnectionDialog::CosmyxPrinterConnectionDialog(wxWindow* parent)
    : DPIDialog(parent ? parent : static_cast<wxWindow*>(wxGetApp().mainframe), wxID_ANY, _L("Physical Printer"), wxDefaultPosition,
                wxDefaultSize, wxCAPTION | wxCLOSE_BOX | wxRESIZE_BORDER)
{
    SetBackgroundColour(*wxWHITE);
    SetFont(Label::Body_14);

    Tab* tab  = wxGetApp().get_tab(Preset::TYPE_PRINTER);
    m_presets = tab->get_presets();
    m_saved   = saved_settings_of(m_presets->get_selected_preset());

    auto* sizer = new wxBoxSizer(wxVERTICAL);

    auto* tabs = new wxBoxSizer(wxHORIZONTAL);
    m_tab_setup = new Button(this, _L("Setup"));
    m_tab_info  = new Button(this, _L("Machine information"));
    m_tab_info->EnableTooltipEvenDisabled();
    m_tab_setup->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { select_page(k_page_setup); });
    m_tab_info->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { select_page(k_page_info); });
    tabs->Add(m_tab_setup, 0, wxRIGHT, FromDIP(8));
    tabs->Add(m_tab_info, 0);
    sizer->Add(tabs, 0, wxLEFT | wxRIGHT | wxTOP, FromDIP(16));

    m_book = new wxSimplebook(this, wxID_ANY);
    m_book->SetBackgroundColour(*wxWHITE);
    m_book->AddPage(build_setup_page(m_book), wxEmptyString);
    m_book->AddPage(build_info_page(m_book), wxEmptyString);
    sizer->Add(m_book, 1, wxEXPAND | wxALL, FromDIP(16));

    m_buttons = new DialogButtons(this, {"Apply", "OK", "Cancel"}, _L("OK"));
    m_buttons->GetAPPLY()->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { save(); });
    m_buttons->GetOK()->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) {
        // Like upstream OnOK: stay open when the save did not happen.
        if (save())
            EndModal(wxID_OK);
    });
    m_buttons->GetCANCEL()->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { EndModal(wxID_CANCEL); });
    sizer->Add(m_buttons, 0, wxEXPAND);

    update_setup();
    select_page(k_page_setup);

    SetSizerAndFit(sizer);
    CenterOnParent();
    wxGetApp().UpdateDlgDarkUI(this);

    // An already configured machine: check it in the background, so the
    // "Machine information" tab unlocks without a manual test.
    if (m_saved)
        start_test(*m_saved, true);
}

Label* CosmyxPrinterConnectionDialog::add_hint(wxWindow* parent)
{
    auto* hint = new Label(parent, Label::Body_12, wxEmptyString, LB_AUTO_WRAP);
    hint->SetForegroundColour(hint_colour());
    hint->SetMaxSize(wxSize(FromDIP(420), -1));
    hint->Hide();
    return hint;
}

void CosmyxPrinterConnectionDialog::add_field(
    wxWindow* parent, wxBoxSizer* sizer, const wxString& title, ::TextInput** input, Label** hint, const wxString& value)
{
    auto* label = new Label(parent, Label::Head_14, title);
    *input      = new ::TextInput(parent, value, wxEmptyString, wxEmptyString, wxDefaultPosition, wxSize(FromDIP(420), -1));
    (*input)->GetTextCtrl()->Bind(wxEVT_TEXT, [this](wxCommandEvent& e) {
        update_setup();
        e.Skip();
    });
    *hint = add_hint(parent);
    sizer->Add(label, 0, wxTOP, FromDIP(12));
    sizer->Add(*input, 0, wxEXPAND | wxTOP, FromDIP(4));
    sizer->Add(*hint, 0, wxEXPAND | wxTOP, FromDIP(4));
}

wxWindow* CosmyxPrinterConnectionDialog::build_setup_page(wxWindow* parent)
{
    auto* page = new wxPanel(parent);
    page->SetBackgroundColour(*wxWHITE);
    auto* sizer = new wxBoxSizer(wxVERTICAL);

    // Same default name as upstream PhysicalPrinterDialog.
    const Preset&     selected = m_presets->get_selected_preset();
    const std::string suffix   = _u8L_CONTEXT(L_CONTEXT("Copy", "PresetName"), "PresetName");
    const std::string name     = selected.is_default ? _u8L("Untitled") :
                                 selected.is_system  ? (boost::format("%1% - %2%") % selected.name % suffix).str() :
                                                       selected.name;

    // Prefill from the edited preset, the values upstream's dialog shows too.
    const DynamicPrintConfig&        edited = m_presets->get_edited_preset().config;
    const std::optional<std::string> host   = host_from_octoprint_url(option_string(edited, "print_host"));

    add_field(page, sizer, _L("Save as"), &m_name_input, &m_name_hint, from_u8(name));
    add_field(page, sizer, _L("Machine IP"), &m_host_input, &m_host_hint, host ? from_u8(*host) : wxString());
    m_host_input->GetTextCtrl()->SetHint("192.0.2.10");
    add_field(page, sizer, _L("API key"), &m_key_input, &m_key_hint, from_u8(option_string(edited, "printhost_apikey")));

    auto* test_row = new wxBoxSizer(wxHORIZONTAL);
    m_test_button  = new Button(page, _L("Test connection"));
    m_test_button->SetStyle(ButtonStyle::Regular, ButtonType::Parameter);
    m_test_button->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) {
        if (const std::optional<ConnectionSettings> settings = typed_settings())
            start_test(*settings, false);
    });
    test_row->Add(m_test_button, 0, wxALIGN_CENTER_VERTICAL);
    sizer->Add(test_row, 0, wxTOP, FromDIP(16));

    m_test_status = new Label(page, Label::Body_12, wxEmptyString, LB_AUTO_WRAP);
    m_test_status->SetMaxSize(wxSize(FromDIP(420), -1));
    sizer->Add(m_test_status, 0, wxEXPAND | wxTOP, FromDIP(8));

    page->SetSizer(sizer);
    return page;
}

wxWindow* CosmyxPrinterConnectionDialog::build_info_page(wxWindow* parent)
{
    auto* page = new wxPanel(parent);
    page->SetBackgroundColour(*wxWHITE);
    auto* sizer = new wxBoxSizer(wxVERTICAL);

    m_lock_hint = new Label(page, Label::Body_12,
                            _L("Save the settings and run a successful connection test to see the machine information."), LB_AUTO_WRAP);
    m_lock_hint->SetMaxSize(wxSize(FromDIP(420), -1));
    sizer->Add(m_lock_hint, 0, wxEXPAND | wxBOTTOM, FromDIP(8));

    auto* top        = new wxBoxSizer(wxHORIZONTAL);
    m_refresh_button = new Button(page, _L("Refresh"));
    m_refresh_button->SetStyle(ButtonStyle::Regular, ButtonType::Parameter);
    m_refresh_button->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { start_fetch(); });
    m_info_status = new Label(page, Label::Body_12, wxEmptyString);
    top->Add(m_refresh_button, 0, wxALIGN_CENTER_VERTICAL);
    top->Add(m_info_status, 1, wxALIGN_CENTER_VERTICAL | wxLEFT, FromDIP(8));
    sizer->Add(top, 0, wxEXPAND);

    m_info_panel = new wxScrolledWindow(page, wxID_ANY, wxDefaultPosition, wxSize(FromDIP(420), FromDIP(320)), wxVSCROLL);
    m_info_panel->SetBackgroundColour(*wxWHITE);
    m_info_panel->SetScrollRate(0, FromDIP(10));
    m_info_panel->SetSizer(new wxBoxSizer(wxVERTICAL));
    sizer->Add(m_info_panel, 1, wxEXPAND | wxTOP, FromDIP(8));

    page->SetSizer(sizer);
    return page;
}

void CosmyxPrinterConnectionDialog::refit()
{
    if (GetSizer() == nullptr)
        return;
    const wxSize min  = GetSizer()->ComputeFittingWindowSize(this);
    const wxSize size = GetSize();
    SetMinSize(min);
    if (size.x < min.x || size.y < min.y)
        SetSize(wxSize(std::max(size.x, min.x), std::max(size.y, min.y)));
    for (size_t i = 0; i < m_book->GetPageCount(); ++i)
        m_book->GetPage(i)->Layout();
    Layout();
}

void CosmyxPrinterConnectionDialog::style_tabs()
{
    m_tab_setup->SetStyle(m_page == k_page_setup ? ButtonStyle::Confirm : ButtonStyle::Regular, ButtonType::Choice);
    m_tab_info->SetStyle(m_page == k_page_info ? ButtonStyle::Confirm : ButtonStyle::Regular, ButtonType::Choice);
}

void CosmyxPrinterConnectionDialog::select_page(int page)
{
    const bool unlocked = machine_info_unlocked(m_saved, m_last_successful_test);
    if (page == k_page_info && !unlocked)
        page = k_page_setup;
    m_page = page;
    m_book->ChangeSelection(static_cast<size_t>(page));
    update_lock();
    if (m_page == k_page_info && !m_info_loaded && !m_fetch_running)
        start_fetch();
}

void CosmyxPrinterConnectionDialog::update_lock()
{
    const bool unlocked = machine_info_unlocked(m_saved, m_last_successful_test);
    if (!unlocked && m_page == k_page_info) {
        m_page = k_page_setup;
        m_book->ChangeSelection(static_cast<size_t>(k_page_setup));
    }
    m_tab_info->Enable(unlocked);
    m_tab_info->SetToolTip(unlocked ? wxString() : m_lock_hint->GetLabel());
    m_lock_hint->Show(!unlocked);
    m_refresh_button->Enable(unlocked && !m_fetch_running);
    style_tabs();
    refit();
}

std::optional<ConnectionSettings> CosmyxPrinterConnectionDialog::typed_settings() const
{
    const HostCheck   host = check_host(into_u8(m_host_input->GetTextCtrl()->GetValue()));
    const ApiKeyCheck key  = check_api_key(into_u8(m_key_input->GetTextCtrl()->GetValue()));
    if (!host.ok() || !key.ok())
        return std::nullopt;
    return ConnectionSettings{host.host, key.key};
}

void CosmyxPrinterConnectionDialog::update_setup()
{
    // update_setup() runs from the field events, which may fire before every field exists.
    if (m_name_input == nullptr || m_host_input == nullptr || m_key_input == nullptr || m_test_button == nullptr)
        return;

    wxString               name_info;
    const PresetNameStatus name_status = check_preset_name(*m_presets, into_u8(m_name_input->GetTextCtrl()->GetValue()), name_info);
    m_name_valid = name_status != PresetNameStatus::Invalid;
    m_name_hint->SetLabel(name_info);
    m_name_hint->Show(!name_info.IsEmpty());

    const HostCheck host = check_host(into_u8(m_host_input->GetTextCtrl()->GetValue()));
    m_host_hint->SetLabel(host_error_text(host.error));
    m_host_hint->Show(!host.ok());

    const ApiKeyCheck key = check_api_key(into_u8(m_key_input->GetTextCtrl()->GetValue()));
    m_key_hint->SetLabel(key.ok() ? wxString() : _L("The API key must not contain spaces."));
    m_key_hint->Show(!key.ok());

    const bool settings_ok = host.ok() && key.ok();
    m_test_button->Enable(settings_ok && !m_test_running);
    if (m_buttons != nullptr) {
        m_buttons->GetOK()->Enable(settings_ok && m_name_valid);
        m_buttons->GetAPPLY()->Enable(settings_ok && m_name_valid);
    }
    refit();
}

bool CosmyxPrinterConnectionDialog::save()
{
    const std::optional<ConnectionSettings> settings = typed_settings();
    if (!settings || !m_name_valid)
        return false;

    // Only these four keys: every other print host setting stays as it is.
    const PrintHostValues values = print_host_values(*settings);
    DynamicPrintConfig&   config = m_presets->get_edited_preset().config;
    config.set_deserialize_strict({{"host_type", values.host_type},
                                   {"print_host", values.print_host},
                                   {"print_host_webui", values.print_host_webui},
                                   {"printhost_apikey", values.printhost_apikey}});

    const std::string name = into_u8(m_name_input->GetTextCtrl()->GetValue());
    if (!wxGetApp().get_tab(Preset::TYPE_PRINTER)->save_preset("", false, false, true, name))
        return false;

    m_saved = saved_settings_of(m_presets->get_selected_preset());
    // The saved preset may have a new name: re-check it (an existing name only warns).
    update_setup();
    update_lock();
    if (m_saved && !machine_info_unlocked(m_saved, m_last_successful_test))
        start_test(*m_saved, true);
    return true;
}

void CosmyxPrinterConnectionDialog::start_test(const ConnectionSettings& settings, bool automatic)
{
    // A copy of the edited printer config with the tested values: testing
    // never changes the preset.
    DynamicPrintConfig    config = m_presets->get_edited_preset().config;
    const PrintHostValues values = print_host_values(settings);
    config.set_deserialize_strict({{"host_type", values.host_type},
                                   {"print_host", values.print_host},
                                   {"print_host_webui", values.print_host_webui},
                                   {"printhost_apikey", values.printhost_apikey}});
    std::shared_ptr<PrintHost> host(PrintHost::get_print_host(&config));
    if (!host) {
        m_test_status->SetForegroundColour(hint_colour());
        m_test_status->SetLabel(_L("Could not get a valid Printer Host reference"));
        refit();
        return;
    }

    const int generation = ++m_test_generation;
    m_test_running       = true;
    m_test_status->SetForegroundColour(StateColor::darkModeColorFor(wxColour("#6B6B6B")));
    m_test_status->SetLabel(automatic ? _L("Checking the connection to the saved machine...") : _L("Testing the connection..."));
    update_setup();

    std::shared_ptr<std::atomic<bool>> alive = m_alive;
    std::thread([this, alive, host, settings, generation, automatic]() {
        // Upstream OctoPrint test: GET <print_host>api/version with the key.
        wxString   curl_msg;
        const bool ok = host->test(curl_msg);
        if (!alive->load() || wxGetApp().is_closing())
            return;
        wxGetApp().CallAfter([this, alive, host, settings, generation, automatic, ok, curl_msg]() {
            if (!alive->load())
                return;
            wxString message = curl_msg;
            on_test_done(generation, settings, ok, ok ? host->get_test_ok_msg() : host->get_test_failed_msg(message), automatic);
        });
    }).detach();
}

void CosmyxPrinterConnectionDialog::on_test_done(int generation, ConnectionSettings settings, bool ok, wxString message, bool automatic)
{
    if (generation != m_test_generation)
        return;
    m_test_running = false;
    if (ok)
        m_last_successful_test = settings;
    else if (m_last_successful_test == settings)
        m_last_successful_test.reset();
    m_test_status->SetForegroundColour(ok ? StateColor::darkModeColorFor(wxColour("#009688")) : hint_colour());
    m_test_status->SetLabel(message);
    BOOST_LOG_TRIVIAL(info) << "Cosmyx printer connection: " << (automatic ? "automatic" : "manual") << " test "
                            << (ok ? "succeeded" : "failed");
    update_setup();
    update_lock();
}

void CosmyxPrinterConnectionDialog::start_fetch()
{
    if (!machine_info_unlocked(m_saved, m_last_successful_test))
        return;
    const ConnectionSettings settings   = *m_saved;
    const int                generation = ++m_fetch_generation;
    m_fetch_running                     = true;
    m_info_status->SetLabel(_L("Reading the machine information..."));
    update_lock();

    std::shared_ptr<std::atomic<bool>> alive = m_alive;
    std::thread([this, alive, settings, generation]() {
        MachineInfo info;
        info.device = fetch<DeviceInfo>(settings, k_api_device, parse_device_info);
        // The other requests would fail the same way when the machine cannot be
        // reached or refuses the key.
        const bool reachable = !info.device.failure || *info.device.failure == HttpFailure::NotFound ||
                               *info.device.failure == HttpFailure::BadResponse || *info.device.failure == HttpFailure::HttpError;
        if (reachable && alive->load()) {
            info.options  = fetch<InstalledOptions>(settings, k_api_profile, parse_installed_options);
            info.hot_ends = fetch<std::vector<HotEnd>>(settings, k_api_nozzles, parse_hot_ends);
            info.camera   = fetch<CameraInfo>(settings, k_api_camera, parse_camera);
        }
        if (!alive->load() || wxGetApp().is_closing())
            return;
        wxGetApp().CallAfter([this, alive, generation, info = std::move(info)]() {
            if (alive->load())
                on_fetch_done(generation, info);
        });
    }).detach();
}

void CosmyxPrinterConnectionDialog::on_fetch_done(int generation, MachineInfo info)
{
    if (generation != m_fetch_generation)
        return;
    m_fetch_running = false;
    m_info_loaded   = true;
    m_info_status->SetLabel(wxEmptyString);
    show_info(info);
    update_lock();
}

void CosmyxPrinterConnectionDialog::add_section(wxSizer* sizer, const wxString& title)
{
    auto* label = new Label(m_info_panel, Label::Head_14, title);
    sizer->Add(label, 0, wxTOP | wxBOTTOM, FromDIP(6));
}

void CosmyxPrinterConnectionDialog::add_row(wxFlexGridSizer* grid, const wxString& label, const wxString& value)
{
    auto* name = new Label(m_info_panel, Label::Body_13, label);
    name->SetForegroundColour(StateColor::darkModeColorFor(wxColour("#6B6B6B")));
    auto* text = new Label(m_info_panel, Label::Body_13, value);
    grid->Add(name, 0, wxALIGN_CENTER_VERTICAL);
    grid->Add(text, 0, wxALIGN_CENTER_VERTICAL);
}

void CosmyxPrinterConnectionDialog::add_failure(wxSizer* sizer, HttpFailure failure, unsigned status)
{
    auto* label = new Label(m_info_panel, Label::Body_13, failure_text(failure, status), LB_AUTO_WRAP);
    label->SetForegroundColour(hint_colour());
    label->SetMaxSize(wxSize(FromDIP(400), -1));
    sizer->Add(label, 0, wxEXPAND | wxBOTTOM, FromDIP(4));
}

void CosmyxPrinterConnectionDialog::show_info(const MachineInfo& info)
{
    m_info_panel->Freeze();
    // Every child of the panel sits in its sizer: Clear(true) destroys them all.
    wxSizer* sizer = m_info_panel->GetSizer();
    sizer->Clear(true);
    auto  new_grid = [this, sizer]() {
        auto* grid = new wxFlexGridSizer(2, FromDIP(4), FromDIP(16));
        grid->AddGrowableCol(1);
        sizer->Add(grid, 0, wxEXPAND | wxBOTTOM, FromDIP(8));
        return grid;
    };

    add_section(sizer, _L("Identity"));
    if (const DeviceInfo* device = info.device.value ? &*info.device.value : nullptr) {
        wxFlexGridSizer* grid = new_grid();
        add_row(grid, _L("Model"), text_or_dash(device->model));
        add_row(grid, _L("Serial number"), text_or_dash(device->serial));
        add_row(grid, _L("Software version"), text_or_dash(device->software));
        add_row(grid, _L("Hardware version"), text_or_dash(device->hardware));
    } else if (info.device.failure) {
        add_failure(sizer, *info.device.failure, info.device.status);
    }

    // Nothing else was asked when the identity request could not reach the machine.
    const bool asked = info.options.value || info.options.failure;
    if (asked) {
        add_section(sizer, _L("Installed options"));
        if (const InstalledOptions* options = info.options.value ? &*info.options.value : nullptr) {
            wxFlexGridSizer* grid = new_grid();
            add_row(grid, _L("Speed mode"), text_or_dash(options->speed_mode));
            add_row(grid, _L("High temperature"), yes_no(options->high_temperature));
            add_row(grid, _L("Heated enclosure"), yes_no(options->enclosure_heated));
            add_row(grid, _L("Extraction system"), yes_no(options->extraction_system));
            add_row(grid, _L("Enclosure maximum temperature"), number_with_unit(options->enclosure_max_temperature, "\xC2\xB0" "C"));
            add_row(grid, _L("Heated bed"), yes_no(options->bed_heated));
            add_row(grid, _L("Bed maximum temperature"), number_with_unit(options->bed_max_temperature, "\xC2\xB0" "C"));
            add_row(grid, _L("Uninterrupted power supply"), yes_no(options->uninterrupted_power_supply));
            wxString volume = "-";
            if (options->build_volume_x && options->build_volume_y && options->build_volume_z)
                volume = from_u8(format_number(*options->build_volume_x) + " \xC3\x97 " + format_number(*options->build_volume_y) +
                                 " \xC3\x97 " + format_number(*options->build_volume_z) + " mm");
            add_row(grid, _L("Build volume"), volume);
            add_row(grid, _L("Bed probe"), text_or_dash(options->bed_probe));
        } else {
            add_failure(sizer, *info.options.failure, info.options.status);
        }

        add_section(sizer, _L("Hot ends"));
        if (const std::vector<HotEnd>* hot_ends = info.hot_ends.value ? &*info.hot_ends.value : nullptr) {
            if (hot_ends->empty()) {
                sizer->Add(new Label(m_info_panel, Label::Body_13, _L("The machine reports no hot end.")), 0, wxBOTTOM, FromDIP(8));
            }
            for (const HotEnd& hot_end : *hot_ends) {
                wxFlexGridSizer* grid = new_grid();
                // TRN %1% is the head number reported by the machine (0, 1, ...).
                add_row(grid, format_wxstr(_L("Head %1%"), hot_end.head ? std::to_string(*hot_end.head) : std::string("-")),
                        text_or_dash(hot_end.hotend));
                add_row(grid, _L("Nozzle diameter"), number_with_unit(hot_end.output, "mm"));
                add_row(grid, _L("Hardened"), yes_no(hot_end.hardened));
                add_row(grid, _L("Maximum temperature"), number_with_unit(hot_end.max_temperature, "\xC2\xB0" "C"));
                add_row(grid, _L("Direct drive"), yes_no(hot_end.direct));
            }
        } else {
            add_failure(sizer, *info.hot_ends.failure, info.hot_ends.status);
        }

        add_section(sizer, _L("Camera"));
        wxString camera;
        if (info.camera.value)
            camera = !info.camera.value->online ? wxString("-") : *info.camera.value->online ? _L("Online") : _L("Offline");
        else if (info.camera.failure && *info.camera.failure == HttpFailure::NotFound)
            camera = _L("No camera");
        else
            camera = info.camera.failure ? failure_text(*info.camera.failure, info.camera.status) : wxString("-");
        sizer->Add(new Label(m_info_panel, Label::Body_13, camera, LB_AUTO_WRAP), 0, wxEXPAND | wxBOTTOM, FromDIP(8));
    }

    wxGetApp().UpdateDarkUIWin(m_info_panel);
    m_info_panel->FitInside();
    m_info_panel->Layout();
    m_info_panel->Thaw();
}

void CosmyxPrinterConnectionDialog::on_dpi_changed(const wxRect& /*suggested_rect*/)
{
    m_tab_setup->Rescale();
    m_tab_info->Rescale();
    m_test_button->Rescale();
    m_refresh_button->Rescale();
    style_tabs();
    m_test_button->SetStyle(ButtonStyle::Regular, ButtonType::Parameter);
    m_refresh_button->SetStyle(ButtonStyle::Regular, ButtonType::Parameter);
    for (::TextInput* input : {m_name_input, m_host_input, m_key_input}) {
        input->Rescale();
        input->SetMinSize(wxSize(FromDIP(420), -1));
    }
    m_info_panel->SetMinSize(wxSize(FromDIP(420), FromDIP(320)));
    m_info_panel->SetScrollRate(0, FromDIP(10));
    GetSizer()->SetSizeHints(this);
    Refresh();
}

void CosmyxPrinterConnectionDialog::on_sys_color_changed()
{
    // Hand-picked colours are dark-mapped when set; the rest follows UpdateDlgDarkUI.
    m_name_hint->SetForegroundColour(hint_colour());
    m_host_hint->SetForegroundColour(hint_colour());
    m_key_hint->SetForegroundColour(hint_colour());
    style_tabs();
    wxGetApp().UpdateDlgDarkUI(this);
    Refresh();
}

} // namespace

bool show_cosmyx_printer_dialog(wxWindow* parent)
{
    if (!current_printer_is_cosmyx())
        return false;
    CosmyxPrinterConnectionDialog dialog(parent);
    dialog.ShowModal();
    return true;
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
