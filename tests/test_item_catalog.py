import os
import unittest

import pygame

from item_catalog import (
    CHEST_CONTENT_ENTRIES,
    CHEST_CONTENT_WEIGHTS,
    ITEM_DATABASE,
    CHEST_LOOT_IDS,
    CHEST_LOOT_WEIGHTS,
    ENEMY_LOOT_IDS,
    ENEMY_LOOT_WEIGHTS,
)
from items import LootDrop
from shop import SHOP_ITEMS


class ItemCatalogSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_enemy_loot_tables_match_catalog(self):
        expected = [
            (item_id, data["drop_weight"])
            for item_id, data in ITEM_DATABASE.items()
            if data["can_loot"] and data["drop_weight"] > 0
        ]

        self.assertEqual(ENEMY_LOOT_IDS, [item_id for item_id, _weight in expected])
        self.assertEqual(ENEMY_LOOT_WEIGHTS, [weight for _item_id, weight in expected])

    def test_shop_catalog_stays_backed_by_item_database(self):
        purchaseable_ids = sorted(
            item_id
            for item_id, data in ITEM_DATABASE.items()
            if data["can_purchase"]
        )

        self.assertEqual(sorted(item.id for item in SHOP_ITEMS), purchaseable_ids)

    def test_chest_loot_tables_match_catalog(self):
        expected = [
            (item_id, data["chest_drop_weight"])
            for item_id, data in ITEM_DATABASE.items()
            if data["chest_drop_weight"] > 0
        ]

        self.assertEqual(CHEST_LOOT_IDS, [item_id for item_id, _weight in expected])
        self.assertEqual(CHEST_LOOT_WEIGHTS, [weight for _item_id, weight in expected])

    def test_chest_content_table_keeps_coin_entry_and_catalog_loot_entries(self):
        self.assertIn(("coin", None), CHEST_CONTENT_ENTRIES)
        loot_entries = {
            item_id
            for entry_kind, item_id in CHEST_CONTENT_ENTRIES
            if entry_kind == "loot"
        }

        self.assertEqual(loot_entries, set(CHEST_LOOT_IDS))
        self.assertAlmostEqual(sum(CHEST_CONTENT_WEIGHTS), 1.0)

    def test_loot_drop_uses_item_catalog_metadata(self):
        drop = LootDrop(10, 20, "health_potion_small")

        self.assertEqual(drop.max_owned, ITEM_DATABASE["health_potion_small"]["max_owned"])
        self.assertEqual(drop.color, ITEM_DATABASE["health_potion_small"]["icon_color"])

    def test_biome_reward_items_are_loot_only_and_excluded_from_random_chest_table(self):
        for item_id in ("stat_shard", "tempo_rune", "mobility_charge"):
            data = ITEM_DATABASE[item_id]
            self.assertEqual(data["category"], "biome_reward")
            self.assertFalse(data["can_purchase"], f"{item_id} should not be purchasable")
            self.assertFalse(data["can_loot"], f"{item_id} should not drop from enemies")
            self.assertEqual(data["chest_drop_weight"], 0, f"{item_id} should not appear in random chest rolls")
            self.assertEqual(data["drop_weight"], 0)
            self.assertNotIn(item_id, CHEST_LOOT_IDS)
            self.assertGreaterEqual(data["max_owned"], 1)


if __name__ == "__main__":
    unittest.main()