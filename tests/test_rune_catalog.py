"""Tests for the rune catalog: registry integrity and category/rarity filters."""

import unittest

from rune_catalog import (
    RUNE_CATEGORIES,
    RUNE_CATEGORY_BEHAVIOR,
    RUNE_CATEGORY_IDENTITY,
    RUNE_CATEGORY_STAT,
    RUNE_DATABASE,
    RUNE_SLOT_CAPACITY,
    RuneDefinition,
    all_runes,
    get_rune,
    runes_by_category,
    runes_by_rarity,
)


class RuneCatalogStructureTests(unittest.TestCase):
    def test_every_entry_is_a_rune_definition_keyed_by_its_own_id(self):
        for rune_id, rune in RUNE_DATABASE.items():
            self.assertIsInstance(rune, RuneDefinition)
            self.assertEqual(rune.rune_id, rune_id)

    def test_every_rune_has_required_text_fields_populated(self):
        for rune in RUNE_DATABASE.values():
            self.assertTrue(rune.name, f"{rune.rune_id} missing name")
            self.assertTrue(rune.bonus_text, f"{rune.rune_id} missing bonus_text")
            self.assertTrue(
                rune.tradeoff_text,
                f"{rune.rune_id} missing tradeoff_text",
            )

    def test_every_rune_uses_a_known_category(self):
        for rune in RUNE_DATABASE.values():
            self.assertIn(rune.category, RUNE_CATEGORIES)

    def test_rune_ids_are_unique(self):
        ids = [rune.rune_id for rune in all_runes()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_get_rune_returns_none_for_unknown_id(self):
        self.assertIsNone(get_rune("not_a_real_rune"))


class RuneCatalogCompositionTests(unittest.TestCase):
    def test_each_category_has_at_least_one_rune(self):
        for category in RUNE_CATEGORIES:
            self.assertGreater(len(runes_by_category(category)), 0)

    def test_stat_runes_meet_minimum_count_for_altar_offers(self):
        # altar offers up to 3 distinct runes; we need a healthy pool.
        self.assertGreaterEqual(len(runes_by_category(RUNE_CATEGORY_STAT)), 12)
        self.assertGreaterEqual(
            len(runes_by_category(RUNE_CATEGORY_BEHAVIOR)),
            6,
        )
        self.assertGreaterEqual(
            len(runes_by_category(RUNE_CATEGORY_IDENTITY)),
            3,
        )

    def test_rarity_filter_returns_only_matching_runes(self):
        for rune in runes_by_rarity("legendary"):
            self.assertEqual(rune.rarity, "legendary")

    def test_slot_capacity_table_covers_every_category(self):
        for category in RUNE_CATEGORIES:
            self.assertIn(category, RUNE_SLOT_CAPACITY)
            self.assertGreater(RUNE_SLOT_CAPACITY[category], 0)


if __name__ == "__main__":
    unittest.main()
