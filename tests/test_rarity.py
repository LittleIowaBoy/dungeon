"""Tests for the F1 rarity foundation layer."""
import os
import unittest

import pygame

from item_catalog import ITEM_DATABASE, rarity_color, tier_index
from settings import (
    RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE,
    RARITY_SUPERIOR, RARITY_EXQUISITE, RARITY_EXOTIC, RARITY_LEGENDARY,
    RARITY_TIERS, RARITY_COLORS,
)
from shop import SHOP_ITEMS


class RarityConstantsTests(unittest.TestCase):
    def test_rarity_tiers_ordered_low_to_high(self):
        self.assertEqual(
            RARITY_TIERS,
            (RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE,
             RARITY_SUPERIOR, RARITY_EXQUISITE, RARITY_EXOTIC, RARITY_LEGENDARY),
        )

    def test_rarity_colors_covers_all_tiers(self):
        for tier in RARITY_TIERS:
            self.assertIn(tier, RARITY_COLORS)
            r, g, b = RARITY_COLORS[tier]
            self.assertIsInstance(r, int)
            self.assertIsInstance(g, int)
            self.assertIsInstance(b, int)


class ItemCatalogRarityTests(unittest.TestCase):
    def test_every_item_has_valid_rarity(self):
        for item_id, data in ITEM_DATABASE.items():
            rarity = data.get("rarity")
            self.assertIsNotNone(rarity, f"{item_id} missing 'rarity'")
            self.assertIn(rarity, RARITY_TIERS, f"{item_id} has unknown rarity '{rarity}'")

    def test_known_rarity_assignments(self):
        expectations = {
            "sword": RARITY_COMMON,
            "spear": RARITY_COMMON,
            "axe": RARITY_COMMON,
            "hammer": RARITY_COMMON,
            "health_potion_small": RARITY_COMMON,
            "speed_boost": RARITY_COMMON,
            "iron_helmet": RARITY_COMMON,
            "iron_bracers": RARITY_COMMON,
            "traveler_boots": RARITY_COMMON,
            "health_potion_medium": RARITY_UNCOMMON,
            "attack_boost": RARITY_UNCOMMON,
            "armor": RARITY_UNCOMMON,
            "sword_plus": RARITY_UNCOMMON,
            "spear_plus": RARITY_UNCOMMON,
            "axe_plus": RARITY_UNCOMMON,
            "compass": RARITY_UNCOMMON,
            "health_potion_large": RARITY_RARE,
            "golem_crown": RARITY_SUPERIOR,
            "golem_husk": RARITY_SUPERIOR,
            "golem_stride": RARITY_SUPERIOR,
            "golem_fists": RARITY_SUPERIOR,
            "stat_shard": RARITY_EXOTIC,
            "tempo_rune": RARITY_EXOTIC,
            "mobility_charge": RARITY_EXOTIC,
            "prismatic_keystone": RARITY_LEGENDARY,
        }
        for item_id, expected_rarity in expectations.items():
            actual = ITEM_DATABASE[item_id]["rarity"]
            self.assertEqual(actual, expected_rarity, f"{item_id}: expected {expected_rarity}, got {actual}")

    def test_rarity_color_returns_correct_rgb(self):
        self.assertEqual(rarity_color("sword"), RARITY_COLORS[RARITY_COMMON])
        self.assertEqual(rarity_color("golem_crown"), RARITY_COLORS[RARITY_SUPERIOR])
        self.assertEqual(rarity_color("prismatic_keystone"), RARITY_COLORS[RARITY_LEGENDARY])

    def test_tier_index_orders_correctly(self):
        self.assertLess(tier_index("sword"), tier_index("armor"))
        self.assertLess(tier_index("armor"), tier_index("health_potion_large"))
        self.assertLess(tier_index("health_potion_large"), tier_index("golem_crown"))
        self.assertLess(tier_index("golem_crown"), tier_index("stat_shard"))
        self.assertLess(tier_index("stat_shard"), tier_index("prismatic_keystone"))

    def test_tier_index_range(self):
        for item_id in ITEM_DATABASE:
            idx = tier_index(item_id)
            self.assertGreaterEqual(idx, 0)
            self.assertLess(idx, len(RARITY_TIERS))


class ShopSortingTests(unittest.TestCase):
    def test_shop_items_sorted_by_rarity_tier_then_name(self):
        for i in range(len(SHOP_ITEMS) - 1):
            a = SHOP_ITEMS[i]
            b = SHOP_ITEMS[i + 1]
            key_a = (tier_index(a.id), a.name)
            key_b = (tier_index(b.id), b.name)
            self.assertLessEqual(
                key_a, key_b,
                f"Shop order wrong: '{a.id}' ({a.name}) should come before '{b.id}' ({b.name})",
            )

    def test_common_items_before_uncommon_in_shop(self):
        tier_sequence = [tier_index(item.id) for item in SHOP_ITEMS]
        for i in range(len(tier_sequence) - 1):
            self.assertLessEqual(
                tier_sequence[i], tier_sequence[i + 1],
                "Rarity tiers must be non-decreasing in SHOP_ITEMS",
            )


class LootDropRarityBorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((100, 100))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_common_item_no_border_pixel(self):
        """Common items get no border — corner pixel stays the item's icon_color."""
        from items import LootDrop
        drop = LootDrop(50, 50, "health_potion_small")
        # Corner pixel should be the item color (no rarity ring drawn over it)
        icon_color = ITEM_DATABASE["health_potion_small"]["icon_color"]
        corner = drop.image.get_at((0, 0))[:3]
        self.assertEqual(corner, icon_color)

    def test_non_common_item_has_rarity_border(self):
        """Superior items (golem_crown can_loot=False, but we test via LootDrop directly)."""
        from items import LootDrop
        # Use attack_boost (uncommon, can_loot=True) as the test subject
        drop = LootDrop(50, 50, "attack_boost")
        expected_border = RARITY_COLORS[RARITY_UNCOMMON]
        # The 2px rect border sets the top edge; check top-left and top-right
        top_left = drop.image.get_at((0, 0))[:3]
        self.assertEqual(top_left, expected_border)
