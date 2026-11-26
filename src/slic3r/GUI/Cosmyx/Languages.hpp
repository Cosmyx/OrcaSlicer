#ifndef slic3r_GUI_Cosmyx_Languages_hpp_
#define slic3r_GUI_Cosmyx_Languages_hpp_

// wxWidgets side of the Cosmyx UI languages (decision 0220): the table lives
// in logic/UiLocaleTable.inc, the matching rules in logic/UiLocales.hpp.

#include <vector>

#include <wx/intl.h>
#include <wx/string.h>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Replaces the languages the Preferences selector lists with the offered
// ones whose catalogue wxWidgets found, English always included, in code
// order. Hooked in PreferencesDialog::create_item_language_combobox().
void select_ui_languages(std::vector<const wxLanguageInfo*>& infos);

// The selector label of a language: its name in that language, or `fallback`
// for a language that is not offered.
wxString ui_language_name(const wxLanguageInfo* info, const wxString& fallback);

// The language GUI_App::load_language() switches to: the offered language
// matching `resolved` (what upstream picked from the app config, the system
// and the available translations), else British English. Never nullptr.
const wxLanguageInfo* ui_language_info(const wxLanguageInfo* resolved);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_Languages_hpp_
