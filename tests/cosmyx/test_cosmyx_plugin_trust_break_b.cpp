// Holes found by breaking the plugin install trust layer (decision 0204):
// the server address policy, the pinned-key rule and the package record.
// Each case reproduces a deviation from the decision and fails until the
// logic is fixed.

#include <catch2/catch_test_macros.hpp>

#include <ios>
#include <string>

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

// k1 of the CosmoCloud vectors (seed 000102...1f).
constexpr const char* K1_PUBLIC       = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8";
constexpr const char* K1_PUBLIC_UPPER = "03A107BFF3CE10BE1D70DD18E74BC09967E4D6309BA50D5F1DDC8664125531B8";

constexpr const char* CUSTOM = "https://plugins.example.org";

void write_file(const fs::path& path, const std::string& data)
{
    boost::nowide::ofstream file(path.string(), std::ios::binary | std::ios::trunc);
    file.write(data.data(), static_cast<std::streamsize>(data.size()));
    REQUIRE(file);
}

} // namespace

// Decision 0204: "The build's pins cover CLOUD_SERVER_URL only; nothing the
// user stores for that address is used", and the pins are keyed by the
// normalized API address. A spelling of the same address that differs only in
// the case of the scheme or host, or in an explicit default port, reaches the
// same server, yet it is treated as a custom server: the user's pins and the
// unverified opt-in then apply to packages from the Cosmyx server, and the
// build's keys do not.
TEST_CASE("An equivalent spelling of the Cosmyx address is still the Cosmyx server", "[cosmyx][break]")
{
    const std::string variants[] = {
        "https://ORCA-CLOUD.COSMYX3D.FR",
        "https://Orca-Cloud.cosmyx3d.fr",
        "HTTPS://orca-cloud.cosmyx3d.fr",
        "https://orca-cloud.cosmyx3d.fr:443",
    };
    for (const std::string& url : variants) {
        INFO(url);
        AppConfig config;
        CC::set_server_pins(config, url, {"", true});
        CC::ServerTrust trust = CC::server_trust(config, url);
        CHECK(trust.cosmyx_server);
        CHECK_FALSE(trust.allow_unverified);
        CHECK(trust.keys == CC::built_in_keys());

        CC::set_server_pins(config, url, {K1_PUBLIC, false});
        trust = CC::server_trust(config, url);
        CHECK(trust.cosmyx_server);
        CHECK(trust.keys == CC::built_in_keys());
    }
}

// Decision 0204 and PluginTrust.cpp: "A pinned key always means full
// verification, never a fallback." A pin whose key is stored in a form
// server_pins() does not accept (upper case, surrounding spaces, a typo) is
// dropped silently, and the opt-in stored next to it then turns the server
// into an unverified one: the user who pinned a key gets unsigned installs.
TEST_CASE("A pinned key that cannot be read never falls back to unverified plugins", "[cosmyx][break]")
{
    const std::string stored_keys[] = {
        K1_PUBLIC_UPPER,
        std::string(" ") + K1_PUBLIC + " ",
        std::string(K1_PUBLIC).substr(0, 63),
        "ZZ",
    };
    for (const std::string& key : stored_keys) {
        INFO(key);
        AppConfig config;
        nlohmann::json doc;
        doc[CUSTOM] = {{"public_key", key}, {"allow_unverified", true}};
        config.set(CC::PLUGIN_TRUST_KEY, doc.dump());
        const CC::ServerTrust trust = CC::server_trust(config, CUSTOM);
        CHECK_FALSE(trust.allow_unverified);
    }

    // The same through the public setter, which stores whatever it is given.
    AppConfig config;
    CC::set_server_pins(config, CUSTOM, {K1_PUBLIC_UPPER, true});
    CHECK_FALSE(CC::server_trust(config, CUSTOM).allow_unverified);
}

// PluginTrust.hpp: remember_checked_package() keeps the record "until its
// install commits it. Thread-safe." The pending records are keyed by SHA-256
// alone, so two plugins whose packages have the same bytes (signed rows bind
// the plugin id, not the body) overwrite each other: the first plugin's
// install then finds no record for its id and is left with none, read as
// unverified, and loses its anti-rollback floor.
TEST_CASE("Two plugins with the same package bytes each keep their own record", "[cosmyx][break]")
{
    const std::string body = "# plugin body shared by two plugin ids\n";
    const std::string sha  = CC::sha256_hex(body);
    const std::string id_a = "0b8f7c1e-5d4a-4f3b-9a2c-1e0d9c8b7a61";
    const std::string id_b = "7c6b5a49-3827-4615-a4b3-c2d1e0f9a8b7";

    CC::remember_checked_package({id_a, "1.0.0", sha, body.size(), ""});
    CC::remember_checked_package({id_b, "2.0.0", sha, body.size(), ""});

    ScopedTemporaryDir dir_a("cosmyx-break-a");
    ScopedTemporaryDir dir_b("cosmyx-break-b");
    write_file(dir_a.path() / "plugin.py", body);
    write_file(dir_b.path() / "plugin.py", body);

    std::string error;
    REQUIRE(CC::commit_package_record(id_a, dir_a.path(), dir_a.path() / "plugin.py", error));
    REQUIRE(CC::commit_package_record(id_b, dir_b.path(), dir_b.path() / "plugin.py", error));

    CC::PackageRecord record;
    REQUIRE(CC::read_package_record(dir_a.path(), record));
    CHECK(record.plugin_id == id_a);
    CHECK(record.version == "1.0.0");
    REQUIRE(CC::read_package_record(dir_b.path(), record));
    CHECK(record.plugin_id == id_b);
    CHECK(record.version == "2.0.0");
}
