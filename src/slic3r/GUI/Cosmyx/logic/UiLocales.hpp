#ifndef slic3r_GUI_Cosmyx_logic_UiLocales_hpp_
#define slic3r_GUI_Cosmyx_logic_UiLocales_hpp_

// The UI languages Cosmyx offers (decision 0220), read from UiLocaleTable.inc.
//
// The Preferences language selector lists exactly these languages, and
// GUI_App::load_language() resolves every requested or detected language to
// one of them, falling back to British English, whose catalogue starts as a
// copy of the upstream English one and leaves untranslated strings in the
// source English. Upstream catalogues of other languages stay in the tree but
// are never offered.
//
// wxWidgets-free, so cosmyx_tests checks it directly; Languages.cpp maps the
// rows to wxLanguageInfo.

#include <string>
#include <string_view>
#include <vector>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Where a language's catalogue lives.
enum class CatalogSource {
    // localization/i18n/<catalogue>, owned by upstream and never edited.
    Upstream,
    // localization/cosmyx/i18n/<catalogue>, installed into localization/i18n
    // by scripts/cosmyx/languages.py before the build compiles the catalogues.
    Cosmyx,
};

// Writing system of a language, which decides the ImGui glyphs it needs.
enum class Script { Latin, Greek, Cyrillic, Arabic, Devanagari, Han, Japanese, Hangul };

struct UiLocale
{
    std::string_view code;         // "fr_FR", the value stored under the "language" app key
    std::string_view wx_id;        // wxLanguage enum name without wxLANGUAGE_, "FRENCH"
    std::string_view catalog;      // catalogue folder, "fr"
    CatalogSource    source;
    std::string_view seed;         // upstream catalogue a Cosmyx one was copied from, or empty
    std::string_view native_name;  // UTF-8 name of the language in that language
    bool             rtl;          // right-to-left layout
    Script           script;
    std::string_view plural_forms; // Plural-Forms of a Cosmyx catalogue, empty for an upstream one

    // Language part of the code, "fr" for "fr_FR".
    std::string_view language() const { return code.substr(0, code.find('_')); }
};

// Every offered language, in code order.
const std::vector<UiLocale>& ui_locales();

// The row for a locale name as wxWidgets or the app config spell it ("fr_FR",
// "fr-FR", "fr", "fr_CA", "fr_FR.UTF-8", "sr_RS@latin"): the exact code first,
// else the primary row of the same language (the one whose catalogue is named
// after the bare language, else the first one in code order). nullptr when no
// offered language matches.
const UiLocale* match_ui_locale(std::string_view name);

// The language used when nothing requested or detected is offered.
const UiLocale& fallback_ui_locale();

// Rows the selector lists, in code order: those whose catalogue folder is in
// `available_catalogs` (the translations wxWidgets found), plus the English
// rows, which fall back to the source strings and so are always usable.
std::vector<const UiLocale*> offered_ui_locales(const std::vector<std::string>& available_catalogs);

// Whether the fonts OrcaSlicer bundles for ImGui (resources/fonts) hold the
// glyphs of a script. False for Arabic and Devanagari, which is one reason no
// language written in them is offered yet (decision 0220).
bool imgui_fonts_cover(Script script);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_logic_UiLocales_hpp_
