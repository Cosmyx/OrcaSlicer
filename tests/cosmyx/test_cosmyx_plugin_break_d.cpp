// Holes found by the third round of breaking the plugin install trust layer
// (decision 0204), aimed at the canonical-or-refuse address parser and at the
// agreement between Preferences and the plugin check. Each case reproduces a
// deviation from the decision and fails until the logic is fixed.

#include <catch2/catch_test_macros.hpp>

#include <string>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp"

using namespace Slic3r;
namespace CC = Slic3r::GUI::Cosmyx;
using CC::CloudValueError;

// Decision 0204, "Preferences agree": check_cloud_url() requires
// parse_server_address() to accept the address, "so Preferences never takes an
// address whose plugins would all be refused". server_trust() also refuses, as
// unrecognised, any port other than the default one on the Cosmyx host, but
// check_cloud_url() only asks the parser, which reads such an address fine. So
// Preferences takes https://<Cosmyx host>:8443 and every plugin install from it
// is then refused with unrecognised_server.
TEST_CASE("Preferences never takes a Cosmyx host address that the plugin check calls unrecognised", "[cosmyx][break]")
{
    AppConfig         config;
    const std::string host = "orca-cloud.cosmyx3d.fr";
    for (const std::string& url : {"https://" + host + ":8443", std::string("https://ORCA-CLOUD.cosmyx3d.fr:65535/api"),
                                  "https://" + host + ".:1/v1"}) {
        INFO(url);
        if (CC::check_cloud_url(url) == CloudValueError::None)
            CHECK_FALSE(CC::server_trust(config, url).unrecognised);
        else
            SUCCEED("Preferences refuses it");

        // The same through the Preferences path, which normalizes first.
        CC::CloudValues values{url, url, url, "key"};
        if (CC::normalize_cloud_values(values).ok())
            CHECK_FALSE(CC::server_trust(config, values[CC::ApiUrl]).unrecognised);
        else
            SUCCEED("Preferences refuses it");
    }
}

// check_cloud_url() lets plain http through only on a loopback host, "where it
// never leaves the machine". is_loopback_ipv4() reads each octet as decimal, so
// it takes 127.0.0.08. libcurl reads a numeric host part with a leading zero as
// octal (strtoul with base 0); "08" and "09" are not octal, so libcurl keeps
// the whole host as a name and hands it to the resolver, which sends a DNS
// query for it (search domains appended): the plain-http API traffic then goes
// wherever the network's DNS answers, not to 127.0.0.1.
TEST_CASE("Plain http is refused on a dotted host that libcurl does not read as a loopback address", "[cosmyx][break]")
{
    for (const std::string& url : {"http://127.0.0.08", "http://127.0.0.09:8000", "http://127.08.0.1/api", "http://127.0.09.1"}) {
        INFO(url);
        CHECK(CC::check_cloud_url(url) != CloudValueError::None);
    }
    // Typed without a scheme, the Preferences path reads it as a loopback host
    // and adds http:// to it.
    CC::CloudValues values{"127.0.0.08:8000", "127.0.0.08:8000", "127.0.0.08:8000", "key"};
    INFO(values[CC::ApiUrl]);
    if (CC::normalize_cloud_values(values).ok())
        CHECK(values[CC::ApiUrl].rfind("http://", 0) != 0);
    else
        SUCCEED("Preferences refuses it");
}

// parse_server_address() reads "an [IPv6] literal", but any bracketed run of
// hex digits, ':' and '.' passes, so Preferences takes addresses that are not
// IPv6 addresses at all (libcurl refuses them with a bad IPv6 error, so every
// request to them fails).
TEST_CASE("A bracketed host that is not an IPv6 address is not read as one", "[cosmyx][break]")
{
    for (const std::string& url : {"https://[:]", "https://[1.2.3.4]", "https://[::1::2]", "https://[.]", "https://[abc]"}) {
        INFO(url);
        CC::ServerAddress address;
        CHECK_FALSE(CC::parse_server_address(url, address));
        CHECK(CC::check_cloud_url(url) != CloudValueError::None);
    }
}
