#ifndef slic3r_GUI_Cosmyx_FlipNotifier_hpp_
#define slic3r_GUI_Cosmyx_FlipNotifier_hpp_

// A cached boolean that calls its listeners only when the value flips. The
// Cosmyx machine hook (../CosmyxMachineHook.cpp) feeds it the "selected printer
// is a Cosmyx machine" flag every time the printer presets change, and the GUI
// features gated on Cosmyx machines subscribe to it (decision 0222).
//
// wxWidgets-free: compiled into libslic3r_gui and into cosmyx_tests.

#include <cstddef>
#include <functional>
#include <optional>
#include <utility>
#include <vector>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

class FlipNotifier
{
public:
    using Listener = std::function<void(bool)>;
    // 0 is never handed out, so a default-constructed handle subscribes nothing.
    using Handle = std::size_t;

    // Adds a listener. It is not called here: the caller reads the current
    // value itself, the notifier only reports changes.
    Handle subscribe(Listener listener);
    // Removes a listener. Unknown or already removed handles are ignored.
    void unsubscribe(Handle handle);

    // Records value. The first value ever recorded, and any value that differs
    // from the previous one, calls every listener with it and returns true; an
    // unchanged value calls nobody and returns false. Listeners may subscribe
    // or unsubscribe from inside the call: the listeners called are the ones
    // subscribed when update() started, minus those removed meanwhile.
    bool update(bool value);

    // The last recorded value, empty before the first update().
    std::optional<bool> value() const { return m_value; }
    std::size_t listener_count() const { return m_listeners.size(); }

private:
    std::optional<bool>                     m_value;
    std::vector<std::pair<Handle, Listener>> m_listeners;
    Handle                                  m_next_handle = 1;
};

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_FlipNotifier_hpp_
