#include "Languages.hpp"

#include <string>
#include <string_view>

#include <boost/log/trivial.hpp>

#include <wx/translation.h>

#include "libslic3r_version.h"
#include "logic/UiLocales.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

// wxLanguage of each table row. Expanding the table here makes a wrong wx id a
// compile error.
wxLanguage wx_language(const UiLocale& row)
{
    struct Id { std::string_view code; wxLanguage language; };
    static const Id ids[] = {
#define COSMYX_UI_LOCALE(code, wx_id, catalog, source, seed, name, rtl, script, plural_forms) Id{code, wxLANGUAGE_##wx_id},
#include "logic/UiLocaleTable.inc"
#undef COSMYX_UI_LOCALE
    };
    for (const Id& id : ids)
        if (id.code == row.code)
            return id.language;
    return wxLANGUAGE_UNKNOWN;
}

const wxLanguageInfo* wx_info(const UiLocale& row)
{
    const wxLanguageInfo* info = wxLocale::GetLanguageInfo(wx_language(row));
    return info != nullptr ? info : wxLocale::FindLanguageInfo(wxString::FromUTF8(row.code.data(), row.code.size()));
}

const UiLocale* row_of(const wxLanguageInfo* info)
{
    return info == nullptr ? nullptr : match_ui_locale(info->CanonicalName.ToStdString());
}

} // namespace

void select_ui_languages(std::vector<const wxLanguageInfo*>& infos)
{
    std::vector<std::string> available;
    const wxArrayString translations = wxTranslations::Get()->GetAvailableTranslations(SLIC3R_APP_KEY);
    for (const wxString& name : translations)
        available.emplace_back(name.ToStdString());
    infos.clear();
    for (const UiLocale* row : offered_ui_locales(available))
        if (const wxLanguageInfo* info = wx_info(*row))
            infos.push_back(info);
}

wxString ui_language_name(const wxLanguageInfo* info, const wxString& fallback)
{
    const UiLocale* row = row_of(info);
    if (row == nullptr)
        return fallback;
    return wxString::FromUTF8(row->native_name.data(), row->native_name.size());
}

const wxLanguageInfo* ui_language_info(const wxLanguageInfo* requested, const wxLanguageInfo* resolved)
{
    const UiLocale* row = row_of(requested);
    if (row == nullptr)
        row = row_of(resolved);
    if (row == nullptr)
        row = &fallback_ui_locale();
    const wxLanguageInfo* info = wx_info(*row);
    if (info == nullptr) {
        BOOST_LOG_TRIVIAL(error) << "Cosmyx: wxWidgets does not know the UI language " << row->code;
        return resolved != nullptr ? resolved : wxLocale::GetLanguageInfo(wxLANGUAGE_ENGLISH_US);
    }
    if (info != resolved)
        BOOST_LOG_TRIVIAL(info) << "Cosmyx: UI language " << row->code << " (offered languages only, decision 0220)";
    return info;
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
