"""Tests for identity-rune effect resolution (identity_runes.py)."""

import unittest
from unittest import mock

import pygame

import combat_rules
import consumable_rules
import identity_runes
import rune_rules
import stat_runes
import status_effects


pygame.init()


class _Player:
    def __init__(self):
        self.equipped_runes = rune_rules.empty_loadout()
        self.rune_state = {"room": {}}
        self.max_hp = 100
        self.current_hp = 100
        self.armor_hp = 0
        self._invincible_until = 0
        self.attack_boost_until = 0
        self.dodge_until = 0
        self.dodge_cooldown_until = 0
        self.statuses = {}
        self.rect = pygame.Rect(0, 0, 32, 32)
        self.progress = None
        self.selected_potion_size = consumable_rules.DEFAULT_POTION_SIZE


class _Progress:
    def __init__(self):
        self.equipped_runes = rune_rules.empty_loadout()
        self.inventory = {}


class _Enemy:
    def __init__(self, x=0, y=0, hp=10):
        self.rect = pygame.Rect(x - 8, y - 8, 16, 16)
        self.current_hp = hp
        self.max_hp = hp
        self.statuses = {}

    def take_damage(self, amount):
        self.current_hp -= amount


def _equip(holder, rune_id):
    rune_rules.equip_rune(holder, rune_id)


# ── pacifist ────────────────────────────────────────────
class PacifistTests(unittest.TestCase):
    def test_zero_outgoing_damage(self):
        p = _Player(); _equip(p, "the_pacifist")
        self.assertEqual(stat_runes.modify_outgoing_damage(p, _Enemy(), 100), 0)

    def test_doubles_speed(self):
        p = _Player(); _equip(p, "the_pacifist")
        self.assertAlmostEqual(stat_runes.modify_speed_multiplier(p, 1.0), 2.0)

    def test_passive_update_sets_enemy_vs_enemy_multiplier(self):
        p = _Player(); _equip(p, "the_pacifist")
        identity_runes.passive_update(p)
        self.assertEqual(p.rune_state["enemy_vs_enemy_multiplier"], 5.0)

    def test_passive_update_clears_when_unequipped(self):
        p = _Player(); _equip(p, "the_pacifist")
        identity_runes.passive_update(p)
        rune_rules.unequip_rune(p, "the_pacifist")
        identity_runes.passive_update(p)
        self.assertEqual(p.rune_state["enemy_vs_enemy_multiplier"], 0.0)

    def test_destroy_on_weapon_pickup(self):
        p = _Player(); pr = _Progress()
        _equip(p, "the_pacifist"); _equip(pr, "the_pacifist")
        self.assertTrue(identity_runes.destroy_pacifist_on_weapon_pickup(p, pr))
        self.assertFalse(rune_rules.has_rune(p, "the_pacifist"))
        self.assertFalse(rune_rules.has_rune(pr, "the_pacifist"))

    def test_destroy_on_weapon_pickup_no_rune(self):
        p = _Player()
        self.assertFalse(identity_runes.destroy_pacifist_on_weapon_pickup(p, None))


# ── glass_soul ──────────────────────────────────────────
class GlassSoulTests(unittest.TestCase):
    def test_max_hp_locked_to_one(self):
        p = _Player(); _equip(p, "glass_soul")
        self.assertEqual(stat_runes.modify_max_hp(p, 100), 1)

    def test_take_damage_grants_iframes_no_hp_loss(self):
        p = _Player(); _equip(p, "glass_soul")
        p.current_hp = 1
        combat_rules.take_damage(p, 10, now_ticks=1000)
        self.assertEqual(p.current_hp, 1)
        self.assertEqual(p._invincible_until, 1000 + identity_runes.GLASS_SOUL_INVINCIBLE_MS)

    def test_take_damage_during_iframes_skipped(self):
        p = _Player(); _equip(p, "glass_soul")
        p.current_hp = 1
        p._invincible_until = 5000
        combat_rules.take_damage(p, 10, now_ticks=1000)
        self.assertEqual(p.current_hp, 1)  # locked at 1, unchanged

    def test_potion_converts_to_attack_speed_buff(self):
        p = _Player(); _equip(p, "glass_soul")
        pr = _Progress(); pr.inventory["health_potion_small"] = 1
        p.progress = pr
        with mock.patch("pygame.time.get_ticks", return_value=1000):
            self.assertTrue(consumable_rules.use_selected_potion(p))
        self.assertEqual(
            p.attack_boost_until,
            1000 + identity_runes.GLASS_SOUL_HEAL_ATK_BUFF_MS,
        )

    def test_stunned_kills_glass_soul(self):
        p = _Player(); _equip(p, "glass_soul")
        p.current_hp = 1
        status_effects.apply_status(p, status_effects.STUNNED, 1000)
        self.assertEqual(p.current_hp, 0)

    def test_stunned_does_not_kill_without_rune(self):
        p = _Player(); p.current_hp = 50
        status_effects.apply_status(p, status_effects.STUNNED, 1000)
        self.assertEqual(p.current_hp, 50)


# ── time_anchor ─────────────────────────────────────────
class TimeAnchorTests(unittest.TestCase):
    def test_standing_fills_meter(self):
        p = _Player(); _equip(p, "time_anchor")
        identity_runes.update_time_anchor(p, 1000, is_moving=False)
        self.assertAlmostEqual(identity_runes.time_anchor_meter(p), 0.25)

    def test_moving_drains_meter(self):
        p = _Player(); _equip(p, "time_anchor")
        identity_runes.update_time_anchor(p, 4000, is_moving=False)  # full
        identity_runes.update_time_anchor(p, 1000, is_moving=True)
        self.assertAlmostEqual(identity_runes.time_anchor_meter(p), 0.5)

    def test_full_meter_fires_freeze_event(self):
        p = _Player(); _equip(p, "time_anchor")
        result = identity_runes.update_time_anchor(p, 4000, is_moving=False)
        self.assertEqual(result, "freeze")

    def test_freeze_only_fires_once_per_fill(self):
        p = _Player(); _equip(p, "time_anchor")
        identity_runes.update_time_anchor(p, 4000, is_moving=False)  # fires
        result = identity_runes.update_time_anchor(p, 100, is_moving=False)
        self.assertIsNone(result)

    def test_consume_freeze_resets(self):
        p = _Player(); _equip(p, "time_anchor")
        identity_runes.update_time_anchor(p, 4000, is_moving=False)
        identity_runes.consume_time_anchor_freeze(p)
        self.assertEqual(identity_runes.time_anchor_meter(p), 0.0)

    def test_time_scale_when_still(self):
        p = _Player(); _equip(p, "time_anchor")
        self.assertEqual(identity_runes.time_anchor_time_scale(p, is_moving=False), 0.2)
        self.assertEqual(identity_runes.time_anchor_time_scale(p, is_moving=True), 1.0)

    def test_no_rune_no_time_scale_override(self):
        self.assertIsNone(identity_runes.time_anchor_time_scale(_Player(), is_moving=False))


# ── necromancer ─────────────────────────────────────────
class NecromancerTests(unittest.TestCase):
    def test_no_rune_register_returns_false(self):
        self.assertFalse(identity_runes.necromancer_register_kill(_Player()))

    def test_every_third_kill_signals(self):
        p = _Player(); _equip(p, "necromancer")
        results = [identity_runes.necromancer_register_kill(p) for _ in range(6)]
        self.assertEqual(results, [False, False, True, False, False, True])

    def test_consume_pending_clears_flag(self):
        p = _Player(); _equip(p, "necromancer")
        for _ in range(3):
            identity_runes.necromancer_register_kill(p)
        self.assertTrue(identity_runes.necromancer_consume_pending(p))
        self.assertFalse(identity_runes.necromancer_consume_pending(p))


# ── the_conduit ─────────────────────────────────────────
class ConduitTests(unittest.TestCase):
    def test_no_rune_full_primary(self):
        primary, splash = identity_runes.conduit_split_damage(_Player(), 100)
        self.assertEqual(primary, 100)
        self.assertEqual(splash, 0)

    def test_rune_splits_60_40(self):
        p = _Player(); _equip(p, "the_conduit")
        primary, splash = identity_runes.conduit_split_damage(p, 100)
        self.assertEqual(primary, 60)
        self.assertEqual(splash, 40)

    def test_finds_nearest_other_enemy(self):
        p = _Player(); _equip(p, "the_conduit")
        primary = _Enemy(0, 0)
        near = _Enemy(40, 0)
        far = _Enemy(200, 0)
        self.assertIs(
            identity_runes.conduit_find_splash_target(p, primary, [primary, near, far]),
            near,
        )

    def test_no_target_when_no_other_enemies(self):
        p = _Player(); _equip(p, "the_conduit")
        primary = _Enemy(0, 0)
        self.assertIsNone(
            identity_runes.conduit_find_splash_target(p, primary, [primary])
        )

    def test_skips_dead_enemies(self):
        p = _Player(); _equip(p, "the_conduit")
        primary = _Enemy(0, 0)
        dead = _Enemy(20, 0, hp=0)
        live = _Enemy(60, 0)
        self.assertIs(
            identity_runes.conduit_find_splash_target(
                p, primary, [primary, dead, live]
            ),
            live,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
