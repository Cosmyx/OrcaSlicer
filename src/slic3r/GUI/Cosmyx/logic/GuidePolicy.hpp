#ifndef slic3r_GUI_Cosmyx_logic_GuidePolicy_hpp_
#define slic3r_GUI_Cosmyx_logic_GuidePolicy_hpp_

// Cosmyx policy for the first-run setup guide (WebGuideDialog).
//
// Cosmyx builds always run in stealth mode (decision 0070). The guide must
// therefore never offer to leave it, nor to install the Bambu network plugin:
//
// - stealth_mode is reported as on, so the guide state matches the forced
//   AppConfig::get_stealth_mode();
// - network_plugin_install and network_plugin_compability are reported as "1"
//   (installed and compatible). resources/web/guide/22/22.js then keeps the
//   Finish button and never shows the Next button that leads to the stealth
//   mode page (4orca/) and the network plugin page (5/).
//
// The two network plugin keys are only read by 22.js. They do not trigger any
// download or install: that only happens when page 5 sends the
// "network_plugin_install" command with "yes" (decision 0073).
//
// wxWidgets-free, so cosmyx_tests checks it directly.

#include <nlohmann/json.hpp>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Rewrites the guide profile sent to the web pages, and the dialog's own
// stealth flag that SaveProfile() writes to the app config.
inline void apply_guide_policy(nlohmann::json& profile, bool& stealth)
{
    stealth                               = true;
    profile["stealth_mode"]               = true;
    profile["network_plugin_install"]     = "1";
    profile["network_plugin_compability"] = "1";
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_logic_GuidePolicy_hpp_
