#include "UpdateCheck.hpp"

#include <exception>
#include <regex>
#include <sstream>
#include <string>
#include <tuple>

#include <boost/optional.hpp>
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include "CosmyxVersion.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

// An ASCII decimal number without a leading zero, at most 9 digits so that
// std::stoi never overflows (decision 0064 for the same rule on the patch).
#define COSMYX_NUMBER "(0|[1-9][0-9]{0,8})"

std::optional<CosmyxVersionNumber> match_version(const std::string& text, const std::regex& pattern)
{
    std::smatch match;
    if (!std::regex_match(text, match, pattern))
        return std::nullopt;
    CosmyxVersionNumber version;
    for (int i = 0; i < 3; ++i)
        version.base[i] = std::stoi(match[i + 1].str());
    version.patch = std::stoi(match[4].str());
    return version;
}

std::string base_string(const CosmyxVersionNumber& version)
{
    return std::to_string(version.base[0]) + "." + std::to_string(version.base[1]) + "." + std::to_string(version.base[2]);
}

} // namespace

UpdateCheckAction update_check_action(bool stealth_mode, bool by_user)
{
    if (!stealth_mode)
        return UpdateCheckAction::Check;
    return by_user ? UpdateCheckAction::ExplainStealth : UpdateCheckAction::Skip;
}

bool operator<(const CosmyxVersionNumber& lhs, const CosmyxVersionNumber& rhs)
{
    return std::tie(lhs.base, lhs.patch) < std::tie(rhs.base, rhs.patch);
}

bool operator==(const CosmyxVersionNumber& lhs, const CosmyxVersionNumber& rhs)
{
    return lhs.base == rhs.base && lhs.patch == rhs.patch;
}

std::optional<CosmyxVersionNumber> parse_release_tag(const std::string& tag)
{
    static const std::regex pattern("v?" COSMYX_NUMBER "\\." COSMYX_NUMBER "\\." COSMYX_NUMBER "\\." COSMYX_NUMBER);
    return match_version(tag, pattern);
}

std::optional<CosmyxVersionNumber> parse_display_version(const std::string& text)
{
    static const std::regex pattern(COSMYX_NUMBER "\\." COSMYX_NUMBER "\\." COSMYX_NUMBER "-" COSMYX_NUMBER);
    return match_version(text, pattern);
}

std::string display_form(const CosmyxVersionNumber& version)
{
    return compose_display_version(base_string(version), version.patch);
}

std::optional<InstalledVersion> parse_installed_version(const std::string& upstream_version, int patch)
{
    static const std::regex pattern(COSMYX_NUMBER "\\." COSMYX_NUMBER "\\." COSMYX_NUMBER "(-[0-9A-Za-z.]+)?");
    std::smatch             match;
    if (patch < 0 || !std::regex_match(upstream_version, match, pattern))
        return std::nullopt;
    InstalledVersion installed;
    for (int i = 0; i < 3; ++i)
        installed.number.base[i] = std::stoi(match[i + 1].str());
    installed.number.patch        = patch;
    installed.upstream_prerelease = match[4].matched;
    return installed;
}

bool is_newer(const CosmyxVersionNumber& release, const InstalledVersion& installed)
{
    if (release.base != installed.number.base)
        return installed.number.base < release.base;
    return installed.upstream_prerelease || installed.number.patch < release.patch;
}

std::optional<std::vector<ReleaseEntry>> parse_releases_json(const std::string& json)
{
    namespace pt = boost::property_tree;
    pt::ptree root;
    try {
        std::istringstream stream(json);
        pt::read_json(stream, root);
    } catch (const std::exception&) {
        return std::nullopt;
    }

    std::vector<ReleaseEntry> entries;
    auto add = [&entries](const pt::ptree& node) {
        const auto tag = node.get_optional<std::string>("tag_name");
        if (!tag)
            return;
        ReleaseEntry entry;
        entry.tag_name   = *tag;
        // A flag that cannot be read counts as set: when in doubt, the
        // release is not offered.
        entry.prerelease = node.get_optional<bool>("prerelease").get_value_or(node.count("prerelease") != 0);
        entry.draft      = node.get_optional<bool>("draft").get_value_or(node.count("draft") != 0);
        entry.html_url   = node.get_optional<std::string>("html_url").get_value_or(std::string());
        entry.body       = node.get_optional<std::string>("body").get_value_or(std::string());
        entries.push_back(std::move(entry));
    };

    if (root.count("tag_name") != 0)
        add(root);
    else
        for (const auto& child : root)
            add(child.second);
    return entries;
}

std::optional<OfferedRelease> pick_update(const std::vector<ReleaseEntry>& releases, const InstalledVersion& installed)
{
    std::optional<OfferedRelease> best;
    for (const ReleaseEntry& entry : releases) {
        // Only real releases are ever offered: never a draft, a pre-release,
        // a dev or a nightly build (decision 0221).
        if (entry.draft || entry.prerelease)
            continue;
        const auto version = parse_release_tag(entry.tag_name);
        if (!version || !is_newer(*version, installed))
            continue;
        if (!best || best->version < *version)
            best = OfferedRelease{*version, entry.html_url, entry.body};
    }
    return best;
}

bool is_skipped(const std::string& skip_version, const CosmyxVersionNumber& offered)
{
    const auto skipped = parse_display_version(skip_version);
    return skipped && !(*skipped < offered);
}

#undef COSMYX_NUMBER

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
