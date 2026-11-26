#include "ColorMode.hpp"

#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Cosmyx/ColorModeDefault.hpp"
#include "slic3r/GUI/GUI_App.hpp"

#include <boost/log/trivial.hpp>

#include <atomic>

#include <wx/app.h>
#include <wx/thread.h>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

#ifndef _WIN32
// Native widgets follow the system appearance on macOS and GTK, so a light
// system would draw light controls under the dark Orca colours. Windows needs
// nothing here: upstream already drives its native dark mode (NppDarkMode)
// from dark_mode(), which is forced (decision 0138, OS exception).
void apply_native_dark_appearance()
{
    // dark_mode() is called very often; ask once, from the main thread, once
    // the application object exists (it does from GUI_App::on_init_inner(),
    // where the first call happens).
    static std::atomic<bool> requested{false};
    if (wxTheApp == nullptr || !wxIsMainThread() || requested.exchange(true))
        return;
    const wxApp::AppearanceResult result = wxTheApp->SetAppearance(wxApp::Appearance::Dark);
    if (result != wxApp::AppearanceResult::Ok)
        BOOST_LOG_TRIVIAL(warning) << "Cosmyx: the native dark appearance could not be applied (result "
                                   << static_cast<int>(result) << "); native widgets may stay light";
}
#endif // _WIN32

} // namespace

bool force_dark_mode()
{
    // Upstream sites write "0" right before calling dark_mode() (the system
    // theme sync at startup on macOS and Linux, update_dark_config(), the
    // Windows Preferences toggle), so healing here keeps the ten direct
    // readers of the key dark too (decision 0137).
    if (wxTheApp != nullptr)
        if (AppConfig* config = wxGetApp().app_config; config != nullptr)
            Slic3r::Cosmyx::force_dark_color_mode(*config);
#ifndef _WIN32
    apply_native_dark_appearance();
#endif
    return true;
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
