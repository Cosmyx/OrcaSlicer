// Server addresses as the plugin check (decision 0204) and Preferences
// (decision 0203) read them: IPv6 literals, the spellings of a loopback host
// that may carry plain http, and the one rule both apply.

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <utility>

#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"

namespace CC = Slic3r::GUI::Cosmyx;
using CC::CloudValueError;

TEST_CASE("An IPv6 literal is read as inet_pton reads it and kept in its RFC 5952 spelling", "[cosmyx]")
{
    const std::pair<std::string, std::string> recognised[] = {
        {"https://[::]", "https://[::]"},
        {"https://[0:0:0:0:0:0:0:1]", "https://[::1]"},
        {"https://[2001:DB8:0:0:1:0:0:1]:8443", "https://[2001:db8::1:0:0:1]:8443"},
        {"https://[2001:0db8::0001]", "https://[2001:db8::1]"},
        {"https://[1:0:0:2:0:0:0:3]", "https://[1:0:0:2::3]"},
        {"https://[1::2:3:4:5:6:7]", "https://[1:0:2:3:4:5:6:7]"},
        {"https://[::ffff:1.2.3.4]", "https://[::ffff:102:304]"},
        {"https://[1:2:3:4:5:6:7:8]", "https://[1:2:3:4:5:6:7:8]"},
    };
    for (const auto& [typed, expected] : recognised) {
        INFO(typed);
        CC::ServerAddress address;
        REQUIRE(CC::parse_server_address(typed, address));
        CHECK(address.url() == expected);
        CHECK(CC::check_cloud_url(typed) == CloudValueError::None);
    }
    for (const std::string typed : {"https://[:::]", "https://[1:2:3:4:5:6:7:8:9]", "https://[1:2:3:4:5:6:7]", "https://[1::2::3]",
                                    "https://[12345::]", "https://[::1.2.3]", "https://[::01.2.3.4]", "https://[1.2.3.4::]",
                                    "https://[::1:]", "https://[:1::]", "https://[1:2:3:4:5:6:7::8]", "https://[g::]"}) {
        INFO(typed);
        CC::ServerAddress address;
        CHECK_FALSE(CC::parse_server_address(typed, address));
    }
}

TEST_CASE("Plain http loopback addresses are spelled so that libcurl never resolves them", "[cosmyx]")
{
    // ::1 in any spelling is a literal libcurl connects to.
    CHECK(CC::check_cloud_url("http://[0:0:0:0:0:0:0:1]:8000") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://[0::1]") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://127.0.0.0") == CloudValueError::None);
    // A trailing-dot name may go to DNS; a mapped address depends on the OS;
    // a leading zero is octal or a name to libcurl; a short form is a name to
    // libcurl's IPv4 check here.
    for (const std::string url : {"http://localhost.", "http://cloud.localhost.", "http://[::ffff:127.0.0.1]", "http://[::127.0.0.1]",
                                  "http://0127.0.0.1", "http://127.0.0.01", "http://127.000.0.1", "http://127.1", "http://2130706433",
                                  "http://0x7f.0.0.1"}) {
        INFO(url);
        CHECK(CC::check_cloud_url(url) == CloudValueError::NotHttps);
    }
}

TEST_CASE("Preferences and the plugin check read an address by the same rule", "[cosmyx]")
{
    CHECK(CC::server_kind("") == CC::ServerKind::Cosmyx);
    CHECK(CC::server_kind(CC::CLOUD_SERVER_URL) == CC::ServerKind::Cosmyx);
    CHECK(CC::server_kind("https://ORCA-CLOUD.cosmyx3d.fr.:443/api") == CC::ServerKind::Cosmyx);
    CHECK(CC::server_kind("https://cloud.example.org") == CC::ServerKind::Custom);
    for (const std::string url : {" ", "\t\n", "https://orca-cloud.cosmyx3d.fr:8443", "http://orca-cloud.cosmyx3d.fr",
                                  "https://u@orca-cloud.cosmyx3d.fr", "orca-cloud.cosmyx3d.fr"}) {
        INFO(url);
        CHECK(CC::server_kind(url) == CC::ServerKind::Unrecognised);
        CHECK(CC::check_cloud_url(CC::trim_value(url)) != CloudValueError::None);
    }
    CC::ServerAddress address;
    REQUIRE(CC::server_kind("https://Cloud.Example.org:0443/", &address) == CC::ServerKind::Custom);
    CHECK(address.url() == "https://cloud.example.org");
}
