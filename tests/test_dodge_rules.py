import unittest
from types import SimpleNamespace

import dodge_rules


def _player(facing=(1.0, 0.0)):
    p = SimpleNamespace(facing_dx=facing[0], facing_dy=facing[1])
    dodge_rules.reset_runtime_dodge(p)
    return p


class ResetTests(unittest.TestCase):
    def test_reset_initializes_all_fields(self):
        p = SimpleNamespace(facing_dx=1.0, facing_dy=0.0)
        dodge_rules.reset_runtime_dodge(p)
        self.assertEqual(p.dodge_until, 0)
        self.assertEqual(p.dodge_cooldown_until, 0)
        self.assertFalse(p.dodge_pass_through)
        self.assertEqual(p.dodge_facing, (0.0, 0.0))


class CanDodgeTests(unittest.TestCase):
    def test_initially_can_dodge(self):
        p = _player()
        self.assertTrue(dodge_rules.can_dodge(p, 0))

    def test_cannot_dodge_during_active_phase(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 1000)
        self.assertFalse(dodge_rules.can_dodge(p, 1100))

    def test_cannot_dodge_during_cooldown(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 1000)
        # After active phase but before cooldown ends.
        self.assertFalse(dodge_rules.can_dodge(p, 1000 + dodge_rules.DODGE_DURATION_MS + 100))

    def test_can_dodge_again_after_cooldown(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 1000)
        end = 1000 + dodge_rules.DODGE_DURATION_MS + dodge_rules.DODGE_COOLDOWN_MS + 1
        self.assertTrue(dodge_rules.can_dodge(p, end))


class TriggerTests(unittest.TestCase):
    def test_trigger_returns_true_and_sets_state(self):
        p = _player(facing=(1.0, 0.0))
        self.assertTrue(dodge_rules.trigger_dodge(p, 500))
        self.assertEqual(p.dodge_until, 500 + dodge_rules.DODGE_DURATION_MS)
        self.assertEqual(p.dodge_facing, (1.0, 0.0))

    def test_trigger_rejected_when_facing_zero(self):
        p = _player(facing=(0.0, 0.0))
        self.assertFalse(dodge_rules.trigger_dodge(p, 500))
        self.assertEqual(p.dodge_until, 0)

    def test_trigger_rejected_during_cooldown(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 1000)
        self.assertFalse(dodge_rules.trigger_dodge(p, 1100))

    def test_pass_through_flag_set_when_requested(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 0, pass_through=True)
        self.assertTrue(p.dodge_pass_through)

    def test_custom_duration_and_cooldown(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 0, duration_ms=400, cooldown_ms=2000)
        self.assertEqual(p.dodge_until, 400)
        self.assertEqual(p.dodge_cooldown_until, 400 + 2000)


class UpdateStateTests(unittest.TestCase):
    def test_pass_through_clears_after_active_phase(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 0, pass_through=True)
        dodge_rules.update_dodge_state(p, dodge_rules.DODGE_DURATION_MS + 1)
        self.assertFalse(p.dodge_pass_through)

    def test_pass_through_persists_during_active_phase(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 0, pass_through=True)
        dodge_rules.update_dodge_state(p, 50)
        self.assertTrue(p.dodge_pass_through)


class DodgeVelocityTests(unittest.TestCase):
    def test_returns_none_when_not_dodging(self):
        p = _player()
        self.assertIsNone(dodge_rules.dodge_velocity(p, 0, 100.0))

    def test_returns_boosted_velocity_in_facing_direction(self):
        p = _player(facing=(1.0, 0.0))
        dodge_rules.trigger_dodge(p, 0)
        v = dodge_rules.dodge_velocity(p, 50, 100.0)
        self.assertIsNotNone(v)
        vx, vy = v
        self.assertAlmostEqual(vx, 100.0 * dodge_rules.DODGE_SPEED_MULTIPLIER)
        self.assertEqual(vy, 0.0)


class CombatIntegrationTests(unittest.TestCase):
    def test_combat_is_invincible_true_during_dodge(self):
        import combat_rules
        p = SimpleNamespace(facing_dx=1.0, facing_dy=0.0, _invincible_until=0)
        dodge_rules.reset_runtime_dodge(p)
        dodge_rules.trigger_dodge(p, 1000)
        self.assertTrue(combat_rules.is_invincible(p, 1100))

    def test_combat_take_damage_blocked_during_dodge(self):
        import combat_rules
        p = SimpleNamespace(
            facing_dx=1.0, facing_dy=0.0,
            _invincible_until=0, current_hp=10, max_hp=10, armor_hp=0,
        )
        dodge_rules.reset_runtime_dodge(p)
        dodge_rules.trigger_dodge(p, 1000)
        combat_rules.take_damage(p, 5, 1100)
        self.assertEqual(p.current_hp, 10)


class CooldownFractionTests(unittest.TestCase):
    def test_zero_when_ready(self):
        p = _player()
        self.assertEqual(dodge_rules.cooldown_fraction_remaining(p, 0), 0.0)

    def test_one_just_after_trigger(self):
        p = _player()
        dodge_rules.trigger_dodge(p, 0)
        # Right after trigger, cooldown_until = duration + cooldown.
        frac = dodge_rules.cooldown_fraction_remaining(p, 1)
        self.assertGreater(frac, 0.99)


if __name__ == "__main__":
    unittest.main()
