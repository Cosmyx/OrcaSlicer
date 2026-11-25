// Checks of the Cosmyx UI language table and its matching rules (decision
// 0220). scripts/cosmyx/tests/test_languages.py checks the same table from the
// catalogue side.

#include <catch2/catch_test_macros.hpp>

#include <set>
#include <string>
#include <string_view>
#include <vector>

#include "slic3r/GUI/Cosmyx/logic/UiLocales.hpp"

namespace CX = Slic3r::GUI::Cosmyx;

namespace {

std::string code_of(const CX::UiLocale* row) { return row == nullptr ? std::string("<none>") : std::string(row->code); }

} // namespace

TEST_CASE("The table lists exactly the offered languages", "[cosmyx][UiLocales]")
{
    const std::vector<std::string> expected{"ar_SA", "da_DK", "de_DE", "el_GR", "en_GB", "es_ES", "fi_FI", "fr_FR",
                                            "ga_IE", "hi_IN", "it_IT", "ja_JP", "ko_KR", "nb_NO", "nl_BE", "nl_NL",
                                            "pl_PL", "pt_PT", "sv_SE", "uk_UA", "vi_VN", "zh_CN", "zh_HK", "zh_TW"};
    std::vector<std::string> codes;
    std::set<std::string_view> catalogs;
    for (const CX::UiLocale& row : CX::ui_locales()) {
        codes.emplace_back(row.code);
        catalogs.insert(row.catalog);
        INFO(row.code);
        CHECK_FALSE(row.native_name.empty());
        CHECK_FALSE(row.wx_id.empty());
        CHECK(row.rtl == (row.script == CX::Script::Arabic));
        CHECK(row.plural_forms.empty() == (row.source == CX::CatalogSource::Upstream));
    }
    CHECK(codes == expected);
    CHECK(catalogs.size() == codes.size());
}

TEST_CASE("Locale names match their offered language", "[cosmyx][UiLocales]")
{
    CHECK(code_of(CX::match_ui_locale("fr_FR")) == "fr_FR");
    CHECK(code_of(CX::match_ui_locale("fr-FR")) == "fr_FR");
    CHECK(code_of(CX::match_ui_locale("fr_FR.UTF-8")) == "fr_FR");
    CHECK(code_of(CX::match_ui_locale("FR_fr")) == "fr_FR");
    CHECK(code_of(CX::match_ui_locale("fr")) == "fr_FR");
    CHECK(code_of(CX::match_ui_locale("fr_CA")) == "fr_FR");
    CHECK(code_of(CX::match_ui_locale("de_AT")) == "de_DE");

    SECTION("a bare language picks the variant named after its catalogue")
    {
        CHECK(code_of(CX::match_ui_locale("nl")) == "nl_NL");
        CHECK(code_of(CX::match_ui_locale("nl_BE")) == "nl_BE");
        CHECK(code_of(CX::match_ui_locale("en_US")) == "en_GB");
        CHECK(code_of(CX::match_ui_locale("pt_BR")) == "pt_PT");
        CHECK(code_of(CX::match_ui_locale("zh")) == "zh_CN");
        CHECK(code_of(CX::match_ui_locale("zh_HK")) == "zh_HK");
        CHECK(code_of(CX::match_ui_locale("zh_MO")) == "zh_CN");
        CHECK(code_of(CX::match_ui_locale("ar_EG")) == "ar_SA");
        CHECK(code_of(CX::match_ui_locale("nb")) == "nb_NO");
    }

    SECTION("languages that are not offered match nothing")
    {
        for (const char* name : {"ru_RU", "cs", "tr_TR", "th", "", "_", "@latin", "no_NO"})
            CHECK(CX::match_ui_locale(name) == nullptr);
    }

    CHECK(CX::fallback_ui_locale().code == "en_GB");
}

TEST_CASE("The selector offers the languages whose catalogue exists", "[cosmyx][UiLocales]")
{
    std::vector<std::string> found;
    for (const CX::UiLocale* row : CX::offered_ui_locales({"fr", "da_DK", "ru", "pt_BR"}))
        found.emplace_back(row->code);
    // English falls back to the source strings, so it is always offered.
    CHECK(found == std::vector<std::string>{"da_DK", "en_GB", "fr_FR"});
    CHECK(CX::offered_ui_locales({}).size() == 1);
}

TEST_CASE("Bundled ImGui fonts miss the Arabic and Devanagari scripts", "[cosmyx][UiLocales]")
{
    CHECK_FALSE(CX::imgui_fonts_cover(CX::Script::Arabic));
    CHECK_FALSE(CX::imgui_fonts_cover(CX::Script::Devanagari));
    CHECK(CX::imgui_fonts_cover(CX::Script::Greek));
    CHECK(CX::imgui_fonts_cover(CX::Script::Han));
}
