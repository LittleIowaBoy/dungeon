import unittest
from types import SimpleNamespace

import status_effects as se


def _holder():
    h = SimpleNamespace()
    se.reset_statuses(h)
    return h


class ApplyTests(unittest.TestCase):
    def test_apply_burning_with_defaults(self):
        h = _holder()
        self.assertTrue(se.apply_status(h, se.BURNING, 1000))
        entry = h.statuses[se.BURNING]
        self.assertEqual(entry["expires_at"], 1000 + 3000)
        self.assertEqual(entry["tick_interval_ms"], 500)
        self.assertEqual(entry["tick_damage"], 1)

    def test_apply_unknown_returns_false(self):
        h = _holder()
        self.assertFalse(se.apply_status(h, "mystery", 0))

    def test_reapply_refreshes_duration(self):
        h = _holder()
        se.apply_status(h, se.FROZEN, 0)
        se.apply_status(h, se.FROZEN, 5000)
        self.assertEqual(h.statuses[se.FROZEN]["expires_at"], 5000 + 1500)

    def test_apply_with_overrides(self):
        h = _holder()
        se.apply_status(h, se.BURNING, 0, duration_ms=10000, tick_damage=5)
        e = h.statuses[se.BURNING]
        self.assertEqual(e["expires_at"], 10000)
        self.assertEqual(e["tick_damage"], 5)


class HasStatusTests(unittest.TestCase):
    def test_has_status_true_during_window(self):
        h = _holder()
        se.apply_status(h, se.STUNNED, 0)
        self.assertTrue(se.has_status(h, se.STUNNED, 500))

    def test_has_status_false_after_expiry(self):
        h = _holder()
        se.apply_status(h, se.STUNNED, 0)
        self.assertFalse(se.has_status(h, se.STUNNED, 5000))

    def test_remove_status(self):
        h = _holder()
        se.apply_status(h, se.STUNNED, 0)
        self.assertTrue(se.remove_status(h, se.STUNNED))
        self.assertFalse(se.has_status(h, se.STUNNED, 0))


class ImmobilizeTests(unittest.TestCase):
    def test_frozen_immobilizes(self):
        h = _holder()
        se.apply_status(h, se.FROZEN, 0)
        self.assertTrue(se.is_immobilized(h, 100))

    def test_stunned_immobilizes(self):
        h = _holder()
        se.apply_status(h, se.STUNNED, 0)
        self.assertTrue(se.is_immobilized(h, 100))

    def test_burning_does_not_immobilize(self):
        h = _holder()
        se.apply_status(h, se.BURNING, 0)
        self.assertFalse(se.is_immobilized(h, 100))


class SilenceTests(unittest.TestCase):
    def test_stunned_silences(self):
        h = _holder()
        se.apply_status(h, se.STUNNED, 0)
        self.assertTrue(se.is_silenced(h, 100))

    def test_no_status_means_not_silenced(self):
        h = _holder()
        self.assertFalse(se.is_silenced(h, 0))


class SpeedMultiplierTests(unittest.TestCase):
    def test_no_status_returns_one(self):
        h = _holder()
        self.assertEqual(se.speed_multiplier(h, 0), 1.0)

    def test_slowed_applies_magnitude(self):
        h = _holder()
        se.apply_status(h, se.SLOWED, 0)
        self.assertAlmostEqual(se.speed_multiplier(h, 100), 0.5)

    def test_slowed_and_poisoned_stack(self):
        h = _holder()
        se.apply_status(h, se.SLOWED, 0)
        se.apply_status(h, se.POISONED, 0)
        self.assertAlmostEqual(se.speed_multiplier(h, 100), 0.5 * 0.7)


class TickStatusesTests(unittest.TestCase):
    def setUp(self):
        self.h = _holder()
        self.dmg = []

    def _damage_fn(self, holder, amount):
        self.dmg.append(amount)

    def test_dot_tick_applies_damage_at_interval(self):
        se.apply_status(self.h, se.BURNING, 0)
        se.tick_statuses(self.h, 500, self._damage_fn)
        self.assertEqual(self.dmg, [1])

    def test_dot_no_tick_before_interval(self):
        se.apply_status(self.h, se.BURNING, 0)
        se.tick_statuses(self.h, 100, self._damage_fn)
        self.assertEqual(self.dmg, [])

    def test_dot_multiple_ticks(self):
        se.apply_status(self.h, se.BURNING, 0)
        se.tick_statuses(self.h, 500, self._damage_fn)
        se.tick_statuses(self.h, 1000, self._damage_fn)
        self.assertEqual(self.dmg, [1, 1])

    def test_status_removed_after_expiry(self):
        se.apply_status(self.h, se.BURNING, 0)
        se.tick_statuses(self.h, 5000, self._damage_fn)
        self.assertNotIn(se.BURNING, self.h.statuses)

    def test_non_dot_status_removed_after_expiry(self):
        se.apply_status(self.h, se.STUNNED, 0)
        se.tick_statuses(self.h, 5000, self._damage_fn)
        self.assertNotIn(se.STUNNED, self.h.statuses)


class IntegrationTests(unittest.TestCase):
    def test_attack_blocked_when_silenced(self):
        import pygame
        pygame.init()
        import attack_rules

        weapon = SimpleNamespace(attack=lambda *a, **kw: object())
        player = SimpleNamespace(
            weapon=weapon,
            rect=SimpleNamespace(centerx=0, centery=0),
            facing_dx=1.0, facing_dy=0.0,
        )
        se.reset_statuses(player)
        # Apply STUNNED at the *current* tick so its expires_at lands in
        # the future relative to the get_ticks() call inside attack().
        # (Applying at now_ticks=0 made the status appear stale once the
        # rest of the suite had been running for >1.5s.)
        se.apply_status(player, se.STUNNED, pygame.time.get_ticks())
        self.assertIsNone(attack_rules.attack(player))


if __name__ == "__main__":
    unittest.main()
