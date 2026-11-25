// The UI languages Cosmyx offers, and no others (decision 0220).
//
// This list is the single source of truth: the C++ code expands it through the
// COSMYX_UI_LOCALE macro (logic/UiLocales.cpp for the wxWidgets-free table,
// Languages.cpp for the wxLanguage ids), and scripts/cosmyx/languages.py parses
// it to generate, install and check the catalogues. Keep one row per line, in
// code order, with string literals and bare identifiers only.
//
// Columns:
//   code          locale stored in the app config ("language" key)
//   wx id         wxLanguage enum value, without its wxLANGUAGE_ prefix
//   catalogue     folder holding OrcaSlicer_<folder>.po and, once compiled,
//                 resources/i18n/<folder>/OrcaSlicer.mo
//   source        Upstream: localization/i18n/<folder> (never edited by Cosmyx)
//                 Cosmyx:   localization/cosmyx/i18n/<folder>, installed into
//                           localization/i18n at build time
//   seed          upstream catalogue a Cosmyx catalogue was first copied from
//                 (every copied entry is marked for review), or "" when it
//                 started untranslated
//   name          language name written in that language, for the selector
//   rtl           right-to-left layout
//   script        writing system, which decides the ImGui glyphs it needs
//   plural forms  gettext Plural-Forms of a Cosmyx catalogue; "" for an
//                 upstream catalogue, whose own header is authoritative
//
// COSMYX_UI_LOCALE(code, wx id, catalogue, source, seed, name, rtl, script, plural forms)
COSMYX_UI_LOCALE("da_DK", DANISH,               "da_DK", Cosmyx,   "",      "Dansk",                    false, Latin,      "nplurals=2; plural=(n != 1);")
COSMYX_UI_LOCALE("de_DE", GERMAN,               "de",    Upstream, "",      "Deutsch",                  false, Latin,      "")
COSMYX_UI_LOCALE("el_GR", GREEK,                "el_GR", Cosmyx,   "",      "Ελληνικά",                 false, Greek,      "nplurals=2; plural=(n != 1);")
COSMYX_UI_LOCALE("en_GB", ENGLISH_UK,           "en_GB", Cosmyx,   "en",    "English (United Kingdom)", false, Latin,      "nplurals=2; plural=(n != 1);")
COSMYX_UI_LOCALE("es_ES", SPANISH,              "es",    Upstream, "",      "Español",                  false, Latin,      "")
COSMYX_UI_LOCALE("fi_FI", FINNISH,              "fi_FI", Cosmyx,   "",      "Suomi",                    false, Latin,      "nplurals=2; plural=(n != 1);")
COSMYX_UI_LOCALE("fr_FR", FRENCH,               "fr",    Upstream, "",      "Français",                 false, Latin,      "")
COSMYX_UI_LOCALE("ga_IE", IRISH,                "ga_IE", Cosmyx,   "",      "Gaeilge",                  false, Latin,      "nplurals=5; plural=(n==1 ? 0 : n==2 ? 1 : n>=3 && n<=6 ? 2 : n>=7 && n<=10 ? 3 : 4);")
COSMYX_UI_LOCALE("it_IT", ITALIAN,              "it",    Upstream, "",      "Italiano",                 false, Latin,      "")
COSMYX_UI_LOCALE("ja_JP", JAPANESE,             "ja",    Upstream, "",      "日本語",                   false, Japanese,   "")
COSMYX_UI_LOCALE("ko_KR", KOREAN,               "ko",    Upstream, "",      "한국어",                   false, Hangul,     "")
COSMYX_UI_LOCALE("nb_NO", NORWEGIAN_BOKMAL,     "nb_NO", Cosmyx,   "",      "Norsk bokmål",             false, Latin,      "nplurals=2; plural=(n != 1);")
COSMYX_UI_LOCALE("nl_BE", DUTCH_BELGIAN,        "nl_BE", Cosmyx,   "nl",    "Nederlands (België)",      false, Latin,      "nplurals=2; plural=(n != 1);")
COSMYX_UI_LOCALE("nl_NL", DUTCH,                "nl",    Upstream, "",      "Nederlands (Nederland)",   false, Latin,      "")
COSMYX_UI_LOCALE("pl_PL", POLISH,               "pl",    Upstream, "",      "Polski",                   false, Latin,      "")
COSMYX_UI_LOCALE("pt_PT", PORTUGUESE,           "pt_PT", Cosmyx,   "pt_BR", "Português (Portugal)",     false, Latin,      "nplurals=2; plural=(n != 1);")
COSMYX_UI_LOCALE("sv_SE", SWEDISH,              "sv",    Upstream, "",      "Svenska",                  false, Latin,      "")
COSMYX_UI_LOCALE("uk_UA", UKRAINIAN,            "uk",    Upstream, "",      "Українська",               false, Cyrillic,   "")
COSMYX_UI_LOCALE("vi_VN", VIETNAMESE,           "vi",    Upstream, "",      "Tiếng Việt",               false, Latin,      "")
COSMYX_UI_LOCALE("zh_CN", CHINESE_SIMPLIFIED,   "zh_CN", Upstream, "",      "中文(简体)",               false, Han,        "")
COSMYX_UI_LOCALE("zh_HK", CHINESE_HONGKONG,     "zh_HK", Cosmyx,   "zh_TW", "中文(香港)",               false, Han,        "nplurals=1; plural=0;")
COSMYX_UI_LOCALE("zh_TW", CHINESE_TRADITIONAL,  "zh_TW", Upstream, "",      "中文(繁體)",               false, Han,        "")
