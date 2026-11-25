#include "UpdateCheckRequest.hpp"

#include <optional>
#include <string>
#include <utility>

#include <boost/format.hpp>
#include <boost/log/trivial.hpp>

#include <wx/event.h>
#include <wx/string.h>

#include "libslic3r/AppConfig.hpp"
#include "libslic3r_version.h"
#include "logic/CosmyxVersion.hpp"
#include "logic/UpdateCheck.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/I18N.hpp"
#include "slic3r/GUI/MainFrame.hpp"
#include "slic3r/GUI/MsgDialog.hpp"
#include "slic3r/Utils/Http.hpp"
#include "slic3r/Utils/PresetUpdater.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

void explain_stealth_mode()
{
    const wxString message =
        // TRN Shown by Help > Check for Updates while Stealth mode is on: the check never goes online then.
        _L("Checking for updates is turned off while Stealth mode is on. Turn off Stealth mode in Preferences to "
           "check for a new release.");
    InfoDialog dialog(wxGetApp().mainframe, _L("Stealth Mode"), message);
    dialog.ShowModal();
}

// Main thread: the skip_version setting and version_info are only touched here.
void offer(const OfferedRelease& release, int by_user, AppConfig& app_config, VersionInfo& version_info)
{
    const std::string shown = display_form(release.version);
    if (is_skipped(app_config.get("skip_version"), release.version)) {
        // The startup check stays quiet; a user who asked still sees it,
        // without the Skip button (upstream EVT_SLIC3R_VERSION_ONLINE handler).
        if (by_user == 0) {
            BOOST_LOG_TRIVIAL(info) << "Cosmyx update check: " << shown << " was skipped by the user";
            return;
        }
    } else {
        // The upstream handler compares versions as text ("2.5.2-10" <
        // "2.5.2-9"), so an older skip_version is cleared here first.
        app_config.set("skip_version", "");
    }

    version_info.url           = release.url;
    version_info.version_str   = shown;
    version_info.description   = release.notes;
    version_info.force_upgrade = false;

    auto* evt = new wxCommandEvent(EVT_SLIC3R_VERSION_ONLINE);
    evt->SetString(wxString::FromUTF8(shown));
    evt->SetInt(by_user);
    wxGetApp().QueueEvent(evt);
}

} // namespace

void check_for_update(AppConfig& app_config, int by_user, VersionInfo& version_info)
{
    switch (update_check_action(app_config.get_stealth_mode(), by_user != 0)) {
    case UpdateCheckAction::Skip: BOOST_LOG_TRIVIAL(info) << "Cosmyx update check: skipped in Stealth mode"; return;
    case UpdateCheckAction::ExplainStealth: explain_stealth_mode(); return;
    case UpdateCheckAction::Check: break;
    }

    const auto installed = parse_installed_version(SoftFever_VERSION, patch_version);
    if (!installed) {
        BOOST_LOG_TRIVIAL(error) << "Cosmyx update check: cannot read the running version " << display_version();
        return;
    }

    auto http = Http::get(update_check_url);
    http.header("Accept", "application/vnd.github+json")
        .timeout_connect(5)
        .timeout_max(10)
        .on_error([](std::string /*body*/, std::string error, unsigned http_status) {
            BOOST_LOG_TRIVIAL(error) << boost::format("Cosmyx update check: HTTP %1%, %2%") % http_status % error;
        })
        .on_complete([by_user, current = *installed, &app_config, &version_info](std::string body, unsigned http_status) {
            if (http_status != 200)
                return;
            const auto releases = parse_releases_json(body);
            if (!releases) {
                BOOST_LOG_TRIVIAL(error) << "Cosmyx update check: the releases answer is not JSON";
                return;
            }
            std::optional<OfferedRelease> release = pick_update(*releases, current);
            wxGetApp().CallAfter([by_user, release = std::move(release), &app_config, &version_info] {
                if (release)
                    offer(*release, by_user, app_config, version_info);
                else if (by_user != 0)
                    wxGetApp().no_new_version();
            });
        });
    http.perform();
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
