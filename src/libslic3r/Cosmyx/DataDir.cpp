#include "DataDir.hpp"

#include <filesystem>

namespace Slic3r {
namespace Cosmyx {

std::string vendor_app_subdir(const std::string &app_key)
{
    return (std::filesystem::path(DATA_DIR_VENDOR) / app_key).string();
}

bool skip_legacy_data_migration(const std::string &data_dir)
{
    std::filesystem::path path(data_dir);
    // A trailing separator leaves an empty last component; look at the real leaf.
    while (path.has_relative_path() && path.filename().empty())
        path = path.parent_path();
    if (!path.has_relative_path())
        return false;
    return path.parent_path().filename() == DATA_DIR_VENDOR;
}

} // namespace Cosmyx
} // namespace Slic3r
