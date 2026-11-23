// Holes found by the fourth round of breaking the plugin install trust layer
// (decision 0204), aimed at the addresses a hand-edited app config can hold:
// Preferences trims and checks what it writes, but orca_api_url can be edited
// by hand, and the cloud agent then uses it exactly as stored. Each case
// reproduces a deviation from the decision and fails until the logic is fixed.

#include <catch2/catch_test_macros.hpp>

#include <string>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp"

using namespace Slic3r;
namespace CC = Slic3r::GUI::Cosmyx;
using CC::CloudValueError;
using CC::ServerKind;

// Decision 0204, "Canonical or refused addresses": an address is read only
// when it has no "whitespace, control or non-ASCII character anywhere", and a
// blank orca_api_url is unrecognised because the agent "uses it as it is".
// server_kind() trims the address first, so a hand-edited " https://host "
// or "https://host\n" is read as https://host, while
// OrcaCloudServiceAgent::configure_urls() hands the untrimmed value, with a
// path appended, to libcurl. The plugin check then names a server other than
// the string the agent actually requests, and a user's pin or opt-in for
// https://custom.example applies to it.
TEST_CASE("An API address with surrounding whitespace is unrecognised, as the agent uses it untrimmed", "[cosmyx][break]")
{
    const std::string custom = "https://custom.example";
    AppConfig         config;
    REQUIRE(CC::set_server_pins(config, custom, {"", true}));
    REQUIRE(CC::server_trust(config, custom).allow_unverified);

    for (const std::string& url : {" " + custom, custom + " ", "\t" + custom + "\n", custom + "\r\n"}) {
        INFO("[" << url << "]");
        CHECK(CC::server_kind(url) == ServerKind::Unrecognised);
        const CC::ServerTrust trust = CC::server_trust(config, url);
        CHECK(trust.unrecognised);
        CHECK_FALSE(trust.allow_unverified);
    }
    for (const std::string& url : {std::string(" ") + CC::CLOUD_SERVER_URL, std::string(CC::CLOUD_SERVER_URL) + "\n"}) {
        INFO("[" << url << "]");
        CHECK(CC::server_kind(url) == ServerKind::Unrecognised);
        CHECK_FALSE(CC::server_trust(config, url).cosmyx_server);
    }
    // Preferences trims before it checks, so a padded value typed there is
    // still taken, and stored trimmed.
    CC::CloudValues values{" " + custom + " ", custom, custom, "key"};
    REQUIRE(CC::normalize_cloud_values(values).ok());
    CHECK(values[CC::ApiUrl] == custom);
    CHECK(CC::server_kind(values[CC::ApiUrl]) == ServerKind::Custom);
}

// Decision 0204, "Loopback is spelled so that libcurl never resolves it":
// plain http is allowed on a loopback host only, and "an orca_api_url written
// by hand in the app config can still be anything, and is then refused for
// plugins by the rule above". server_kind() only refuses http on the Cosmyx
// host: a hand-edited http address on any other host is a custom server, so
// the user's "Allow unverified plugins from this server" opt-in installs
// unsigned packages fetched over plain http, which anyone on the path can
// replace. check_cloud_url() refuses every one of these addresses.
TEST_CASE("A plain http API address on a non-loopback host is refused for plugins", "[cosmyx][break]")
{
    for (const std::string& url : {"http://custom.example", "http://custom.example:8000/api", "http://10.0.0.5:8000",
                                   "http://192.168.1.20", "http://127.0.0.08", "http://localhost.:8000", "http://[::ffff:127.0.0.1]:8000",
                                   "http://[2001:db8::1]", "http://2130706433"}) {
        INFO(url);
        REQUIRE(CC::check_cloud_url(url) == CloudValueError::NotHttps);

        AppConfig config;
        CC::set_server_pins(config, url, {"", true});
        CHECK(CC::server_kind(url) == ServerKind::Unrecognised);
        const CC::ServerTrust trust = CC::server_trust(config, url);
        CHECK(trust.unrecognised);
        CHECK_FALSE(trust.allow_unverified);
    }
    // Plain http on a loopback host stays a custom server (decision 0203).
    for (const std::string& url : {"http://localhost:8000", "http://api.localhost", "http://127.0.0.1:8000", "http://[::1]:8000"}) {
        INFO(url);
        REQUIRE(CC::check_cloud_url(url) == CloudValueError::None);
        AppConfig config;
        REQUIRE(CC::set_server_pins(config, url, {"", true}));
        CHECK(CC::server_kind(url) == ServerKind::Custom);
        CHECK(CC::server_trust(config, url).allow_unverified);
    }
}
