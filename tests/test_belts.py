"""Tests for Phase F6: Belts — slot, catalog, theme-keyed per-piece bonuses."""
import unittest
from types import SimpleNamespace

from item_catalog import (
    EQUIPMENT_SLOTS,
    ITEM_DATABASE,
    DEFAULT_EQUIPPED_SLOTS,
)
from armor_rules import (
    aggregate_equipped_stats,
    aggregate_damage_resistances,
    total_damage_resistance,
    _belt_bonus_stats,
    _count_armor_pieces_with_theme,
    BELT_PER_PIECE_BONUSES,
)


# ── helpers ───────────────────────────────────────────────────────────────────
def _equipped(**kwargs):
    """Build a minimal equipped_slots dict for testing."""
    slots = dict(DEFAULT_EQUIPPED_SLOTS)
    slots.update(kwargs)
    return slots


def _progress(equipped=None):
    return SimpleNamespace(equipped_slots=equipped or dict(DEFAULT_EQUIPPED_SLOTS))


# ── Belt slot registration ────────────────────────────────────────────────────
class BeltSlotTests(unittest.TestCase):
    def test_belt_in_equipment_slots(self):
        self.assertIn("belt", EQUIPMENT_SLOTS)

    def test_belt_in_default_equipped_slots(self):
        self.assertIn("belt", DEFAULT_EQUIPPED_SLOTS)
        self.assertIsNone(DEFAULT_EQUIPPED_SLOTS["belt"])


# ── Belt items in ITEM_DATABASE ───────────────────────────────────────────────
class BeltCatalogTests(unittest.TestCase):
    BELT_IDS = ("leather_strap", "bulwark_belt", "runner_sash", "mage_cord", "phoenix_girdle")

    def test_all_belt_items_exist(self):
        for bid in self.BELT_IDS:
            with self.subTest(bid=bid):
                self.assertIn(bid, ITEM_DATABASE)

    def test_all_belts_equippable_in_belt_slot(self):
        for bid in self.BELT_IDS:
            with self.subTest(bid=bid):
                slots = ITEM_DATABASE[bid].get("equipment_slots", [])
                self.assertEqual(slots, ["belt"])

    def test_all_belts_accessory_category(self):
        for bid in self.BELT_IDS:
            with self.subTest(bid=bid):
                self.assertEqual(ITEM_DATABASE[bid].get("category"), "accessory")

    def test_belt_theme_match_fields(self):
        from settings import RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE, RARITY_EXOTIC
        expected_themes = {
            "leather_strap": None,
            "bulwark_belt": "heavy",
            "runner_sash": "light",
            "mage_cord": "arcane",
            "phoenix_girdle": "heavy",
        }
        for bid, theme in expected_themes.items():
            with self.subTest(bid=bid):
                self.assertEqual(ITEM_DATABASE[bid].get("theme_match"), theme)

    def test_belt_rarities(self):
        from settings import RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE, RARITY_EXOTIC
        expected = {
            "leather_strap": RARITY_COMMON,
            "bulwark_belt": RARITY_UNCOMMON,
            "runner_sash": RARITY_UNCOMMON,
            "mage_cord": RARITY_RARE,
            "phoenix_girdle": RARITY_EXOTIC,
        }
        for bid, rarity in expected.items():
            with self.subTest(bid=bid):
                self.assertEqual(ITEM_DATABASE[bid].get("rarity"), rarity)

    def test_theme_match_normalizer_on_non_belt(self):
        """Non-belt items should have theme_match=None via the normalizer."""
        self.assertIsNone(ITEM_DATABASE["iron_helmet"].get("theme_match"))
        self.assertIsNone(ITEM_DATABASE["band_of_vigor"].get("theme_match"))


# ── _count_armor_pieces_with_theme ───────────────────────────────────────────
class CountThemeTests(unittest.TestCase):
    def test_zero_pieces_empty_slots(self):
        p = _progress(equipped={"helmet": None, "chest": None, "arms": None, "legs": None})
        self.assertEqual(_count_armor_pieces_with_theme(p, "heavy"), 0)

    def test_count_none_theme_counts_all_pieces(self):
        """theme=None (leather_strap) counts any equipped armor."""
        p = _progress(equipped=_equipped(
            helmet="iron_helmet",
            chest="iron_chestplate",
        ))
        self.assertEqual(_count_armor_pieces_with_theme(p, None), 2)

    def test_count_heavy_counts_only_heavy(self):
        p = _progress(equipped=_equipped(
            helmet="iron_helmet",    # heavy
            chest="wayfarer_jerkin", # light — should not count
        ))
        self.assertEqual(_count_armor_pieces_with_theme(p, "heavy"), 1)

    def test_count_light_with_full_wayfarer_set(self):
        p = _progress(equipped=_equipped(
            helmet="wayfarer_hood",
            chest="wayfarer_jerkin",
            arms="wayfarer_wraps",
            legs="wayfarer_treads",
        ))
        self.assertEqual(_count_armor_pieces_with_theme(p, "light"), 4)

    def test_count_arcane_with_spellweave(self):
        p = _progress(equipped=_equipped(
            helmet="spellweave_circlet",
            chest="spellweave_robe",
            arms=None,
            legs=None,
        ))
        self.assertEqual(_count_armor_pieces_with_theme(p, "arcane"), 2)

    def test_weapon_slots_ignored(self):
        """Weapons don't count even though they're equipped."""
        p = _progress(equipped=_equipped(helmet="iron_helmet"))
        # weapon_1/weapon_2 are swords/spears, not armor — must not count
        self.assertEqual(_count_armor_pieces_with_theme(p, None), 1)


# ── _belt_bonus_stats ─────────────────────────────────────────────────────────
class BeltBonusStatsTests(unittest.TestCase):
    def test_no_belt_returns_empty(self):
        p = _progress(equipped=_equipped(belt=None))
        self.assertEqual(_belt_bonus_stats(p), {})

    def test_leather_strap_zero_pieces(self):
        p = _progress(equipped=_equipped(belt="leather_strap"))
        self.assertEqual(_belt_bonus_stats(p), {})

    def test_leather_strap_one_piece(self):
        p = _progress(equipped=_equipped(belt="leather_strap", helmet="iron_helmet"))
        bonus = _belt_bonus_stats(p)
        self.assertEqual(bonus.get("max_hp_bonus"), 2)

    def test_leather_strap_four_pieces(self):
        p = _progress(equipped=_equipped(
            belt="leather_strap",
            helmet="iron_helmet", chest="armor",
            arms="iron_bracers", legs="traveler_boots",
        ))
        bonus = _belt_bonus_stats(p)
        self.assertEqual(bonus.get("max_hp_bonus"), 8)

    def test_bulwark_belt_wrong_theme_zero_bonus(self):
        """bulwark_belt needs heavy armor; light pieces give 0."""
        p = _progress(equipped=_equipped(
            belt="bulwark_belt",
            helmet="wayfarer_hood",  # light
        ))
        self.assertEqual(_belt_bonus_stats(p), {})

    def test_bulwark_belt_two_heavy_pieces(self):
        p = _progress(equipped=_equipped(
            belt="bulwark_belt",
            helmet="iron_helmet",  # heavy
            chest="armor",         # heavy (Iron Chestplate)
        ))
        bonus = _belt_bonus_stats(p)
        self.assertAlmostEqual(bonus.get("damage_reduction"), 0.06)

    def test_runner_sash_two_light_pieces(self):
        p = _progress(equipped=_equipped(
            belt="runner_sash",
            helmet="wayfarer_hood",
            chest="wayfarer_jerkin",
        ))
        bonus = _belt_bonus_stats(p)
        self.assertAlmostEqual(bonus.get("speed_bonus"), 0.06)

    def test_mage_cord_resist_and_magic_find(self):
        p = _progress(equipped=_equipped(
            belt="mage_cord",
            helmet="spellweave_circlet",
            chest="spellweave_robe",
        ))
        bonus = _belt_bonus_stats(p)
        self.assertAlmostEqual(bonus.get("magic_find"), 0.10)
        self.assertAlmostEqual(bonus["damage_resistance"]["arcane"], 0.10)

    def test_phoenix_girdle_scalar_and_resist(self):
        p = _progress(equipped=_equipped(
            belt="phoenix_girdle",
            helmet="iron_helmet",
            chest="armor",         # heavy (Iron Chestplate)
        ))
        bonus = _belt_bonus_stats(p)
        self.assertAlmostEqual(bonus.get("damage_reduction"), 0.10)
        self.assertAlmostEqual(bonus.get("max_hp_bonus"), 4)
        self.assertAlmostEqual(bonus["damage_resistance"]["fire"], 0.08)


# ── aggregate integration ─────────────────────────────────────────────────────
class BeltAggregateIntegrationTests(unittest.TestCase):
    def test_leather_strap_max_hp_in_aggregate(self):
        p = _progress(equipped=_equipped(
            belt="leather_strap",
            helmet="iron_helmet",
            chest="armor",
        ))
        stats = aggregate_equipped_stats(p)
        self.assertGreaterEqual(stats.get("max_hp_bonus", 0), 4)

    def test_bulwark_belt_dr_in_aggregate(self):
        p = _progress(equipped=_equipped(
            belt="bulwark_belt",
            helmet="iron_helmet",
        ))
        stats = aggregate_equipped_stats(p)
        self.assertAlmostEqual(stats.get("damage_reduction", 0.0), 0.03)

    def test_runner_sash_speed_in_aggregate(self):
        p = _progress(equipped=_equipped(
            belt="runner_sash",
            legs="wayfarer_treads",
        ))
        stats = aggregate_equipped_stats(p)
        # wayfarer_treads speed_bonus(0.10) + runner_sash 1×0.03
        self.assertAlmostEqual(stats.get("speed_bonus", 0.0), 0.13)

    def test_mage_cord_resist_in_damage_resistance(self):
        p = _progress(equipped=_equipped(
            belt="mage_cord",
            chest="spellweave_robe",  # arcane, +15% arcane resist via EQUIPMENT_STAT_BONUSES
        ))
        r = total_damage_resistance(p, "arcane")
        # spellweave_robe: 0.15 arcane + mage_cord 1×0.05 arcane = 0.20
        self.assertAlmostEqual(r, 0.20)

    def test_phoenix_girdle_fire_resist_in_damage_resistance(self):
        p = _progress(equipped=_equipped(
            belt="phoenix_girdle",
            helmet="iron_helmet",
        ))
        r = total_damage_resistance(p, "fire")
        self.assertAlmostEqual(r, 0.04)

    def test_no_belt_no_change_to_baseline(self):
        p_no_belt = _progress(equipped=_equipped(belt=None, helmet="iron_helmet"))
        p_with_belt = _progress(equipped=_equipped(belt="leather_strap", helmet="iron_helmet"))
        stats_no = aggregate_equipped_stats(p_no_belt)
        stats_with = aggregate_equipped_stats(p_with_belt)
        self.assertLess(stats_no.get("max_hp_bonus", 0), stats_with.get("max_hp_bonus", 0))
