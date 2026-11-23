// Checks of the plugin package check outside the app and of the entry package
// name rule where a wheel's metadata is read (decision 0204, "Without the app"
// and "Entry package guard"). The upstream plugin tests drive the plugin
// manager with no app and install unsigned packages over plain http, and read
// resource-only wheels: both must behave as upstream.

#include <catch2/catch_test_macros.hpp>

#include <ios>
#include <string>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>
#include <boost/nowide/fstream.hpp>
#include <miniz.h>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginSigning.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp"
#include "test_utils.hpp"

using namespace Slic3r;
namespace CC = Slic3r::GUI::Cosmyx;
namespace fs = boost::filesystem;

namespace {

constexpr const char* CUSTOM = "https://plugins.example.org";

} // namespace

TEST_CASE("Without the app the plugin package check is off", "[cosmyx]")
{
    CHECK_FALSE(CC::package_check_on(false));
    CHECK(CC::package_check_on(true));

    // Whatever the config says, no app means no check: there are no trust
    // settings the user could have set.
    CHECK_FALSE(CC::download_check(false, nullptr).on);
    AppConfig config;
    CC::set_server_pins(config, CUSTOM, {"", false});
    CHECK_FALSE(CC::download_check(false, &config).on);
}

TEST_CASE("In the app with no config yet, only the build's keys for the Cosmyx server apply", "[cosmyx]")
{
    const CC::DownloadCheck check = CC::download_check(true, nullptr);
    CHECK(check.on);
    CHECK(check.server == CC::CLOUD_SERVER_URL);
    CHECK(check.trust.cosmyx_server);
    CHECK_FALSE(check.trust.allow_unverified);
    CHECK_FALSE(check.trust.unrecognised);
    CHECK(check.trust.keys == CC::built_in_keys());
}

TEST_CASE("In the app the API address and the user's pins apply", "[cosmyx]")
{
    AppConfig config;
    CC::use_custom_cloud(config, {CUSTOM, CUSTOM, CUSTOM, "user-key"});
    CC::apply_cloud_server(config);
    REQUIRE(CC::set_server_pins(config, CUSTOM, {"", true}));

    const CC::DownloadCheck check = CC::download_check(true, &config);
    CHECK(check.on);
    CHECK(check.server == CUSTOM);
    CHECK_FALSE(check.trust.cosmyx_server);
    CHECK(check.trust.allow_unverified);
    CHECK(check.trust.keys.empty());

    // Plain http to a remote host is still unrecognised in the app.
    CC::use_custom_cloud(config, {"http://plugins.example.org", CUSTOM, CUSTOM, "user-key"});
    CC::apply_cloud_server(config);
    const CC::DownloadCheck http = CC::download_check(true, &config);
    CHECK(http.on);
    CHECK(http.trust.unrecognised);
}

TEST_CASE("With the check on, an install whose download was never checked is refused", "[cosmyx]")
{
    ScopedTemporaryDir dir("cosmyx-no-check");
    const fs::path     package = dir.path() / "plugin.py";
    {
        boost::nowide::ofstream file(package.string(), std::ios::binary);
        file << "x = 1\n";
    }
    std::string error;
    CHECK_FALSE(CC::commit_package_record("never-checked", dir.path(), package, error));
    CHECK_FALSE(error.empty());
    CHECK_FALSE(fs::exists(package));
}

TEST_CASE("A resource-only wheel's entry package name is accepted where it is read", "[cosmyx]")
{
    // The shape of upstream's resource-texture wheel: dist-info only, no
    // Python package, entry package from its top_level.txt.
    ScopedTemporaryDir dir("cosmyx-resource-wheel");
    const fs::path     wheel = dir.path() / "texture_pack-1.0-py3-none-any.whl";
    {
        mz_zip_archive archive;
        mz_zip_zero_struct(&archive);
        REQUIRE(mz_zip_writer_init_file(&archive, wheel.string().c_str(), 0));
        const std::string text = "texture_pack\n";
        for (const char* name : {"texture_pack-1.0.dist-info/METADATA", "texture_pack-1.0.dist-info/WHEEL",
                                 "texture_pack-1.0.dist-info/RECORD", "texture_pack-1.0.dist-info/top_level.txt"})
            REQUIRE(mz_zip_writer_add_mem(&archive, name, text.data(), text.size(), MZ_DEFAULT_COMPRESSION));
        REQUIRE(mz_zip_writer_finalize_archive(&archive));
        REQUIRE(mz_zip_writer_end(&archive));
    }

    std::string error;
    CHECK(CC::check_entry_package_name("texture_pack", error));
    CHECK(error.empty());

    // The name rule that closes the path escape still applies there.
    for (const char* name : {"../../escape", "a/b", "a\\b", "__init__", "CON", "lpt1", "hello.sub", "1abc", ""}) {
        INFO(name);
        error.clear();
        CHECK_FALSE(CC::check_entry_package_name(name, error));
        CHECK_FALSE(error.empty());
    }

    // Right before an import, the wheel must hold the package it imports.
    error.clear();
    CHECK_FALSE(CC::check_entry_package(wheel.string(), "texture_pack", error));
    CHECK_FALSE(error.empty());
}
