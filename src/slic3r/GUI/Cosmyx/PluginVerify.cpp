#include "PluginVerify.hpp"

#include <string>

#include <boost/filesystem/path.hpp>
#include <boost/log/trivial.hpp>
#include <nlohmann/json.hpp>

#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Platform.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/I18N.hpp"
#include "slic3r/GUI/NotificationManager.hpp"
#include "slic3r/GUI/Plater.hpp"
#include "slic3r/GUI/format.hpp"
#include "slic3r/plugin/PluginDescriptor.hpp"
#include "logic/CloudServer.hpp"
#include "logic/PluginSigning.hpp"
#include "logic/PluginTrust.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

std::string refusal_message(const std::string& reason, const ServerTrust& trust, const std::string& version,
                            const std::string& installed_version)
{
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

} // namespace

bool verify_cloud_plugin_package(const PluginDescriptor& entry,
                                 const std::string&      requested_version,
                                 const nlohmann::json*   row,
                                 const std::string&      body,
                                 std::string&            error)
{
    const AppConfig* config = wxGetApp().app_config;
    ClientRequest    request;
    request.plugin_id = entry.cloud_uuid();
    // The request carries a strict X.Y.Z or none (latest); any other version is refused.
    const bool request_ok = request_version(requested_version, request.version);

    std::string row_version;
    if (row != nullptr && row->is_object() && row->contains("version") && row->at("version").is_string())
        row_version = row->at("version").get<std::string>();

    PackageRecord installed;
    std::string   installed_version;
    if (!entry.plugin_root.empty() && read_package_record(boost::filesystem::path(entry.plugin_root), installed) &&
        installed.plugin_id == request.plugin_id)
        installed_version = installed.version;

    const std::string server = config != nullptr ? active_api_url(*config) : std::string(CLOUD_SERVER_URL);
    const ServerTrust trust  = config != nullptr ? server_trust(*config, server) : ServerTrust{true, built_in_keys(), false};

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

bool commit_cloud_plugin_record(const PluginDescriptor& installed, std::string& error)
{
    std::string reason;
    if (commit_package_record(installed.cloud_uuid(), boost::filesystem::path(installed.plugin_root),
                              boost::filesystem::path(installed.entry_path), reason))
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
