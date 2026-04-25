"""Tests for the universal damage-feedback system (health bars + numbers)."""

import unittest
from types import SimpleNamespace

import pygame

import damage_feedback


def _entity(hp=20, max_hp=20, center=(50, 50)):
    rect = pygame.Rect(0, 0, 16, 16)
    rect.center = center
    return SimpleNamespace(current_hp=hp, max_hp=max_hp, rect=rect)


class HealthBarTrackerTests(unittest.TestCase):
    def setUp(self):
        damage_feedback.reset_all()

    def test_entity_unmarked_until_first_damage(self):
        ent = _entity()
        damage_feedback.report_damage(ent, 0)
        self.assertFalse(damage_feedback.get_health_bar_tracker().is_damaged(ent))

    def test_first_damage_registers_bar(self):
        ent = _entity()
        damage_feedback.report_damage(ent, 5, now_ticks=100)
        self.assertTrue(damage_feedback.get_health_bar_tracker().is_damaged(ent))

    def test_reset_clears_tracker(self):
        ent = _entity()
        damage_feedback.report_damage(ent, 3, now_ticks=100)
        damage_feedback.reset_all()
        self.assertFalse(damage_feedback.get_health_bar_tracker().is_damaged(ent))

    def test_entity_without_hp_not_tracked(self):
        ent = SimpleNamespace(rect=pygame.Rect(0, 0, 8, 8))
        # Should not raise; should not register since no current_hp/max_hp.
        damage_feedback.report_damage(ent, 4, now_ticks=100)
        self.assertFalse(damage_feedback.get_health_bar_tracker().is_damaged(ent))


class DamageNumberTrackerTests(unittest.TestCase):
    def setUp(self):
        damage_feedback.reset_all()

    def test_single_hit_creates_number(self):
        ent = _entity(center=(40, 60))
        damage_feedback.report_damage(ent, 7, now_ticks=100)
        active = damage_feedback.build_damage_number_views(now_ticks=120)
        self.assertEqual(len(active), 1)
        text, world_pos, age = active[0]
        self.assertEqual(text, "7")
        self.assertEqual(world_pos, (40, 60))
        self.assertGreater(age, 0)
        self.assertLess(age, 1)

    def test_rapid_hits_coalesce_into_sum_and_reset_age(self):
        ent = _entity(center=(40, 60))
        damage_feedback.report_damage(ent, 7, now_ticks=100)
        damage_feedback.report_damage(ent, 5, now_ticks=200)  # within window
        active = damage_feedback.build_damage_number_views(now_ticks=210)
        self.assertEqual(len(active), 1)
        text, _world_pos, age = active[0]
        self.assertEqual(text, "12")
        # Age fraction reflects time since the LATEST hit (200), not the first.
        expected_age = (210 - 200) / damage_feedback.DAMAGE_NUMBER_LIFETIME_MS
        self.assertAlmostEqual(age, expected_age, places=4)

    def test_outside_window_creates_new_number(self):
        ent = _entity(center=(0, 0))
        damage_feedback.report_damage(ent, 4, now_ticks=100)
        # Far outside the coalesce window, but within lifetime, so the first
        # number is still alive while a second is appended.
        damage_feedback.report_damage(
            ent,
            6,
            now_ticks=100 + damage_feedback.DAMAGE_NUMBER_COALESCE_WINDOW_MS + 100,
        )
        active = damage_feedback.build_damage_number_views(
            now_ticks=100 + damage_feedback.DAMAGE_NUMBER_COALESCE_WINDOW_MS + 110,
        )
        amounts = sorted(int(t) for (t, _, _) in active)
        self.assertEqual(amounts, [4, 6])

    def test_expired_numbers_are_pruned(self):
        ent = _entity(center=(0, 0))
        damage_feedback.report_damage(ent, 9, now_ticks=0)
        active = damage_feedback.build_damage_number_views(
            now_ticks=damage_feedback.DAMAGE_NUMBER_LIFETIME_MS + 1,
        )
        self.assertEqual(active, ())

    def test_coalesce_is_per_entity(self):
        a = _entity(center=(10, 10))
        b = _entity(center=(80, 80))
        damage_feedback.report_damage(a, 3, now_ticks=100)
        damage_feedback.report_damage(b, 4, now_ticks=110)
        active = damage_feedback.build_damage_number_views(now_ticks=120)
        amounts = sorted(int(t) for (t, _, _) in active)
        self.assertEqual(amounts, [3, 4])


class HealthBarProjectionTests(unittest.TestCase):
    def setUp(self):
        damage_feedback.reset_all()

    def test_player_excluded_from_world_bars(self):
        player = _entity(hp=10, center=(0, 0))
        enemy = _entity(hp=7, max_hp=10, center=(50, 50))
        damage_feedback.report_damage(player, 3, now_ticks=100)
        damage_feedback.report_damage(enemy, 3, now_ticks=100)
        bars = damage_feedback.build_entity_health_bar_views(
            ([player, enemy],), exclude=(player,)
        )
        self.assertEqual(len(bars), 1)
        rect, current_hp, max_hp = bars[0]
        self.assertEqual(rect.center, (50, 50))
        self.assertEqual(current_hp, 7)
        self.assertEqual(max_hp, 10)

    def test_undamaged_entities_have_no_bar(self):
        ent = _entity(hp=10, center=(50, 50))
        bars = damage_feedback.build_entity_health_bar_views(([ent],))
        self.assertEqual(bars, ())

    def test_dead_entities_excluded(self):
        ent = _entity(hp=0, center=(50, 50))
        damage_feedback.report_damage(ent, 5, now_ticks=100)
        bars = damage_feedback.build_entity_health_bar_views(([ent],))
        self.assertEqual(bars, ())


if __name__ == "__main__":
    unittest.main()
