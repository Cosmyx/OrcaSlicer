// Checks of FlipNotifier (decision 0222): the Cosmyx machine flag reaches its
// subscribers once per flip, never for an unchanged value.

#include <catch2/catch_test_macros.hpp>

#include <vector>

#include "slic3r/GUI/Cosmyx/logic/FlipNotifier.hpp"

using Slic3r::GUI::Cosmyx::FlipNotifier;

TEST_CASE("The notifier starts without a value", "[cosmyx][FlipNotifier]")
{
    FlipNotifier notifier;
    CHECK_FALSE(notifier.value().has_value());
}

TEST_CASE("Subscribing does not call the listener", "[cosmyx][FlipNotifier]")
{
    FlipNotifier notifier;
    int          calls = 0;
    notifier.subscribe([&](bool) { ++calls; });
    CHECK(calls == 0);
}

TEST_CASE("The first value notifies, an unchanged one does not, a flip does", "[cosmyx][FlipNotifier]")
{
    FlipNotifier      notifier;
    std::vector<bool> seen;
    notifier.subscribe([&](bool v) { seen.push_back(v); });

    CHECK(notifier.update(false));
    CHECK_FALSE(notifier.update(false));
    CHECK(notifier.update(true));
    CHECK_FALSE(notifier.update(true));
    CHECK_FALSE(notifier.update(true));
    CHECK(notifier.update(false));

    CHECK(seen == std::vector<bool>{ false, true, false });
    REQUIRE(notifier.value().has_value());
    CHECK(*notifier.value() == false);
}

TEST_CASE("A first value of true notifies too", "[cosmyx][FlipNotifier]")
{
    FlipNotifier      notifier;
    std::vector<bool> seen;
    notifier.subscribe([&](bool v) { seen.push_back(v); });
    CHECK(notifier.update(true));
    CHECK(seen == std::vector<bool>{ true });
}

TEST_CASE("Every listener hears a flip, in subscription order", "[cosmyx][FlipNotifier]")
{
    FlipNotifier     notifier;
    std::vector<int> order;
    notifier.subscribe([&](bool) { order.push_back(1); });
    notifier.subscribe([&](bool) { order.push_back(2); });
    notifier.update(true);
    CHECK(order == std::vector<int>{ 1, 2 });
}

TEST_CASE("An unsubscribed listener is not called", "[cosmyx][FlipNotifier]")
{
    FlipNotifier notifier;
    int          calls = 0;
    const auto   handle = notifier.subscribe([&](bool) { ++calls; });
    notifier.unsubscribe(handle);
    CHECK(notifier.listener_count() == 0);
    notifier.update(true);
    CHECK(calls == 0);
}

TEST_CASE("Unknown and repeated unsubscribes are ignored", "[cosmyx][FlipNotifier]")
{
    FlipNotifier notifier;
    int          calls  = 0;
    const auto   handle = notifier.subscribe([&](bool) { ++calls; });
    notifier.unsubscribe(0);
    notifier.unsubscribe(handle + 100);
    CHECK(notifier.listener_count() == 1);
    notifier.unsubscribe(handle);
    notifier.unsubscribe(handle);
    CHECK(notifier.listener_count() == 0);
}

TEST_CASE("Handles are distinct and never zero", "[cosmyx][FlipNotifier]")
{
    FlipNotifier notifier;
    const auto   a = notifier.subscribe([](bool) {});
    const auto   b = notifier.subscribe([](bool) {});
    CHECK(a != 0);
    CHECK(b != 0);
    CHECK(a != b);
}

TEST_CASE("A listener may unsubscribe itself while notified", "[cosmyx][FlipNotifier]")
{
    FlipNotifier         notifier;
    int                  calls  = 0;
    FlipNotifier::Handle handle = 0;
    handle = notifier.subscribe([&](bool) {
        ++calls;
        notifier.unsubscribe(handle);
    });
    notifier.update(true);
    notifier.update(false);
    CHECK(calls == 1);
}

TEST_CASE("A listener removed by an earlier one during the same flip is skipped", "[cosmyx][FlipNotifier]")
{
    FlipNotifier         notifier;
    int                  second_calls = 0;
    FlipNotifier::Handle second       = 0;
    notifier.subscribe([&](bool) { notifier.unsubscribe(second); });
    second = notifier.subscribe([&](bool) { ++second_calls; });
    notifier.update(true);
    CHECK(second_calls == 0);
}

TEST_CASE("A listener added during a flip hears the next flip only", "[cosmyx][FlipNotifier]")
{
    FlipNotifier notifier;
    int          late_calls = 0;
    bool         added      = false;
    notifier.subscribe([&](bool) {
        if (!added) {
            added = true;
            notifier.subscribe([&](bool) { ++late_calls; });
        }
    });
    notifier.update(true);
    CHECK(late_calls == 0);
    notifier.update(false);
    CHECK(late_calls == 1);
}
