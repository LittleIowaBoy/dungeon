import unittest
from types import SimpleNamespace

import pygame

import enemy_collision_rules as ecr


class _FakeEnemy:
    def __init__(self, x, y, *, hp=10, damage=5):
        self.rect = pygame.Rect(x, y, 20, 20)
        self.current_hp = hp
        self.damage = damage
        self._alive = True
        ecr.reset_collision_state(self)

    def take_damage(self, amount, damage_type=None):
        self.current_hp -= amount
        if self.current_hp <= 0:
            self._alive = False

    def alive(self):
        return self._alive


class _FakeGroup(list):
    pass


class MultiplierLookupTests(unittest.TestCase):
    def test_default_zero_when_state_missing(self):
        p = SimpleNamespace()
        self.assertEqual(ecr.enemy_vs_enemy_multiplier(p), 0.0)

    def test_default_zero_when_no_key(self):
        p = SimpleNamespace(rune_state={})
        self.assertEqual(ecr.enemy_vs_enemy_multiplier(p), 0.0)

    def test_reads_value(self):
        p = SimpleNamespace(rune_state={"enemy_vs_enemy_multiplier": 2.5})
        self.assertEqual(ecr.enemy_vs_enemy_multiplier(p), 2.5)

    def test_invalid_value_falls_back_to_zero(self):
        p = SimpleNamespace(rune_state={"enemy_vs_enemy_multiplier": "nope"})
        self.assertEqual(ecr.enemy_vs_enemy_multiplier(p), 0.0)


class CollisionTests(unittest.TestCase):
    def test_no_op_when_multiplier_zero(self):
        a = _FakeEnemy(0, 0)
        b = _FakeEnemy(5, 5)  # overlap
        events = ecr.apply_enemy_collisions(_FakeGroup([a, b]), 0.0, 1000)
        self.assertEqual(events, [])
        self.assertEqual(a.current_hp, 10)
        self.assertEqual(b.current_hp, 10)

    def test_collision_damages_both_enemies(self):
        a = _FakeEnemy(0, 0, damage=4)
        b = _FakeEnemy(5, 5, damage=6)
        events = ecr.apply_enemy_collisions(_FakeGroup([a, b]), 1.0, 1000)
        self.assertEqual(len(events), 1)
        # a damaged b by a.damage*1.0 = 4; b damaged a by b.damage*1.0 = 6
        self.assertEqual(b.current_hp, 6)
        self.assertEqual(a.current_hp, 4)

    def test_no_collision_when_far(self):
        a = _FakeEnemy(0, 0)
        b = _FakeEnemy(500, 500)
        events = ecr.apply_enemy_collisions(_FakeGroup([a, b]), 5.0, 1000)
        self.assertEqual(events, [])

    def test_cooldown_prevents_immediate_re_hit(self):
        a = _FakeEnemy(0, 0, damage=1)
        b = _FakeEnemy(5, 5, damage=1)
        ecr.apply_enemy_collisions(_FakeGroup([a, b]), 1.0, 1000)
        ecr.apply_enemy_collisions(_FakeGroup([a, b]), 1.0, 1100)
        # only first hit landed
        self.assertEqual(a.current_hp, 9)
        self.assertEqual(b.current_hp, 9)

    def test_cooldown_expires(self):
        a = _FakeEnemy(0, 0, damage=1)
        b = _FakeEnemy(5, 5, damage=1)
        ecr.apply_enemy_collisions(_FakeGroup([a, b]), 1.0, 1000)
        later = 1000 + ecr.COLLISION_COOLDOWN_MS + 1
        ecr.apply_enemy_collisions(_FakeGroup([a, b]), 1.0, later)
        self.assertEqual(a.current_hp, 8)
        self.assertEqual(b.current_hp, 8)

    def test_dead_enemies_skipped(self):
        a = _FakeEnemy(0, 0)
        b = _FakeEnemy(5, 5, hp=1, damage=1)
        ecr.apply_enemy_collisions(_FakeGroup([a, b]), 5.0, 1000)
        self.assertFalse(b.alive())
        # a took 5 damage, still alive
        self.assertEqual(a.current_hp, 5)

    def test_multiplier_scales_damage(self):
        a = _FakeEnemy(0, 0, damage=4)
        b = _FakeEnemy(5, 5, damage=4)
        ecr.apply_enemy_collisions(_FakeGroup([a, b]), 5.0, 1000)
        # 4 * 5 = 20 → b dies, a takes 20 too
        self.assertFalse(b.alive())
        self.assertFalse(a.alive())


if __name__ == "__main__":
    unittest.main()
