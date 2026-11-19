// Checks of the forced stealth mode (decision 0070) and of the setup guide
// policy that keeps the guide away from the stealth mode and network plugin
// pages (decision 0073).

#include <catch2/catch_test_macros.hpp>

#include <string>

#include <nlohmann/json.hpp>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/Cosmyx/logic/GuidePolicy.hpp"

using namespace Slic3r;

TEST_CASE("Stealth mode is on before the setup guide is finished", "[cosmyx]")
{
    AppConfig config;
    config.set("firstguide", "finish", "0");
    config.set_bool("stealth_mode", false);
    CHECK(config.get_stealth_mode());
}

TEST_CASE("Stealth mode stays on after the setup guide is finished", "[cosmyx]")
{
    AppConfig config;
    config.set("firstguide", "finish", "1");

    SECTION("stored as off") {
        config.set_bool("stealth_mode", false);
        CHECK(config.get_stealth_mode());
    }
    SECTION("stored as on") {
        config.set_bool("stealth_mode", true);
        CHECK(config.get_stealth_mode());
    }
    SECTION("never stored") {
        config.erase("app", "stealth_mode");
        CHECK(config.get_stealth_mode());
    }
}

TEST_CASE("The guide policy forces stealth mode and skips the network plugin page", "[cosmyx]")
{
    // The profile as GuideFrame::SaveProfileData() builds it on a fresh install
    // without the network plugin.
    nlohmann::json profile = nlohmann::json::object();
    profile["region"]                     = "Europe";
    profile["network_plugin_install"]     = "";
    profile["network_plugin_compability"] = "0";
    profile["stealth_mode"]               = false;
    bool stealth                          = false;

    GUI::Cosmyx::apply_guide_policy(profile, stealth);

    CHECK(stealth);
    REQUIRE(profile["stealth_mode"].is_boolean());
    CHECK(profile["stealth_mode"].get<bool>());
    // resources/web/guide/22/22.js compares these with the strings '1' and '0'.
    REQUIRE(profile["network_plugin_install"].is_string());
    CHECK(profile["network_plugin_install"].get<std::string>() == "1");
    REQUIRE(profile["network_plugin_compability"].is_string());
    CHECK(profile["network_plugin_compability"].get<std::string>() == "1");
    // Nothing else is touched.
    CHECK(profile["region"].get<std::string>() == "Europe");
    CHECK(profile.size() == 4);
}

TEST_CASE("The guide policy keeps an already stealth profile unchanged", "[cosmyx]")
{
    nlohmann::json profile = nlohmann::json::object();
    bool stealth           = true;

    GUI::Cosmyx::apply_guide_policy(profile, stealth);
    const nlohmann::json once = profile;
    GUI::Cosmyx::apply_guide_policy(profile, stealth);

    CHECK(stealth);
    CHECK(profile == once);
}
