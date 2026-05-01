"""Tests for the Room Test category submenu.

Validates that ROOM_TEST_CATEGORIES are defined, _category_for_entry routes
correctly by context_label, load_room_test_entries_for_category returns the
right subset, and the RoomTestCategoryView builder populates counts correctly.
"""
import unittest
from dataclasses import dataclass
from room_test_catalog import (
    ROOM_TEST_CATEGORIES,
    ROOM_TEST_CATEGORY_BASE_LAYOUT,
    ROOM_TEST_CATEGORY_MUD_CAVERNS,
    ROOM_TEST_CATEGORY_FROZEN_DEPTHS,
    ROOM_TEST_CATEGORY_SUNKEN_RUINS,
    TUNING_TEST_ROOM_ID,
    _BASE_CONTEXT_LABEL,
    _category_for_entry,
    load_room_test_entries,
    load_room_test_entries_for_category,
)


def _fake_entry(room_id, context_label="Base Layout"):
    @dataclass(frozen=True)
    class FakeEntry:
        room_id: str
        context_label: str
    return FakeEntry(room_id=room_id, context_label=context_label)


class CategoryConstantsTests(unittest.TestCase):
    def test_four_categories_defined(self):
        self.assertEqual(len(ROOM_TEST_CATEGORIES), 4)

    def test_category_names_present(self):
        self.assertIn(ROOM_TEST_CATEGORY_BASE_LAYOUT,   ROOM_TEST_CATEGORIES)
        self.assertIn(ROOM_TEST_CATEGORY_MUD_CAVERNS,   ROOM_TEST_CATEGORIES)
        self.assertIn(ROOM_TEST_CATEGORY_FROZEN_DEPTHS, ROOM_TEST_CATEGORIES)
        self.assertIn(ROOM_TEST_CATEGORY_SUNKEN_RUINS,  ROOM_TEST_CATEGORIES)

    def test_base_context_label_matches_base_layout_category(self):
        self.assertEqual(_BASE_CONTEXT_LABEL, ROOM_TEST_CATEGORY_BASE_LAYOUT)


class CategoryForEntryTests(unittest.TestCase):
    def test_tuning_room_returns_none_category(self):
        self.assertIsNone(_category_for_entry(_fake_entry(TUNING_TEST_ROOM_ID)))

    def test_base_layout_context_routes_to_base_layout(self):
        self.assertEqual(
            _category_for_entry(_fake_entry("standard_combat", "Base Layout")),
            ROOM_TEST_CATEGORY_BASE_LAYOUT,
        )

    def test_mission_base_layout_routes_to_base_layout(self):
        self.assertEqual(
            _category_for_entry(_fake_entry("escort_protection", "Base Layout")),
            ROOM_TEST_CATEGORY_BASE_LAYOUT,
        )

    def test_mud_caverns_context_routes_to_mud_caverns(self):
        self.assertEqual(
            _category_for_entry(_fake_entry("ritual_disruption", "Mud Caverns")),
            ROOM_TEST_CATEGORY_MUD_CAVERNS,
        )

    def test_frozen_depths_context_routes_to_frozen_depths(self):
        self.assertEqual(
            _category_for_entry(_fake_entry("ritual_disruption", "Frozen Depths")),
            ROOM_TEST_CATEGORY_FROZEN_DEPTHS,
        )

    def test_sunken_ruins_context_routes_to_sunken_ruins(self):
        self.assertEqual(
            _category_for_entry(_fake_entry("water_tide_lord_arena", "Sunken Ruins")),
            ROOM_TEST_CATEGORY_SUNKEN_RUINS,
        )

    def test_earth_room_base_layout_routes_to_base_layout(self):
        # Base-layout versions of earth rooms belong to Base Layout, not Mud Caverns.
        self.assertEqual(
            _category_for_entry(_fake_entry("earth_boulder_run", "Base Layout")),
            ROOM_TEST_CATEGORY_BASE_LAYOUT,
        )

    def test_earth_room_mud_caverns_routes_to_mud_caverns(self):
        # The Mud Caverns biome variant of an earth room goes to Mud Caverns.
        self.assertEqual(
            _category_for_entry(_fake_entry("earth_boulder_run", "Mud Caverns")),
            ROOM_TEST_CATEGORY_MUD_CAVERNS,
        )


class LoadEntriesForCategoryTests(unittest.TestCase):
    def setUp(self):
        self.all_entries = load_room_test_entries()

    def test_categories_partition_all_entries(self):
        all_by_category = set()
        for cat in ROOM_TEST_CATEGORIES:
            for entry in load_room_test_entries_for_category(cat):
                all_by_category.add(entry.entry_id)
        # The tuning shortcut returns None from _category_for_entry and is not
        # listed inside any category — exclude it from the partition check.
        categorizable_ids = {
            e.entry_id for e in self.all_entries
            if _category_for_entry(e) is not None
        }
        self.assertEqual(all_by_category, categorizable_ids,
                         "Categories should partition all non-shortcut entries without overlap or gaps")

    def test_no_entry_in_two_categories(self):
        seen = {}
        for cat in ROOM_TEST_CATEGORIES:
            for entry in load_room_test_entries_for_category(cat):
                if entry.entry_id in seen:
                    self.fail(
                        f"Entry {entry.entry_id!r} appears in both "
                        f"{seen[entry.entry_id]!r} and {cat!r}"
                    )
                seen[entry.entry_id] = cat

    def test_sunken_ruins_category_contains_only_sunken_ruins_entries(self):
        for entry in load_room_test_entries_for_category(ROOM_TEST_CATEGORY_SUNKEN_RUINS):
            self.assertEqual(
                entry.context_label, "Sunken Ruins",
                f"Entry {entry.entry_id!r} has context {entry.context_label!r} in Sunken Ruins category",
            )

    def test_mud_caverns_category_contains_only_mud_caverns_entries(self):
        for entry in load_room_test_entries_for_category(ROOM_TEST_CATEGORY_MUD_CAVERNS):
            self.assertEqual(
                entry.context_label, "Mud Caverns",
                f"Entry {entry.entry_id!r} has context {entry.context_label!r} in Mud Caverns category",
            )

    def test_base_layout_category_contains_only_base_layout_entries(self):
        for entry in load_room_test_entries_for_category(ROOM_TEST_CATEGORY_BASE_LAYOUT):
            self.assertEqual(
                entry.context_label, "Base Layout",
                f"Entry {entry.entry_id!r} has context {entry.context_label!r} in Base Layout category",
            )

    def test_returns_tuple(self):
        result = load_room_test_entries_for_category(ROOM_TEST_CATEGORY_SUNKEN_RUINS)
        self.assertIsInstance(result, tuple)


if __name__ == "__main__":
    unittest.main()
