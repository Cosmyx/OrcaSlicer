// Checks of the plugin package check outside the app and of the entry package
// name rule where a wheel's metadata is read (decision 0204, "Without the app"
// and "Entry package guard"). The upstream plugin tests drive the plugin
// manager with no app and install unsigned packages over plain http, and read
// resource-only wheels: both must behave as upstream. Once the app was seen,
// the check stays on for the rest of the process, so a download that ends
// after the app closed is never let through.
//
// The hooks (PluginVerify.cpp) only read the app and the platform and call
// decide_download() and commit_cloud_install(); these drive both end to end.

#include <catch2/catch_test_macros.hpp>

#include <ios>
#include <string>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>
#include <boost/nowide/fstream.hpp>
#include <miniz.h>
#include <nlohmann/json.hpp>

#include "libslic3r/AppConfig.hpp"
#include "slic3r/GUI/Cosmyx/logic/CloudServer.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginSigning.hpp"
#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp"
#include "test_utils.hpp"

using namespace Slic3r;
namespace CC = Slic3r::GUI::Cosmyx;
namespace fs = boost::filesystem;
using nlohmann::json;

namespace {

constexpr const char* CUSTOM = "https://plugins.example.org";

// k1 of the CosmoCloud vectors, which signs the row below.
constexpr const char* K1_PUBLIC = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8";

// The process-wide latch starts and ends each test cleared, whatever the order.
struct GateReset
{
    GateReset() { CC::reset_package_gate_for_tests(); }
    ~GateReset() { CC::reset_package_gate_for_tests(); }
};

// The vector row "script for any target" (version 1.0.0, signed by k1), as
// the download hook gets it on linux x86_64.
struct Download
{
    json             row;
    CC::DownloadInput input;
};

Download script_download()
{
    const fs::path          path = fs::path(TEST_DATA_DIR) / ".." / "cosmyx" / "data" / "plugin-signatures.json";
    boost::nowide::ifstream file(path.string(), std::ios::binary);
    REQUIRE(file);
    const json vectors = json::parse(file);
    for (const json& vector : vectors.at("rows")) {
        if (vector.at("name") != "script for any target")
            continue;
        Download download;
        download.row = vector.at("row");
        REQUIRE(CC::from_lower_hex(vector.at("body_hex").get<std::string>(), download.input.body));
        download.input.plugin_id         = download.row.at("plugin_id").get<std::string>();
        download.input.requested_version = "1.0.0";
        download.input.platform_os       = "linux";
        download.input.platform_arch     = "x86_64";
        return download;
    }
    FAIL("vector row not found");
    return {};
}

// A config whose active server is CUSTOM, with k1 pinned for it.
AppConfig pinned_config()
{
    AppConfig config;
    CC::use_custom_cloud(config, {CUSTOM, CUSTOM, CUSTOM, "user-key"});
    CC::apply_cloud_server(config);
    REQUIRE(CC::set_server_pins(config, CUSTOM, {K1_PUBLIC, false}));
    return config;
}

void write_file(const fs::path& path, const std::string& data)
{
    boost::nowide::ofstream file(path.string(), std::ios::binary | std::ios::trunc);
    file.write(data.data(), static_cast<std::streamsize>(data.size()));
    REQUIRE(file);
}

bool metadata_ok(std::string&) { return true; }

} // namespace

TEST_CASE("The package check latches on once the app was seen", "[cosmyx]")
{
    GateReset reset;
    CHECK(CC::package_gate(false) == CC::PackageGate::Unchecked);
    CHECK(CC::package_gate(false) == CC::PackageGate::Unchecked);

    CHECK(CC::package_gate(true) == CC::PackageGate::Checked);
    // The app gone afterwards never turns the check off again.
    CHECK(CC::package_gate(false) == CC::PackageGate::AppGone);
    CHECK(CC::package_gate(true) == CC::PackageGate::Checked);
    CHECK(CC::package_gate(false) == CC::PackageGate::AppGone);

    // The app seen at its creation (the wxModule), before any hook ran.
    CC::reset_package_gate_for_tests();
    CC::note_app_seen();
    CHECK(CC::package_gate(false) == CC::PackageGate::AppGone);
}

TEST_CASE("Never seen the app, a download and its commit behave as upstream", "[cosmyx]")
{
    GateReset reset;
    // Even a config that pins a key does not apply: no app means no settings.
    const AppConfig config   = pinned_config();
    Download        download = script_download();
    download.input.row       = nullptr; // the row did not reach the hook: still let through
    download.input.body      = "not the signed body";

    const CC::DownloadDecision decision = CC::decide_download(false, &config, download.input);
    CHECK(decision.gate == CC::PackageGate::Unchecked);
    CHECK(decision.install());

    ScopedTemporaryDir dir("cosmyx-no-app");
    const fs::path     package = dir.path() / "plugin.py";
    write_file(package, download.input.body);
    std::string error;
    CHECK(CC::commit_cloud_install(false, download.input.plugin_id, dir.path(), package, metadata_ok, error));
    CHECK(error.empty());
    CHECK(fs::exists(package));
    CHECK_FALSE(fs::exists(dir.path() / CC::PACKAGE_RECORD_FILE));

    // Nothing was latched by any of it.
    CHECK(CC::package_gate(false) == CC::PackageGate::Unchecked);
}

TEST_CASE("A download that ends after the app closed is refused", "[cosmyx]")
{
    GateReset       reset;
    const AppConfig config = pinned_config();
    CHECK(CC::package_gate(true) == CC::PackageGate::Checked); // the app ran when the install started

    Download download  = script_download();
    download.input.row = &download.row;
    // A valid signed package, which the app would have accepted, is refused:
    // the settings it is checked against can no longer be read.
    const CC::DownloadDecision decision = CC::decide_download(false, nullptr, download.input);
    CHECK(decision.gate == CC::PackageGate::AppGone);
    CHECK_FALSE(decision.install());
    CHECK(decision.verdict.reason == CC::SIGN_APP_GONE);

    // Nothing was remembered for it, so its commit is refused as well.
    ScopedTemporaryDir dir("cosmyx-app-gone");
    const fs::path     package = dir.path() / "plugin.py";
    write_file(package, download.input.body);
    std::string error;
    CHECK_FALSE(CC::commit_cloud_install(false, download.input.plugin_id, dir.path(), package, metadata_ok, error));
    CHECK_FALSE(error.empty());
    CHECK_FALSE(fs::exists(package));
    CHECK_FALSE(fs::exists(dir.path() / CC::PACKAGE_RECORD_FILE));
    CC::forget_checked_packages(download.input.plugin_id);
}

TEST_CASE("A download checked with the app is committed after it closed only for the checked bytes", "[cosmyx]")
{
    GateReset       reset;
    const AppConfig config   = pinned_config();
    Download        download = script_download();
    download.input.row       = &download.row;

    const CC::DownloadDecision decision = CC::decide_download(true, &config, download.input);
    REQUIRE(decision.gate == CC::PackageGate::Checked);
    REQUIRE(decision.install());
    CHECK(decision.verdict.verified());
    CHECK(decision.check.server == CUSTOM);

    // The checked bytes, committed once the app is gone: recorded.
    {
        ScopedTemporaryDir dir("cosmyx-commit-gone");
        const fs::path     package = dir.path() / "plugin.py";
        write_file(package, download.input.body);
        std::string error;
        CHECK(CC::commit_cloud_install(false, download.input.plugin_id, dir.path(), package, metadata_ok, error));
        CC::PackageRecord record;
        REQUIRE(CC::read_package_record(dir.path(), record));
        CHECK(record.sha256 == decision.verdict.record.sha256);
        CHECK(record.version == "1.0.0");
        CHECK(fs::exists(package));
    }

    // Checked again, then other bytes installed: refused and removed, app gone or not.
    REQUIRE(CC::decide_download(true, &config, download.input).install());
    for (const bool running : {false, true}) {
        INFO(running);
        ScopedTemporaryDir dir("cosmyx-commit-swapped");
        const fs::path     package = dir.path() / "plugin.py";
        write_file(package, download.input.body + "# swapped\n");
        std::string error;
        CHECK_FALSE(CC::commit_cloud_install(running, download.input.plugin_id, dir.path(), package, metadata_ok, error));
        CHECK_FALSE(error.empty());
        CHECK_FALSE(fs::exists(package));
        CHECK_FALSE(fs::exists(dir.path() / CC::PACKAGE_RECORD_FILE));
    }

    // Metadata that differs from what the installer read refuses it too.
    {
        ScopedTemporaryDir dir("cosmyx-commit-metadata");
        const fs::path     package = dir.path() / "plugin.py";
        write_file(package, download.input.body);
        std::string error;
        const auto  other_metadata = [](std::string& why) {
            why = "differs";
            return false;
        };
        CHECK_FALSE(CC::commit_cloud_install(false, download.input.plugin_id, dir.path(), package, other_metadata, error));
        CHECK(error == "differs");
        CHECK_FALSE(fs::exists(package));
    }
    CC::forget_checked_packages(download.input.plugin_id);
}

TEST_CASE("With the app, a download is checked against its settings", "[cosmyx]")
{
    GateReset       reset;
    const AppConfig config   = pinned_config();
    Download        download = script_download();
    download.input.row       = &download.row;

    // A strict version or the latest only.
    CC::DownloadInput input = download.input;
    input.requested_version = "1.0";
    CHECK(CC::decide_download(true, &config, input).verdict.reason == CC::SIGN_WRONG_VERSION);

    // A platform the protocol cannot name.
    input                = download.input;
    input.platform_os    = "haiku";
    CHECK(CC::decide_download(true, &config, input).verdict.reason == CC::SIGN_UNKNOWN_SLOT);

    // No row reached the hook.
    input     = download.input;
    input.row = nullptr;
    CHECK(CC::decide_download(true, &config, input).verdict.reason == CC::SIGN_NO_ROW);

    // Older than the installed version.
    input                   = download.input;
    input.installed_version = "2.0.0";
    CHECK(CC::decide_download(true, &config, input).verdict.reason == CC::SIGN_DOWNGRADE);

    // The bytes are not the signed ones.
    input      = download.input;
    input.body = download.input.body + "x";
    CHECK_FALSE(CC::decide_download(true, &config, input).install());

    // The signing key revoked.
    input = download.input;
    input.revoked.insert(CC::public_key_id(K1_PUBLIC));
    CHECK_FALSE(CC::decide_download(true, &config, input).install());

    // No config loaded yet: the Cosmyx server with the build's keys, which do
    // not hold k1, so the custom server's package is refused.
    const CC::DownloadDecision no_config = CC::decide_download(true, nullptr, download.input);
    CHECK(no_config.check.server == CC::CLOUD_SERVER_URL);
    CHECK(no_config.check.trust.cosmyx_server);
    CHECK_FALSE(no_config.install());

    // A refused download leaves nothing to commit.
    ScopedTemporaryDir dir("cosmyx-refused");
    const fs::path     package = dir.path() / "plugin.py";
    write_file(package, download.input.body);
    std::string error;
    CHECK_FALSE(CC::commit_cloud_install(true, download.input.plugin_id, dir.path(), package, metadata_ok, error));
    CHECK_FALSE(fs::exists(package));
}

TEST_CASE("In the app with no config yet, only the build's keys for the Cosmyx server apply", "[cosmyx]")
{
    const CC::DownloadCheck check = CC::download_check(nullptr);
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

    const CC::DownloadCheck check = CC::download_check(&config);
    CHECK(check.server == CUSTOM);
    CHECK_FALSE(check.trust.cosmyx_server);
    CHECK(check.trust.allow_unverified);
    CHECK(check.trust.keys.empty());

    // Plain http to a remote host is still unrecognised in the app.
    CC::use_custom_cloud(config, {"http://plugins.example.org", CUSTOM, CUSTOM, "user-key"});
    CC::apply_cloud_server(config);
    CHECK(CC::download_check(&config).trust.unrecognised);
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
