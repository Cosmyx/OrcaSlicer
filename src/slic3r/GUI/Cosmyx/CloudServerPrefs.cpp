#include "CloudServerPrefs.hpp"

#include <array>
#include <cstddef>

#include <wx/colour.h>
#include <wx/event.h>
#include <wx/gdicmn.h>
#include <wx/panel.h>
#include <wx/sizer.h>
#include <wx/stattext.h>
#include <wx/string.h>
#include <wx/textctrl.h>
#include <wx/window.h>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/GUI.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/I18N.hpp"
#include "slic3r/GUI/MsgDialog.hpp"
#include "slic3r/GUI/Widgets/Button.hpp"
#include "slic3r/GUI/Widgets/CheckBox.hpp"
#include "slic3r/GUI/Widgets/Label.hpp"
#include "slic3r/GUI/Widgets/StateColor.hpp"
#include "slic3r/GUI/Widgets/TextInput.hpp"
#include "logic/CloudServer.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

// Same metrics and label colour as the Preferences rows (Preferences.hpp).
constexpr int LEFT_MARGIN = 25;
constexpr int LABEL_WIDTH = 280;
constexpr int INPUT_WIDTH = 260;
const wxColour LABEL_COLOUR("#363636");
const wxColour ERROR_COLOUR("#D01B1B");

wxString error_text(std::size_t field, CloudValueError error)
{
    if (field == PubKey)
        return error == CloudValueError::Empty ? _L("Enter the public key.") : _L("The public key must not contain spaces.");
    switch (error) {
    case CloudValueError::Empty: return _L("Enter an address.");
    case CloudValueError::NotHttps: return _L("The address must start with https:// (http:// only for localhost).");
    case CloudValueError::NoHost: return _L("The address has no host name.");
    default: return _L("This address is not valid.");
    }
}

class CloudServerPrefsPanel : public wxPanel
{
public:
    explicit CloudServerPrefsPanel(wxWindow* parent) : wxPanel(parent, wxID_ANY)
    {
        SetBackgroundColour(*wxWHITE); // palette colour, dark-mapped by UpdateDlgDarkUI

        const wxString tip = _L("Connect to your own cloud server instead of Cosmyx Cloud. "
                                "The cloud is only used when stealth mode is off.");

        auto* sizer = new wxBoxSizer(wxVERTICAL);

        auto* row = new wxBoxSizer(wxHORIZONTAL);
        row->AddSpacer(FromDIP(LEFT_MARGIN));
        row->Add(make_label(this, _L("Custom Cloud Instance"), tip), 0, wxALIGN_CENTER | wxTOP | wxBOTTOM, FromDIP(3));
        row->AddSpacer(FromDIP(5));
        m_checkbox = new ::CheckBox(this);
        m_checkbox->SetToolTip(tip);
        row->Add(m_checkbox, 0, wxALIGN_CENTER);
        auto* restart = make_label(this, _L("(Requires restart)"), tip, -1);
        row->Add(restart, 0, wxALIGN_CENTER | wxLEFT, FromDIP(5));
        sizer->Add(row, 0, wxEXPAND);

        m_fields = new wxPanel(this, wxID_ANY);
        m_fields->SetBackgroundColour(*wxWHITE);
        auto* fields_sizer = new wxBoxSizer(wxVERTICAL);
        const std::array<wxString, CLOUD_FIELD_COUNT> labels = {_L("API address"), _L("Authentication address"),
                                                                _L("Web address"), _L("Public key")};
        StateColor input_bg(std::pair<wxColour, int>(wxColour("#F0F0F1"), StateColor::Disabled),
                            std::pair<wxColour, int>(*wxWHITE, StateColor::Enabled));
        for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field) {
            auto* field_row = new wxBoxSizer(wxHORIZONTAL);
            field_row->AddSpacer(m_fields->FromDIP(LEFT_MARGIN));
            field_row->Add(make_label(m_fields, labels[field], labels[field]), 0, wxALIGN_CENTER_VERTICAL);
            field_row->AddSpacer(m_fields->FromDIP(5));
            m_inputs[field] = new ::TextInput(m_fields, wxEmptyString, wxEmptyString, wxEmptyString, wxDefaultPosition,
                                              wxSize(m_fields->FromDIP(INPUT_WIDTH), -1));
            m_inputs[field]->SetBackgroundColor(input_bg);
            m_inputs[field]->SetToolTip(labels[field]);
            field_row->Add(m_inputs[field], 0, wxALIGN_CENTER_VERTICAL);
            fields_sizer->Add(field_row, 0, wxTOP, m_fields->FromDIP(4));

            m_errors[field] = new wxStaticText(m_fields, wxID_ANY, wxEmptyString);
            m_errors[field]->SetForegroundColour(ERROR_COLOUR);
            m_errors[field]->SetFont(::Label::Body_12);
            m_errors[field]->Hide();
            fields_sizer->Add(m_errors[field], 0, wxLEFT, m_fields->FromDIP(LEFT_MARGIN + LABEL_WIDTH + 5));
        }
        m_apply = new Button(m_fields, _L("Apply"));
        m_apply->SetStyle(ButtonStyle::Confirm, ButtonType::Parameter);
        m_apply->SetToolTip(_L("Check the addresses and save them."));
        auto* apply_row = new wxBoxSizer(wxHORIZONTAL);
        apply_row->AddSpacer(m_fields->FromDIP(LEFT_MARGIN + LABEL_WIDTH + 5));
        apply_row->Add(m_apply, 0, wxALIGN_CENTER_VERTICAL);
        fields_sizer->Add(apply_row, 0, wxTOP, m_fields->FromDIP(4));
        m_fields->SetSizer(fields_sizer);
        sizer->Add(m_fields, 0, wxEXPAND | wxBOTTOM, FromDIP(4));

        SetSizer(sizer);

        AppConfig* config = wxGetApp().app_config;
        const bool custom = config != nullptr && custom_cloud_enabled(*config);
        m_checkbox->SetValue(custom);
        load_fields();
        m_fields->Show(custom);

        m_checkbox->Bind(wxEVT_TOGGLEBUTTON, [this](wxCommandEvent& e) {
            on_toggle(m_checkbox->GetValue());
            e.Skip(); // CheckBox refreshes its bitmap in its own handler
        });
        m_apply->Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { on_apply(); });
    }

private:
    static wxStaticText* make_label(wxWindow* parent, const wxString& text, const wxString& tip, int width = LABEL_WIDTH)
    {
        auto* label = new wxStaticText(parent, wxID_ANY, text, wxDefaultPosition,
                                       width < 0 ? wxDefaultSize : wxSize(parent->FromDIP(width), -1));
        label->SetForegroundColour(LABEL_COLOUR);
        label->SetFont(::Label::Body_14);
        label->SetToolTip(tip);
        label->Wrap(-1);
        return label;
    }

    void load_fields()
    {
        AppConfig* config = wxGetApp().app_config;
        if (config == nullptr)
            return;
        const CloudValues values = custom_cloud_values(*config);
        for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field)
            m_inputs[field]->GetTextCtrl()->SetValue(from_u8(values[field]));
    }

    void clear_errors()
    {
        for (wxStaticText* error : m_errors)
            error->Hide();
    }

    void relayout()
    {
        m_fields->Layout();
        Layout();
        InvalidateBestSize();
        if (wxWindow* page = GetParent()) {
            page->Layout();
            page->FitInside();
        }
    }

    void on_toggle(bool custom)
    {
        clear_errors();
        if (custom) {
            // Nothing is written until Apply accepts the values.
            load_fields();
        } else if (AppConfig* config = wxGetApp().app_config; config != nullptr && custom_cloud_enabled(*config)) {
            use_cosmocloud(*config);
            config->save();
            show_restart_note();
        }
        m_fields->Show(custom);
        relayout();
    }

    void on_apply()
    {
        AppConfig* config = wxGetApp().app_config;
        if (config == nullptr)
            return;
        CloudValues values;
        for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field)
            values[field] = into_u8(m_inputs[field]->GetTextCtrl()->GetValue());

        clear_errors();
        const CloudValidation result = normalize_cloud_values(values);
        if (!result.ok()) {
            m_errors[result.field]->SetLabel(error_text(result.field, result.error));
            m_errors[result.field]->Show();
            m_inputs[result.field]->GetTextCtrl()->SetFocus();
            relayout();
            return;
        }
        // Show the values as they are stored.
        for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field)
            m_inputs[field]->GetTextCtrl()->SetValue(from_u8(values[field]));
        use_custom_cloud(*config, values);
        config->save();
        relayout();
        show_restart_note();
    }

    void show_restart_note()
    {
        // The cloud agent reads the keys only when it is created (decision 0203).
        // Shown after the click handler returns; wx drops the call if the panel
        // is destroyed first.
        CallAfter([this]() {
            MessageDialog dlg(wxGetTopLevelParent(this), _L("Restart the application to connect to the new cloud server."),
                              _L("Restart Required"), wxOK | wxICON_INFORMATION);
            dlg.ShowModal();
        });
    }

    ::CheckBox*                                    m_checkbox = nullptr;
    wxPanel*                                       m_fields   = nullptr;
    Button*                                        m_apply    = nullptr;
    std::array<::TextInput*, CLOUD_FIELD_COUNT>    m_inputs{};
    std::array<wxStaticText*, CLOUD_FIELD_COUNT>   m_errors{};
};

} // namespace

wxWindow* create_cloud_server_prefs(wxWindow* parent) { return new CloudServerPrefsPanel(parent); }

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
