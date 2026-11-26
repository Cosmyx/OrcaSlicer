// Checks that the shipped Cosmyx vendor bundle (resources/profiles/Cosmyx)
// loads as a system bundle, and that every Cosmyx printer finds its default
// process and filament presets and is compatible with them.

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <string>
#include <vector>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>

#include "libslic3r/Config.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/PresetBundle.hpp"
#include "libslic3r/PrintConfig.hpp"

using namespace Slic3r;

namespace {

bool lists(const Preset& preset, const std::string& printer)
{
    const auto* compatible = preset.config.option<ConfigOptionStrings>("compatible_printers");
    return compatible != nullptr &&
           std::find(compatible->values.begin(), compatible->values.end(), printer) != compatible->values.end();
}

} // namespace

TEST_CASE("The Cosmyx bundle loads and every printer resolves its default presets", "[cosmyx][profiles]")
{
    // PROFILES_DIR is baked in at build time; a sparse checkout without
    // resources/ has no bundle to load.
    const boost::filesystem::path profiles(PROFILES_DIR);
    if (!boost::filesystem::exists(profiles / "Cosmyx.json"))
        SKIP("Cosmyx bundle not present in this checkout: " << profiles.string());

    PresetBundle bundle;
    // No cache: the test must read the JSONs as shipped, and write nothing
    // into the source tree.
    const auto loaded = bundle.load_vendor_configs_from_json(profiles.string(), "Cosmyx", PresetBundle::LoadSystem,
                                                             ForwardCompatibilitySubstitutionRule::EnableSilent,
                                                             nullptr, /*allow_cache=*/false);
    CHECK(loaded.first.empty());
    REQUIRE(bundle.vendors.count("Cosmyx") == 1);
    CHECK(bundle.vendors.at("Cosmyx").models.size() == 8);

    // Only instantiated printers load as presets; the bases stay config-only.
    std::vector<std::string> names;
    for (const Preset& preset : bundle.printers.get_presets())
        if (!preset.is_default)
            names.push_back(preset.name);
    REQUIRE(names.size() == 32);

    for (const std::string& name : names) {
        INFO("printer: " << name);
        Preset* printer = bundle.printers.find_preset(name);
        REQUIRE(printer != nullptr);
        // The Cosmyx bed type is not ported: every model names the Textured PEI Plate.
        CHECK(printer->get_default_bed_type(&bundle) == btPTE);

        const Preset* process = bundle.prints.find_preset(printer->config.opt_string("default_print_profile"));
        REQUIRE(process != nullptr);
        CHECK(lists(*process, printer->name));

        const auto* filaments = printer->config.option<ConfigOptionStrings>("default_filament_profile");
        REQUIRE(filaments != nullptr);
        REQUIRE_FALSE(filaments->values.empty());
        for (const std::string& name : filaments->values) {
            INFO("filament: " << name);
            const Preset* filament = bundle.filaments.find_preset(name);
            REQUIRE(filament != nullptr);
            CHECK(lists(*filament, printer->name));
        }
    }
}
