"""Tests for the post-run shop, focused on biome trophy exchange rules."""

import unittest

from progress import PlayerProgress
from settings import BIOME_TROPHY_EXCHANGE_RATIO, BIOME_TROPHY_IDS, BIOME_TROPHY_KEYSTONE_ID
from shop import Shop


class BiomeTrophyExchangeTests(unittest.TestCase):
    def setUp(self):
        self.shop = Shop()
        self.progress = PlayerProgress()

    def test_can_exchange_requires_minimum_surplus_of_source(self):
        self.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO - 1
        self.assertFalse(
            self.shop.can_exchange_trophy("stat_shard", "tempo_rune", self.progress)
        )

    def test_exchange_consumes_ratio_of_source_and_grants_one_target(self):
        self.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO + 1

        self.assertTrue(
            self.shop.exchange_trophy("stat_shard", "tempo_rune", self.progress)
        )

        self.assertEqual(self.progress.inventory["stat_shard"], 1)
        self.assertEqual(self.progress.inventory["tempo_rune"], 1)

    def test_exchange_drains_inventory_entry_when_count_hits_zero(self):
        self.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO

        self.assertTrue(
            self.shop.exchange_trophy("stat_shard", "tempo_rune", self.progress)
        )

        self.assertNotIn("stat_shard", self.progress.inventory)
        self.assertEqual(self.progress.inventory["tempo_rune"], 1)

    def test_exchange_rejects_same_source_and_target(self):
        self.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO

        self.assertFalse(
            self.shop.exchange_trophy("stat_shard", "stat_shard", self.progress)
        )
        self.assertEqual(
            self.progress.inventory["stat_shard"], BIOME_TROPHY_EXCHANGE_RATIO
        )

    def test_exchange_rejects_non_trophy_ids(self):
        self.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO
        self.progress.inventory["health_potion_small"] = 5

        self.assertFalse(
            self.shop.exchange_trophy("stat_shard", "health_potion_small", self.progress)
        )
        self.assertFalse(
            self.shop.exchange_trophy("health_potion_small", "stat_shard", self.progress)
        )

    def test_exchange_blocked_when_target_at_max_owned(self):
        # tempo_rune.max_owned == 5 (item_catalog.py); pre-fill to cap.
        self.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO
        self.progress.inventory["tempo_rune"] = 5

        self.assertFalse(
            self.shop.exchange_trophy("stat_shard", "tempo_rune", self.progress)
        )
        self.assertEqual(
            self.progress.inventory["stat_shard"], BIOME_TROPHY_EXCHANGE_RATIO
        )
        self.assertEqual(self.progress.inventory["tempo_rune"], 5)

    def test_best_trophy_source_picks_largest_exchangeable_stack(self):
        self.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO
        self.progress.inventory["mobility_charge"] = BIOME_TROPHY_EXCHANGE_RATIO + 2

        self.assertEqual(
            self.shop.best_trophy_source_for("tempo_rune", self.progress),
            "mobility_charge",
        )

    def test_best_trophy_source_returns_none_when_no_surplus(self):
        self.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO - 1
        self.assertIsNone(
            self.shop.best_trophy_source_for("tempo_rune", self.progress)
        )

    def test_best_trophy_source_excludes_target(self):
        # Even with a huge stack of the target, it must not be its own source.
        self.progress.inventory["tempo_rune"] = 10
        self.assertIsNone(
            self.shop.best_trophy_source_for("tempo_rune", self.progress)
        )


class PrismaticKeystoneCraftTests(unittest.TestCase):
    def setUp(self):
        self.shop = Shop()
        self.progress = PlayerProgress()

    def _stock_one_of_each(self):
        for trophy_id in BIOME_TROPHY_IDS:
            self.progress.inventory[trophy_id] = 1

    def test_can_craft_requires_one_of_each_trophy(self):
        self.assertFalse(self.shop.can_craft_keystone(self.progress))
        self._stock_one_of_each()
        self.assertTrue(self.shop.can_craft_keystone(self.progress))

    def test_can_craft_false_when_any_trophy_missing(self):
        self._stock_one_of_each()
        del self.progress.inventory["tempo_rune"]
        self.assertFalse(self.shop.can_craft_keystone(self.progress))

    def test_craft_consumes_one_of_each_and_grants_one_keystone(self):
        self._stock_one_of_each()

        self.assertTrue(self.shop.craft_keystone(self.progress))

        for trophy_id in BIOME_TROPHY_IDS:
            self.assertNotIn(trophy_id, self.progress.inventory)
        # Crafted keystones land on the persistent meta counter, NOT inventory.
        self.assertNotIn(BIOME_TROPHY_KEYSTONE_ID, self.progress.inventory)
        self.assertEqual(self.progress.meta_keystones, 1)

    def test_craft_preserves_extra_trophies_above_one(self):
        for trophy_id in BIOME_TROPHY_IDS:
            self.progress.inventory[trophy_id] = 3

        self.assertTrue(self.shop.craft_keystone(self.progress))

        for trophy_id in BIOME_TROPHY_IDS:
            self.assertEqual(self.progress.inventory[trophy_id], 2)
        self.assertEqual(self.progress.meta_keystones, 1)

    def test_craft_blocked_when_keystone_at_max_owned(self):
        self._stock_one_of_each()
        self.progress.meta_keystones = 3  # KEYSTONE_MAX_OWNED

        self.assertFalse(self.shop.can_craft_keystone(self.progress))
        self.assertFalse(self.shop.craft_keystone(self.progress))
        for trophy_id in BIOME_TROPHY_IDS:
            self.assertEqual(self.progress.inventory[trophy_id], 1)
        self.assertEqual(self.progress.meta_keystones, 3)


if __name__ == "__main__":
    unittest.main()
