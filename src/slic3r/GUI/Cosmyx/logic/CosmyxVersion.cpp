#include "CosmyxVersion.hpp"

#include "libslic3r_version.h"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

std::string compose_display_version(const std::string& upstream_version, int patch)
{
    return upstream_version + "-" + std::to_string(patch);
}

std::string display_version()
{
    return compose_display_version(SoftFever_VERSION, patch_version);
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
