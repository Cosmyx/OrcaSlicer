#include "DataDir.hpp"

#include <filesystem>

namespace Slic3r {
namespace Cosmyx {

std::string vendor_app_subdir(const std::string &app_key)
{
    return (std::filesystem::path(DATA_DIR_VENDOR) / app_key).string();
}

std::string without_vendor_dir(const std::string &data_dir)
{
    std::filesystem::path path(data_dir);
    // A trailing separator leaves an empty last component; look at the real leaf.
    while (path.has_relative_path() && path.filename().empty())
        path = path.parent_path();
    if (!path.has_relative_path())
        return data_dir;
    const std::filesystem::path parent = path.parent_path();
    if (parent.filename() != DATA_DIR_VENDOR)
        return data_dir;
    return (parent.parent_path() / path.filename()).string();
}

} // namespace Cosmyx
} // namespace Slic3r
