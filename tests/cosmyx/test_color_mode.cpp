// Checks of the always-on Cosmyx dark mode, config side (decisions 0136, 0137):
// "dark_color_mode" is "1" on a fresh config and is forced back to "1" whatever
// a saved config or an upstream write left in it.

#include <catch2/catch_test_macros.hpp>

#include <string>

#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Cosmyx/ColorModeDefault.hpp"
#include "libslic3r/Thread.hpp"
#include "libslic3r/Utils.hpp"
#include "test_utils.hpp"

using namespace Slic3r;

namespace {

// Points data_dir() at a throwaway folder for one test, then restores it.
struct ScopedDataDir
{
    ScopedTemporaryDir tmp{"cosmyx-color-mode"};
    std::string        previous{data_dir()};

    ScopedDataDir() { set_data_dir(tmp.path().string()); }
    ~ScopedDataDir() { set_data_dir(previous); }
};

} // namespace

TEST_CASE("A fresh app config is dark on every OS", "[cosmyx][ColorMode]")
{
    AppConfig config;
    CHECK(config.get("dark_color_mode") == "1");
}

TEST_CASE("The pinned value is the dark one", "[cosmyx][ColorMode]")
{
    CHECK(std::string(Cosmyx::forced_dark_color_mode) == "1");
}

TEST_CASE("Any other dark_color_mode value is forced back to dark", "[cosmyx][ColorMode]")
{
    AppConfig config;
    for (const char* value : {"0", "", "true", "light"}) {
        config.set("dark_color_mode", std::string(value));
        CHECK(Cosmyx::force_dark_color_mode(config));
        CHECK(config.get("dark_color_mode") == "1");
    }
}

TEST_CASE("Forcing an already dark config changes nothing", "[cosmyx][ColorMode]")
{
    AppConfig config;
    REQUIRE(config.get("dark_color_mode") == "1");
    CHECK_FALSE(Cosmyx::force_dark_color_mode(config));
    CHECK(config.get("dark_color_mode") == "1");
}

TEST_CASE("Setting the defaults turns a light config dark", "[cosmyx][ColorMode]")
{
    // set_defaults() runs after every load, so this is what an existing config
    // that holds "0" goes through at startup.
    AppConfig config;
    config.set("dark_color_mode", std::string("0"));
    config.set_defaults();
    CHECK(config.get("dark_color_mode") == "1");
}

TEST_CASE("A saved light config loads dark", "[cosmyx][ColorMode]")
{
    ScopedDataDir data_dir_guard;
    save_main_thread_id();

    {
        AppConfig config;
        config.set("dark_color_mode", std::string("0"));
        config.save();
    }

    AppConfig reloaded;
    REQUIRE(reloaded.load().empty());
    CHECK(reloaded.get("dark_color_mode") == "1");
}
