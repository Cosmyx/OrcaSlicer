#ifndef slic3r_GUI_Cosmyx_UpdateCheck_hpp_
#define slic3r_GUI_Cosmyx_UpdateCheck_hpp_

// wxWidgets-free part of the Cosmyx update check (decision 0221).
//
// The check reads the GitHub releases of the Cosmyx fork, keeps only real
// releases (never a draft or a pre-release, whatever the user's
// "check_stable_update_only" setting says) whose tag follows the Cosmyx
// convention `v<OrcaSlicer base>.<Cosmyx patch>` (for example v2.5.2.8), and
// offers the newest one when it is newer than the running build. Versions are
// shown and stored (skip_version) in the display form "<base>-<patch>"
// (decision 0060), for example "2.5.2-8".

#include <array>
#include <optional>
#include <string>
#include <vector>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// GitHub releases of the Cosmyx fork, newest first, as a JSON array.
inline constexpr const char* update_check_url = "https://api.github.com/repos/Cosmyx/OrcaSlicer/releases";

enum class UpdateCheckAction {
    Skip,           // do nothing: the startup check in Stealth mode
    Check,          // query the releases
    ExplainStealth, // tell the user who asked that Stealth mode turns the check off
};

// The check never reaches the network in Stealth mode. A check the user
// started from the menu says why nothing happens; the startup check is silent.
UpdateCheckAction update_check_action(bool stealth_mode, bool by_user);

// A Cosmyx version: the OrcaSlicer base (major, minor, patch) and the Cosmyx
// patch number.
struct CosmyxVersionNumber
{
    std::array<int, 3> base{};
    int                patch{0};
};

bool operator<(const CosmyxVersionNumber& lhs, const CosmyxVersionNumber& rhs);
bool operator==(const CosmyxVersionNumber& lhs, const CosmyxVersionNumber& rhs);

// "v2.5.2.8" or "2.5.2.8" -> {2.5.2, 8}. Anything else (old tags such as
// "v3.0", suffixes, leading zeros, non-ASCII digits) is not a Cosmyx release.
std::optional<CosmyxVersionNumber> parse_release_tag(const std::string& tag);

// "2.5.2-8" -> {2.5.2, 8}: the display form, as stored in skip_version.
std::optional<CosmyxVersionNumber> parse_display_version(const std::string& text);

// "2.5.2-8".
std::string display_form(const CosmyxVersionNumber& version);

// The running build: SoftFever_VERSION, which may carry an upstream
// pre-release suffix ("2.6.0-dev"), and the Cosmyx patch.
struct InstalledVersion
{
    CosmyxVersionNumber number;
    bool                upstream_prerelease{false};
};

std::optional<InstalledVersion> parse_installed_version(const std::string& upstream_version, int patch);

// A release on a newer base is newer whatever its patch. On the same base it
// is newer when the running build is an upstream pre-release of that base
// (2.6.0-dev-9 is older than the 2.6.0.8 release) or has a lower patch.
bool is_newer(const CosmyxVersionNumber& release, const InstalledVersion& installed);

// One entry of the GitHub releases answer.
struct ReleaseEntry
{
    std::string tag_name;
    bool        prerelease{false};
    bool        draft{false};
    std::string html_url;
    std::string body;
};

// Reads a GitHub releases array, or a single release object. Returns nothing
// when the text is not JSON; entries without a tag are dropped.
std::optional<std::vector<ReleaseEntry>> parse_releases_json(const std::string& json);

struct OfferedRelease
{
    CosmyxVersionNumber version;
    std::string         url;
    std::string         notes;
};

// The newest real release newer than the running build, if any.
std::optional<OfferedRelease> pick_update(const std::vector<ReleaseEntry>& releases, const InstalledVersion& installed);

// True when the user skipped this release or a newer one. An empty or
// unreadable skip_version (an upstream "2.3.1" for example) skips nothing.
bool is_skipped(const std::string& skip_version, const CosmyxVersionNumber& offered);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_UpdateCheck_hpp_
