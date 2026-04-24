"""Tests for behavior-rune effect resolution (behavior_runes.py)."""

import unittest
from types import SimpleNamespace

import pygame

import behavior_runes
import rune_rules
import status_effects
from settings import TILE_SIZE


pygame.init()


class _Player:
    def __init__(self):
        self.equipped_runes = rune_rules.empty_loadout()
        self.rune_state = {"room": {}}
        self.max_hp = 100
        self.current_hp = 100
        self.rect = pygame.Rect(0, 0, 32, 32)
        self.statuses = {}


class _Enemy:
    def __init__(self, x=0, y=0, hp=10):
        self.rect = pygame.Rect(x - 8, y - 8, 16, 16)
        self.current_hp = hp
        self.max_hp = hp
        self.statuses = {}


def _equip(player, rune_id):
    rune_rules.equip_rune(player, rune_id)


# ── ricochet ────────────────────────────────────────────
class RicochetTests(unittest.TestCase):
    def test_no_rune_returns_none(self):
        p = _Player()
        primary = _Enemy(0, 0)
        hitbox = SimpleNamespace(_hit_enemies={id(primary)})
        self.assertIsNone(
            behavior_runes.find_ricochet_target(p, hitbox, primary, [primary, _Enemy(20, 0)])
        )

    def test_finds_closest_unhit_enemy(self):
        p = _Player(); _equip(p, "ricochet")
        primary = _Enemy(0, 0)
        near = _Enemy(40, 0)
        far = _Enemy(80, 0)
        hitbox = SimpleNamespace(_hit_enemies={id(primary)})
        result = behavior_runes.find_ricochet_target(p, hitbox, primary, [primary, near, far])
        self.assertIs(result, near)

    def test_skips_already_hit(self):
        p = _Player(); _equip(p, "ricochet")
        primary = _Enemy(0, 0)
        near = _Enemy(40, 0)
        far = _Enemy(80, 0)
        hitbox = SimpleNamespace(_hit_enemies={id(primary), id(near)})
        self.assertIs(
            behavior_runes.find_ricochet_target(p, hitbox, primary, [primary, near, far]),
            far,
        )

    def test_skips_dead(self):
        p = _Player(); _equip(p, "ricochet")
        primary = _Enemy(0, 0)
        dead = _Enemy(20, 0, hp=0)
        live = _Enemy(60, 0)
        hitbox = SimpleNamespace(_hit_enemies={id(primary)})
        self.assertIs(
            behavior_runes.find_ricochet_target(p, hitbox, primary, [primary, dead, live]),
            live,
        )

    def test_returns_none_outside_radius(self):
        p = _Player(); _equip(p, "ricochet")
        primary = _Enemy(0, 0)
        too_far = _Enemy(behavior_runes.RICOCHET_RADIUS + 50, 0)
        hitbox = SimpleNamespace(_hit_enemies={id(primary)})
        self.assertIsNone(
            behavior_runes.find_ricochet_target(p, hitbox, primary, [primary, too_far])
        )


# ── shockwave ───────────────────────────────────────────
class ShockwaveTests(unittest.TestCase):
    def test_no_rune_no_change(self):
        p = _Player()
        self.assertEqual(behavior_runes.shockwave_damage_multiplier(p), 1.0)
        self.assertEqual(behavior_runes.shockwave_duration_multiplier(p), 1.0)
        self.assertEqual(behavior_runes.shockwave_cooldown_multiplier(p), 1.0)

    def test_shockwave_buffs_damage_and_duration_and_cd(self):
        p = _Player(); _equip(p, "shockwave")
        self.assertEqual(behavior_runes.shockwave_damage_multiplier(p), 1.5)
        self.assertEqual(behavior_runes.shockwave_duration_multiplier(p), 3.0)
        self.assertEqual(behavior_runes.shockwave_cooldown_multiplier(p), 1.5)


# ── vampiric strike ─────────────────────────────────────
class VampiricStrikeTests(unittest.TestCase):
    def test_no_rune_no_heal(self):
        self.assertEqual(behavior_runes.vampiric_kill_heal_amount(_Player()), 0)

    def test_with_rune_heals_8(self):
        p = _Player(); _equip(p, "vampiric_strike")
        self.assertEqual(behavior_runes.vampiric_kill_heal_amount(p), 8)

    def test_blocks_potion_pickup(self):
        p = _Player(); _equip(p, "vampiric_strike")
        self.assertTrue(behavior_runes.blocks_health_pickup(p))

    def test_no_rune_does_not_block(self):
        self.assertFalse(behavior_runes.blocks_health_pickup(_Player()))


# ── afterimage ──────────────────────────────────────────
class AfterimageTests(unittest.TestCase):
    def test_no_rune_no_decoy(self):
        self.assertFalse(behavior_runes.spawns_afterimage(_Player()))
        self.assertEqual(
            behavior_runes.afterimage_dodge_distance_multiplier(_Player()), 1.0
        )

    def test_rune_enables_decoy_and_halves_distance(self):
        p = _Player(); _equip(p, "afterimage")
        self.assertTrue(behavior_runes.spawns_afterimage(p))
        self.assertEqual(behavior_runes.afterimage_dodge_distance_multiplier(p), 0.5)

    def test_make_decoy_hitbox(self):
        decoy = behavior_runes.make_afterimage_hitbox((100, 200))
        self.assertEqual(decoy.rect.center, (100, 200))
        self.assertEqual(decoy.damage, behavior_runes.AFTERIMAGE_DAMAGE)
        self.assertEqual(decoy._duration, behavior_runes.AFTERIMAGE_DURATION_MS)


# ── overclock ───────────────────────────────────────────
class OverclockTests(unittest.TestCase):
    def test_no_rune_single_fire(self):
        self.assertFalse(behavior_runes.should_double_fire(_Player()))
        self.assertEqual(behavior_runes.ability_cooldown_multiplier(_Player()), 1.0)

    def test_rune_double_fires_and_triples_cd(self):
        p = _Player(); _equip(p, "overclock")
        self.assertTrue(behavior_runes.should_double_fire(p))
        self.assertEqual(behavior_runes.ability_cooldown_multiplier(p), 3.0)


# ── chain reaction ──────────────────────────────────────
class ChainReactionTests(unittest.TestCase):
    def test_no_rune_no_targets(self):
        p = _Player()
        target = _Enemy(0, 0)
        nearby = _Enemy(20, 0)
        self.assertEqual(
            behavior_runes.chain_reaction_targets(p, target.rect, [target, nearby]),
            [],
        )

    def test_rune_finds_nearby_targets(self):
        p = _Player(); _equip(p, "chain_reaction")
        target = _Enemy(0, 0)
        nearby = _Enemy(20, 0)
        far = _Enemy(behavior_runes.CHAIN_REACTION_RADIUS + 50, 0)
        result = behavior_runes.chain_reaction_targets(p, target.rect, [target, nearby, far])
        self.assertIn(nearby, result)
        self.assertNotIn(far, result)
        self.assertNotIn(target, result)

    def test_apply_status_with_chain_spreads(self):
        p = _Player(); _equip(p, "chain_reaction")
        target = _Enemy(0, 0)
        nearby = _Enemy(20, 0)
        far = _Enemy(behavior_runes.CHAIN_REACTION_RADIUS + 50, 0)
        count = behavior_runes.apply_status_with_chain(
            p, target, status_effects.BURNING, 1000, [target, nearby, far]
        )
        # Target + nearby + self (chain_reaction also affects player) = 3
        self.assertEqual(count, 3)
        self.assertIn(status_effects.BURNING, target.statuses)
        self.assertIn(status_effects.BURNING, nearby.statuses)
        self.assertNotIn(status_effects.BURNING, far.statuses)
        self.assertIn(status_effects.BURNING, p.statuses)

    def test_apply_status_without_rune_only_target(self):
        p = _Player()
        target = _Enemy(0, 0)
        nearby = _Enemy(20, 0)
        count = behavior_runes.apply_status_with_chain(
            p, target, status_effects.BURNING, 1000, [target, nearby]
        )
        self.assertEqual(count, 1)
        self.assertIn(status_effects.BURNING, target.statuses)
        self.assertNotIn(status_effects.BURNING, nearby.statuses)


# ── shrapnel burst ──────────────────────────────────────
class ShrapnelBurstTests(unittest.TestCase):
    def test_no_rune_no_blast(self):
        p = _Player()
        kill_rect = pygame.Rect(0, 0, 16, 16)
        self.assertEqual(behavior_runes.shrapnel_burst_targets(p, kill_rect, []), [])
        self.assertEqual(behavior_runes.shrapnel_burst_damage(p, 100), 0)
        self.assertFalse(behavior_runes.player_in_shrapnel_blast(p, kill_rect))

    def test_rune_deals_80_percent(self):
        p = _Player(); _equip(p, "shrapnel_burst")
        self.assertEqual(behavior_runes.shrapnel_burst_damage(p, 100), 80)

    def test_rune_self_damage_is_50_of_blast(self):
        p = _Player(); _equip(p, "shrapnel_burst")
        self.assertEqual(behavior_runes.shrapnel_burst_self_damage(p, 100), 40)

    def test_rune_finds_nearby_enemies(self):
        p = _Player(); _equip(p, "shrapnel_burst")
        kill_rect = pygame.Rect(0, 0, 16, 16); kill_rect.center = (0, 0)
        near = _Enemy(20, 0)
        far = _Enemy(behavior_runes.SHRAPNEL_RADIUS + 50, 0)
        targets = behavior_runes.shrapnel_burst_targets(p, kill_rect, [near, far])
        self.assertIn(near, targets)
        self.assertNotIn(far, targets)

    def test_player_in_blast_when_nearby(self):
        p = _Player(); _equip(p, "shrapnel_burst")
        p.rect = pygame.Rect(0, 0, 32, 32); p.rect.center = (10, 0)
        kill_rect = pygame.Rect(0, 0, 16, 16); kill_rect.center = (0, 0)
        self.assertTrue(behavior_runes.player_in_shrapnel_blast(p, kill_rect))


# ── static charge ───────────────────────────────────────
class StaticChargeTests(unittest.TestCase):
    def test_no_rune_no_change(self):
        p = _Player()
        behavior_runes.update_static_charge(p, 1000, is_moving=True)
        self.assertEqual(behavior_runes.static_charge_value(p), 0.0)
        self.assertEqual(behavior_runes.consume_static_charge(p), 1.0)

    def test_movement_builds_charge(self):
        p = _Player(); _equip(p, "static_charge")
        behavior_runes.update_static_charge(p, 500, is_moving=True)
        self.assertAlmostEqual(behavior_runes.static_charge_value(p), 0.5)

    def test_full_charge_grants_3x_damage(self):
        p = _Player(); _equip(p, "static_charge")
        behavior_runes.update_static_charge(p, 2000, is_moving=True)
        self.assertEqual(behavior_runes.consume_static_charge(p), 3.0)
        self.assertEqual(behavior_runes.static_charge_value(p), 0.0)

    def test_standing_dissipates_at_2x(self):
        p = _Player(); _equip(p, "static_charge")
        behavior_runes.update_static_charge(p, 1000, is_moving=True)  # full
        behavior_runes.update_static_charge(p, 250, is_moving=False)  # 2.0/s × 0.25 = 0.5
        self.assertAlmostEqual(behavior_runes.static_charge_value(p), 0.5)

    def test_partial_charge_linear_ramp(self):
        p = _Player(); _equip(p, "static_charge")
        behavior_runes.update_static_charge(p, 500, is_moving=True)  # charge 0.5
        # 1.0 + 2.0 * 0.5 = 2.0
        self.assertAlmostEqual(behavior_runes.consume_static_charge(p), 2.0)


# ── boomerang ───────────────────────────────────────────
class BoomerangTests(unittest.TestCase):
    def test_no_rune_full_outbound(self):
        self.assertEqual(behavior_runes.boomerang_outbound_multiplier(_Player()), 1.0)

    def test_rune_zeroes_outbound(self):
        p = _Player(); _equip(p, "boomerang")
        self.assertEqual(behavior_runes.boomerang_outbound_multiplier(p), 0.0)

    def test_queue_noop_without_rune(self):
        p = _Player()
        behavior_runes.queue_boomerang_return(p, (10, 20), 25, now_ticks=1000)
        self.assertNotIn("boomerang_pending", p.rune_state)

    def test_queue_records_pending_entry(self):
        p = _Player(); _equip(p, "boomerang")
        behavior_runes.queue_boomerang_return(p, (40, 50), 25, now_ticks=1000)
        pending = p.rune_state["boomerang_pending"]
        self.assertEqual(len(pending), 1)
        entry = pending[0]
        self.assertEqual(entry["center"], (40, 50))
        self.assertEqual(entry["damage"], 25)
        self.assertEqual(
            entry["spawn_at"], 1000 + behavior_runes.BOOMERANG_RETURN_DELAY_MS
        )

    def test_update_holds_until_delay_elapses(self):
        p = _Player(); _equip(p, "boomerang")
        behavior_runes.queue_boomerang_return(p, (40, 50), 25, now_ticks=1000)
        group = pygame.sprite.Group()
        spawned = behavior_runes.update_boomerang_returns(p, group, now_ticks=1100)
        self.assertEqual(spawned, [])
        self.assertEqual(len(group), 0)
        self.assertEqual(len(p.rune_state["boomerang_pending"]), 1)

    def test_update_spawns_return_hitbox_after_delay(self):
        p = _Player(); _equip(p, "boomerang")
        behavior_runes.queue_boomerang_return(p, (40, 50), 25, now_ticks=1000)
        group = pygame.sprite.Group()
        spawn_at = 1000 + behavior_runes.BOOMERANG_RETURN_DELAY_MS
        spawned = behavior_runes.update_boomerang_returns(p, group, now_ticks=spawn_at)
        self.assertEqual(len(spawned), 1)
        hb = spawned[0]
        self.assertEqual(hb.rect.center, (40, 50))
        self.assertEqual(hb.damage, 25)
        self.assertEqual(hb.weapon_id, "boomerang")
        self.assertEqual(p.rune_state["boomerang_pending"], [])

    def test_return_damage_floors_to_one_minimum(self):
        p = _Player(); _equip(p, "boomerang")
        behavior_runes.queue_boomerang_return(p, (0, 0), 0, now_ticks=0)
        self.assertEqual(p.rune_state["boomerang_pending"][0]["damage"], 1)

    def test_room_enter_clears_pending_returns(self):
        p = _Player(); _equip(p, "boomerang")
        behavior_runes.queue_boomerang_return(p, (40, 50), 25, now_ticks=1000)
        rune_rules.on_room_enter(p)
        self.assertEqual(p.rune_state["boomerang_pending"], [])
