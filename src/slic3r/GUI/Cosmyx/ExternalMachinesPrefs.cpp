#include "ExternalMachinesPrefs.hpp"

#include <cstddef>

#include <boost/log/trivial.hpp>

#include <wx/defs.h>
#include <wx/event.h>
#include <wx/sizer.h>
#include <wx/string.h>
#include <wx/tglbtn.h>
#include <wx/window.h>

#include "slic3r/GUI/I18N.hpp"
#include "slic3r/GUI/MsgDialog.hpp"
#include "slic3r/GUI/Widgets/CheckBox.hpp"
#include "slic3r/GUI/Widgets/StaticLine.hpp"
#include "logic/ExternalMachines.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

// Upstream builds each row as a horizontal sizer holding its widgets, and each
// section title as a sizer holding one StaticLine (PreferencesDialog::
// create_item_title()). These helpers only read that shape.

::CheckBox* find_checkbox(wxSizer* row)
{
    for (wxSizerItem* item : row->GetChildren()) {
        if (auto* checkbox = dynamic_cast<::CheckBox*>(item->GetWindow()))
            return checkbox;
        if (wxSizer* nested = item->GetSizer())
            if (::CheckBox* checkbox = find_checkbox(nested))
                return checkbox;
    }
    return nullptr;
}

StaticLine* title_line(wxSizerItem* item)
{
    if (item == nullptr || item->GetSizer() == nullptr)
        return nullptr;
    for (wxSizerItem* child : item->GetSizer()->GetChildren())
        if (auto* line = dynamic_cast<StaticLine*>(child->GetWindow()))
            return line;
    return nullptr;
}

int index_of(wxSizer* page, wxSizer* row)
{
    int index = 0;
    for (wxSizerItem* item : page->GetChildren()) {
        if (item->GetSizer() == row)
            return index;
        ++index;
    }
    return wxNOT_FOUND;
}

wxSizerItem* item_at(wxSizer* page, int index)
{
    if (index < 0 || std::size_t(index) >= page->GetItemCount())
        return nullptr;
    return page->GetItem(std::size_t(index));
}

bool confirm_enable(wxWindow* anchor)
{
    MessageDialog dlg(wxGetTopLevelParent(anchor),
                      // TRN Warning shown in Preferences before "Enable Bambu Cloud" or "Enable Bambu network plug-in" is turned on.
                      _L("This module has not been verified by Cosmyx and relies on machines the Cosmyx team does not support. "
                         "Use it at your own risk."),
                      // TRN Caption of the warning, named after the Preferences section holding the two toggles.
                      _L("External machines"), wxYES | wxCANCEL | wxICON_WARNING);
    // TRN Button of the warning that turns the module on.
    dlg.SetButtonLabel(wxID_YES, _L("Enable"));
    return dlg.ShowModal() == wxID_YES;
}

void guard_toggle(::CheckBox* checkbox)
{
    if (checkbox == nullptr) {
        BOOST_LOG_TRIVIAL(warning) << "Cosmyx: an External machines toggle was not found, it is left without its warning";
        return;
    }
    // Bound after upstream's handler, so wx calls this one first: dynamic
    // handlers run in reverse order of binding. Not skipping the event keeps
    // upstream's handler, which saves the setting, from ever seeing a cancel.
    checkbox->Bind(wxEVT_TOGGLEBUTTON, [checkbox](wxCommandEvent& e) {
        const bool turned_on = checkbox->GetValue();
        const bool confirmed = external_toggle_needs_warning(turned_on) && confirm_enable(checkbox);
        const ExternalToggleOutcome outcome = external_toggle_outcome(turned_on, confirmed);
        checkbox->SetValue(outcome.value);
        if (outcome.apply)
            e.Skip();
    });
}

// Moves the Bambu Cloud row right above the network plug-in row and renames
// the plug-in section "External machines". The section the Bambu Cloud row
// leaves is removed with its title when the row was its only one.
void gather_rows(wxSizer* page, wxSizer* bambu_cloud_row, wxSizer* network_plugin_row)
{
    const int plugin_index = index_of(page, network_plugin_row);
    StaticLine* plugin_title = title_line(item_at(page, plugin_index - 1));
    if (plugin_index == wxNOT_FOUND || plugin_title == nullptr) {
        BOOST_LOG_TRIVIAL(warning) << "Cosmyx: the network plug-in section was not found, External machines is left as upstream built it";
        return;
    }
    // TRN Title of the Preferences section holding the Bambu Cloud and Bambu network plug-in toggles.
    plugin_title->SetLabel(_L("External machines"));

    const int cloud_index = index_of(page, bambu_cloud_row);
    if (cloud_index == wxNOT_FOUND)
        return;
    wxSizerItem* above = item_at(page, cloud_index - 1);
    wxSizerItem* below = item_at(page, cloud_index + 1);
    const bool only_row = title_line(above) != nullptr && (below == nullptr || title_line(below) != nullptr);
    page->Detach(bambu_cloud_row);
    if (only_row) {
        // Destroyed rather than hidden: switching tabs shows every item of the page again.
        wxSizer* old_title = above->GetSizer();
        old_title->Clear(true);
        page->Remove(old_title);
    }
    page->Insert(std::size_t(index_of(page, network_plugin_row)), bambu_cloud_row);
}

} // namespace

void setup_external_machines(wxSizer* page, wxSizer* bambu_cloud_row, wxSizer* network_plugin_row)
{
    if (page == nullptr || bambu_cloud_row == nullptr || network_plugin_row == nullptr)
        return;
    guard_toggle(find_checkbox(bambu_cloud_row));
    guard_toggle(find_checkbox(network_plugin_row));
    gather_rows(page, bambu_cloud_row, network_plugin_row);
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
