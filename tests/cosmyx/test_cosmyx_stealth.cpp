// Checks of the stealth mode policy, on until the user opts out (decision
// 0200, amending 0070), and of the setup guide policy that keeps the guide
// away from the stealth mode and network plugin pages (decision 0073).

#include <catch2/catch_test_macros.hpp>

#include <string>

#include <nlohmann/json.hpp>

#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Cosmyx/StealthMode.hpp"
#include "slic3r/GUI/Cosmyx/logic/GuidePolicy.hpp"

using namespace Slic3r;

TEST_CASE("Stealth mode defaults to on", "[cosmyx]")
{
    CHECK(Cosmyx::STEALTH_MODE_DEFAULT);
}

TEST_CASE("Stealth mode is on before the setup guide is finished", "[cosmyx]")
{
    AppConfig config;
    config.set("firstguide", "finish", "0");
    config.set_bool("stealth_mode", false);

    SECTION("never seeded") {
        CHECK(config.get_stealth_mode());
    }
    SECTION("seeded, then turned off") {
        Cosmyx::seed_stealth_mode(config);
        config.set_bool("stealth_mode", false);
        CHECK(config.get_stealth_mode());
    }
}

TEST_CASE("Stealth mode takes the Cosmyx default until it is seeded", "[cosmyx]")
{
    AppConfig config;
    config.set("firstguide", "finish", "1");
    REQUIRE_FALSE(config.has(Cosmyx::STEALTH_SEEDED_KEY));

    // AppConfig::set_defaults() stores false; it is not a user choice.
    SECTION("stored as off by the upstream defaults") {
        config.set_bool("stealth_mode", false);
        CHECK(config.get_stealth_mode() == Cosmyx::STEALTH_MODE_DEFAULT);
    }
    SECTION("never stored") {
        config.erase("app", "stealth_mode");
        CHECK(config.get_stealth_mode() == Cosmyx::STEALTH_MODE_DEFAULT);
    }
}

TEST_CASE("Seeding writes the default once and then follows the user", "[cosmyx]")
{
    AppConfig config;
    config.set("firstguide", "finish", "1");
    config.set_bool("stealth_mode", false);

    CHECK(Cosmyx::seed_stealth_mode(config));
    CHECK(config.has(Cosmyx::STEALTH_SEEDED_KEY));
    CHECK(config.get_bool("stealth_mode") == Cosmyx::STEALTH_MODE_DEFAULT);
    CHECK(config.get_stealth_mode() == Cosmyx::STEALTH_MODE_DEFAULT);

    // The user opts out from Preferences or the login dialog.
    config.set_bool("stealth_mode", false);
    CHECK_FALSE(config.get_stealth_mode());

    // A later start seeds nothing, so the choice survives.
    CHECK_FALSE(Cosmyx::seed_stealth_mode(config));
    CHECK_FALSE(config.get_bool("stealth_mode"));
    CHECK_FALSE(config.get_stealth_mode());

    // And the user can turn it back on.
    config.set_bool("stealth_mode", true);
    CHECK(config.get_stealth_mode());
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
