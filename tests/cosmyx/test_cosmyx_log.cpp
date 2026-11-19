// Checks of the Cosmyx log channel: COSMYX_LOG records go to the Cosmyx file
// only, upstream BOOST_LOG_TRIVIAL records never do, the file rotates, and the
// sink is never registered while Orca has no log file of its own.

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>
#include <boost/log/trivial.hpp>
#include <boost/system/error_code.hpp>

#include "libslic3r/Cosmyx/CosmyxLog.hpp"

using namespace Slic3r;
namespace fs = boost::filesystem;

namespace {

// Fresh, empty folder under the system temp folder, removed on destruction.
struct TempFolder
{
    fs::path path;
    TempFolder() : path(fs::temp_directory_path() / fs::unique_path("cosmyx_log_%%%%-%%%%-%%%%")) { fs::create_directories(path); }
    ~TempFolder()
    {
        boost::system::error_code ec;
        fs::remove_all(path, ec);
    }
};

// Every file of `folder` whose name starts with `prefix`, sorted by name.
std::vector<fs::path> files_with_prefix(const fs::path& folder, const std::string& prefix)
{
    std::vector<fs::path> out;
    for (const fs::directory_entry& entry : fs::directory_iterator(folder))
        if (entry.path().filename().string().compare(0, prefix.size(), prefix) == 0)
            out.push_back(entry.path());
    std::sort(out.begin(), out.end());
    return out;
}

std::string read_all(const fs::path& file)
{
    std::ifstream in(file.string(), std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

std::string read_all(const std::vector<fs::path>& files)
{
    std::string out;
    for (const fs::path& file : files)
        out += read_all(file);
    return out;
}

} // namespace

TEST_CASE("Cosmyx log sink is not registered while Orca has no log file", "[cosmyx][CosmyxLog]")
{
    // The test binary never calls set_log_path_and_level(), as the CLI does not:
    // registering a sink there would turn off Boost.Log's default console sink.
    COSMYX_LOG(warning) << "Cosmyx record without an Orca log file";
    CHECK_FALSE(Cosmyx::log_active());
    CHECK(Cosmyx::log_file_path().empty());
}

TEST_CASE("Cosmyx records land in the Cosmyx file, upstream records do not", "[cosmyx][CosmyxLog]")
{
    TempFolder folder;
    REQUIRE(Cosmyx::init_log(folder.path, "cosmyx_test.log"));
    REQUIRE(Cosmyx::log_active());

    COSMYX_LOG(warning) << "cosmyx-marker-1";
    BOOST_LOG_TRIVIAL(warning) << "upstream-marker-1";
    COSMYX_LOG(error) << "cosmyx-marker-2";
    Cosmyx::flush_log();

    const fs::path current = Cosmyx::log_file_path();
    CHECK(current.parent_path() == folder.path);
    CHECK(current.filename().string() == "cosmyx_test.log.0");

    // Close the file before reading it, as Windows may hold it.
    Cosmyx::shutdown_log();
    CHECK_FALSE(Cosmyx::log_active());

    const std::vector<fs::path> files = files_with_prefix(folder.path, "cosmyx_test.log");
    REQUIRE(files.size() == 1);
    const std::string text = read_all(files);
    CHECK(text.find("cosmyx-marker-1") != std::string::npos);
    CHECK(text.find("cosmyx-marker-2") != std::string::npos);
    CHECK(text.find("upstream-marker-1") == std::string::npos);
    // Same line layout as Orca's debug log: severity first.
    CHECK(text.compare(0, 9, "[warning]") == 0);
    CHECK(text.find("[error]") != std::string::npos);

    // After shutdown, Cosmyx records are no longer written there.
    COSMYX_LOG(warning) << "cosmyx-marker-after-shutdown";
    CHECK(read_all(files_with_prefix(folder.path, "cosmyx_test.log")).find("cosmyx-marker-after-shutdown") ==
          std::string::npos);
}

TEST_CASE("Cosmyx log file rotates at its size limit", "[cosmyx][CosmyxLog]")
{
    TempFolder folder;
    REQUIRE(Cosmyx::init_log(folder.path, "cosmyx_rotate.log", 1024));

    const std::string payload(200, 'x');
    for (int i = 0; i < 40; ++i)
        COSMYX_LOG(warning) << "line-" << i << " " << payload;
    Cosmyx::shutdown_log();

    const std::vector<fs::path> files = files_with_prefix(folder.path, "cosmyx_rotate.log");
    CHECK(files.size() >= 2);
    for (const fs::path& file : files)
        CHECK(fs::file_size(file) <= 1024 + 512); // One record may overflow before rotating.
    const std::string text = read_all(files);
    CHECK(text.find("line-0 ") != std::string::npos);
    CHECK(text.find("line-39 ") != std::string::npos);
}

TEST_CASE("Cosmyx log init fails cleanly on an unusable folder", "[cosmyx][CosmyxLog]")
{
    TempFolder folder;
    // A regular file where the folder should be.
    const fs::path blocker = folder.path / "not_a_folder";
    std::ofstream(blocker.string()) << "x";
    CHECK_FALSE(Cosmyx::init_log(blocker, "cosmyx_fail.log"));
    CHECK_FALSE(Cosmyx::log_active());
}

TEST_CASE("Cosmyx log file name is paired with Orca's", "[cosmyx][CosmyxLog]")
{
    const fs::path folder = fs::path("data") / "log";
    CHECK(Cosmyx::paired_log_file_name(folder / "debug_Thu_Nov_19_10_00_00_123.log.0") ==
          "cosmyx_Thu_Nov_19_10_00_00_123.log");
    CHECK(Cosmyx::paired_log_file_name(folder / "debug_Thu_Nov_19_10_00_00_123.log.12") ==
          "cosmyx_Thu_Nov_19_10_00_00_123.log");
    CHECK(Cosmyx::paired_log_file_name("debug_a.log") == "cosmyx_a.log");
    CHECK(Cosmyx::paired_log_file_name("orca.log.0") == "cosmyx_orca.log");
    CHECK(Cosmyx::paired_log_file_name("orca.log.x1") == "cosmyx_orca.log.x1");
    CHECK(Cosmyx::paired_log_file_name(fs::path()).empty());
    // A folder, not a file: Boost filesystem v3 gives "." as the file name of a
    // path with a trailing separator ("/" is a separator on every OS).
    CHECK(Cosmyx::paired_log_file_name(fs::path("data/log/")).empty());
    CHECK(Cosmyx::paired_log_file_name(folder / ".").empty());
    CHECK(Cosmyx::paired_log_file_name(folder / "..").empty());
}

TEST_CASE("Cosmyx log channel is named Cosmyx", "[cosmyx][CosmyxLog]")
{
    CHECK(Cosmyx::log_channel() == "Cosmyx");
}
