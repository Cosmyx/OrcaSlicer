# 0220. The offered UI languages

## Status

Accepted.

## Context

The product offers exactly these 22 UI languages and no others: da_DK,
de_DE, el_GR, en_GB, es_ES, fi_FI, fr_FR, ga_IE, it_IT, ja_JP, ko_KR, nb_NO,
nl_BE, nl_NL, pl_PL, pt_PT, sv_SE, uk_UA, vi_VN, zh_CN, zh_HK, zh_TW.

OrcaSlicer ships catalogues for ca, cs, de, en, es, eu, fr, hu, it, ja, ko,
lt, nl, pl, pt_BR, ru, sv, th, tr, uk, vi, zh_CN and zh_TW in
`localization/i18n/<folder>/OrcaSlicer_<folder>.po`. Its build scripts
(`scripts/run_gettext.sh`, `scripts/run_gettext.bat`) compile every catalogue
found there into `resources/i18n/<folder>/OrcaSlicer.mo`, which the bundles
package as they are. wxWidgets looks a language up as
`<prefix>/<canonical>/` then `<prefix>/<language>/`, so `fr_FR` finds the `fr`
folder, but `pt_PT` never finds `pt_BR` and `zh_HK` never finds `zh_TW`.

The Preferences selector (`PreferencesDialog::create_item_language_combobox`)
lists a hard-coded set of wxLanguage values that have a catalogue, and
`GUI_App::load_language` refuses every right-to-left language. Upstream edits
both often, and every upstream catalogue changes with each template refresh,
so neither may be edited beyond one-line hooks (decision 0002).

## Decision

- One table, `src/slic3r/GUI/Cosmyx/logic/UiLocaleTable.inc`, lists the 22
  languages, one row per line: code, wxLanguage id, catalogue folder, catalogue
  source, seed, name in that language, right-to-left flag, script and, for a
  Cosmyx catalogue, its Plural-Forms. The C++ code expands it with the
  `COSMYX_UI_LOCALE` macro (a wrong wx id fails the build);
  `scripts/cosmyx/languages.py` parses it.
- A language OrcaSlicer ships uses its upstream catalogue, never edited:
  de_DE `de`, es_ES `es`, fr_FR `fr`, it_IT `it`, ja_JP `ja`, ko_KR `ko`, nl_NL
  `nl`, pl_PL `pl`, sv_SE `sv`, uk_UA `uk`, vi_VN `vi`, zh_CN `zh_CN`, zh_TW
  `zh_TW`.
- The other nine get a full catalogue in
  `localization/cosmyx/i18n/<code>/OrcaSlicer_<code>.po`, generated from
  `OrcaSlicer.pot` by `just languages-generate`, which keeps existing
  translations. en_GB, nl_BE, pt_PT and zh_HK start as copies of `en`, `nl`,
  `pt_BR` and `zh_TW`: every copied entry carries
  `# Needs human review: copied from the <seed> catalogue, ...`, never
  `fuzzy`, so it ships while the translator reviews it. da_DK, el_GR, fi_FI,
  ga_IE and nb_NO start untranslated. Their Plural-Forms are the CLDR integer
  rules: ga 5 forms, zh_HK 1, the others `(n != 1)`.
- Build hook: the prepare action (`.github/actions/cosmyx-prepare`, decision
  0080) runs `languages.py install` before the graft, which copies those
  catalogues into `localization/i18n/<code>/`, so the upstream scripts compile
  and package them and the graft fills their Cosmyx strings. After the graft,
  `languages.py drop` deletes the upstream catalogues no row uses (ca, cs, eu,
  hu, lt, pt_BR, ru, th, tr; `en`, the source language, stays), so they are
  not packaged; the hide step keeps the deletion out of `git diff`. The
  committed tree keeps every upstream catalogue untouched.
- Feature catalogues (decision 0081) exist for every language with a
  catalogue, the Cosmyx ones included. `just languages-sync-features` adds the
  missing `<lang>.po` of every feature folder without xgettext (a seeded
  language starts from its seed's file, marked for review);
  `just i18n-extract` does the same during a full extraction. The folder
  `localization/cosmyx/i18n` is not a feature.
- GUI hooks, one line each:
  - `Preferences.cpp`: `Cosmyx::select_ui_languages()` after the upstream
    list is built replaces it with the offered languages whose catalogue
    wxWidgets found (English always), in code order, and
    `Cosmyx::ui_language_name()` labels each one in its own language.
  - `GUI_App.cpp`, `load_language()`: `Cosmyx::ui_language_info()`, after
    the upstream fallback chain (which still refuses right-to-left
    languages), switches to the offered language matching upstream's choice,
    else en_GB.
    A language is matched by its exact code, else by its language part (the
    row whose catalogue is named after the bare language, else the first one):
    en_US gives en_GB, pt_BR gives pt_PT, ru_RU gives en_GB.
- ImGui glyphs: Greek is already covered (OrcaSlicer adds U+0370-U+03FF to
  every language and HarmonyOS Sans holds the monotonic set), as are the Latin
  letters of da, fi, ga and nb.
- Arabic (ar_SA) and Hindi (hi_IN) are not offered for now, by the user's
  choice. No bundled font (HarmonyOS Sans SC, Nanum Gothic, Sarabun) holds
  Arabic or Devanagari, so the 3D scene overlays would show them as missing
  glyphs (`imgui_fonts_cover()` records it), and ImGui has neither shaping
  nor bidi, so even with a font both scripts would render unjoined, Arabic
  left-to-right. The table keeps its right-to-left column and the Arabic and
  Devanagari scripts so that adding them back stays a data change plus the
  steps below.
- Adding them back takes: an OFL TrueType font per script, Regular and Bold,
  in `resources/fonts` with its licence file, loaded for ImGui with the
  script's glyph ranges; HarfBuzz-style shaping, that is a shaping pass
  before ImGui draws Arabic (joining forms and right-to-left runs), and
  Devanagari (conjuncts and vowel signs); the two table rows and
  `languages-generate`; and, for Arabic, keeping the requested language in
  `load_language()` before upstream refuses right-to-left ones (one more
  hook line) so wxWidgets lays the app out right-to-left.

## Consequences

- Translating language X means editing, for an upstream-catalogue row,
  `localization/cosmyx/<feature>/<folder>.po` only (the upstream catalogue
  stays as upstream ships it), and for a Cosmyx row both
  `localization/cosmyx/i18n/<code>/OrcaSlicer_<code>.po` and
  `localization/cosmyx/<feature>/<code>.po`.
- After upstream refreshes `OrcaSlicer.pot`, `just languages-generate` brings
  the Cosmyx catalogues in line; `just languages-check` (and the script tests)
  fail until then.
- Known risks, to verify on the built app: the custom-drawn widgets
  (`src/slic3r/GUI/Widgets`) paint with explicit coordinates and do not mirror
  under right-to-left, nor would the web pages get `dir="rtl"`, once Arabic
  is back; `GUI_App::current_language_code_safe()` reports zh_HK as zh_CN, pt_PT as
  pt_BR and the new languages as en_US to the web services.
- Removing it: delete the hooks, the table and its two C++ files,
  `languages.py`, the two prepare steps and `localization/cosmyx/i18n`; the
  selector then lists the upstream languages again.
