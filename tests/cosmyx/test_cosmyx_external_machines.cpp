// Checks of the "External machines" toggle rules (decision 0219): turning
// Bambu Cloud or the Bambu network plug-in on asks first, a cancel reverts the
// toggle without saving, and turning one off never asks.

#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>

#include "slic3r/GUI/Cosmyx/logic/ExternalMachines.hpp"

namespace CC = Slic3r::GUI::Cosmyx;

TEST_CASE("Turning an external machine toggle on asks first", "[cosmyx][ExternalMachines]")
{
    CHECK(CC::external_toggle_needs_warning(true));
}

TEST_CASE("Turning an external machine toggle off never asks", "[cosmyx][ExternalMachines]")
{
    CHECK_FALSE(CC::external_toggle_needs_warning(false));
}

TEST_CASE("A confirmed warning keeps the toggle on and applies it", "[cosmyx][ExternalMachines]")
{
    const CC::ExternalToggleOutcome outcome = CC::external_toggle_outcome(true, true);
    CHECK(outcome.value);
    CHECK(outcome.apply);
}

TEST_CASE("A cancelled warning reverts the toggle and saves nothing", "[cosmyx][ExternalMachines]")
{
    const CC::ExternalToggleOutcome outcome = CC::external_toggle_outcome(true, false);
    CHECK_FALSE(outcome.value);
    CHECK_FALSE(outcome.apply);
}

TEST_CASE("Turning off applies whatever the confirmation says", "[cosmyx][ExternalMachines]")
{
    const bool confirmed = GENERATE(true, false);
    const CC::ExternalToggleOutcome outcome = CC::external_toggle_outcome(false, confirmed);
    CHECK_FALSE(outcome.value);
    CHECK(outcome.apply);
}
