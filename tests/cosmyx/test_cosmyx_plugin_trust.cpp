// Checks of what a plugin package is checked against (decision 0204): the
// build's pins for the Cosmyx server, the user's pin or unverified opt-in for a
// custom server, the one spelling of a server address, the anti-rollback rule,
// the package record written after an install (and the refusal of bytes that
// were not checked), and the guard on a wheel's entry package name.

#include <catch2/catch_test_macros.hpp>

#include <ios>
#include <string>
#include <utility>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>
#include <boost/nowide/fstream.hpp>
#include <miniz.h>
#include <nlohmann/json.hpp>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginSigning.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp"
#include "test_utils.hpp"

using namespace Slic3r;
namespace CC = Slic3r::GUI::Cosmyx;
namespace fs = boost::filesystem;
using nlohmann::json;

namespace {

constexpr const char* CUSTOM = "https://plugins.example.org";

// k1 of the CosmoCloud vectors (seed 000102...1f).
constexpr const char* K1_PUBLIC = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8";
constexpr const char* K1_PUBLIC_UPPER = "03A107BFF3CE10BE1D70DD18E74BC09967E4D6309BA50D5F1DDC8664125531B8";
constexpr const char* K1_ID     = "56475aa75463474c0285df5dbf2bcab73da651358839e9b77481b2eab107708c";
constexpr const char* K2_PUBLIC = "29acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd7";

json load_vectors()
{
    const fs::path          path = fs::path(TEST_DATA_DIR) / ".." / "cosmyx" / "data" / "plugin-signatures.json";
    boost::nowide::ifstream file(path.string(), std::ios::binary);
    REQUIRE(file);
    return json::parse(file);
}

// The vector row "script for any target", signed by k1, and its body.
struct SignedPackage
{
    json              row;
    std::string       body;
    CC::ClientRequest request;
};

SignedPackage script_package()
{
    const json vectors = load_vectors();
    for (const json& vector : vectors.at("rows")) {
        if (vector.at("name") != "script for any target")
            continue;
        SignedPackage package;
        package.row = vector.at("row");
        REQUIRE(CC::from_lower_hex(vector.at("body_hex").get<std::string>(), package.body));
        package.request = {package.row.at("plugin_id").get<std::string>(), "1.0.0", "linux", "x86_64"};
        return package;
    }
    FAIL("vector row not found");
    return {};
}

CC::ServerTrust custom_trust(AppConfig& config, const CC::ServerPins& pins)
{
    CC::set_server_pins(config, CUSTOM, pins);
    return CC::server_trust(config, CUSTOM);
}

void write_file(const fs::path& path, const std::string& data)
{
    boost::nowide::ofstream file(path.string(), std::ios::binary | std::ios::trunc);
    file.write(data.data(), static_cast<std::streamsize>(data.size()));
    REQUIRE(file);
}

} // namespace

TEST_CASE("The Cosmyx server is checked against the build's pins only", "[cosmyx]")
{
    AppConfig config;
    // A pin or an opt-in stored for the Cosmyx address is never used.
    CC::set_server_pins(config, CC::CLOUD_SERVER_URL, {K1_PUBLIC, true});
    for (const std::string& url : {std::string(CC::CLOUD_SERVER_URL), std::string(CC::CLOUD_SERVER_URL) + "/", std::string()}) {
        INFO(url);
        const CC::ServerTrust trust = CC::server_trust(config, url);
        CHECK(trust.cosmyx_server);
        CHECK_FALSE(trust.allow_unverified);
        CHECK(trust.keys == CC::built_in_keys());
    }
}

TEST_CASE("A custom server uses the key the user pinned for its address", "[cosmyx]")
{
    AppConfig config;
    CC::ServerTrust trust = custom_trust(config, {K1_PUBLIC, false});
    CHECK_FALSE(trust.cosmyx_server);
    REQUIRE(trust.keys.size() == 1);
    CHECK(trust.keys.count(K1_ID) == 1);

    // A pinned key always means full verification: the opt-in is ignored.
    trust = custom_trust(config, {K1_PUBLIC, true});
    CHECK_FALSE(trust.allow_unverified);

    // The pin belongs to that address only.
    CHECK(CC::server_trust(config, "https://other.example.org").keys.empty());
    CHECK(CC::server_trust(config, std::string(CUSTOM) + "/").keys.size() == 1);

    // No key: refused unless the user allowed unverified plugins.
    trust = custom_trust(config, {"", false});
    CHECK(trust.keys.empty());
    CHECK_FALSE(trust.allow_unverified);
    trust = custom_trust(config, {"", true});
    CHECK(trust.allow_unverified);
}

TEST_CASE("Pins are stored per address and read back", "[cosmyx]")
{
    AppConfig config;
    CC::set_server_pins(config, std::string(CUSTOM) + "//", {K2_PUBLIC, true});
    CC::ServerPins pins = CC::server_pins(config, CUSTOM);
    CHECK(pins.public_key == K2_PUBLIC);
    CHECK(pins.allow_unverified);

    CC::set_server_pins(config, CUSTOM, {});
    pins = CC::server_pins(config, CUSTOM);
    CHECK(pins.public_key.empty());
    CHECK_FALSE(pins.allow_unverified);
    CHECK(json::parse(config.get(CC::PLUGIN_TRUST_KEY)).empty());

    // A hand-edited value that is not a key is ignored, never trusted.
    config.set(CC::PLUGIN_TRUST_KEY, R"({"https://plugins.example.org": {"public_key": "ZZ", "allow_unverified": "yes"}})");
    pins = CC::server_pins(config, CUSTOM);
    CHECK(pins.public_key.empty());
    CHECK_FALSE(pins.allow_unverified);
    config.set(CC::PLUGIN_TRUST_KEY, "not json");
    CHECK(CC::server_pins(config, CUSTOM).public_key.empty());
}

TEST_CASE("A stored key is normalized and a key that is not one is refused", "[cosmyx]")
{
    AppConfig config;
    REQUIRE(CC::set_server_pins(config, CUSTOM, {std::string(" ") + K1_PUBLIC_UPPER + "\n", false}));
    CHECK(json::parse(config.get(CC::PLUGIN_TRUST_KEY)).at(CUSTOM).at("public_key") == K1_PUBLIC);
    CHECK(CC::server_pins(config, CUSTOM).public_key == K1_PUBLIC);

    // A typo is refused and the stored pin is kept as it was.
    CHECK_FALSE(CC::set_server_pins(config, CUSTOM, {std::string(K1_PUBLIC).substr(0, 63), true}));
    CHECK(CC::server_pins(config, CUSTOM).public_key == K1_PUBLIC);
    CHECK_FALSE(CC::server_pins(config, CUSTOM).allow_unverified);

    // A hand-edited key in another case is still read as the key.
    config.set(CC::PLUGIN_TRUST_KEY, json{{CUSTOM, {{"public_key", K1_PUBLIC_UPPER}, {"allow_unverified", false}}}}.dump());
    CHECK(CC::server_trust(config, CUSTOM).keys.count(K1_ID) == 1);
    // A pin that is not a string refuses the server, opt-in or not.
    config.set(CC::PLUGIN_TRUST_KEY, json{{CUSTOM, {{"public_key", 42}, {"allow_unverified", true}}}}.dump());
    CHECK(CC::server_trust(config, CUSTOM).keys.empty());
    CHECK_FALSE(CC::server_trust(config, CUSTOM).allow_unverified);
}

TEST_CASE("Server addresses have one spelling", "[cosmyx]")
{
    const std::pair<std::string, std::string> cases[] = {
        {"", ""},
        {"   ", ""},
        {" https://Plugins.Example.ORG/ ", "https://plugins.example.org"},
        {"HTTPS://plugins.example.org:443//", "https://plugins.example.org"},
        {"https://plugins.example.org:0443", "https://plugins.example.org"},
        {"https://plugins.example.org.:443", "https://plugins.example.org"},
        {"https://plugins.example.org.", "https://plugins.example.org"},
        {"https://plugins.example.org:", "https://plugins.example.org"},
        {"https://plugins.example.org:8443", "https://plugins.example.org:8443"},
        {"https://plugins.example.org:80", "https://plugins.example.org:80"},
        {"http://LocalHost:80/", "http://localhost"},
        {"http://localhost:443", "http://localhost:443"},
        {"http://[::1]:080", "http://[::1]"},
        {"https://[::1]:8443/", "https://[::1]:8443"},
        {"https://plugins.example.org/API/V1/", "https://plugins.example.org/API/V1"},
        // No scheme: libcurl would guess http, so the address is unrecognised.
        {"plugins.example.org", ""},
    };
    for (const auto& [typed, expected] : cases) {
        INFO(typed);
        CHECK(CC::normalize_server_url(typed) == expected);
    }
    CHECK(CC::normalize_server_url(CC::CLOUD_SERVER_URL) == CC::CLOUD_SERVER_URL);
    // http and https on the same host are different servers.
    CHECK(CC::normalize_server_url("http://plugins.example.org") != CC::normalize_server_url(CUSTOM));
}

TEST_CASE("An address that is not plainly scheme://host[:port][/path] is refused outright", "[cosmyx]")
{
    const SignedPackage package = script_package();
    const std::string   unrecognised[] = {
        "plugins.example.org",
        "//plugins.example.org",
        "ftp://plugins.example.org",
        "https://plugins.example.org/a/../b",
        "https://plugins.example.org/./b",
        "https://plugins.example.org/b/..",
        "https://plugins%2Eexample.org",
        "https://plugins.example.org/%7Euser",
        "https://user@plugins.example.org",
        "https://plugins.example.org/?x=1",
        "https://plugins.example.org/#top",
        "https://plugins.example.org\\api",
        "https://plugins.example .org",
        "https://plugins.example.org/a b",
        "https://pl\xc3\xbcgins.example.org",
        "https://plugins..example.org",
        "https://.plugins.example.org",
        "https://plugins.example.org:0",
        "https://plugins.example.org:65536",
        "https://plugins.example.org:1:2",
        "https://[::1]x",
        "https://[]",
        "https://",
    };
    for (const std::string& url : unrecognised) {
        INFO(url);
        AppConfig config;
        CHECK(CC::normalize_server_url(url).empty());
        // No pin is ever stored or read for it.
        CHECK_FALSE(CC::set_server_pins(config, url, {K1_PUBLIC, true}));
        CHECK(config.get(CC::PLUGIN_TRUST_KEY).empty());
        const CC::ServerTrust trust = CC::server_trust(config, url);
        CHECK(trust.unrecognised);
        CHECK_FALSE(trust.cosmyx_server);
        CHECK(trust.keys.empty());
        CHECK_FALSE(trust.allow_unverified);
        CHECK(CC::check_plugin_package(&package.row, package.body, package.request, trust, {}, "", false).reason ==
              CC::SIGN_UNRECOGNISED_SERVER);
    }
}

TEST_CASE("The Cosmyx server is told by its parsed host, and only https on the default port", "[cosmyx]")
{
    AppConfig config;
    for (const std::string url : {"https://orca-cloud.cosmyx3d.fr/api/v1", "https://ORCA-CLOUD.cosmyx3d.fr.:0443/",
                                  "HTTPS://orca-cloud.COSMYX3D.fr:"}) {
        INFO(url);
        CHECK(CC::server_trust(config, url).cosmyx_server);
    }
    // Plain http, or another port, on the Cosmyx host is refused: never the
    // build's keys, never the user's pins.
    for (const std::string url : {"http://orca-cloud.cosmyx3d.fr", "HTTP://orca-cloud.cosmyx3d.fr:443",
                                  "https://orca-cloud.cosmyx3d.fr:8443", "http://orca-cloud.cosmyx3d.fr:80/api"}) {
        INFO(url);
        CHECK(CC::set_server_pins(config, url, {K1_PUBLIC, true}));
        const CC::ServerTrust trust = CC::server_trust(config, url);
        CHECK(trust.unrecognised);
        CHECK_FALSE(trust.cosmyx_server);
        CHECK(trust.keys.empty());
        CHECK_FALSE(trust.allow_unverified);
    }
    // Another host under the Cosmyx domain is a custom server.
    const CC::ServerTrust other = CC::server_trust(config, "https://plugins.orca-cloud.cosmyx3d.fr");
    CHECK_FALSE(other.unrecognised);
    CHECK_FALSE(other.cosmyx_server);
}

TEST_CASE("A typed public key gives its key id", "[cosmyx]")
{
    std::string normalized;
    CHECK(CC::public_key_id(std::string("  ") + K1_PUBLIC + "\n", &normalized) == K1_ID);
    CHECK(normalized == K1_PUBLIC);
    CHECK(CC::public_key_id("03A107BFF3CE10BE1D70DD18E74BC09967E4D6309BA50D5F1DDC8664125531B8") == K1_ID);
    CHECK(CC::public_key_id("03a1").empty());
    CHECK(CC::public_key_id(std::string(K1_PUBLIC) + "00").empty());
    CHECK(CC::public_key_id("g3a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8").empty());
}

TEST_CASE("A signed package from a pinned server passes and gives its record", "[cosmyx]")
{
    AppConfig             config;
    const SignedPackage   package = script_package();
    const CC::ServerTrust trust   = custom_trust(config, {K1_PUBLIC, false});

    const CC::PackageVerdict verdict = CC::check_plugin_package(&package.row, package.body, package.request, trust, {}, "", false);
    CHECK(verdict.reason == CC::SIGN_OK);
    CHECK(verdict.verified());
    CHECK(verdict.record.plugin_id == package.request.plugin_id);
    CHECK(verdict.record.version == "1.0.0");
    CHECK(verdict.record.sha256 == package.row.at("sha256").get<std::string>());
    CHECK(verdict.record.size == package.body.size());
    CHECK(verdict.record.key_id == K1_ID);

    // The revoked list applies to the user's pins too.
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, trust, {K1_ID}, "", false).reason ==
          CC::SIGN_UNKNOWN_KEY);
    // Another pinned key does not verify a k1 signature.
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, custom_trust(config, {K2_PUBLIC, true}), {}, "",
                                   false)
              .reason == CC::SIGN_UNKNOWN_KEY);
}

TEST_CASE("A server with nothing to verify against is refused", "[cosmyx]")
{
    AppConfig           config;
    const SignedPackage package = script_package();

    CC::ServerTrust cosmyx = CC::server_trust(config, CC::CLOUD_SERVER_URL);
    cosmyx.keys.clear(); // the production table is empty until a release fills it
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, cosmyx, {}, "", false).reason ==
          CC::SIGN_NO_PINNED_KEY);
    // Even a Cosmyx trust flagged as allowing unverified plugins refuses.
    cosmyx.allow_unverified = true;
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, cosmyx, {}, "", false).reason ==
          CC::SIGN_NO_PINNED_KEY);

    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, custom_trust(config, {}), {}, "", false).reason ==
          CC::SIGN_NO_PINNED_KEY);
    CHECK(CC::check_plugin_package(nullptr, package.body, package.request, custom_trust(config, {K1_PUBLIC, false}), {}, "", false)
              .reason == CC::SIGN_NO_ROW);
}

TEST_CASE("An allowed unverified server still checks the row and the body", "[cosmyx]")
{
    AppConfig             config;
    SignedPackage         package = script_package();
    const CC::ServerTrust trust   = custom_trust(config, {"", true});
    package.row.erase("signatures");

    CC::PackageVerdict verdict = CC::check_plugin_package(&package.row, package.body, package.request, trust, {}, "", false);
    CHECK(verdict.reason == CC::SIGN_OK);
    CHECK_FALSE(verdict.verified());
    CHECK(verdict.record.key_id.empty());
    CHECK(verdict.record.sha256 == package.row.at("sha256").get<std::string>());

    std::string changed = package.body;
    changed[0] = static_cast<char>(changed[0] ^ 0x01);
    CHECK(CC::check_plugin_package(&package.row, changed, package.request, trust, {}, "", false).reason == CC::SIGN_SHA256_MISMATCH);
    CHECK(CC::check_plugin_package(&package.row, package.body + "x", package.request, trust, {}, "", false).reason ==
          CC::SIGN_SIZE_MISMATCH);
    CHECK(CC::check_plugin_package(&package.row, "PK\x03\x04" + package.body.substr(4), package.request, trust, {}, "", false).reason !=
          CC::SIGN_OK);

    json wheel = package.row;
    wheel["kind"] = "wheel";
    CHECK(CC::check_plugin_package(&wheel, package.body, package.request, trust, {}, "", false).reason == CC::SIGN_KIND_MISMATCH);
    json malformed = package.row;
    malformed["size"] = 63.0;
    CHECK(CC::check_plugin_package(&malformed, package.body, package.request, trust, {}, "", false).reason == CC::SIGN_MALFORMED_ROW);
    CC::ClientRequest other = package.request;
    other.plugin_id         = "11111111-1111-4111-8111-111111111111";
    CHECK(CC::check_plugin_package(&package.row, package.body, other, trust, {}, "", false).reason == CC::SIGN_WRONG_PLUGIN);
}

TEST_CASE("A version older than the installed one is refused before the signature check", "[cosmyx]")
{
    AppConfig             config;
    const SignedPackage   package = script_package();
    const CC::ServerTrust trust   = custom_trust(config, {K1_PUBLIC, false});

    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, trust, {}, "1.0.1", false).reason == CC::SIGN_DOWNGRADE);
    // Before step 1 and before the signature: even a broken row reads downgrade.
    json broken = package.row;
    broken["sha256"] = "nope";
    CHECK(CC::check_plugin_package(&broken, package.body, package.request, trust, {}, "2.0.0", false).reason == CC::SIGN_DOWNGRADE);
    // Same or newer version, nothing recorded, or a downgrade the user chose.
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, trust, {}, "1.0.0", false).reason == CC::SIGN_OK);
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, trust, {}, "0.9.0", false).reason == CC::SIGN_OK);
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, trust, {}, "", false).reason == CC::SIGN_OK);
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, trust, {}, "1.0.1", true).reason == CC::SIGN_OK);
}

TEST_CASE("The installed package's record is written once for the bytes that passed", "[cosmyx]")
{
    AppConfig           config;
    const SignedPackage package = script_package();
    const CC::PackageVerdict verdict =
        CC::check_plugin_package(&package.row, package.body, package.request, custom_trust(config, {K1_PUBLIC, false}), {}, "", false);
    REQUIRE(verdict.ok());

    ScopedTemporaryDir dir("cosmyx-plugin");
    const fs::path     plugin_dir   = dir.path();
    const fs::path     package_file = plugin_dir / "hello.py";
    write_file(package_file, package.body);

    CC::PackageRecord record;
    CHECK_FALSE(CC::read_package_record(plugin_dir, record)); // a legacy install has none

    CC::remember_checked_package(verdict.record);
    std::string error;
    REQUIRE(CC::commit_package_record(package.request.plugin_id, plugin_dir, package_file, error));
    CHECK(error.empty());
    REQUIRE(CC::read_package_record(plugin_dir, record));
    CHECK(record.plugin_id == package.request.plugin_id);
    CHECK(record.version == "1.0.0");
    CHECK(record.sha256 == verdict.record.sha256);
    CHECK(record.size == package.body.size());
    CHECK(record.key_id == K1_ID);
    CHECK_FALSE(fs::exists(plugin_dir / (std::string(CC::PACKAGE_RECORD_FILE) + ".tmp")));
    CHECK(fs::exists(package_file));

    // The record is used once: installing the same bytes again without a new
    // check is refused, and nothing of it is left to load.
    CHECK_FALSE(CC::commit_package_record(package.request.plugin_id, plugin_dir, package_file, error));
    CHECK_FALSE(error.empty());
    CHECK_FALSE(CC::read_package_record(plugin_dir, record));
    CHECK_FALSE(fs::exists(plugin_dir / CC::PACKAGE_RECORD_FILE));
    CHECK_FALSE(fs::exists(package_file));
}

TEST_CASE("A record is never taken by another plugin id", "[cosmyx]")
{
    AppConfig           config;
    const SignedPackage package = script_package();
    const CC::PackageVerdict verdict =
        CC::check_plugin_package(&package.row, package.body, package.request, custom_trust(config, {K1_PUBLIC, false}), {}, "", false);
    REQUIRE(verdict.ok());
    CC::remember_checked_package(verdict.record);

    ScopedTemporaryDir dir("cosmyx-plugin");
    const fs::path     package_file = dir.path() / "hello.py";
    write_file(package_file, package.body);
    std::string error;
    CHECK_FALSE(CC::commit_package_record("11111111-1111-4111-8111-111111111111", dir.path(), package_file, error));
    CHECK_FALSE(fs::exists(package_file));

    // The record of the right plugin is still there for its own install.
    write_file(package_file, package.body);
    CHECK(CC::commit_package_record(package.request.plugin_id, dir.path(), package_file, error));
}

TEST_CASE("Installed bytes that differ from the checked ones are refused and removed", "[cosmyx]")
{
    AppConfig           config;
    const SignedPackage package = script_package();
    const CC::PackageVerdict verdict =
        CC::check_plugin_package(&package.row, package.body, package.request, custom_trust(config, {K1_PUBLIC, false}), {}, "", false);
    REQUIRE(verdict.ok());
    CC::remember_checked_package(verdict.record);

    // The downloaded file was swapped between the check and the install copy;
    // a record left by an earlier install must not vouch for it either.
    ScopedTemporaryDir dir("cosmyx-plugin");
    const fs::path     package_file = dir.path() / "hello.py";
    write_file(package_file, package.body + "# changed\n");
    write_file(dir.path() / CC::PACKAGE_RECORD_FILE, CC::record_to_json(verdict.record));
    std::string error;
    CHECK_FALSE(CC::commit_package_record(package.request.plugin_id, dir.path(), package_file, error));
    CHECK_FALSE(error.empty());
    CC::PackageRecord record;
    CHECK_FALSE(CC::read_package_record(dir.path(), record));
    CHECK_FALSE(fs::exists(package_file));
    CC::forget_checked_packages(package.request.plugin_id);
}

TEST_CASE("A refused install keeps the version floor of the package it replaced", "[cosmyx]")
{
    AppConfig           config;
    const SignedPackage package = script_package();
    const CC::PackageRecord floor{package.request.plugin_id, "2.0.0", std::string(64, 'a'), 10, K1_ID};

    // The installed bytes are not the checked ones: refused, and the floor is
    // written back in place of the (absent) record of the new folder.
    ScopedTemporaryDir dir("cosmyx-plugin");
    const fs::path     package_file = dir.path() / "hello.py";
    write_file(package_file, package.body + "# changed\n");
    std::string error;
    CHECK_FALSE(CC::commit_package_record(package.request.plugin_id, dir.path(), package_file, error, &floor));
    CHECK_FALSE(fs::exists(package_file));
    CC::PackageRecord record;
    REQUIRE(CC::read_package_record(dir.path(), record));
    CHECK(record.version == "2.0.0");
    CHECK(record.sha256 == floor.sha256);
    // The next download of an older version is still a downgrade.
    CHECK(CC::check_plugin_package(&package.row, package.body, package.request, custom_trust(config, {K1_PUBLIC, false}), {},
                                   record.version, false)
              .reason == CC::SIGN_DOWNGRADE);

    // A refusal for any other reason (the metadata check of the GUI hook) does the same.
    write_file(package_file, package.body);
    fs::remove(dir.path() / CC::PACKAGE_RECORD_FILE);
    CC::refuse_installed_package(dir.path(), package_file, &floor);
    CHECK_FALSE(fs::exists(package_file));
    REQUIRE(CC::read_package_record(dir.path(), record));
    CHECK(record.version == "2.0.0");
    // With no floor, nothing is left.
    write_file(package_file, package.body);
    CC::refuse_installed_package(dir.path(), package_file, nullptr);
    CHECK_FALSE(fs::exists(package_file));
    CHECK_FALSE(fs::exists(dir.path() / CC::PACKAGE_RECORD_FILE));
    CC::forget_checked_packages(package.request.plugin_id);
}

TEST_CASE("A record that cannot be written leaves no temporary file", "[cosmyx]")
{
    ScopedTemporaryDir dir("cosmyx-plugin");
    // A non-empty folder in place of the record makes the final rename fail.
    fs::create_directories(dir.path() / CC::PACKAGE_RECORD_FILE / "busy");
    std::string error;
    CHECK_FALSE(CC::write_package_record(dir.path(), {"id", "1.0.0", std::string(64, 'a'), 1, ""}, error));
    CHECK_FALSE(error.empty());
    CHECK_FALSE(fs::exists(dir.path() / (std::string(CC::PACKAGE_RECORD_FILE) + ".tmp")));
    // A folder squatting the temporary name is not ours: refused, and kept.
    fs::remove_all(dir.path() / CC::PACKAGE_RECORD_FILE);
    fs::create_directories(dir.path() / (std::string(CC::PACKAGE_RECORD_FILE) + ".tmp"));
    CHECK_FALSE(CC::write_package_record(dir.path(), {"id", "1.0.0", std::string(64, 'a'), 1, ""}, error));
    CHECK(fs::is_directory(dir.path() / (std::string(CC::PACKAGE_RECORD_FILE) + ".tmp")));
    CHECK_FALSE(fs::exists(dir.path() / CC::PACKAGE_RECORD_FILE));
}

TEST_CASE("A failed install drops the records its plugin id was checked with", "[cosmyx]")
{
    const std::string body = "# checked but never installed\n";
    const std::string id   = "22222222-2222-4222-8222-222222222222";
    const std::string kept = "33333333-3333-4333-8333-333333333333";
    CC::remember_checked_package({id, "1.0.0", CC::sha256_hex(body), body.size(), ""});
    CC::remember_checked_package({id, "1.0.1", CC::sha256_hex(body + "1"), body.size() + 1, ""});
    CC::remember_checked_package({kept, "1.0.0", CC::sha256_hex(body), body.size(), ""});

    CC::forget_checked_packages(id);

    ScopedTemporaryDir dir("cosmyx-plugin");
    const fs::path     package_file = dir.path() / "plugin.py";
    std::string        error;
    write_file(package_file, body);
    CHECK_FALSE(CC::commit_package_record(id, dir.path(), package_file, error));
    write_file(package_file, body + "1");
    CHECK_FALSE(CC::commit_package_record(id, dir.path(), package_file, error));
    // Another plugin's record is untouched.
    write_file(package_file, body);
    CHECK(CC::commit_package_record(kept, dir.path(), package_file, error));
}

TEST_CASE("A requested version is the latest or a strict X.Y.Z", "[cosmyx]")
{
    std::string version = "unchanged";
    CHECK(CC::request_version("", version));
    CHECK(version.empty());
    CHECK(CC::request_version("1.2.3", version));
    CHECK(version == "1.2.3");
    for (const std::string requested : {"1.2", "v1.2.3", "1.2.3-beta", " 1.2.3", "01.2.3", "latest", "1.2.3.4"}) {
        INFO(requested);
        version = "unchanged";
        CHECK_FALSE(CC::request_version(requested, version));
        CHECK(version == "unchanged");
    }
}

TEST_CASE("A wheel's entry package must be a safe name at the top of the wheel", "[cosmyx]")
{
    ScopedTemporaryDir dir("cosmyx-wheel");
    const fs::path     wheel = dir.path() / "hello-1.0.0-py3-none-any.whl";
    {
        mz_zip_archive archive;
        mz_zip_zero_struct(&archive);
        REQUIRE(mz_zip_writer_init_file(&archive, wheel.string().c_str(), 0));
        const std::string text = "x = 1\n";
        for (const char* name : {"hello/__init__.py", "solo.py", "hello-1.0.0.dist-info/METADATA", "nested/deep/__init__.py"})
            REQUIRE(mz_zip_writer_add_mem(&archive, name, text.data(), text.size(), MZ_DEFAULT_COMPRESSION));
        REQUIRE(mz_zip_writer_finalize_archive(&archive));
        REQUIRE(mz_zip_writer_end(&archive));
    }

    std::string error;
    CHECK(CC::check_wheel_import_name(wheel, "hello", error));
    CHECK(CC::check_wheel_import_name(wheel, "solo", error));
    CHECK(CC::check_wheel_import_name(wheel, "nested", error));
    for (const char* name : {"../../escape", "deep", "missing", "__init__", "CON", "hello.sub", ""}) {
        INFO(name);
        error.clear();
        CHECK_FALSE(CC::check_wheel_import_name(wheel, name, error));
        CHECK_FALSE(error.empty());
    }
    CHECK_FALSE(CC::check_wheel_import_name(dir.path() / "absent.whl", "hello", error));

    // Right before the import: a wheel entry is checked whatever the case of
    // its extension; a script or folder entry is not a wheel extraction.
    CHECK(CC::check_entry_package(wheel.string(), "hello", error));
    CHECK_FALSE(CC::check_entry_package(wheel.string(), "../../escape", error));
    const fs::path upper = dir.path() / "HELLO.WHL";
    fs::copy_file(wheel, upper);
    CHECK_FALSE(CC::check_entry_package(upper.string(), "missing", error));
    CHECK(CC::check_entry_package((dir.path() / "plugin.py").string(), "pkg.sub", error));
}

TEST_CASE("The plugin check uses the API address the agent was created with", "[cosmyx]")
{
    AppConfig config;
    CC::use_custom_cloud(config, {CUSTOM, CUSTOM, CUSTOM, "user-key"});
    CC::apply_cloud_server(config);
    CHECK(CC::active_api_url(config) == CUSTOM);

    // A change in Preferences reaches the agent at the next start only.
    CC::use_cosmocloud(config);
    CHECK(CC::active_api_url(config) == CUSTOM);
    CC::apply_cloud_server(config);
    CHECK(CC::active_api_url(config) == CC::CLOUD_SERVER_URL);
}

// apply_cloud_server() fills an empty orca_api_url with the Cosmyx address,
// but keeps a blank one, which the agent then uses as it is.
TEST_CASE("A blank API address is unrecognised, an empty one is the Cosmyx server", "[cosmyx]")
{
    AppConfig config;
    CHECK(CC::server_trust(config, "").cosmyx_server);
    for (const std::string url : {" ", "\t", " \n "}) {
        INFO(url);
        const CC::ServerTrust trust = CC::server_trust(config, url);
        CHECK(trust.unrecognised);
        CHECK_FALSE(trust.cosmyx_server);
        CHECK(trust.keys.empty());
    }
}

TEST_CASE("A wheel entry is told by its extension in any case", "[cosmyx]")
{
    for (const std::string path : {"a/plugin.whl", "a/PLUGIN.WHL", "plugin.Whl"})
        CHECK(CC::is_wheel_path(path));
    for (const std::string path : {"a/plugin.py", "a/plugin.whl.py", "a/whl", "a/plugin.whlx", ""})
        CHECK_FALSE(CC::is_wheel_path(path));
}
