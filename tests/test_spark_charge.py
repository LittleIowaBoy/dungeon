"""Tests for F7: spark_charge consumable."""
import unittest
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import item_catalog
import consumable_rules
import dodge_rules
from settings import (
    SPARK_CHARGE_DURATION_MS,
    SPARK_CHARGE_COOLDOWN_MULT,
    SPARK_CHARGE_MAX,
)
from dodge_rules import DODGE_COOLDOWN_MS


# ── Helpers ──────────────────────────────────────────────────────────────────

def _progress(inventory=None):
    p = MagicMock()
    p.inventory = inventory or {}
    return p


def _player(inventory=None, spark_until=0, dodge_cooldown_until=0, progress=None):
    pl = MagicMock()
    pl.progress = progress or _progress(inventory)
    pl.spark_until = spark_until
    pl.dodge_cooldown_until = dodge_cooldown_until
    # dodge fields required by trigger_dodge
    pl.bonus_dodges_remaining = 0
    pl.dodge_until = 0
    pl.facing_dx = 1.0
    pl.facing_dy = 0.0
    return pl


# ── Catalog tests ─────────────────────────────────────────────────────────────

class SparkChargeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.item = item_catalog.ITEM_DATABASE["spark_charge"]

    def test_item_exists(self):
        self.assertIn("spark_charge", item_catalog.ITEM_DATABASE)

    def test_category_boost(self):
        self.assertEqual(self.item["category"], "boost")

    def test_max_owned(self):
        self.assertEqual(self.item["max_owned"], SPARK_CHARGE_MAX)

    def test_can_purchase(self):
        self.assertTrue(self.item["can_purchase"])

    def test_can_loot(self):
        self.assertTrue(self.item["can_loot"])

    def test_drop_weight_positive(self):
        self.assertGreater(self.item["drop_weight"], 0)

    def test_chest_drop_weight_positive(self):
        self.assertGreater(self.item["chest_drop_weight"], 0)

    def test_cost_is_25(self):
        self.assertEqual(self.item["cost"], 25)

    def test_rarity_uncommon(self):
        from settings import RARITY_UNCOMMON
        self.assertEqual(self.item["rarity"], RARITY_UNCOMMON)


# ── Settings constants ────────────────────────────────────────────────────────

class SparkChargeConstantsTests(unittest.TestCase):
    def test_duration_12_seconds(self):
        self.assertEqual(SPARK_CHARGE_DURATION_MS, 12_000)

    def test_cooldown_mult_0_4(self):
        self.assertAlmostEqual(SPARK_CHARGE_COOLDOWN_MULT, 0.4)

    def test_max_2(self):
        self.assertEqual(SPARK_CHARGE_MAX, 2)


# ── use_spark_charge ──────────────────────────────────────────────────────────

class UseSparkChargeTests(unittest.TestCase):
    def test_no_stock_returns_false(self):
        pl = _player(inventory={})
        result = consumable_rules.use_spark_charge(pl, 1000)
        self.assertFalse(result)

    def test_no_progress_returns_false(self):
        pl = _player()
        pl.progress = None
        result = consumable_rules.use_spark_charge(pl, 1000)
        self.assertFalse(result)

    def test_consumes_one_charge(self):
        pl = _player(inventory={"spark_charge": 2})
        consumable_rules.use_spark_charge(pl, 1000)
        self.assertEqual(pl.progress.inventory.get("spark_charge", 0), 1)

    def test_sets_spark_until(self):
        now = 5000
        pl = _player(inventory={"spark_charge": 1})
        consumable_rules.use_spark_charge(pl, now)
        self.assertEqual(pl.spark_until, now + SPARK_CHARGE_DURATION_MS)

    def test_extends_existing_spark_until(self):
        """Using a second charge while active extends the timer."""
        now = 1000
        future = now + 5000
        pl = _player(inventory={"spark_charge": 1}, spark_until=future)
        consumable_rules.use_spark_charge(pl, now)
        self.assertEqual(pl.spark_until, now + SPARK_CHARGE_DURATION_MS)

    def test_returns_true_on_success(self):
        pl = _player(inventory={"spark_charge": 1})
        result = consumable_rules.use_spark_charge(pl, 0)
        self.assertTrue(result)

    def test_shortens_in_flight_cooldown(self):
        now = 1000
        remaining = 1200  # ms left on cooldown
        pl = _player(
            inventory={"spark_charge": 1},
            dodge_cooldown_until=now + remaining,
        )
        consumable_rules.use_spark_charge(pl, now)
        expected = now + int(remaining * SPARK_CHARGE_COOLDOWN_MULT)
        self.assertEqual(pl.dodge_cooldown_until, expected)

    def test_no_cooldown_active_leaves_zero(self):
        """If not on cooldown, dodge_cooldown_until stays 0."""
        now = 1000
        pl = _player(inventory={"spark_charge": 1}, dodge_cooldown_until=0)
        consumable_rules.use_spark_charge(pl, now)
        self.assertEqual(pl.dodge_cooldown_until, 0)

    def test_expired_cooldown_not_modified(self):
        """If cooldown_until is in the past, it should not be modified."""
        now = 5000
        pl = _player(
            inventory={"spark_charge": 1},
            dodge_cooldown_until=now - 100,  # already expired
        )
        consumable_rules.use_spark_charge(pl, now)
        self.assertEqual(pl.dodge_cooldown_until, now - 100)


# ── reset_runtime_consumables initialises spark_until ─────────────────────────

class ResetRuntimeConsumablesTests(unittest.TestCase):
    def test_spark_until_initialised_to_zero(self):
        pl = _player()
        pl.spark_until = 9999
        consumable_rules.reset_runtime_consumables(pl)
        self.assertEqual(pl.spark_until, 0)


# ── dodge_rules spark cooldown multiplier ─────────────────────────────────────

class DodgeSparkMultiplierTests(unittest.TestCase):
    def _trigger(self, player, now=1000, **kwargs):
        """Call trigger_dodge with stat_rune stubs patched."""
        import unittest.mock as mock
        with mock.patch("stat_runes.dodge_cooldown_ms", side_effect=lambda p, ms: ms), \
             mock.patch("stat_runes.can_dodge", return_value=True), \
             mock.patch("stat_runes.dodge_grants_pass_through", return_value=False):
            return dodge_rules.trigger_dodge(player, now, **kwargs)

    def test_spark_active_reduces_cooldown_set(self):
        now = 1000
        pl = _player(spark_until=now + 10_000)  # spark active
        pl.dodge_cooldown_until = 0
        pl.bonus_dodges_remaining = 0
        pl.dodge_until = 0
        pl.facing_dx = 1.0
        pl.facing_dy = 0.0
        self._trigger(pl, now=now)
        # cooldown_until = now + DODGE_DURATION_MS + cooldown_ms
        # cooldown_ms = DODGE_COOLDOWN_MS * SPARK_CHARGE_COOLDOWN_MULT
        from dodge_rules import DODGE_DURATION_MS
        expected_cooldown = int(DODGE_COOLDOWN_MS * SPARK_CHARGE_COOLDOWN_MULT)
        expected_until = now + DODGE_DURATION_MS + expected_cooldown
        self.assertEqual(pl.dodge_cooldown_until, expected_until)

    def test_no_spark_uses_full_cooldown(self):
        now = 1000
        pl = _player(spark_until=0)  # spark inactive
        pl.dodge_cooldown_until = 0
        pl.bonus_dodges_remaining = 0
        pl.dodge_until = 0
        pl.facing_dx = 1.0
        pl.facing_dy = 0.0
        self._trigger(pl, now=now)
        from dodge_rules import DODGE_DURATION_MS
        expected_until = now + DODGE_DURATION_MS + DODGE_COOLDOWN_MS
        self.assertEqual(pl.dodge_cooldown_until, expected_until)

    def test_expired_spark_uses_full_cooldown(self):
        now = 5000
        pl = _player(spark_until=100)  # spark expired
        pl.dodge_cooldown_until = 0
        pl.bonus_dodges_remaining = 0
        pl.dodge_until = 0
        pl.facing_dx = 1.0
        pl.facing_dy = 0.0
        self._trigger(pl, now=now)
        from dodge_rules import DODGE_DURATION_MS
        expected_until = now + DODGE_DURATION_MS + DODGE_COOLDOWN_MS
        self.assertEqual(pl.dodge_cooldown_until, expected_until)


# ── HUD view ─────────────────────────────────────────────────────────────────

class SparkChargeHUDViewTests(unittest.TestCase):
    def _build_view(self, player):
        import hud_view
        return hud_view._build_quick_bar_view(player)

    def _player_with_spark(self, count):
        import consumable_rules as cr
        pl = MagicMock()
        pl.progress = MagicMock()
        pl.progress.inventory = {"spark_charge": count}
        pl.selected_potion_size = cr.DEFAULT_POTION_SIZE
        pl.compass_uses = 0
        return pl

    def test_spark_count_in_quickbar_view(self):
        pl = self._player_with_spark(2)
        view = self._build_view(pl)
        self.assertEqual(view.spark_charge_count, 2)

    def test_zero_spark_count_when_none(self):
        pl = self._player_with_spark(0)
        view = self._build_view(pl)
        self.assertEqual(view.spark_charge_count, 0)

    def test_active_spark_in_effects(self):
        import hud_view
        pl = MagicMock()
        now = 1000
        pl.speed_boost_until = 0
        pl.attack_boost_until = 0
        pl.spark_until = now + 8000
        effects = hud_view._build_active_effects(pl, now)
        kinds = [e.kind for e in effects]
        self.assertIn("spark", kinds)

    def test_no_active_spark_when_expired(self):
        import hud_view
        pl = MagicMock()
        now = 5000
        pl.speed_boost_until = 0
        pl.attack_boost_until = 0
        pl.spark_until = 100  # expired
        effects = hud_view._build_active_effects(pl, now)
        kinds = [e.kind for e in effects]
        self.assertNotIn("spark", kinds)

    def test_active_spark_seconds_remaining(self):
        import hud_view
        pl = MagicMock()
        now = 1000
        pl.speed_boost_until = 0
        pl.attack_boost_until = 0
        pl.spark_until = now + 6000
        effects = hud_view._build_active_effects(pl, now)
        spark_effect = next(e for e in effects if e.kind == "spark")
        self.assertAlmostEqual(spark_effect.seconds_remaining, 6.0)


if __name__ == "__main__":
    unittest.main()
