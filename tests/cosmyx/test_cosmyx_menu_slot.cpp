// Checks of slot_insert_position (decision 0223): the Cosmyx models submenu
// goes back right after the item it followed, not at the end of the menu.

#include <catch2/catch_test_macros.hpp>

#include <vector>

#include "slic3r/GUI/Cosmyx/logic/MenuSlot.hpp"

using Slic3r::GUI::Cosmyx::slot_insert_position;

TEST_CASE("The slot follows its anchor item", "[cosmyx][MenuSlot]")
{
    // Add Primitive (10), Add Handy models (11), Add Models (12), separator (13).
    const std::vector<int> ids{ 10, 11, 12, 13 };
    CHECK(slot_insert_position(ids, 11, 0) == 2);
    CHECK(slot_insert_position(ids, 11, 99) == 2);
}

TEST_CASE("The slot follows its anchor wherever the anchor moved", "[cosmyx][MenuSlot]")
{
    const std::vector<int> ids{ 1, 2, 3, 10, 11, 12 };
    CHECK(slot_insert_position(ids, 11, 2) == 5);
}

TEST_CASE("An anchor that is the last item puts the slot at the end", "[cosmyx][MenuSlot]")
{
    const std::vector<int> ids{ 10, 11 };
    CHECK(slot_insert_position(ids, 11, 0) == 2);
}

TEST_CASE("Without its anchor the slot goes back to its saved index", "[cosmyx][MenuSlot]")
{
    const std::vector<int> ids{ 10, 12, 13 };
    CHECK(slot_insert_position(ids, 11, 1) == 1);
}

TEST_CASE("A saved index past the end is clamped to the end", "[cosmyx][MenuSlot]")
{
    const std::vector<int> ids{ 10, 12 };
    CHECK(slot_insert_position(ids, 11, 7) == 2);
}

TEST_CASE("An empty menu takes the slot at index 0", "[cosmyx][MenuSlot]")
{
    CHECK(slot_insert_position({}, 11, 3) == 0);
}
