// Holes found by the second round of breaking the plugin install trust layer
// (decision 0204), aimed at the one-spelling rule of server addresses. Each
// case reproduces a deviation from the decision and fails until the logic is
// fixed.
//
// The cloud agent hands its API address, with a path appended, to libcurl
// (Http::get(api_base_url + path)). libcurl decodes a percent-encoded host,
// accepts and drops user info, removes dot segments from the path and, for an
// address with no scheme, guesses http. Every such spelling of the Cosmyx
// address therefore reaches the Cosmyx server, yet normalize_server_url()
// keeps it apart from CLOUD_SERVER_URL, so server_trust() treats it as a
// custom server and applies the user's pins and unverified opt-in to it.

#include <catch2/catch_test_macros.hpp>

#include <string>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginSigning.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp"

using namespace Slic3r;
namespace CC = Slic3r::GUI::Cosmyx;

namespace {

// k1 of the CosmoCloud vectors (seed 000102...1f).
constexpr const char* K1_PUBLIC = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8";

constexpr const char* CUSTOM = "https://plugins.example.org";

// The user's opt-in and pinned key stored for url never apply to it: it is
// either refused as unrecognised (no key at all, not even the build's), or the
// Cosmyx server, checked against the build's keys only.
void check_never_custom(const std::string& url)
{
    INFO(url);
    AppConfig config;
    CC::set_server_pins(config, url, {"", true});
    CC::ServerTrust trust = CC::server_trust(config, url);
    CHECK_FALSE(trust.allow_unverified);
    CHECK(trust.keys == (trust.unrecognised ? CC::KeyTable{} : CC::built_in_keys()));

    CC::set_server_pins(config, url, {K1_PUBLIC, false});
    trust = CC::server_trust(config, url);
    CHECK_FALSE(trust.allow_unverified);
    CHECK(trust.keys == (trust.unrecognised ? CC::KeyTable{} : CC::built_in_keys()));
}

} // namespace

// Decision 0204: "every spelling of CLOUD_SERVER_URL is the Cosmyx server, and
// the user's pins and opt-in never apply to it". Preferences accepts any path
// (check_cloud_url() only checks the authority), and libcurl removes the dot
// segments of base + "/api/v1/...", so these addresses reach the Cosmyx API.
TEST_CASE("A dot segment in the path of the Cosmyx address is still the Cosmyx server", "[cosmyx][break]")
{
    const std::string base = CC::CLOUD_SERVER_URL;
    for (const std::string& url : {base + "/.", base + "/./", base + "/x/..", base + "/x/../", base + "/a/b/../.."})
        check_never_custom(url);
}

// libcurl decodes %XX in the host name, so these reach the Cosmyx host.
// check_cloud_url() does not refuse '%' in the host, so Preferences takes them.
TEST_CASE("A percent-encoded host of the Cosmyx address is still the Cosmyx server", "[cosmyx][break]")
{
    for (const std::string url : {"https://orca-cloud.cosmyx3d%2Efr", "https://%6Frca-cloud.cosmyx3d.fr",
                                  "https://ORCA-CLOUD.COSMYX3D%2efr", "https://orca-cloud.cosmyx3d.fr%2E"})
        check_never_custom(url);
}

// normalize_authority() leaves an authority holding '@' as it is, on the
// assumption that the cloud settings refuse user info. apply_cloud_server()
// keeps any orca_api_url the user wrote by hand, and libcurl sends such an
// address to the host after the '@'.
TEST_CASE("User info in front of the Cosmyx host is still the Cosmyx server", "[cosmyx][break]")
{
    for (const std::string url : {"https://user@orca-cloud.cosmyx3d.fr", "https://user:secret@orca-cloud.cosmyx3d.fr",
                                  "https://@orca-cloud.cosmyx3d.fr", "https://user@ORCA-CLOUD.cosmyx3d.fr:443/"})
        check_never_custom(url);
}

// normalize_server_url() reads an address with no scheme as https, but the
// agent passes orca_api_url to libcurl as it is, and libcurl guesses http for
// it. The pins and the unverified opt-in the user gave the https server then
// apply to packages fetched in plain http from that host, where anyone on the
// path can serve them. (test_cosmyx_plugin_trust.cpp "Server addresses have
// one spelling" pins the https reading; it describes the hole.)
TEST_CASE("An address with no scheme does not take the pins of its https address", "[cosmyx][break]")
{
    AppConfig config;
    CC::set_server_pins(config, CUSTOM, {"", true});
    REQUIRE(CC::server_trust(config, CUSTOM).allow_unverified);
    CHECK_FALSE(CC::server_trust(config, "plugins.example.org").allow_unverified);
    CHECK_FALSE(CC::server_trust(config, "plugins.example.org:443").allow_unverified);
}
