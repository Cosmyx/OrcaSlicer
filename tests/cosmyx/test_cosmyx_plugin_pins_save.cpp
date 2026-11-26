// Checks of what the Preferences plugin rows store (decision 0204): pins are
// only ever saved for the server they were loaded for, never for the Cosmyx
// server, and never over a stored document that cannot be read. Also the
// install commit that refuses a package whose metadata cannot be read again.

#include <catch2/catch_test_macros.hpp>

#include <ios>
#include <stdexcept>
#include <string>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>
#include <boost/nowide/fstream.hpp>
#include <nlohmann/json.hpp>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginSigning.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp"
#include "test_utils.hpp"

using namespace Slic3r;
namespace CC = Slic3r::GUI::Cosmyx;
namespace fs = boost::filesystem;

namespace {

constexpr const char* SERVER_A  = "https://a.example.org";
constexpr const char* SERVER_B  = "https://b.example.org";
constexpr const char* K1_PUBLIC = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8";
constexpr const char* K1_ID     = "56475aa75463474c0285df5dbf2bcab73da651358839e9b77481b2eab107708c";
constexpr const char* K2_PUBLIC = "29acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd7";
constexpr const char* PLUGIN_ID = "22222222-2222-4222-8222-222222222222";

void write_file(const fs::path& path, const std::string& data)
{
    boost::nowide::ofstream file(path.string(), std::ios::binary | std::ios::trunc);
    file.write(data.data(), static_cast<std::streamsize>(data.size()));
    REQUIRE(file);
}

} // namespace

TEST_CASE("The plugin rows are stored only for the address they were loaded for", "[cosmyx]")
{
    // Same address: what the rows hold is stored.
    CHECK(CC::pins_to_save(SERVER_A, SERVER_A) == CC::PinsSave::Typed);
    // A spelling of the same address (case, trailing slash, default port).
    CHECK(CC::pins_to_save(SERVER_A, "HTTPS://A.example.org:443/") == CC::PinsSave::Typed);
    CHECK(CC::pins_to_save("https://a.example.org/", SERVER_A) == CC::PinsSave::Typed);
    // Another server: nothing is stored, its own pins stay.
    CHECK(CC::pins_to_save(SERVER_A, SERVER_B) == CC::PinsSave::Keep);
    CHECK(CC::pins_to_save(SERVER_A, "https://a.example.org/api") == CC::PinsSave::Keep);
    CHECK(CC::pins_to_save(SERVER_A, "https://a.example.org:8443") == CC::PinsSave::Keep);
    // Rows loaded for no address (or an unrecognised one) are never stored.
    CHECK(CC::pins_to_save("", SERVER_B) == CC::PinsSave::Keep);
    CHECK(CC::pins_to_save("ftp://a.example.org", SERVER_A) == CC::PinsSave::Keep);
    // The Cosmyx server, from anywhere: its pins are never used, so never stored.
    CHECK(CC::pins_to_save(SERVER_A, CC::CLOUD_SERVER_URL) == CC::PinsSave::None);
    CHECK(CC::pins_to_save(CC::CLOUD_SERVER_URL, CC::CLOUD_SERVER_URL) == CC::PinsSave::None);
    CHECK(CC::pins_to_save(SERVER_A, std::string(CC::CLOUD_SERVER_URL) + "/") == CC::PinsSave::None);
    // Leaving the Cosmyx server for a custom one: the rows were disabled, B keeps its pins.
    CHECK(CC::pins_to_save(CC::CLOUD_SERVER_URL, SERVER_B) == CC::PinsSave::Keep);
    CHECK(CC::pins_to_save(SERVER_A, "not an address") == CC::PinsSave::None);
}

TEST_CASE("Changing the API address keeps both servers' own pins", "[cosmyx]")
{
    // Mirrors Apply: the rows show A's opt-in, the address is edited to B.
    AppConfig config;
    REQUIRE(CC::set_server_pins(config, SERVER_A, {"", true}));
    REQUIRE(CC::set_server_pins(config, SERVER_B, {K2_PUBLIC, false}));
    const CC::ServerPins rows = CC::server_pins(config, SERVER_A);
    if (CC::pins_to_save(SERVER_A, SERVER_B) == CC::PinsSave::Typed)
        CC::set_server_pins(config, SERVER_B, rows);

    // A's opt-in does not carry to B, and B's key is not overwritten.
    const CC::ServerPins b = CC::server_pins(config, SERVER_B);
    CHECK(b.public_key == K2_PUBLIC);
    CHECK_FALSE(b.allow_unverified);
    CHECK(CC::server_pins(config, SERVER_A).allow_unverified);
    CHECK_FALSE(CC::server_trust(config, SERVER_B).allow_unverified);
}

TEST_CASE("Pins are never saved over a stored document that cannot be read", "[cosmyx]")
{
    for (const std::string& stored : {std::string("not json"), std::string("[1, 2]"), std::string("\"text\""),
                                     std::string(R"({"https://a.example.org": )")}) {
        INFO(stored);
        AppConfig config;
        config.set(CC::PLUGIN_TRUST_KEY, stored);
        CHECK_FALSE(CC::set_server_pins(config, SERVER_B, {K1_PUBLIC, false}));
        CHECK_FALSE(CC::set_server_pins(config, SERVER_B, {}));
        // The stored value is left as it was, for the user to repair.
        CHECK(config.get(CC::PLUGIN_TRUST_KEY) == stored);
        CHECK(CC::server_pins(config, SERVER_B).public_key.empty());
    }

    // Nothing stored yet (empty or blank) is an empty document, and saving works.
    for (const std::string& stored : {std::string(), std::string("  ")}) {
        AppConfig config;
        config.set(CC::PLUGIN_TRUST_KEY, stored);
        CHECK(CC::set_server_pins(config, SERVER_B, {K1_PUBLIC, false}));
        CHECK(CC::server_pins(config, SERVER_B).public_key == K1_PUBLIC);
    }
}

TEST_CASE("An install whose metadata cannot be read again is refused, with its floor kept", "[cosmyx]")
{
    const CC::PackageRecord floor{PLUGIN_ID, "2.0.0", std::string(64, 'a'), 10, K1_ID};
    ScopedTemporaryDir      dir("cosmyx-plugin");
    const fs::path          package_file = dir.path() / "hello.py";

    // The metadata reader throws (a filesystem error): refused, not propagated.
    write_file(package_file, "print('hello')\n");
    std::string error;
    bool        result = true;
    CHECK_NOTHROW(result = CC::commit_checked_install(
                      PLUGIN_ID, dir.path(), package_file,
                      [](std::string&) -> bool { throw std::runtime_error("boom"); }, error, &floor));
    CHECK_FALSE(result);
    CHECK(error.find("boom") != std::string::npos);
    CHECK_FALSE(fs::exists(package_file));
    CC::PackageRecord record;
    REQUIRE(CC::read_package_record(dir.path(), record));
    CHECK(record.version == "2.0.0");

    // A throw of something that is not a std::exception is refused too.
    write_file(package_file, "print('hello')\n");
    CHECK_NOTHROW(result = CC::commit_checked_install(
                      PLUGIN_ID, dir.path(), package_file, [](std::string&) -> bool { throw 42; }, error, nullptr));
    CHECK_FALSE(result);
    CHECK_FALSE(error.empty());
    CHECK_FALSE(fs::exists(package_file));
    CHECK_FALSE(fs::exists(dir.path() / CC::PACKAGE_RECORD_FILE));

    // A mismatch reported by the reader is refused with its reason.
    write_file(package_file, "print('hello')\n");
    CHECK_FALSE(CC::commit_checked_install(
        PLUGIN_ID, dir.path(), package_file,
        [](std::string& why) {
            why = "different metadata";
            return false;
        },
        error, &floor));
    CHECK(error == "different metadata");
    CHECK_FALSE(fs::exists(package_file));
    REQUIRE(CC::read_package_record(dir.path(), record));
    CHECK(record.version == "2.0.0");

    // Matching metadata goes on to the record check: no checked record, refused.
    write_file(package_file, "print('hello')\n");
    CHECK_FALSE(CC::commit_checked_install(
        PLUGIN_ID, dir.path(), package_file, [](std::string&) { return true; }, error, nullptr));
    CHECK_FALSE(error.empty());
    CHECK_FALSE(fs::exists(package_file));
    CC::forget_checked_packages(PLUGIN_ID);
}

TEST_CASE("An install whose metadata matches commits the checked record", "[cosmyx]")
{
    ScopedTemporaryDir dir("cosmyx-plugin");
    const fs::path     package_file = dir.path() / "hello.py";
    const std::string  body         = "print('hello')\n";
    write_file(package_file, body);
    CC::remember_checked_package({PLUGIN_ID, "1.0.0", CC::sha256_hex(body), body.size(), K1_ID});
    std::string error;
    REQUIRE(CC::commit_checked_install(PLUGIN_ID, dir.path(), package_file, [](std::string&) { return true; }, error));
    CC::PackageRecord record;
    REQUIRE(CC::read_package_record(dir.path(), record));
    CHECK(record.version == "1.0.0");
    CHECK(fs::exists(package_file));
    CC::forget_checked_packages(PLUGIN_ID);
}
