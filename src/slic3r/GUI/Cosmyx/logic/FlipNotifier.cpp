#include "FlipNotifier.hpp"

#include <algorithm>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

FlipNotifier::Handle FlipNotifier::subscribe(Listener listener)
{
    const Handle handle = m_next_handle++;
    m_listeners.emplace_back(handle, std::move(listener));
    return handle;
}

void FlipNotifier::unsubscribe(Handle handle)
{
    m_listeners.erase(std::remove_if(m_listeners.begin(), m_listeners.end(),
                                     [handle](const auto& entry) { return entry.first == handle; }),
                      m_listeners.end());
}

bool FlipNotifier::update(bool value)
{
    if (m_value.has_value() && *m_value == value)
        return false;
    m_value = value;

    // Iterate over a snapshot of the handles, so a listener that subscribes or
    // unsubscribes does not invalidate the loop, and look each one up again so
    // a listener removed by an earlier one is skipped.
    std::vector<Handle> handles;
    handles.reserve(m_listeners.size());
    for (const auto& entry : m_listeners)
        handles.push_back(entry.first);
    for (Handle handle : handles) {
        const auto it = std::find_if(m_listeners.begin(), m_listeners.end(),
                                     [handle](const auto& entry) { return entry.first == handle; });
        if (it == m_listeners.end())
            continue;
        // Copy: the listener may unsubscribe itself while running.
        const Listener listener = it->second;
        if (listener)
            listener(value);
    }
    return true;
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
