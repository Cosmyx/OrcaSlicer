// Checks of the Cosmyx update check logic (decision 0221): only real releases
// of the Cosmyx fork, tagged v<base>.<patch>, are offered, compared with the
// running Cosmyx version and shown in the display form <base>-<patch>.

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <vector>

#include "slic3r/GUI/Cosmyx/logic/UpdateCheck.hpp"

using namespace Slic3r::GUI::Cosmyx;

namespace {

CosmyxVersionNumber version(int major, int minor, int micro, int patch)
{
    CosmyxVersionNumber v;
    v.base  = {major, minor, micro};
    v.patch = patch;
    return v;
}

InstalledVersion installed(const std::string& upstream, int patch)
{
    const auto parsed = parse_installed_version(upstream, patch);
    REQUIRE(parsed);
    return *parsed;
}

ReleaseEntry release(const std::string& tag, bool prerelease = false, bool draft = false)
{
    return ReleaseEntry{tag, prerelease, draft, "https://example.invalid/" + tag, "notes " + tag};
}

} // namespace

TEST_CASE("The update check queries the Cosmyx releases", "[cosmyx][UpdateCheck]")
{
    CHECK(std::string(update_check_url) == "https://api.github.com/repos/Cosmyx/OrcaSlicer/releases");
}

TEST_CASE("Stealth mode turns the update check off", "[cosmyx][UpdateCheck]")
{
    CHECK(update_check_action(false, false) == UpdateCheckAction::Check);
    CHECK(update_check_action(false, true) == UpdateCheckAction::Check);
    CHECK(update_check_action(true, false) == UpdateCheckAction::Skip);
    CHECK(update_check_action(true, true) == UpdateCheckAction::ExplainStealth);
}

TEST_CASE("Release tags follow v<base>.<patch>", "[cosmyx][UpdateCheck]")
{
    CHECK(parse_release_tag("v2.5.2.8") == version(2, 5, 2, 8));
    CHECK(parse_release_tag("2.5.2.8") == version(2, 5, 2, 8));
    CHECK(parse_release_tag("v2.10.0.12") == version(2, 10, 0, 12));
    CHECK(parse_release_tag("v0.0.0.0") == version(0, 0, 0, 0));
}

TEST_CASE("Tags outside the convention are not Cosmyx releases", "[cosmyx][UpdateCheck]")
{
    for (const char* tag : {"v3.0", "v4.0", "v2.5.2", "v2.5.2-8", "v2.5.2.8-beta", "v2.5.2.8.1", "V2.5.2.8", "vv2.5.2.8",
                            "v02.5.2.8", "v2.5.2.08", "v2.5.2.1234567890", "", "v", "nightly", "v2.5.2.8 ",
                            "v2.5.2.\xEF\xBC\x98" /* fullwidth 8 */}) {
        INFO(tag);
        CHECK_FALSE(parse_release_tag(tag));
    }
}

TEST_CASE("The display form is <base>-<patch>", "[cosmyx][UpdateCheck]")
{
    CHECK(display_form(version(2, 5, 2, 8)) == "2.5.2-8");
    CHECK(parse_display_version("2.5.2-8") == version(2, 5, 2, 8));
    CHECK_FALSE(parse_display_version("2.5.2"));
    CHECK_FALSE(parse_display_version("2.5.2.8"));
    CHECK_FALSE(parse_display_version("2.6.0-dev-8"));
}

TEST_CASE("The running version reads SoftFever_VERSION and the patch", "[cosmyx][UpdateCheck]")
{
    const InstalledVersion release_build = installed("2.5.2", 8);
    CHECK(release_build.number == version(2, 5, 2, 8));
    CHECK_FALSE(release_build.upstream_prerelease);

    const InstalledVersion dev_build = installed("2.6.0-dev", 9);
    CHECK(dev_build.number == version(2, 6, 0, 9));
    CHECK(dev_build.upstream_prerelease);

    CHECK_FALSE(parse_installed_version("2.6", 8));
    CHECK_FALSE(parse_installed_version("2.5.2", -1));
}

TEST_CASE("A release is newer by base, then by patch", "[cosmyx][UpdateCheck]")
{
    const InstalledVersion current = installed("2.5.2", 8);
    CHECK(is_newer(version(2, 5, 2, 9), current));
    CHECK(is_newer(version(2, 5, 3, 1), current));
    CHECK(is_newer(version(2, 10, 0, 0), current));
    CHECK_FALSE(is_newer(version(2, 5, 2, 8), current));
    CHECK_FALSE(is_newer(version(2, 5, 2, 7), current));
    CHECK_FALSE(is_newer(version(2, 5, 1, 99), current));
}

TEST_CASE("A release is newer than a pre-release build of its own base", "[cosmyx][UpdateCheck]")
{
    const InstalledVersion dev = installed("2.6.0-dev", 9);
    CHECK(is_newer(version(2, 6, 0, 8), dev));
    CHECK_FALSE(is_newer(version(2, 5, 9, 99), dev));
}

TEST_CASE("Only the newest real release newer than the build is offered", "[cosmyx][UpdateCheck]")
{
    const InstalledVersion current = installed("2.5.2", 8);
    const std::vector<ReleaseEntry> releases{
        release("v2.5.2.9"),
        release("v2.5.3.10"),
        release("v2.6.0.11", true),        // pre-release
        release("v2.7.0.12", false, true), // draft
        release("v4.0"),                   // old tag, not the convention
        release("v2.5.2.7"),
    };
    const auto offered = pick_update(releases, current);
    REQUIRE(offered);
    CHECK(offered->version == version(2, 5, 3, 10));
    CHECK(offered->url == "https://example.invalid/v2.5.3.10");
    CHECK(offered->notes == "notes v2.5.3.10");
}

TEST_CASE("Nothing is offered when no real release is newer", "[cosmyx][UpdateCheck]")
{
    const InstalledVersion current = installed("2.5.2", 8);
    CHECK_FALSE(pick_update({}, current));
    CHECK_FALSE(pick_update({release("v2.5.2.8"), release("v2.5.2.7")}, current));
    CHECK_FALSE(pick_update({release("v2.5.2.9", true), release("v2.5.2.10", false, true)}, current));
}

TEST_CASE("The GitHub releases array is read", "[cosmyx][UpdateCheck]")
{
    const std::string json = R"([
        {"tag_name": "v2.5.2.9", "prerelease": false, "draft": false,
         "html_url": "https://github.com/Cosmyx/OrcaSlicer/releases/tag/v2.5.2.9", "body": "Fixes"},
        {"tag_name": "v2.5.3.10", "prerelease": true, "draft": false, "html_url": "u", "body": ""},
        {"name": "no tag"}
    ])";
    const auto entries = parse_releases_json(json);
    REQUIRE(entries);
    REQUIRE(entries->size() == 2);
    CHECK((*entries)[0].tag_name == "v2.5.2.9");
    CHECK_FALSE((*entries)[0].prerelease);
    CHECK_FALSE((*entries)[0].draft);
    CHECK((*entries)[0].html_url == "https://github.com/Cosmyx/OrcaSlicer/releases/tag/v2.5.2.9");
    CHECK((*entries)[0].body == "Fixes");
    CHECK((*entries)[1].prerelease);

    const auto offered = pick_update(*entries, installed("2.5.2", 8));
    REQUIRE(offered);
    CHECK(display_form(offered->version) == "2.5.2-9");
}

TEST_CASE("A single release object and an empty array are read", "[cosmyx][UpdateCheck]")
{
    const auto single = parse_releases_json(R"({"tag_name": "v2.5.2.9", "prerelease": false})");
    REQUIRE(single);
    REQUIRE(single->size() == 1);
    CHECK((*single)[0].tag_name == "v2.5.2.9");

    const auto empty = parse_releases_json("[]");
    REQUIRE(empty);
    CHECK(empty->empty());
}

TEST_CASE("An unreadable release flag keeps the release out", "[cosmyx][UpdateCheck]")
{
    const auto entries = parse_releases_json(R"([{"tag_name": "v2.5.2.9", "prerelease": "maybe"},
                                                 {"tag_name": "v2.5.2.10", "draft": null}])");
    REQUIRE(entries);
    REQUIRE(entries->size() == 2);
    CHECK((*entries)[0].prerelease);
    CHECK((*entries)[1].draft);
    CHECK_FALSE(pick_update(*entries, installed("2.5.2", 8)));
}

TEST_CASE("Text that is not JSON gives no releases", "[cosmyx][UpdateCheck]")
{
    CHECK_FALSE(parse_releases_json("<html>rate limited</html>"));
    CHECK_FALSE(parse_releases_json(""));
}

TEST_CASE("A skipped version hides it and older ones only", "[cosmyx][UpdateCheck]")
{
    CHECK(is_skipped("2.5.2-9", version(2, 5, 2, 9)));
    CHECK(is_skipped("2.5.2-10", version(2, 5, 2, 9)));
    // Compared as numbers: 10 is newer than 9 although "10" < "9" as text.
    CHECK_FALSE(is_skipped("2.5.2-9", version(2, 5, 2, 10)));
    CHECK_FALSE(is_skipped("2.5.9-1", version(2, 5, 10, 1)));
    CHECK_FALSE(is_skipped("", version(2, 5, 2, 9)));
    // An upstream OrcaSlicer skip_version does not hide a Cosmyx release.
    CHECK_FALSE(is_skipped("2.5.2", version(2, 5, 2, 9)));
}
