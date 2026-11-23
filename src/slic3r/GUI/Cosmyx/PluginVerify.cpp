#include "PluginVerify.hpp"

#include <optional>
#include <string>

#include <boost/filesystem/path.hpp>
#include <boost/log/trivial.hpp>
#include <nlohmann/json.hpp>
#include <wx/app.h>

#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Platform.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/I18N.hpp"
#include "slic3r/GUI/NotificationManager.hpp"
#include "slic3r/GUI/Plater.hpp"
#include "slic3r/GUI/format.hpp"
#include "slic3r/plugin/PluginDescriptor.hpp"
#include "slic3r/plugin/PluginFsUtils.hpp"
#include "logic/PluginSigning.hpp"
#include "logic/PluginTrust.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

std::string refusal_message(const std::string& reason, const ServerTrust& trust, const std::string& version,
                            const std::string& installed_version)
{
    if (reason == SIGN_UNRECOGNISED_SERVER)
        return _u8L("The plugin server address is not a plain https address, so its plugins cannot be verified. "
                    "The plugin was not installed.");
    if (reason == SIGN_DOWNGRADE)
        // TRN %1% is the version offered by the server, %2% the installed version.
        return GUI::format(_u8L("Plugin version %1% is older than the installed version %2%, so it was not installed."), version,
                      installed_version);
    if (reason == SIGN_NO_PINNED_KEY)
        return trust.cosmyx_server ?
                   _u8L("This build has no signing key for the Cosmyx plugin server, so its plugins cannot be verified. "
                        "The plugin was not installed.") :
                   _u8L("No signing key is pinned for this plugin server. Pin its key in Preferences, or allow unverified "
                        "plugins from it. The plugin was not installed.");
    if (reason == SIGN_UNKNOWN_SLOT)
        return _u8L("Plugin packages cannot be verified on this platform. The plugin was not installed.");
    // TRN %1% is a fixed code naming the failed check, such as bad_signature or sha256_mismatch.
    return GUI::format(_u8L("The plugin package failed its signature check (%1%). The plugin was not installed."), reason);
}

// True when the OrcaSlicer app runs. wxGetApp() casts wxTheApp unchecked, so
// it is only called once this holds: a process without the app (the upstream
// plugin tests) has no wxTheApp, or a plain wxApp (wxInitializer).
bool app_running() { return dynamic_cast<GUI_App*>(wxTheApp) != nullptr; }

void notify_unverified(const std::string& name)
{
    // TRN %1% is the plugin name.
    const std::string text = GUI::format(_u8L("Plugin %1% was installed unverified: this server may serve unverified plugins."), name);
    wxGetApp().CallAfter([text]() {
        if (wxGetApp().is_closing())
            return;
        Plater* plater = wxGetApp().plater();
        if (plater == nullptr || plater->get_notification_manager() == nullptr)
            return;
        plater->get_notification_manager()->push_notification(NotificationType::CustomNotification,
                                                              NotificationManager::NotificationLevel::WarningNotificationLevel, text);
    });
}

// The record of the package installed for entry, or nothing.
std::optional<PackageRecord> installed_record(const PluginDescriptor& entry)
{
    PackageRecord record;
    if (entry.plugin_root.empty() || !read_package_record(boost::filesystem::path(entry.plugin_root), record) ||
        record.plugin_id != entry.cloud_uuid())
        return std::nullopt;
    return record;
}

// The installer read the dependencies and the entry package from the
// downloaded file before it copied it, so a file swapped there and back would
// pass the digest check with another package's metadata. Read them again from
// the installed bytes, the ones whose digest is checked.
bool same_package_metadata(const PluginDescriptor& installed, std::string& reason)
{
    const boost::filesystem::path file(installed.entry_path);
    PluginDescriptor              read;
    std::string                   error;
    const bool ok = is_wheel_path(installed.entry_path) ? read_wheel_plugin_metadata(file, read, error) :
                                                          read_python_plugin_metadata(file, read, error);
    if (!ok) {
        reason = "the installed package cannot be read: " + error;
        return false;
    }
    if (read.dependencies != installed.dependencies || read.entry_package != installed.entry_package) {
        reason = "the dependencies or the entry package read before the install are not the installed package's";
        return false;
    }
    return true;
}

} // namespace

bool verify_cloud_plugin_package(const PluginDescriptor& entry,
                                 const std::string&      requested_version,
                                 const nlohmann::json*   row,
                                 const std::string&      body,
                                 std::string&            error)
{
    const bool          running = app_running();
    const DownloadCheck check   = download_check(running, running ? wxGetApp().app_config : nullptr);
    ClientRequest       request;
    request.plugin_id = entry.cloud_uuid();
    if (!check.on) {
        // No app, so no trust settings: the download is installed as upstream
        // does, unchecked and without a record (decision 0204, "Without the app").
        BOOST_LOG_TRIVIAL(warning) << "Cosmyx plugin package NOT CHECKED (no OrcaSlicer app in this process): plugin "
                                   << request.plugin_id;
        return true;
    }
    // The request carries a strict X.Y.Z or none (latest); any other version is refused.
    const bool request_ok = request_version(requested_version, request.version);

    std::string row_version;
    if (row != nullptr && row->is_object() && row->contains("version") && row->at("version").is_string())
        row_version = row->at("version").get<std::string>();

    const std::optional<PackageRecord> installed         = installed_record(entry);
    const std::string                  installed_version = installed ? installed->version : std::string();

    const std::string& server = check.server;
    const ServerTrust& trust  = check.trust;

    PackageVerdict verdict;
    if (!request_ok)
        verdict.reason = SIGN_WRONG_VERSION;
    else if (!client_slot(platform_os_type(), platform_architecture(), request.os, request.arch))
        verdict.reason = SIGN_UNKNOWN_SLOT;
    else
        verdict = check_plugin_package(row, body, request, trust, revoked_key_ids(), installed_version,
                                       /*allow_downgrade=*/false);

    if (!verdict.ok()) {
        BOOST_LOG_TRIVIAL(error) << "Cosmyx plugin package refused: plugin " << request.plugin_id << " version " << row_version
                                 << " from " << server << ": " << verdict.reason;
        error = refusal_message(verdict.reason, trust, row_version, installed_version);
        return false;
    }

    if (verdict.verified()) {
        BOOST_LOG_TRIVIAL(info) << "Cosmyx plugin package verified: plugin " << request.plugin_id << " version "
                                << verdict.record.version << " key " << verdict.record.key_id;
    } else {
        BOOST_LOG_TRIVIAL(warning) << "Cosmyx plugin package UNVERIFIED (allowed for " << server << "): plugin "
                                   << request.plugin_id << " version " << verdict.record.version;
        notify_unverified(entry.name.empty() ? request.plugin_id : entry.name);
    }
    remember_checked_package(verdict.record);
    return true;
}

CloudInstallScope::CloudInstallScope(const PluginDescriptor& previous)
    : m_plugin_id(previous.cloud_uuid()), m_floor(installed_record(previous))
{}

bool CloudInstallScope::commit(const PluginDescriptor& installed, std::string& error) const
{
    // Without the app the download was not checked, so there is no record to
    // match: the install goes on as upstream. With the app, a missing record
    // still refuses it.
    if (!package_check_on(app_running()))
        return true;
    const boost::filesystem::path plugin_dir(installed.plugin_root);
    const boost::filesystem::path package_file(installed.entry_path);
    const PackageRecord*          floor = m_floor ? &*m_floor : nullptr;
    std::string                   reason;
    // The metadata reader may throw (a filesystem error): that refuses the install too.
    if (commit_checked_install(installed.cloud_uuid(), plugin_dir, package_file,
                               [&installed](std::string& why) { return same_package_metadata(installed, why); }, reason, floor))
        return true;
    BOOST_LOG_TRIVIAL(error) << "Cosmyx plugin package refused after install: plugin " << installed.cloud_uuid() << ": " << reason;
    error = _u8L("The installed plugin package could not be recorded as the one whose signature was checked, so it was removed. "
                 "The plugin was not installed.");
    return false;
}

CloudInstallScope::~CloudInstallScope() { forget_checked_packages(m_plugin_id); }

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
