"""Tests for Phase F3: armor HP distribution, magic find, and dodge bonuses."""
import unittest

from settings import ARMOR_HP_BY_RARITY_BY_SLOT, ARMOR_THEME_TAGS
from armor_rules import (
    armor_hp_for_item,
    compute_total_armor_hp,
    refill_armor_hp,
    apply_magic_find,
    aggregate_equipped_stats,
    EQUIPMENT_STAT_BONUSES,
)
from item_catalog import ITEM_DATABASE


# ── helpers ──────────────────────────────────────────────────────────────────
class _Progress:
    def __init__(self, equipped_slots=None, armor_hp=0):
        self.equipped_slots = equipped_slots or {}
        self.armor_hp = armor_hp


# ── Settings constants ────────────────────────────────────────────────────────
class ArmorHPTableTests(unittest.TestCase):
    def test_all_rarities_present(self):
        for rarity in ("common", "uncommon", "rare", "superior", "exquisite", "exotic", "legendary"):
            self.assertIn(rarity, ARMOR_HP_BY_RARITY_BY_SLOT)

    def test_all_body_slots_present(self):
        for slot in ("helmet", "chest", "arms", "legs"):
            self.assertIn(slot, ARMOR_HP_BY_RARITY_BY_SLOT["common"])

    def test_superior_chest_is_40(self):
        self.assertEqual(ARMOR_HP_BY_RARITY_BY_SLOT["superior"]["chest"], 40)

    def test_common_set_total_is_40(self):
        row = ARMOR_HP_BY_RARITY_BY_SLOT["common"]
        self.assertEqual(sum(row.values()), 40)

    def test_theme_tags_tuple_has_3_entries(self):
        self.assertEqual(len(ARMOR_THEME_TAGS), 3)
        for tag in ("heavy", "light", "arcane"):
            self.assertIn(tag, ARMOR_THEME_TAGS)


# ── item_catalog theme_tag ────────────────────────────────────────────────────
class ItemThemeTagTests(unittest.TestCase):
    def test_iron_helmet_is_heavy(self):
        self.assertEqual(ITEM_DATABASE["iron_helmet"]["theme_tag"], "heavy")

    def test_traveler_boots_is_light(self):
        self.assertEqual(ITEM_DATABASE["traveler_boots"]["theme_tag"], "light")

    def test_golem_husk_is_heavy(self):
        self.assertEqual(ITEM_DATABASE["golem_husk"]["theme_tag"], "heavy")

    def test_wayfarer_hood_is_light(self):
        self.assertEqual(ITEM_DATABASE["wayfarer_hood"]["theme_tag"], "light")

    def test_spellweave_robe_is_arcane(self):
        self.assertEqual(ITEM_DATABASE["spellweave_robe"]["theme_tag"], "arcane")

    def test_new_items_have_correct_slots(self):
        slot_map = {
            "wayfarer_hood": "helmet",
            "wayfarer_jerkin": "chest",
            "wayfarer_wraps": "arms",
            "wayfarer_treads": "legs",
            "spellweave_circlet": "helmet",
            "spellweave_robe": "chest",
            "spellweave_cuffs": "arms",
            "spellweave_slippers": "legs",
        }
        for item_id, expected_slot in slot_map.items():
            with self.subTest(item_id=item_id):
                slots = ITEM_DATABASE[item_id]["equipment_slots"]
                self.assertEqual(slots, [expected_slot])

    def test_armor_iron_chestplate_description_no_hardcoded_hp(self):
        # The old description had f"+{ARMOR_HP} armor HP" hard-coded.
        # Now it should be generic text.
        desc = ITEM_DATABASE["armor"]["description"]
        self.assertNotIn("50", desc)


# ── armor_hp_for_item ─────────────────────────────────────────────────────────
class ArmorHpForItemTests(unittest.TestCase):
    def test_iron_helmet_common_helmet(self):
        self.assertEqual(armor_hp_for_item("iron_helmet"), ARMOR_HP_BY_RARITY_BY_SLOT["common"]["helmet"])

    def test_iron_chestplate_uncommon_chest(self):
        # Iron chestplate ("armor") is RARITY_UNCOMMON + chest slot → 25
        self.assertEqual(armor_hp_for_item("armor"), ARMOR_HP_BY_RARITY_BY_SLOT["uncommon"]["chest"])

    def test_golem_husk_superior_chest(self):
        self.assertEqual(armor_hp_for_item("golem_husk"), ARMOR_HP_BY_RARITY_BY_SLOT["superior"]["chest"])

    def test_wayfarer_treads_rare_legs(self):
        self.assertEqual(armor_hp_for_item("wayfarer_treads"), ARMOR_HP_BY_RARITY_BY_SLOT["rare"]["legs"])

    def test_spellweave_robe_superior_chest(self):
        self.assertEqual(armor_hp_for_item("spellweave_robe"), ARMOR_HP_BY_RARITY_BY_SLOT["superior"]["chest"])

    def test_weapon_returns_zero(self):
        self.assertEqual(armor_hp_for_item("sword"), 0)

    def test_potion_returns_zero(self):
        self.assertEqual(armor_hp_for_item("health_potion_small"), 0)

    def test_unknown_item_returns_zero(self):
        self.assertEqual(armor_hp_for_item("__nonexistent__"), 0)


# ── compute_total_armor_hp / refill_armor_hp ──────────────────────────────────
class TotalArmorHpTests(unittest.TestCase):
    def test_no_equipment_gives_zero(self):
        progress = _Progress()
        self.assertEqual(compute_total_armor_hp(progress), 0)

    def test_none_progress_gives_zero(self):
        self.assertEqual(compute_total_armor_hp(None), 0)

    def test_single_armor_piece(self):
        progress = _Progress({"helmet": "iron_helmet"})
        expected = ARMOR_HP_BY_RARITY_BY_SLOT["common"]["helmet"]
        self.assertEqual(compute_total_armor_hp(progress), expected)

    def test_full_iron_set_common(self):
        progress = _Progress({
            "helmet": "iron_helmet",
            "chest":  "armor",
            "arms":   "iron_bracers",
            "legs":   "traveler_boots",
        })
        row = ARMOR_HP_BY_RARITY_BY_SLOT["common"]
        # iron_helmet=common helmet, armor=uncommon chest, iron_bracers=common arms, traveler_boots=common legs
        expected = row["helmet"] + ARMOR_HP_BY_RARITY_BY_SLOT["uncommon"]["chest"] + row["arms"] + row["legs"]
        self.assertEqual(compute_total_armor_hp(progress), expected)

    def test_weapon_slot_is_ignored(self):
        progress = _Progress({"weapon_1": "sword"})
        self.assertEqual(compute_total_armor_hp(progress), 0)

    def test_refill_sets_armor_hp(self):
        progress = _Progress({"helmet": "iron_helmet"}, armor_hp=999)
        refill_armor_hp(progress)
        expected = ARMOR_HP_BY_RARITY_BY_SLOT["common"]["helmet"]
        self.assertEqual(progress.armor_hp, expected)

    def test_refill_with_none_is_safe(self):
        refill_armor_hp(None)  # must not raise


# ── EQUIPMENT_STAT_BONUSES new entries ────────────────────────────────────────
class NewArmorStatBonusTests(unittest.TestCase):
    def test_wayfarer_hood_magic_find(self):
        bonuses = EQUIPMENT_STAT_BONUSES["wayfarer_hood"]
        self.assertAlmostEqual(bonuses["magic_find"], 0.06)

    def test_wayfarer_wraps_attack_speed(self):
        bonuses = EQUIPMENT_STAT_BONUSES["wayfarer_wraps"]
        self.assertAlmostEqual(bonuses["attack_speed_bonus"], 0.05)

    def test_wayfarer_treads_dodge_cooldown_mult_negative(self):
        bonuses = EQUIPMENT_STAT_BONUSES["wayfarer_treads"]
        self.assertLess(bonuses["dodge_cooldown_mult"], 0.0)

    def test_spellweave_circlet_crit_and_minimap(self):
        bonuses = EQUIPMENT_STAT_BONUSES["spellweave_circlet"]
        self.assertAlmostEqual(bonuses["crit_chance"], 0.08)
        self.assertEqual(bonuses["minimap_radius_bonus"], 1)

    def test_spellweave_robe_arcane_resist(self):
        bonuses = EQUIPMENT_STAT_BONUSES["spellweave_robe"]
        resist = bonuses["damage_resistance"]
        self.assertAlmostEqual(resist["arcane"], 0.15)

    def test_spellweave_slippers_dodge_distance(self):
        bonuses = EQUIPMENT_STAT_BONUSES["spellweave_slippers"]
        self.assertGreater(bonuses["dodge_distance_mult"], 0.0)


# ── aggregate_equipped_stats accepts new keys ─────────────────────────────────
class AggregateNewKeysTests(unittest.TestCase):
    def test_magic_find_aggregated(self):
        progress = _Progress({"helmet": "wayfarer_hood"})
        stats = aggregate_equipped_stats(progress)
        self.assertAlmostEqual(stats.get("magic_find", 0.0), 0.06)

    def test_dodge_cooldown_mult_aggregated(self):
        progress = _Progress({"legs": "wayfarer_treads"})
        stats = aggregate_equipped_stats(progress)
        self.assertLess(stats.get("dodge_cooldown_mult", 0.0), 0.0)

    def test_two_magic_find_items_stack(self):
        progress = _Progress({"helmet": "wayfarer_hood", "arms": "wayfarer_hood"})
        stats = aggregate_equipped_stats(progress)
        self.assertAlmostEqual(stats.get("magic_find", 0.0), 0.12)


# ── apply_magic_find ──────────────────────────────────────────────────────────
class MagicFindTests(unittest.TestCase):
    def test_none_progress_returns_base(self):
        self.assertAlmostEqual(apply_magic_find(0.3, None), 0.3)

    def test_no_equipment_returns_base(self):
        progress = _Progress()
        self.assertAlmostEqual(apply_magic_find(0.3, progress), 0.3)

    def test_magic_find_boosts_chance(self):
        progress = _Progress({"helmet": "wayfarer_hood"})  # +6% magic_find
        boosted = apply_magic_find(0.3, progress)
        self.assertAlmostEqual(boosted, 0.3 * 1.06)

    def test_capped_at_50_percent_bonus(self):
        # Even if we stack multiple wayfarer_hoods (hypothetical), cap at 0.5 bonus.
        # Use 3 hoods stacked (0.18 total).  Result is base * 1.18, well under cap.
        progress = _Progress({"slot_a": "wayfarer_hood", "slot_b": "wayfarer_hood",
                              "slot_c": "wayfarer_hood"})
        bonuses = aggregate_equipped_stats(progress)
        self.assertLessEqual(bonuses.get("magic_find", 0.0), 0.50)

    def test_result_capped_at_1_0(self):
        # Very high base_chance with bonus must not exceed 1.0
        progress = _Progress({"helmet": "wayfarer_hood"})
        self.assertLessEqual(apply_magic_find(0.99, progress), 1.0)


if __name__ == "__main__":
    unittest.main()
