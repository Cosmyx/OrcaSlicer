#ifndef slic3r_GUI_Cosmyx_PluginVerify_hpp_
#define slic3r_GUI_Cosmyx_PluginVerify_hpp_

// The two GUI-side hooks of the plugin package check (decision 0204). The
// rules live in logic/PluginTrust.hpp; these read the app config and the
// platform, show the messages and write the logs.
//
// - CloudPluginService::download_cloud_plugin() calls
//   verify_cloud_plugin_package() once the body is downloaded, before anything
//   is written, for an install and an update alike.
// - PluginManager::install_cloud_plugin_package() calls
//   commit_cloud_plugin_record() once the package is installed.

#include <string>

#include <nlohmann/json_fwd.hpp>

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

// Writes .cosmyx_package.json for the package just installed (see
// commit_package_record()); a failure is logged, the install stands.
void commit_cloud_plugin_record(const PluginDescriptor& installed);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_PluginVerify_hpp_
