#ifndef slic3r_GUI_Cosmyx_PluginVerify_hpp_
#define slic3r_GUI_Cosmyx_PluginVerify_hpp_

// The two GUI-side hooks of the plugin package check (decision 0204). The
// rules live in logic/PluginTrust.hpp; these read the app config and the
// platform, show the messages and write the logs.
//
// - CloudPluginService::download_cloud_plugin() calls
//   verify_cloud_plugin_package() once the body is downloaded, before anything
//   is written, for an install and an update alike.
// - PluginManager::install_cloud_plugin_package() opens a CloudInstallScope
//   first, and calls its commit() once the package is installed, before the
//   plugin entry is marked installed.
//
// Both are no-ops in a process with no OrcaSlicer app (package_check_on()):
// the download is logged as not checked and installed as upstream does.

#include <optional>
#include <string>

#include <nlohmann/json_fwd.hpp>

#include "logic/PluginSigning.hpp"

namespace Slic3r {

struct PluginDescriptor;

namespace GUI {
namespace Cosmyx {

// True when the package may be installed. False sets error to a translated
// message; nothing is installed then. row is the download row as served, or
// null when it did not reach the check.
bool verify_cloud_plugin_package(const PluginDescriptor& entry,
                                 const std::string&      requested_version,
                                 const nlohmann::json*   row,
                                 const std::string&      body,
                                 std::string&            error);

// One cloud install of a plugin. Opened before the install starts, it keeps
// the record of the package being replaced (the downgrade floor); when the
// install ends, failed or not, it drops the checked records that the install
// did not commit (forget_checked_packages()).
class CloudInstallScope
{
public:
    // previous is the plugin entry before the install.
    explicit CloudInstallScope(const PluginDescriptor& previous);
    ~CloudInstallScope();
    CloudInstallScope(const CloudInstallScope&)            = delete;
    CloudInstallScope& operator=(const CloudInstallScope&) = delete;

    // Writes .cosmyx_package.json for the package just installed (see
    // commit_package_record()). False when the installed bytes are not the
    // ones that passed the check, when their dependencies or entry package
    // differ from the ones the installer read (the downloaded file was swapped
    // while it was read), or when the record cannot be written: the package
    // file is removed, the record of the replaced package is put back, error
    // gets a translated message and the install is refused.
    bool commit(const PluginDescriptor& installed, std::string& error) const;

private:
    std::string                  m_plugin_id;
    std::optional<PackageRecord> m_floor;
};

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_PluginVerify_hpp_
