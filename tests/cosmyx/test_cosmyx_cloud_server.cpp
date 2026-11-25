// Checks of the CosmoCloud server defaults (decision 0201) and of the custom
// cloud instance chosen in Preferences (decision 0203). The cloud keys read by
// OrcaCloudServiceAgent::configure_urls() are filled only when empty or still
// holding the value Cosmyx wrote, so a user's value always wins.

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <utility>

#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Cosmyx/StealthMode.hpp"
#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"

using namespace Slic3r;
namespace CC = Slic3r::GUI::Cosmyx;
using CC::CloudValueError;

namespace {

void clear_cloud_keys(AppConfig& config)
{
    config.erase("app", CC::CUSTOM_CLOUD_KEY);
    for (const char* key : CC::CLOUD_KEYS) {
        config.erase("app", key);
        config.erase("app", std::string(CC::SEEDED_PREFIX) + key);
        config.erase("app", std::string(CC::CUSTOM_PREFIX) + key);
    }
}

void check_cosmocloud(const AppConfig& config)
{
    CHECK(config.get("orca_api_url") == CC::CLOUD_SERVER_URL);
    CHECK(config.get("orca_auth_url") == CC::CLOUD_SERVER_URL);
    CHECK(config.get("orca_cloud_url") == CC::CLOUD_SERVER_URL);
    CHECK(config.get("orca_pub_key") == CC::CLOUD_PUB_KEY);
}

CC::CloudValues custom_values()
{
    return {"https://api.example.org", "https://auth.example.org", "https://web.example.org", "user-key"};
}

} // namespace

TEST_CASE("CosmoCloud serves the API, auth and web pages from one host", "[cosmyx]")
{
    const std::string host = CC::CLOUD_SERVER_URL;
    CHECK(host == "https://orca-cloud.cosmyx3d.fr");
    CHECK(CC::check_cloud_url(host) == CloudValueError::None);
    CHECK(CC::check_pub_key(CC::CLOUD_PUB_KEY) == CloudValueError::None);

    CHECK(std::string(CC::CLOUD_KEYS[CC::ApiUrl]) == "orca_api_url");
    CHECK(std::string(CC::CLOUD_KEYS[CC::AuthUrl]) == "orca_auth_url");
    CHECK(std::string(CC::CLOUD_KEYS[CC::CloudUrl]) == "orca_cloud_url");
    CHECK(std::string(CC::CLOUD_KEYS[CC::PubKey]) == "orca_pub_key");
    const CC::CloudValues defaults = CC::cosmocloud_values();
    CHECK(defaults[CC::ApiUrl] == host);
    CHECK(defaults[CC::AuthUrl] == host);
    CHECK(defaults[CC::CloudUrl] == host);
    CHECK(defaults[CC::PubKey] == CC::CLOUD_PUB_KEY);
}

TEST_CASE("A fresh configuration gets every CosmoCloud value", "[cosmyx]")
{
    AppConfig config;
    clear_cloud_keys(config);

    CHECK(CC::apply_cloud_server(config) == 4);
    check_cosmocloud(config);
    CHECK_FALSE(CC::custom_cloud_enabled(config));

    SECTION("applying again changes nothing") {
        CHECK(CC::apply_cloud_server(config) == 0);
        check_cosmocloud(config);
    }
}

TEST_CASE("A cloud value set by hand wins", "[cosmyx]")
{
    AppConfig config;
    clear_cloud_keys(config);
    config.set("orca_api_url", "https://api.example.org");
    config.set("orca_pub_key", "user-key");

    CHECK(CC::apply_cloud_server(config) == 2);
    CHECK(config.get("orca_api_url") == "https://api.example.org");
    CHECK(config.get("orca_pub_key") == "user-key");
    CHECK(config.get("orca_auth_url") == CC::CLOUD_SERVER_URL);
    CHECK(config.get("orca_cloud_url") == CC::CLOUD_SERVER_URL);

    SECTION("also when set after Cosmyx filled it") {
        config.set("orca_cloud_url", "https://web.example.org");
        CHECK(CC::apply_cloud_server(config) == 0);
        CHECK(config.get("orca_cloud_url") == "https://web.example.org");
    }
    SECTION("until the user clears it") {
        config.set("orca_api_url", "");
        CHECK(CC::apply_cloud_server(config) == 1);
        CHECK(config.get("orca_api_url") == CC::CLOUD_SERVER_URL);
    }
}

TEST_CASE("A value Cosmyx wrote follows a new CosmoCloud constant", "[cosmyx]")
{
    AppConfig config;
    clear_cloud_keys(config);
    // As left by an older build whose constant was another host.
    config.set("orca_api_url", "https://old.example.org");
    config.set(std::string(CC::SEEDED_PREFIX) + "orca_api_url", "https://old.example.org");

    CC::apply_cloud_server(config);
    CHECK(config.get("orca_api_url") == CC::CLOUD_SERVER_URL);
    CHECK(config.get(std::string(CC::SEEDED_PREFIX) + "orca_api_url") == CC::CLOUD_SERVER_URL);
}

TEST_CASE("Applying the cloud server seeds the stealth mode default", "[cosmyx]")
{
    AppConfig config;
    config.set("firstguide", "finish", "1");
    config.set_bool("stealth_mode", false);

    CC::apply_cloud_server(config);
    CHECK(config.has(Cosmyx::STEALTH_SEEDED_KEY));
    CHECK(config.get_stealth_mode() == Cosmyx::STEALTH_MODE_DEFAULT);
}

TEST_CASE("A custom cloud instance wins over CosmoCloud", "[cosmyx]")
{
    AppConfig config;
    clear_cloud_keys(config);
    CC::apply_cloud_server(config);

    CC::use_custom_cloud(config, custom_values());
    CHECK(CC::custom_cloud_enabled(config));
    CHECK(config.get("orca_api_url") == "https://api.example.org");
    CHECK(config.get("orca_auth_url") == "https://auth.example.org");
    CHECK(config.get("orca_cloud_url") == "https://web.example.org");
    CHECK(config.get("orca_pub_key") == "user-key");
    CHECK(CC::custom_cloud_values(config) == custom_values());

    SECTION("at the next start") {
        CHECK(CC::apply_cloud_server(config) == 0);
        CHECK(config.get("orca_api_url") == "https://api.example.org");
    }
    SECTION("even when a custom value equals what Cosmyx wrote before") {
        CC::CloudValues values = custom_values();
        values[CC::ApiUrl]     = "https://old.example.org";
        CC::use_custom_cloud(config, values);
        config.set(std::string(CC::SEEDED_PREFIX) + "orca_api_url", "https://old.example.org");
        CHECK(CC::apply_cloud_server(config) == 0);
        CHECK(config.get("orca_api_url") == "https://old.example.org");
    }
    SECTION("but an emptied key never falls back to the upstream cloud") {
        config.set("orca_auth_url", "");
        CHECK(CC::apply_cloud_server(config) == 1);
        CHECK(config.get("orca_auth_url") == CC::CLOUD_SERVER_URL);
        CHECK(config.get("orca_api_url") == "https://api.example.org");
    }
}

TEST_CASE("Turning the custom instance off goes back to CosmoCloud and keeps the values", "[cosmyx]")
{
    AppConfig config;
    clear_cloud_keys(config);
    CC::use_custom_cloud(config, custom_values());

    CC::use_cosmocloud(config);
    CHECK_FALSE(CC::custom_cloud_enabled(config));
    check_cosmocloud(config);
    // Shown back when the user turns it on again.
    CHECK(CC::custom_cloud_values(config) == custom_values());
    // Owned by Cosmyx again, so a new CosmoCloud constant would reach them.
    CHECK(CC::apply_cloud_server(config) == 0);
    for (const char* key : CC::CLOUD_KEYS)
        CHECK(config.get(std::string(CC::SEEDED_PREFIX) + key) == config.get(key));
}

TEST_CASE("Custom values are empty before the first custom instance", "[cosmyx]")
{
    AppConfig config;
    clear_cloud_keys(config);
    CC::apply_cloud_server(config);
    for (const std::string& value : CC::custom_cloud_values(config))
        CHECK(value.empty());
}

TEST_CASE("Cloud values are trimmed", "[cosmyx]")
{
    CHECK(CC::trim_value("  https://a.example \t\r\n") == "https://a.example");
    CHECK(CC::trim_value(" \t ").empty());
    CHECK(CC::trim_value("").empty());
    CHECK(CC::trim_value("key") == "key");
}

TEST_CASE("Cloud addresses must be https with a host, or http on loopback", "[cosmyx]")
{
    CHECK(CC::check_cloud_url("https://cloud.example.org") == CloudValueError::None);
    CHECK(CC::check_cloud_url("HTTPS://cloud.example.org") == CloudValueError::None);
    CHECK(CC::check_cloud_url("https://cloud.example.org/base/path") == CloudValueError::None);
    CHECK(CC::check_cloud_url("https://cloud.example.org:8443") == CloudValueError::None);
    CHECK(CC::check_cloud_url("https://192.168.1.10") == CloudValueError::None);
    CHECK(CC::check_cloud_url("https://[::1]:443") == CloudValueError::None);
    CHECK(CC::check_cloud_url("https://[fe80::1]") == CloudValueError::None);
    CHECK(CC::check_cloud_url("https://localhost") == CloudValueError::None);

    CHECK(CC::check_cloud_url("") == CloudValueError::Empty);
    CHECK(CC::check_cloud_url("http://cloud.example.org") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("cloud.example.org") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("ftp://cloud.example.org") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("https:/cloud.example.org") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("https://") == CloudValueError::NoHost);
    CHECK(CC::check_cloud_url("https:///path") == CloudValueError::NoHost);
    CHECK(CC::check_cloud_url("https://:443") == CloudValueError::NoHost);
    CHECK(CC::check_cloud_url("https://[]") == CloudValueError::NoHost);

    CHECK(CC::check_cloud_url("https://cloud example.org") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://user:pass@cloud.example.org") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org:") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org:abc") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org:0") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org:65536") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org:123456") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://[::1") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://[::1]x") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://[::1]:") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org\t") == CloudValueError::Invalid);
    // What the plugin check would not recognise (decision 0204): Preferences
    // never takes an address whose plugins would all be refused.
    CHECK(CC::check_cloud_url("https://cloud.example.org/base/path?x=1#y") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org/#y") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud%2Eexample.org") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org/a/../b") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org/.") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud.example.org\\api") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cloud..example.org") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("https://cl\xc3\xb6ud.example.org") == CloudValueError::Invalid);
}

TEST_CASE("A server address is read in its one spelling or not at all", "[cosmyx]")
{
    const std::pair<std::string, std::string> recognised[] = {
        {" HTTPS://Cloud.Example.ORG.:0443//", "https://cloud.example.org"},
        {"https://cloud.example.org:", "https://cloud.example.org"},
        {"https://cloud.example.org:8443/API//v1/", "https://cloud.example.org:8443/API//v1"},
        {"http://[::1]:080", "http://[::1]"},
        {"https://[FE80::1]", "https://[fe80::1]"},
        {"https://cloud_1.example.org/a.b/..c", "https://cloud_1.example.org/a.b/..c"},
    };
    for (const auto& [typed, expected] : recognised) {
        INFO(typed);
        CC::ServerAddress address;
        REQUIRE(CC::parse_server_address(typed, address));
        CHECK(address.url() == expected);
    }
    CC::ServerAddress address;
    REQUIRE(CC::parse_server_address("https://h.example.org:8443/p", address));
    CHECK(address.scheme == "https");
    CHECK(address.host == "h.example.org");
    CHECK(address.port == "8443");
    CHECK(address.path == "/p");

    for (const std::string typed : {"", "cloud.example.org", "ws://cloud.example.org", "https:/cloud.example.org",
                                    "https://u@cloud.example.org", "https://cloud.example.org/%41", "https://cloud.example.org?x",
                                    "https://cloud.example.org/..", "https://cloud.example.org/./", "https://[::1",
                                    "https://[::1]:x", "https://[::g]",
                                    "https://cloud.example.org:-1", "https://cloud.example.org:443:443", "https://-.example.org/ x"}) {
        INFO(typed);
        CHECK_FALSE(CC::parse_server_address(typed, address));
    }
}

TEST_CASE("Plain http is accepted only on a loopback host", "[cosmyx]")
{
    // A local test server, e.g. CosmoCloud run on the developer's machine.
    CHECK(CC::check_cloud_url("http://localhost:8000") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://localhost") == CloudValueError::None);
    CHECK(CC::check_cloud_url("HTTP://LocalHost:8000/api") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://cloud.localhost:8000") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://127.0.0.1:8000") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://127.255.255.254") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://[::1]:8000") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://[::1]") == CloudValueError::None);

    CHECK(CC::check_cloud_url("http://cloud.example.org") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://192.168.1.10:8000") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://128.0.0.1") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://127.0.0") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://127.0.0.1.example.org") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://127.0.0.256") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://localhost.example.org") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://notlocalhost") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://.localhost") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://[::2]") == CloudValueError::NotHttps);
    CHECK(CC::check_cloud_url("http://[localhost]") == CloudValueError::NotHttps);

    // The other rules still hold for http.
    CHECK(CC::check_cloud_url("http://") == CloudValueError::NoHost);
    CHECK(CC::check_cloud_url("http://localhost:0") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("http://localhost:65536") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("http://localhost:65535") == CloudValueError::None);
    CHECK(CC::check_cloud_url("http://user@localhost") == CloudValueError::Invalid);
    CHECK(CC::check_cloud_url("http://local host") == CloudValueError::Invalid);
}

TEST_CASE("The public key must be one word", "[cosmyx]")
{
    CHECK(CC::check_pub_key("sb_publishable_abc") == CloudValueError::None);
    CHECK(CC::check_pub_key("") == CloudValueError::Empty);
    CHECK(CC::check_pub_key("two words") == CloudValueError::Invalid);
}

TEST_CASE("Custom values are normalized before they are checked", "[cosmyx]")
{
    CC::CloudValues values = {"  HTTPS://api.example.org/ ", "https://auth.example.org//", "https://web.example.org/base/",
                              "  user-key\n"};
    const CC::CloudValidation result = CC::normalize_cloud_values(values);
    CHECK(result.ok());
    CHECK(values[CC::ApiUrl] == "https://api.example.org");
    CHECK(values[CC::AuthUrl] == "https://auth.example.org");
    CHECK(values[CC::CloudUrl] == "https://web.example.org/base");
    CHECK(values[CC::PubKey] == "user-key");

    SECTION("the first field in error is reported") {
        CC::CloudValues bad = {"https://api.example.org", "http://auth.example.org", "", ""};
        const CC::CloudValidation error = CC::normalize_cloud_values(bad);
        CHECK_FALSE(error.ok());
        CHECK(error.field == CC::AuthUrl);
        CHECK(error.error == CloudValueError::NotHttps);
    }
    SECTION("a missing key is reported") {
        CC::CloudValues bad = custom_values();
        bad[CC::PubKey]     = "   ";
        const CC::CloudValidation error = CC::normalize_cloud_values(bad);
        CHECK(error.field == CC::PubKey);
        CHECK(error.error == CloudValueError::Empty);
    }
    SECTION("an explicit http:// on loopback is kept") {
        CC::CloudValues local = {" http://localhost:8000/ ", "HTTP://127.0.0.1:8000", "http://[::1]:8000/web/", "k"};
        CHECK(CC::normalize_cloud_values(local).ok());
        CHECK(local[CC::ApiUrl] == "http://localhost:8000");
        CHECK(local[CC::AuthUrl] == "http://127.0.0.1:8000");
        CHECK(local[CC::CloudUrl] == "http://[::1]:8000/web");
    }
    SECTION("an explicit http:// elsewhere is refused, not rewritten") {
        CC::CloudValues bad = custom_values();
        bad[CC::ApiUrl]     = "http://api.example.org";
        const CC::CloudValidation error = CC::normalize_cloud_values(bad);
        CHECK(bad[CC::ApiUrl] == "http://api.example.org");
        CHECK(error.field == CC::ApiUrl);
        CHECK(error.error == CloudValueError::NotHttps);
    }
    SECTION("a missing scheme is http on loopback, https elsewhere") {
        CC::CloudValues bare = {"localhost:8000", "127.0.0.1:8000/", "api.example.org", "k"};
        CHECK(CC::normalize_cloud_values(bare).ok());
        CHECK(bare[CC::ApiUrl] == "http://localhost:8000");
        CHECK(bare[CC::AuthUrl] == "http://127.0.0.1:8000");
        CHECK(bare[CC::CloudUrl] == "https://api.example.org");
        CC::CloudValues v6 = {"[::1]:8000", "192.168.1.10:8000", "localhost.example.org", "k"};
        CHECK(CC::normalize_cloud_values(v6).ok());
        CHECK(v6[CC::ApiUrl] == "http://[::1]:8000");
        CHECK(v6[CC::AuthUrl] == "https://192.168.1.10:8000");
        CHECK(v6[CC::CloudUrl] == "https://localhost.example.org");
    }
    SECTION("an unknown scheme is not prefixed") {
        CC::CloudValues bad = custom_values();
        bad[CC::CloudUrl]   = "ftp://web.example.org";
        const CC::CloudValidation error = CC::normalize_cloud_values(bad);
        CHECK(bad[CC::CloudUrl] == "ftp://web.example.org");
        CHECK(error.field == CC::CloudUrl);
        CHECK(error.error == CloudValueError::NotHttps);
    }
    SECTION("https:// alone stays as it is and has no host") {
        CC::CloudValues bad = custom_values();
        bad[CC::ApiUrl]     = "https:///";
        const CC::CloudValidation error = CC::normalize_cloud_values(bad);
        CHECK(bad[CC::ApiUrl] == "https://");
        CHECK(error.error == CloudValueError::NoHost);
    }
}
