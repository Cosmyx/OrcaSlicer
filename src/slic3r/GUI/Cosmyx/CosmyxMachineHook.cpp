#include "CosmyxMachineHook.hpp"

#include <utility>

#include "libslic3r/Cosmyx/CosmyxMachine.hpp"
#include "libslic3r/PresetBundle.hpp"

#include "slic3r/GUI/GUI_App.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

FlipNotifier& notifier()
{
    static FlipNotifier instance;
    return instance;
}

} // namespace

bool current_printer_is_cosmyx()
{
    const PresetBundle* bundle = wxGetApp().preset_bundle;
    return bundle != nullptr && Slic3r::Cosmyx::is_cosmyx_printer(*bundle);
}

FlipNotifier::Handle subscribe_printer_is_cosmyx(std::function<void(bool)> listener)
{
    return notifier().subscribe(std::move(listener));
}

void unsubscribe_printer_is_cosmyx(FlipNotifier::Handle handle)
{
    notifier().unsubscribe(handle);
}

void notify_printer_changed()
{
    notifier().update(current_printer_is_cosmyx());
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
