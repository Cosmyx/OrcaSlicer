// Checks of the version shown to the user: "<SoftFever_VERSION>-<Cosmyx patch>"
// (decisions 0060, 0061).

#include <catch2/catch_test_macros.hpp>

#include <regex>
#include <string>

#include "libslic3r_version.h"
#include "slic3r/GUI/Cosmyx/logic/CosmyxVersion.hpp"

using namespace Slic3r::GUI::Cosmyx;

TEST_CASE("Cosmyx patch numbers start at 8", "[cosmyx][CosmyxVersion]")
{
    // The numbering starts at 8 (decision 0060) and only goes up, so a lower
    // number means the patch was edited by mistake.
    STATIC_REQUIRE(patch_version >= 8);
}

TEST_CASE("The display version appends the Cosmyx patch to the upstream version", "[cosmyx][CosmyxVersion]")
{
    CHECK(compose_display_version("2.6.0", 8) == "2.6.0-8");
    CHECK(compose_display_version("2.3.1", 12) == "2.3.1-12");
}

TEST_CASE("The display version keeps an upstream pre-release suffix", "[cosmyx][CosmyxVersion]")
{
    CHECK(compose_display_version("2.6.0-dev", 8) == "2.6.0-dev-8");
    CHECK(compose_display_version("2.3.2-beta2", 9) == "2.3.2-beta2-9");
}

TEST_CASE("The built display version is SoftFever_VERSION followed by the patch", "[cosmyx][CosmyxVersion]")
{
    const std::string shown = display_version();
    CHECK(shown == std::string(SoftFever_VERSION) + "-" + std::to_string(patch_version));
    // <major>.<minor>.<patch>[-<upstream pre-release>]-<Cosmyx patch>
    CHECK(std::regex_match(shown, std::regex(R"(\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?-\d+)")));
}
