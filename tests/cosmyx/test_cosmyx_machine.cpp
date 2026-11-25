// Checks of the Cosmyx machine detection (decision 0222): the selected printer
// is a Cosmyx machine when its preset, or the system preset it inherits from,
// belongs to the vendor bundle whose id is exactly "Cosmyx".

#include <catch2/catch_test_macros.hpp>

#include <fstream>
#include <string>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>

#include "libslic3r/Config.hpp"
#include "libslic3r/Cosmyx/CosmyxMachine.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/PresetBundle.hpp"
#include "libslic3r/PrintConfig.hpp"

#include "test_utils.hpp"

using namespace Slic3r;
namespace fs = boost::filesystem;

namespace {

// Writes a one-printer vendor bundle `vendor` under root: <vendor>.json plus
// one machine model and one instantiable printer preset "<vendor> Printer".
void write_vendor(const fs::path& root, const std::string& vendor)
{
    const fs::path machine = root / vendor / "machine";
    fs::create_directories(machine);
    std::ofstream((root / (vendor + ".json")).string())
        << R"({"version":"1.0.0","name":")" << vendor << R"(",)"
        << R"("machine_model_list":[{"name":")" << vendor << R"( One","sub_path":"machine/model.json"}],)"
        << R"("machine_list":[{"name":")" << vendor << R"( Printer","sub_path":"machine/printer.json"}]})";
    std::ofstream((machine / "model.json").string())
        << R"({"type":"machine_model","name":")" << vendor << R"( One","nozzle_diameter":"0.4"})";
    std::ofstream((machine / "printer.json").string())
        << R"({"type":"machine","name":")" << vendor << R"( Printer","from":"system","instantiation":"true",)"
        << R"("printer_model":")" << vendor << R"( One","printer_variant":"0.4","nozzle_diameter":["0.4"]})";
}

// Loads the bundle of `vendor` from a fresh directory and selects its printer.
void load_vendor(PresetBundle& bundle, const ScopedTemporaryDir& dir, const std::string& vendor)
{
    const fs::path root = dir.path() / "profiles";
    write_vendor(root, vendor);
    REQUIRE_NOTHROW(bundle.load_vendor_configs_from_json(root.string(), vendor, PresetBundle::LoadSystem,
                                                         ForwardCompatibilitySubstitutionRule::EnableSilent));
    REQUIRE(bundle.printers.find_preset(vendor + " Printer") != nullptr);
    REQUIRE(bundle.printers.select_preset_by_name(vendor + " Printer", true));
}

// Adds and selects a user printer preset `name` inheriting from `parent`
// (no parent when empty), as the GUI does when a user saves a printer.
void select_user_printer(PresetBundle& bundle, const std::string& name, const std::string& parent)
{
    DynamicPrintConfig config = bundle.printers.get_edited_preset().config;
    config.set_key_value("inherits", new ConfigOptionString(parent));
    bundle.printers.load_preset(std::string(), name, config, /*select=*/true);
    REQUIRE(bundle.printers.get_edited_preset().name == name);
    REQUIRE(bundle.printers.get_edited_preset().vendor == nullptr);
}

} // namespace

TEST_CASE("A null vendor is not Cosmyx", "[cosmyx][CosmyxMachine]")
{
    CHECK_FALSE(Cosmyx::is_cosmyx_vendor(nullptr));
}

TEST_CASE("Only the vendor id Cosmyx, compared exactly, is Cosmyx", "[cosmyx][CosmyxMachine]")
{
    CHECK(std::string(Cosmyx::COSMYX_VENDOR_ID) == "Cosmyx");

    VendorProfile cosmyx("Cosmyx");
    CHECK(Cosmyx::is_cosmyx_vendor(&cosmyx));

    for (const char* other : { "Acme", "cosmyx", "COSMYX", "Cosmyx ", "CosmyxLabs", "" }) {
        VendorProfile vendor(other);
        INFO("vendor id: '" << other << "'");
        CHECK_FALSE(Cosmyx::is_cosmyx_vendor(&vendor));
    }
}

TEST_CASE("The vendor name does not make a Cosmyx vendor, only the id does", "[cosmyx][CosmyxMachine]")
{
    VendorProfile vendor("Acme");
    vendor.name = "Cosmyx";
    CHECK_FALSE(Cosmyx::is_cosmyx_vendor(&vendor));
}

TEST_CASE("The default printer of an empty bundle is not a Cosmyx machine", "[cosmyx][CosmyxMachine]")
{
    PresetBundle bundle;
    CHECK_FALSE(Cosmyx::is_cosmyx_printer(bundle));
}

TEST_CASE("A system printer of the Cosmyx bundle is a Cosmyx machine", "[cosmyx][CosmyxMachine]")
{
    ScopedTemporaryDir dir;
    PresetBundle       bundle;
    load_vendor(bundle, dir, "Cosmyx");
    CHECK(Cosmyx::is_cosmyx_printer(bundle));
}

TEST_CASE("A system printer of another bundle is not a Cosmyx machine", "[cosmyx][CosmyxMachine]")
{
    ScopedTemporaryDir dir;
    PresetBundle       bundle;
    load_vendor(bundle, dir, "Acme");
    CHECK_FALSE(Cosmyx::is_cosmyx_printer(bundle));
}

TEST_CASE("A user printer inheriting from a Cosmyx system printer is a Cosmyx machine", "[cosmyx][CosmyxMachine]")
{
    ScopedTemporaryDir dir;
    PresetBundle       bundle;
    load_vendor(bundle, dir, "Cosmyx");
    select_user_printer(bundle, "My Cosmyx", "Cosmyx Printer");
    CHECK(Cosmyx::is_cosmyx_printer(bundle));
}

TEST_CASE("A user printer inheriting from another vendor's printer is not a Cosmyx machine", "[cosmyx][CosmyxMachine]")
{
    ScopedTemporaryDir dir;
    PresetBundle       bundle;
    load_vendor(bundle, dir, "Acme");
    select_user_printer(bundle, "My Acme", "Acme Printer");
    CHECK_FALSE(Cosmyx::is_cosmyx_printer(bundle));
}

TEST_CASE("A custom printer with no system parent is not a Cosmyx machine", "[cosmyx][CosmyxMachine]")
{
    ScopedTemporaryDir dir;
    PresetBundle       bundle;
    load_vendor(bundle, dir, "Cosmyx");
    // Copied from a Cosmyx printer, but detached: nothing links it to the bundle.
    select_user_printer(bundle, "My Custom", "");
    CHECK_FALSE(Cosmyx::is_cosmyx_printer(bundle));
}

TEST_CASE("A user printer whose parent is missing is not a Cosmyx machine", "[cosmyx][CosmyxMachine]")
{
    ScopedTemporaryDir dir;
    PresetBundle       bundle;
    load_vendor(bundle, dir, "Cosmyx");
    select_user_printer(bundle, "My Orphan", "Cosmyx Printer That Does Not Exist");
    CHECK_FALSE(Cosmyx::is_cosmyx_printer(bundle));
}
