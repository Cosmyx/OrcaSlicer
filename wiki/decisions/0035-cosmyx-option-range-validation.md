# 0035. Range check of the Cosmyx options

## Status

Accepted.

## Context

`DynamicPrintConfig::validate()`, which the GUI and the CLI run before
slicing, copies the config into a static `FullPrintConfig` and passes it to
`Slic3r::validate()`, whose out of range check walks the static keys only.
Options added through `Cosmyx::add_option()` are not members of any static
config, so the copy drops them and their `min`/`max` are never checked:
`filament_ironing_temperature = 600` validated cleanly and reached the G-code as
`M104 S600`. Every future Cosmyx numeric option would have had the same hole.

The test `filament_ironing_temperature is a filament option, off by default`
also read the option from `DynamicPrintConfig::full_print_config()`, which only
holds the static keys, so its `REQUIRE(full.has(key))` could not pass.

## Decision

- One generic check, `Cosmyx::validate_option_ranges()`
  (`src/libslic3r/Cosmyx/ConfigValidation.cpp`, declared in
  `ConfigDefExtensions.hpp`), walks the keys of the dynamic config, keeps the
  Cosmyx options (`is_cosmyx_option()`), and checks their numeric values
  (`coFloat`, `coPercent`, `coFloatOrPercent`, `coFloats`, `coPercents`,
  `coInt`, `coInts`, the types `Slic3r::validate()` checks) against their
  definition with `ConfigOptionDef::is_value_valid()`. Nil values of nullable
  options are valid. An out of range value gets the upstream message
  `"%1% not in range [%2%, %3%]"`, so it shares its translation, unless the
  error map already holds an entry for that key.
- Hook: the return line of the FFF branch of `DynamicPrintConfig::validate()`
  in `src/libslic3r/PrintConfig.cpp` now wraps the upstream result:
  `return Cosmyx::validate_option_ranges(*this, Slic3r::validate(fpc, under_cli)); // Cosmyx`.
  It changes one upstream line and needs no new include, since `PrintConfig.cpp`
  already includes `Cosmyx/ConfigDefExtensions.hpp`. This adds a sixth hook
  line to the five listed in 0034.
- `DynamicPrintConfig::full_print_config()` is left as upstream has it. In the
  application the full config of a print comes from
  `PresetBundle::full_fff_config()`, which applies the default filament preset;
  that preset is built from `Preset::filament_options()` and so already carries
  the option at its default. Making `full_print_config()` carry Cosmyx options
  would need another hook in an upstream function many upstream tests call, for
  no change in the application. The test now checks the real source: the
  default filament preset of a `PresetBundle` holds the option at 0, and a full
  config built the way `full_fff_config()` builds it carries it.

## Consequences

- Any numeric option added with `add_option()` is range checked with no extra
  code.
- Removing the check: restore `return Slic3r::validate(fpc, under_cli);` and
  delete `ConfigValidation.cpp` and its declaration; the breaker tests in
  `tests/cosmyx/test_breaker_ironing_temperature.cpp` then fail.
