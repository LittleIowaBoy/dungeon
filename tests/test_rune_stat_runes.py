"""Tests for stat-rune effect resolution (stat_runes.py)."""

import unittest

import rune_rules
import stat_runes


class _Player:
    """Minimal player stand-in: only attributes stat_runes touches."""

    def __init__(self):
        self.equipped_runes = rune_rules.empty_loadout()
        self.rune_state = {"room": {}}
        self.max_hp = 100
        self.current_hp = 100


class _Enemy:
    def __init__(self, max_hp=50, current_hp=50):
        self.max_hp = max_hp
        self.current_hp = current_hp


def _equip(player, rune_id):
    rune_rules.equip_rune(player, rune_id)


# ── outgoing damage ─────────────────────────────────────
class OutgoingDamageTests(unittest.TestCase):
    def test_no_runes_returns_base_damage(self):
        p = _Player()
        e = _Enemy()
        self.assertEqual(stat_runes.modify_outgoing_damage(p, e, 10), 10)

    def test_glass_cannon_boosts_damage(self):
        p = _Player(); _equip(p, "glass_cannon")
        self.assertEqual(stat_runes.modify_outgoing_damage(p, _Enemy(), 10), 18)

    def test_thorns_reduces_outgoing_damage(self):
        p = _Player(); _equip(p, "thorns")
        self.assertEqual(stat_runes.modify_outgoing_damage(p, _Enemy(), 100), 75)

    def test_iron_will_reduces_outgoing_damage(self):
        p = _Player(); _equip(p, "iron_will")
        self.assertEqual(stat_runes.modify_outgoing_damage(p, _Enemy(), 100), 75)

    def test_bloodthirst_first_hit_is_buffed(self):
        p = _Player(); _equip(p, "bloodthirst")
        self.assertEqual(stat_runes.modify_outgoing_damage(p, _Enemy(), 10), 15)

    def test_bloodthirst_subsequent_hits_are_debuffed(self):
        p = _Player(); _equip(p, "bloodthirst")
        e = _Enemy()
        stat_runes.on_player_hit_landed(p, e, 15, killed=False)
        self.assertEqual(stat_runes.modify_outgoing_damage(p, e, 10), 8)

    def test_executioner_above_threshold_reduces(self):
        p = _Player(); _equip(p, "executioner")
        e = _Enemy(max_hp=100, current_hp=80)
        self.assertEqual(stat_runes.modify_outgoing_damage(p, e, 10), 7)

    def test_executioner_below_threshold_doubles(self):
        p = _Player(); _equip(p, "executioner")
        e = _Enemy(max_hp=100, current_hp=20)
        self.assertEqual(stat_runes.modify_outgoing_damage(p, e, 10), 20)

    def test_berserker_stacks_per_kill(self):
        p = _Player(); _equip(p, "berserker")
        e = _Enemy()
        # 2 kills → +10% damage
        stat_runes.on_player_hit_landed(p, e, 50, killed=True)
        stat_runes.on_player_hit_landed(p, _Enemy(), 50, killed=True)
        self.assertEqual(stat_runes.modify_outgoing_damage(p, _Enemy(), 100), 110)

    def test_berserker_resets_on_taking_damage(self):
        p = _Player(); _equip(p, "berserker")
        stat_runes.on_player_hit_landed(p, _Enemy(), 50, killed=True)
        stat_runes.on_player_damage_taken(p, 5)
        self.assertEqual(stat_runes.modify_outgoing_damage(p, _Enemy(), 100), 100)

    def test_heavy_hitter_first_hit_buffed_then_normal(self):
        p = _Player(); _equip(p, "heavy_hitter")
        e = _Enemy()
        first = stat_runes.modify_outgoing_damage(p, e, 10)
        self.assertEqual(first, 25)
        stat_runes.on_player_hit_landed(p, e, first, killed=False)
        self.assertEqual(stat_runes.modify_outgoing_damage(p, e, 10), 10)

    def test_momentum_scales_with_seconds_moved(self):
        p = _Player(); _equip(p, "momentum")
        p.rune_state["momentum_seconds"] = 3.0
        # +10% per second × 3 → ×1.30
        self.assertEqual(stat_runes.modify_outgoing_damage(p, _Enemy(), 100), 130)

    def test_momentum_resets_on_dealing_damage(self):
        p = _Player(); _equip(p, "momentum")
        p.rune_state["momentum_seconds"] = 3.0
        stat_runes.on_player_hit_landed(p, _Enemy(), 100, killed=False)
        self.assertEqual(p.rune_state["momentum_seconds"], 0.0)


# ── incoming damage ─────────────────────────────────────
class IncomingDamageTests(unittest.TestCase):
    def test_no_runes_passes_through(self):
        p = _Player()
        self.assertEqual(stat_runes.modify_incoming_damage(p, 10), 10)

    def test_turtle_shell_reduces_incoming(self):
        p = _Player(); _equip(p, "turtle_shell")
        self.assertEqual(stat_runes.modify_incoming_damage(p, 100), 60)

    def test_last_stand_nullifies_at_low_hp(self):
        p = _Player(); _equip(p, "last_stand")
        p.current_hp = 10  # 10/100 = 10% < 15%
        # 80% reduction (not full invuln): 50 * 0.20 = 10
        self.assertEqual(stat_runes.modify_incoming_damage(p, 50), 10)

    def test_last_stand_inactive_above_threshold(self):
        p = _Player(); _equip(p, "last_stand")
        p.current_hp = 50
        self.assertEqual(stat_runes.modify_incoming_damage(p, 50), 50)

    def test_thorns_reflect(self):
        p = _Player(); _equip(p, "thorns")
        self.assertEqual(stat_runes.compute_reflect(p, 10), 3)

    def test_no_thorns_no_reflect(self):
        self.assertEqual(stat_runes.compute_reflect(_Player(), 10), 0)


# ── max HP ──────────────────────────────────────────────
class MaxHPTests(unittest.TestCase):
    def test_ironhide_adds_flat_hp(self):
        p = _Player(); _equip(p, "ironhide")
        self.assertEqual(stat_runes.modify_max_hp(p, 100), 160)

    def test_glass_cannon_halves_max_hp(self):
        p = _Player(); _equip(p, "glass_cannon")
        self.assertEqual(stat_runes.modify_max_hp(p, 100), 50)

    def test_vampire_lord_reduces_max_hp(self):
        p = _Player(); _equip(p, "vampire_lord")
        self.assertEqual(stat_runes.modify_max_hp(p, 100), 70)

    def test_featherweight_reduces_max_hp(self):
        p = _Player(); _equip(p, "featherweight")
        self.assertEqual(stat_runes.modify_max_hp(p, 100), 60)


# ── kill heals & stacks ─────────────────────────────────
class OnKillTests(unittest.TestCase):
    def test_vampire_lord_heals_on_kill(self):
        p = _Player(); _equip(p, "vampire_lord")
        p.max_hp = 100; p.current_hp = 50
        stat_runes.on_player_hit_landed(p, _Enemy(), 50, killed=True)
        self.assertEqual(p.current_hp, 55)

    def test_no_vampire_lord_no_heal(self):
        p = _Player(); p.current_hp = 50
        stat_runes.on_player_hit_landed(p, _Enemy(), 50, killed=True)
        self.assertEqual(p.current_hp, 50)


# ── speed multiplier ────────────────────────────────────
class SpeedTests(unittest.TestCase):
    def test_no_runes_unchanged(self):
        self.assertEqual(stat_runes.modify_speed_multiplier(_Player(), 1.0), 1.0)

    def test_ironhide_slows(self):
        p = _Player(); _equip(p, "ironhide")
        self.assertAlmostEqual(stat_runes.modify_speed_multiplier(p, 1.0), 0.80)

    def test_sprinter_speeds_up(self):
        p = _Player(); _equip(p, "sprinter")
        self.assertAlmostEqual(stat_runes.modify_speed_multiplier(p, 1.0), 1.50)


# ── weapon cooldown ─────────────────────────────────────
class WeaponCooldownTests(unittest.TestCase):
    def test_no_runes_unchanged(self):
        self.assertEqual(stat_runes.modify_weapon_cooldown(_Player(), 300), 300)

    def test_sprinter_extends_cooldown(self):
        p = _Player(); _equip(p, "sprinter")
        self.assertEqual(stat_runes.modify_weapon_cooldown(p, 300), 429)

    def test_heavy_hitter_extends_cooldown(self):
        p = _Player(); _equip(p, "heavy_hitter")
        self.assertEqual(stat_runes.modify_weapon_cooldown(p, 300), 390)


# ── dodge ───────────────────────────────────────────────
class DodgeRuneTests(unittest.TestCase):
    def test_turtle_shell_blocks_dodge(self):
        p = _Player(); _equip(p, "turtle_shell")
        self.assertFalse(stat_runes.can_dodge(p))

    def test_no_rune_allows_dodge(self):
        self.assertTrue(stat_runes.can_dodge(_Player()))

    def test_slippery_extends_cooldown(self):
        p = _Player(); _equip(p, "slippery")
        self.assertEqual(stat_runes.dodge_cooldown_ms(p, 1500), 2000)

    def test_featherweight_halves_cooldown(self):
        p = _Player(); _equip(p, "featherweight")
        self.assertEqual(stat_runes.dodge_cooldown_ms(p, 1500), 750)

    def test_slippery_and_featherweight_stack(self):
        p = _Player(); _equip(p, "slippery"); _equip(p, "featherweight")
        # slippery sets to 2000, featherweight halves → 1000
        self.assertEqual(stat_runes.dodge_cooldown_ms(p, 1500), 1000)

    def test_ghost_step_disables_iframes(self):
        p = _Player(); _equip(p, "ghost_step")
        self.assertFalse(stat_runes.dodge_grants_iframes(p))
        self.assertTrue(stat_runes.dodge_grants_pass_through(p))

    def test_default_dodge_grants_iframes_no_passthrough(self):
        p = _Player()
        self.assertTrue(stat_runes.dodge_grants_iframes(p))
        self.assertFalse(stat_runes.dodge_grants_pass_through(p))

    def test_slippery_boosts_dodge_speed(self):
        p = _Player(); _equip(p, "slippery")
        self.assertAlmostEqual(stat_runes.dodge_speed_multiplier_bonus(p), 1.40)


# ── statuses ────────────────────────────────────────────
class StatusImmunityTests(unittest.TestCase):
    def test_iron_will_grants_immunity(self):
        p = _Player(); _equip(p, "iron_will")
        self.assertTrue(stat_runes.is_status_immune(p))

    def test_no_rune_no_immunity(self):
        self.assertFalse(stat_runes.is_status_immune(_Player()))


# ── movement state ticker ───────────────────────────────
class MovementStateTickTests(unittest.TestCase):
    def test_momentum_accumulates_when_moving(self):
        p = _Player(); _equip(p, "momentum")
        stat_runes.update_movement_state(p, 0, 500, is_moving=True)
        stat_runes.update_movement_state(p, 500, 500, is_moving=True)
        self.assertAlmostEqual(p.rune_state["momentum_seconds"], 1.0)

    def test_momentum_resets_when_not_moving(self):
        p = _Player(); _equip(p, "momentum")
        stat_runes.update_movement_state(p, 0, 1000, is_moving=True)
        stat_runes.update_movement_state(p, 1000, 16, is_moving=False)
        self.assertEqual(p.rune_state["momentum_seconds"], 0.0)

    def test_no_momentum_rune_no_state_change(self):
        p = _Player()
        stat_runes.update_movement_state(p, 0, 500, is_moving=True)
        self.assertNotIn("momentum_seconds", p.rune_state)
