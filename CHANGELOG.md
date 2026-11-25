# Changelog

Changes made in the Cosmyx fork of OrcaSlicer. Upstream changes are not listed
here; see the upstream release notes.

## Rules

- Every change records one line here, in its own branch, in the same pull
  request. A branch without its line is not finished.
- Newest first: periods are months (`## YYYY-MM`), the current one at the top.
  Open a new period when the first change of a month lands.
- Inside a period, lines are grouped by area, always in this order:
  `repo` (tooling, layout, docs), `libslic3r` (slicing core), `GUI`,
  `i18n` (translations), `CI-release` (workflows, signing, releases).
- Each line says what changed for someone reading the history, not how. It
  ends with the pull request link and the decisions it implements
  (`wiki/decisions/NNNN-slug.md`).
- Breaking changes, removals and migrations start with **Breaking:**,
  **Removed:** or **Migration:** and say what the reader has to do.
- Slot markers (`<!-- cosmyx-slot: Tn -->`) reserve a place for each planned
  task, so parallel branches never edit the same lines. A task inserts its line
  directly under its own marker and never removes or moves a marker.

## 2026-11

### repo

<!-- cosmyx-slot: T0 -->
- Add the Cosmyx foundation: the libslic3r and GUI Cosmyx modules with their
  one-line upstream hooks, the cosmyx_tests suite (built and run by every
  test leg, the flatpak one included, whose test asset keeps the
  `resources/cosmyx` and `resources/info` folders the suite reads), this
  changelog, the decision register under `wiki/decisions/`, the justfile and
  the Cosmyx checks workflow. Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/86. Decisions: 0001, 0002, 0003, 0004, 0005.

### libslic3r

<!-- cosmyx-slot: T1 -->

<!-- cosmyx-slot: T2 -->

<!-- cosmyx-slot: T3 -->

<!-- cosmyx-slot: T4 -->

### GUI

<!-- cosmyx-slot: T5 -->

<!-- cosmyx-slot: T6 -->

<!-- cosmyx-slot: T7 -->

<!-- cosmyx-slot: T11b -->

<!-- cosmyx-slot: T11c -->

<!-- cosmyx-slot: T11d -->

<!-- cosmyx-slot: T11e -->

<!-- cosmyx-slot: T11f -->

<!-- cosmyx-slot: T25 -->
- Offer exactly 22 UI languages: the Preferences selector lists only da_DK,
  de_DE, el_GR, en_GB, es_ES, fi_FI, fr_FR, ga_IE, it_IT, ja_JP, ko_KR, nb_NO,
  nl_BE, nl_NL, pl_PL, pt_PT, sv_SE, uk_UA, vi_VN, zh_CN, zh_HK and zh_TW,
  each named in its own language; any other language starts in British
  English. Arabic and Hindi are not offered yet: they need fonts and text
  shaping the 3D scene lacks. The nine languages OrcaSlicer
  lacks get catalogues under `localization/cosmyx/i18n`, packaged like the
  upstream ones: nl_BE, pt_PT and zh_HK start from nl, pt_BR and zh_TW,
  reviewed and completed by a machine pass; da_DK, el_GR, fi_FI, ga_IE and
  nb_NO are machine-translated; en_GB holds only the British spellings and
  falls back to the source text elsewhere. Machine translations, the Cosmyx
  strings included, are marked for review; the unused upstream
  catalogues (ca, cs, eu, hu, lt, pt_BR, ru, th, tr) are no longer packaged.
  **Migration:** a user whose language was one of those now gets British
  English and can pick another in Preferences. Pull request:
  https://github.com/Cosmyx/OrcaSlicer/pull/123. Decision: 0220.

### i18n

<!-- cosmyx-slot: T8 -->
- Fill the Cosmyx catalogues in all 22 OrcaSlicer languages (CHT nozzle,
  ironing temperature, Cosmyx models), using each language's OrcaSlicer terms
  for shared words. Pull request: pending.
- Translate the Cosmyx strings: per-feature catalogues under
  `localization/cosmyx/` (cht-nozzle, ironing-temperature, models) for every
  OrcaSlicer language, seeded from the previous Cosmyx branch, grafted into
  the OrcaSlicer catalogues by every desktop build, Flatpak included (its
  container workspace is trusted for git), without marking the build "-dirty"
  (the edited files are hidden from git diff).
  Recipes `just i18n-extract`, `i18n-seed`, `i18n-graft`, `i18n-ungraft`,
  `worktree-hidden`. The graft accepts UTF-8 catalogues only, reads strings
  holding Unicode line separators, and never glues an entry to a catalogue
  without a final newline. A script test fails when the catalogues are out of
  date with the sources, and `just i18n-coverage` lists the missing
  translations (a gate with `COSMYX_I18N_STRICT=1`). Pull request: pending. Decisions: 0080, 0081, 0082
  (superseded), 0083, 0084, 0085, 0086, 0087, 0088.

### CI-release

<!-- cosmyx-slot: T9 -->

<!-- cosmyx-slot: T10 -->

<!-- cosmyx-slot: T11a -->

<!-- cosmyx-slot: T13 -->
