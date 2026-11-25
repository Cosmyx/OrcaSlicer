#include "UiLocales.hpp"

#include <algorithm>
#include <cctype>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

const std::vector<UiLocale>& ui_locales()
{
    static const std::vector<UiLocale> table{
#define COSMYX_UI_LOCALE(code, wx_id, catalog, source, seed, name, rtl, script, plural_forms) \
    UiLocale{code, #wx_id, catalog, CatalogSource::source, seed, name, rtl, Script::script, plural_forms},
#include "UiLocaleTable.inc"
#undef COSMYX_UI_LOCALE
    };
    return table;
}

namespace {

// "fr-FR.UTF-8@euro" -> language "fr", region "FR".
void split_locale_name(std::string_view name, std::string& language, std::string& region)
{
    const size_t end = name.find_first_of(".@");
    if (end != std::string_view::npos)
        name = name.substr(0, end);
    const size_t sep = name.find_first_of("_-");
    language.assign(name.substr(0, sep));
    region.assign(sep == std::string_view::npos ? std::string_view() : name.substr(sep + 1));
    std::transform(language.begin(), language.end(), language.begin(), [](unsigned char c) { return char(std::tolower(c)); });
    std::transform(region.begin(), region.end(), region.begin(), [](unsigned char c) { return char(std::toupper(c)); });
}

} // namespace

const UiLocale* match_ui_locale(std::string_view name)
{
    std::string language, region;
    split_locale_name(name, language, region);
    if (language.empty())
        return nullptr;
    const std::vector<UiLocale>& table = ui_locales();
    const std::string code = region.empty() ? language : language + "_" + region;
    for (const UiLocale& row : table)
        if (row.code == code)
            return &row;
    const UiLocale* first = nullptr;
    for (const UiLocale& row : table) {
        if (row.language() != language)
            continue;
        if (row.catalog == language)
            return &row;
        if (first == nullptr)
            first = &row;
    }
    return first;
}

const UiLocale& fallback_ui_locale()
{
    // British English is the only English offered; its untranslated strings
    // show the source English.
    return *match_ui_locale("en_GB");
}

std::vector<const UiLocale*> offered_ui_locales(const std::vector<std::string>& available_catalogs)
{
    std::vector<const UiLocale*> out;
    for (const UiLocale& row : ui_locales()) {
        const bool available = std::find(available_catalogs.begin(), available_catalogs.end(), row.catalog) != available_catalogs.end();
        if (available || row.language() == "en")
            out.push_back(&row);
    }
    return out;
}

bool imgui_fonts_cover(Script script)
{
    switch (script) {
    case Script::Arabic:
    case Script::Devanagari: return false;
    default: return true;
    }
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
