// Checks of the Cosmyx data folder helpers (libslic3r/Cosmyx/DataDir.hpp) and of
// the Linux data folder they build through xdg_config_dir() and default_data_dir().

#include <catch2/catch_test_macros.hpp>

#include <cstdlib>
#include <initializer_list>
#include <optional>
#include <string>

#include <filesystem>

#include "libslic3r/Utils.hpp"
#include "libslic3r_version.h"
#include "libslic3r/Cosmyx/DataDir.hpp"

using namespace Slic3r;
namespace fs = std::filesystem;

namespace {

std::string join(std::initializer_list<const char *> parts)
{
    fs::path out;
    for (const char *part : parts)
        out /= part;
    return out.string();
}

#ifndef _WIN32
// Sets an environment variable for the lifetime of the object, then puts the old value back.
class ScopedEnv
{
public:
    ScopedEnv(const char *name, const char *value) : m_name(name)
    {
        if (const char *old = ::getenv(name))
            m_old = old;
        ::setenv(name, value, 1);
    }
    ~ScopedEnv()
    {
        if (m_old)
            ::setenv(m_name, m_old->c_str(), 1);
        else
            ::unsetenv(m_name);
    }

private:
    const char                *m_name;
    std::optional<std::string> m_old;
};
#endif

} // namespace

TEST_CASE("The data folder vendor is Cosmyx and the folder keeps the upstream name", "[cosmyx][CosmyxPaths]")
{
    CHECK(std::string(Cosmyx::DATA_DIR_VENDOR) == "Cosmyx");
    CHECK(std::string(SLIC3R_APP_KEY) == "OrcaSlicer");
    CHECK(Cosmyx::vendor_app_subdir(SLIC3R_APP_KEY) == join({"Cosmyx", "OrcaSlicer"}));
}

TEST_CASE("without_vendor_dir takes the vendor folder out of a nested data folder", "[cosmyx][CosmyxPaths]")
{
    SECTION("nested folder")
    {
        CHECK(Cosmyx::without_vendor_dir(join({"base", "config", "Cosmyx", "OrcaSlicer"})) ==
              join({"base", "config", "OrcaSlicer"}));
    }
    SECTION("relative folder with the vendor at its root")
    {
        CHECK(Cosmyx::without_vendor_dir(join({"Cosmyx", "OrcaSlicer"})) == "OrcaSlicer");
    }
    SECTION("trailing separator")
    {
        const std::string nested = join({"base", "Cosmyx", "OrcaSlicer"}) + std::string(1, fs::path::preferred_separator);
        CHECK(Cosmyx::without_vendor_dir(nested) == join({"base", "OrcaSlicer"}));
    }
    SECTION("folder not under the vendor comes back unchanged")
    {
        const std::string plain = join({"base", "config", "OrcaSlicer"});
        CHECK(Cosmyx::without_vendor_dir(plain) == plain);
    }
    SECTION("vendor as the leaf is not taken out")
    {
        const std::string leaf = join({"base", "Cosmyx"});
        CHECK(Cosmyx::without_vendor_dir(leaf) == leaf);
    }
    SECTION("a vendor folder higher up is not taken out")
    {
        const std::string deep = join({"Cosmyx", "base", "OrcaSlicer"});
        CHECK(Cosmyx::without_vendor_dir(deep) == deep);
    }
    SECTION("similar names are not the vendor folder")
    {
        const std::string lower = join({"base", "cosmyx", "OrcaSlicer"});
        CHECK(Cosmyx::without_vendor_dir(lower) == lower);
        const std::string longer = join({"base", "CosmyxTools", "OrcaSlicer"});
        CHECK(Cosmyx::without_vendor_dir(longer) == longer);
    }
    SECTION("empty and single component paths")
    {
        CHECK(Cosmyx::without_vendor_dir("").empty());
        CHECK(Cosmyx::without_vendor_dir("OrcaSlicer") == "OrcaSlicer");
    }
}

#ifndef _WIN32
TEST_CASE("The Flatpak legacy data folder ignores the Cosmyx vendor folder", "[cosmyx][CosmyxPaths]")
{
    // migrate_flatpak_legacy_datadir() in GUI_App.cpp: the sandbox config root of the
    // current app id, nested under Cosmyx/, maps to the legacy app id's un-nested folder.
    const std::string data_dir = "/home/user/.var/app/com.orcaslicer.OrcaSlicer/config/Cosmyx/OrcaSlicer";
    std::string       legacy   = Cosmyx::without_vendor_dir(data_dir);
    const std::string current_id = "com.orcaslicer.OrcaSlicer";
    legacy.replace(legacy.find(current_id), current_id.size(), "io.github.softfever.OrcaSlicer");
    CHECK(legacy == "/home/user/.var/app/io.github.softfever.OrcaSlicer/config/OrcaSlicer");
}

TEST_CASE("The XDG data folder is nested under Cosmyx", "[cosmyx][CosmyxPaths]")
{
    SECTION("XDG_CONFIG_HOME set")
    {
        ScopedEnv xdg("XDG_CONFIG_HOME", "/tmp/cosmyx-xdg");
        CHECK(xdg_config_dir(Cosmyx::vendor_app_subdir(SLIC3R_APP_KEY)) == "/tmp/cosmyx-xdg/Cosmyx/OrcaSlicer");
    }
    SECTION("XDG_CONFIG_HOME empty falls back to HOME/.config")
    {
        ScopedEnv xdg("XDG_CONFIG_HOME", "");
        ScopedEnv home("HOME", "/home/cosmyx-user");
        CHECK(xdg_config_dir(Cosmyx::vendor_app_subdir(SLIC3R_APP_KEY)) == "/home/cosmyx-user/.config/Cosmyx/OrcaSlicer");
    }
}
#endif

#ifdef __linux__
TEST_CASE("default_data_dir() on Linux is the nested XDG folder", "[cosmyx][CosmyxPaths]")
{
    // The test binary has no portable data_dir folder next to it.
    ScopedEnv xdg("XDG_CONFIG_HOME", "/tmp/cosmyx-xdg");
    CHECK(default_data_dir() == "/tmp/cosmyx-xdg/Cosmyx/OrcaSlicer");
}
#endif
