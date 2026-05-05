"""Tests for Phase F2: damage type plumbing and resistance infrastructure."""
import unittest

from settings import DAMAGE_TYPES, DAMAGE_TYPE_COLORS
from armor_rules import (
    aggregate_damage_resistances,
    total_damage_resistance,
    apply_incoming_damage_multiplier,
    EQUIPMENT_STAT_BONUSES,
)
import damage_feedback


# ── helpers ─────────────────────────────────────────────
class _Progress:
    def __init__(self, equipped_slots=None):
        self.equipped_slots = equipped_slots or {}


class _Player:
    def __init__(self, equipped_slots=None):
        self.progress = _Progress(equipped_slots)


# Temporarily inject a test item into EQUIPMENT_STAT_BONUSES for some tests.
_TEST_ITEM_FIRE   = "_test_fire_resist_item"
_TEST_ITEM_ICE    = "_test_ice_resist_item"
_TEST_ITEM_MULTI  = "_test_multi_resist_item"


def _inject_test_items():
    EQUIPMENT_STAT_BONUSES[_TEST_ITEM_FIRE]  = {"damage_resistance": {"fire": 0.30}}
    EQUIPMENT_STAT_BONUSES[_TEST_ITEM_ICE]   = {"damage_resistance": {"ice":  0.50}}
    EQUIPMENT_STAT_BONUSES[_TEST_ITEM_MULTI] = {
        "damage_resistance": {"fire": 0.40, "lightning": 0.20}
    }


def _remove_test_items():
    EQUIPMENT_STAT_BONUSES.pop(_TEST_ITEM_FIRE, None)
    EQUIPMENT_STAT_BONUSES.pop(_TEST_ITEM_ICE, None)
    EQUIPMENT_STAT_BONUSES.pop(_TEST_ITEM_MULTI, None)


# ── Settings constants tests ─────────────────────────────────────────────────
class DamageTypesConstantsTests(unittest.TestCase):
    def test_damage_types_tuple_has_8_entries(self):
        self.assertEqual(len(DAMAGE_TYPES), 8)

    def test_expected_types_present(self):
        for dtype in ("slash", "pierce", "blunt", "fire", "ice", "poison", "lightning", "arcane"):
            self.assertIn(dtype, DAMAGE_TYPES)

    def test_damage_type_colors_covers_all_types(self):
        for dtype in DAMAGE_TYPES:
            self.assertIn(dtype, DAMAGE_TYPE_COLORS)
            r, g, b = DAMAGE_TYPE_COLORS[dtype]
            for channel in (r, g, b):
                self.assertGreaterEqual(channel, 0)
                self.assertLessEqual(channel, 255)


# ── Resistance aggregation tests ─────────────────────────────────────────────
class DamageResistanceAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _inject_test_items()

    @classmethod
    def tearDownClass(cls):
        _remove_test_items()

    def test_no_equipment_gives_zero_resistance(self):
        progress = _Progress()
        totals = aggregate_damage_resistances(progress)
        self.assertEqual(totals, {})

    def test_single_fire_resist_item(self):
        progress = _Progress({"slot_a": _TEST_ITEM_FIRE})
        totals = aggregate_damage_resistances(progress)
        self.assertAlmostEqual(totals.get("fire", 0.0), 0.30)

    def test_two_fire_resist_items_stack_additively(self):
        # Two slots both with the same fire-resist item.
        progress = _Progress({"slot_a": _TEST_ITEM_FIRE, "slot_b": _TEST_ITEM_FIRE})
        totals = aggregate_damage_resistances(progress)
        self.assertAlmostEqual(totals.get("fire", 0.0), 0.60)

    def test_different_type_items_do_not_cross_contaminate(self):
        progress = _Progress({"slot_a": _TEST_ITEM_FIRE, "slot_b": _TEST_ITEM_ICE})
        totals = aggregate_damage_resistances(progress)
        self.assertAlmostEqual(totals.get("fire", 0.0), 0.30)
        self.assertAlmostEqual(totals.get("ice", 0.0), 0.50)
        self.assertNotIn("lightning", totals)

    def test_none_progress_returns_empty(self):
        totals = aggregate_damage_resistances(None)
        self.assertEqual(totals, {})


# ── total_damage_resistance cap tests ────────────────────────────────────────
class TotalDamageResistanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _inject_test_items()
        # Also add an item that would push fire resistance over the 85% cap.
        EQUIPMENT_STAT_BONUSES["_test_fire_cap"] = {"damage_resistance": {"fire": 0.80}}

    @classmethod
    def tearDownClass(cls):
        _remove_test_items()
        EQUIPMENT_STAT_BONUSES.pop("_test_fire_cap", None)

    def test_resistance_capped_at_85_percent(self):
        # fire 0.30 + 0.80 = 1.10 — should be clamped to 0.85
        progress = _Progress({"slot_a": _TEST_ITEM_FIRE, "slot_b": "_test_fire_cap"})
        result = total_damage_resistance(progress, "fire")
        self.assertAlmostEqual(result, 0.85)

    def test_zero_resistance_for_unequipped_type(self):
        progress = _Progress({"slot_a": _TEST_ITEM_FIRE})
        result = total_damage_resistance(progress, "ice")
        self.assertEqual(result, 0.0)

    def test_none_progress_returns_zero(self):
        result = total_damage_resistance(None, "fire")
        self.assertEqual(result, 0.0)

    def test_resistance_only_applies_to_matching_type(self):
        progress = _Progress({"slot_a": _TEST_ITEM_FIRE})
        self.assertGreater(total_damage_resistance(progress, "fire"), 0.0)
        self.assertEqual(total_damage_resistance(progress, "poison"), 0.0)
        self.assertEqual(total_damage_resistance(progress, "lightning"), 0.0)


# ── apply_incoming_damage_multiplier tests ───────────────────────────────────
class ApplyIncomingDamageMultiplierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _inject_test_items()

    @classmethod
    def tearDownClass(cls):
        _remove_test_items()

    def test_untyped_damage_ignores_type_resistances(self):
        player = _Player({"slot_a": _TEST_ITEM_FIRE})
        # No damage_type supplied → type resistance does not apply.
        result = apply_incoming_damage_multiplier(player, 100, damage_type=None)
        # No flat DR either (test items only have damage_resistance), so result is 100.
        self.assertEqual(result, 100)

    def test_typed_damage_reduces_by_resistance(self):
        player = _Player({"slot_a": _TEST_ITEM_FIRE})  # 30% fire resistance
        result = apply_incoming_damage_multiplier(player, 100, damage_type="fire")
        # 100 * (1 - 0.30) = 70
        self.assertEqual(result, 70)

    def test_wrong_type_resistance_does_not_apply(self):
        player = _Player({"slot_a": _TEST_ITEM_FIRE})  # only fire resist
        result = apply_incoming_damage_multiplier(player, 100, damage_type="ice")
        self.assertEqual(result, 100)

    def test_zero_damage_input_is_zero(self):
        player = _Player({"slot_a": _TEST_ITEM_FIRE})
        self.assertEqual(apply_incoming_damage_multiplier(player, 0, damage_type="fire"), 0)

    def test_negative_damage_input_passthrough(self):
        player = _Player({"slot_a": _TEST_ITEM_FIRE})
        self.assertEqual(apply_incoming_damage_multiplier(player, -5, damage_type="fire"), -5)


# ── Enemy damage_type attribute tests ────────────────────────────────────────
class EnemyDamageTypeAttributeTests(unittest.TestCase):
    def test_enemy_base_class_has_default(self):
        from enemies import Enemy
        self.assertEqual(Enemy.attack_damage_type, "blunt")

    def test_patrol_enemy_is_slash(self):
        from enemies import PatrolEnemy
        self.assertEqual(PatrolEnemy.attack_damage_type, "slash")

    def test_random_enemy_is_pierce(self):
        from enemies import RandomEnemy
        self.assertEqual(RandomEnemy.attack_damage_type, "pierce")

    def test_chaser_enemy_is_slash(self):
        from enemies import ChaserEnemy
        self.assertEqual(ChaserEnemy.attack_damage_type, "slash")

    def test_pulsator_enemy_is_lightning(self):
        from enemies import PulsatorEnemy
        self.assertEqual(PulsatorEnemy.attack_damage_type, "lightning")

    def test_launcher_enemy_is_pierce(self):
        from enemies import LauncherEnemy
        self.assertEqual(LauncherEnemy.attack_damage_type, "pierce")

    def test_sentry_enemy_is_blunt(self):
        from enemies import SentryEnemy
        self.assertEqual(SentryEnemy.attack_damage_type, "blunt")

    def test_golem_is_blunt(self):
        from enemies import Golem
        self.assertEqual(Golem.attack_damage_type, "blunt")

    def test_golem_shard_is_slash(self):
        from enemies import GolemShard
        self.assertEqual(GolemShard.attack_damage_type, "slash")

    def test_water_spirit_is_poison(self):
        from enemies import WaterSpiritEnemy
        self.assertEqual(WaterSpiritEnemy.attack_damage_type, "poison")

    def test_ice_crystal_is_ice(self):
        from enemies import IceCrystalEnemy
        self.assertEqual(IceCrystalEnemy.attack_damage_type, "ice")

    def test_tide_lord_is_ice(self):
        from enemies import TideLord
        self.assertEqual(TideLord.attack_damage_type, "ice")

    def test_launcher_projectile_is_pierce(self):
        from enemies import LauncherProjectile
        self.assertEqual(LauncherProjectile.damage_type, "pierce")

    def test_golem_boulder_is_blunt(self):
        from enemies import GolemBoulderProjectile
        self.assertEqual(GolemBoulderProjectile.damage_type, "blunt")

    def test_water_spirit_projectile_is_poison(self):
        from enemies import WaterSpiritProjectile
        self.assertEqual(WaterSpiritProjectile.damage_type, "poison")

    def test_tide_lord_projectile_is_ice(self):
        from enemies import TideLordProjectile
        self.assertEqual(TideLordProjectile.damage_type, "ice")


# ── Damage number color tests ────────────────────────────────────────────────
class DamageNumberColorTests(unittest.TestCase):
    def setUp(self):
        damage_feedback.reset_all()

    def _entity(self, center=(0, 0)):
        class _E:
            class rect:
                pass
        e = _E()
        e.rect.center = center
        return e

    def test_untyped_damage_gets_white_color(self):
        ent = self._entity()
        damage_feedback.report_damage(ent, 10, now_ticks=100)
        views = damage_feedback.build_damage_number_views(now_ticks=110)
        self.assertEqual(len(views), 1)
        _text, _pos, _age, color = views[0]
        self.assertEqual(color, (255, 255, 255))

    def test_fire_damage_gets_fire_color(self):
        ent = self._entity()
        damage_feedback.report_damage(ent, 10, now_ticks=100, damage_type="fire")
        views = damage_feedback.build_damage_number_views(now_ticks=110)
        _text, _pos, _age, color = views[0]
        self.assertEqual(color, DAMAGE_TYPE_COLORS["fire"])

    def test_lightning_damage_gets_lightning_color(self):
        ent = self._entity()
        damage_feedback.report_damage(ent, 10, now_ticks=100, damage_type="lightning")
        views = damage_feedback.build_damage_number_views(now_ticks=110)
        _text, _pos, _age, color = views[0]
        self.assertEqual(color, DAMAGE_TYPE_COLORS["lightning"])

    def test_coalesce_updates_color_to_latest_hit(self):
        ent = self._entity()
        damage_feedback.report_damage(ent, 5, now_ticks=100, damage_type="fire")
        damage_feedback.report_damage(ent, 5, now_ticks=150, damage_type="ice")
        views = damage_feedback.build_damage_number_views(now_ticks=160)
        self.assertEqual(len(views), 1)
        _text, _pos, _age, color = views[0]
        self.assertEqual(color, DAMAGE_TYPE_COLORS["ice"])


if __name__ == "__main__":
    unittest.main()
