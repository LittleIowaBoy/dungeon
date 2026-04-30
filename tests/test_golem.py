"""Phase 0d: Golem mini-boss + GolemShard minion behaviour.

Covers:

* :class:`Golem` distance-gated attack selection (slam in melee, throw
  at range), phase-2-only enrage charge, projectile emission.
* :class:`GolemBoulderProjectile` motion + wall despawn.
* :class:`GolemShard` chase + melee strike.
"""

import math
import os
import sys
import unittest

import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import enemies  # noqa: E402
from enemies import (  # noqa: E402
    Golem, GolemShard, GolemBoulderProjectile,
    ATTACK_IDLE, ATTACK_TELEGRAPH, ATTACK_STRIKE,
)
from settings import (  # noqa: E402
    TILE_SIZE,
    GOLEM_HP, GOLEM_MELEE_TRIGGER, GOLEM_THROW_RANGE,
    GOLEM_SLAM_DAMAGE, GOLEM_SLAM_RADIUS,
    GOLEM_BOULDER_DAMAGE, GOLEM_BOULDER_RANGE, GOLEM_BOULDER_SPEED,
    GOLEM_ENRAGE_TRIGGER_MIN, GOLEM_ENRAGE_TRIGGER_MAX,
    GOLEM_SHARD_HP, GOLEM_SHARD_ATTACK_DAMAGE, GOLEM_SHARD_ATTACK_TRIGGER,
)


def _player_rect_at(x, y, size=24):
    return pygame.Rect(0, 0, size, size).move(x - size // 2, y - size // 2)


def _advance(enemy, now, player_rect=None):
    """Advance the attack state machine to ``now``."""
    enemy.update_attack_state(player_rect, now)


class GolemAttackSelectionTests(unittest.TestCase):
    def test_default_stats(self):
        g = Golem(0, 0)
        self.assertEqual(g.max_hp, GOLEM_HP)
        self.assertEqual(g.current_hp, GOLEM_HP)
        self.assertFalse(g.phase_2)

    def test_no_attack_outside_throw_range(self):
        g = Golem(0, 0)
        far = _player_rect_at(GOLEM_THROW_RANGE + 100, 0)
        _advance(g, 0, far)
        self.assertEqual(g._attack_state, ATTACK_IDLE)

    def test_slam_picked_when_player_in_melee(self):
        g = Golem(0, 0)
        close = _player_rect_at(GOLEM_MELEE_TRIGGER - 4, 0)
        _advance(g, 0, close)
        self.assertEqual(g._attack_state, ATTACK_TELEGRAPH)
        self.assertEqual(g._committed_attack, "slam")
        # Strike phase reveals a circular hitbox centred on the Golem.
        _advance(g, g.attack_windup_ms + 1, close)
        self.assertEqual(g._attack_state, ATTACK_STRIKE)
        hitboxes = g.active_hitboxes()
        self.assertEqual(len(hitboxes), 1)
        self.assertEqual(hitboxes[0].width, GOLEM_SLAM_RADIUS * 2)
        self.assertEqual(g.attack_damage, GOLEM_SLAM_DAMAGE)

    def test_throw_picked_when_player_at_range(self):
        g = Golem(0, 0)
        far = _player_rect_at(GOLEM_THROW_RANGE - TILE_SIZE, 0)
        _advance(g, 0, far)
        self.assertEqual(g._committed_attack, "throw")

    def test_throw_strike_emits_aimed_projectile(self):
        g = Golem(100, 100)
        far = _player_rect_at(100 + GOLEM_THROW_RANGE - TILE_SIZE, 100)
        _advance(g, 0, far)
        _advance(g, g.attack_windup_ms + 1, far)
        emitted = g.consume_emitted_projectiles()
        self.assertEqual(len(emitted), 1)
        proj = emitted[0]
        self.assertIsInstance(proj, GolemBoulderProjectile)
        # Aimed +x.
        self.assertGreater(proj._vx, 0)
        self.assertAlmostEqual(proj._vy, 0, places=5)
        self.assertAlmostEqual(
            math.hypot(proj._vx, proj._vy),
            GOLEM_BOULDER_SPEED,
            places=5,
        )
        # Spawn position is the golem centre.
        self.assertEqual(proj.rect.center, g.rect.center)
        # Subsequent calls drain the buffer.
        self.assertEqual(g.consume_emitted_projectiles(), [])

    def test_enrage_only_unlocks_in_phase_2_at_mid_range(self):
        g = Golem(0, 0)
        mid = _player_rect_at(
            (GOLEM_ENRAGE_TRIGGER_MIN + GOLEM_ENRAGE_TRIGGER_MAX) // 2, 0
        )
        # Phase 1 at mid range falls back to throw (still within throw range).
        _advance(g, 0, mid)
        self.assertEqual(g._committed_attack, "throw")
        # Reset and replay in phase 2.
        g2 = Golem(0, 0)
        g2.phase_2 = True
        _advance(g2, 0, mid)
        self.assertEqual(g2._committed_attack, "enrage")

    def test_attacks_disabled_skips_telegraph(self):
        g = Golem(0, 0)
        g.attacks_disabled = True
        close = _player_rect_at(GOLEM_MELEE_TRIGGER - 4, 0)
        _advance(g, 0, close)
        self.assertEqual(g._attack_state, ATTACK_IDLE)


class GolemBoulderProjectileTests(unittest.TestCase):
    def test_projectile_moves_each_update_until_range_exhausted(self):
        proj = GolemBoulderProjectile(0, 0, GOLEM_BOULDER_SPEED, 0)
        group = pygame.sprite.Group(proj)
        start_x = proj.rect.x
        proj.update()
        self.assertEqual(proj.rect.x, start_x + int(GOLEM_BOULDER_SPEED))
        self.assertTrue(proj.alive())
        # Push past the range → kill.
        ticks_needed = int(GOLEM_BOULDER_RANGE / GOLEM_BOULDER_SPEED) + 2
        for _ in range(ticks_needed):
            proj.update()
        self.assertFalse(proj.alive())
        self.assertEqual(len(group), 0)

    def test_projectile_despawns_on_wall_hit(self):
        proj = GolemBoulderProjectile(0, 0, GOLEM_BOULDER_SPEED, 0)
        pygame.sprite.Group(proj)
        wall = pygame.Rect(proj.rect.x, proj.rect.y, 50, 50)
        self.assertTrue(proj.collide_walls([wall]))
        self.assertFalse(proj.alive())

    def test_projectile_damage_matches_setting(self):
        proj = GolemBoulderProjectile(0, 0, 1.0, 0)
        self.assertEqual(proj.damage, GOLEM_BOULDER_DAMAGE)


class GolemShardTests(unittest.TestCase):
    def test_default_stats(self):
        s = GolemShard(0, 0)
        self.assertEqual(s.max_hp, GOLEM_SHARD_HP)
        self.assertEqual(s.current_hp, GOLEM_SHARD_HP)

    def test_shard_chases_player(self):
        s = GolemShard(0, 0)
        target = _player_rect_at(80, 0)
        s.update_movement(target, [])
        self.assertGreater(s.rect.centerx, 0)

    def test_shard_attacks_in_close_range(self):
        s = GolemShard(0, 0)
        close = _player_rect_at(GOLEM_SHARD_ATTACK_TRIGGER - 4, 0)
        # Movement step picks facing.
        s.update_movement(close, [])
        s.update_attack_state(close, 0)
        self.assertEqual(s._attack_state, ATTACK_TELEGRAPH)
        # Strike reveals a hitbox.
        s.update_attack_state(close, s.attack_windup_ms + 1)
        self.assertEqual(s._attack_state, ATTACK_STRIKE)
        self.assertEqual(s.attack_damage, GOLEM_SHARD_ATTACK_DAMAGE)
        boxes = s.active_hitboxes()
        self.assertEqual(len(boxes), 1)


class EnemyClassesRegistryTests(unittest.TestCase):
    def test_golem_and_shard_excluded_from_random_palette(self):
        self.assertNotIn(Golem, enemies.ENEMY_CLASSES)
        self.assertNotIn(GolemShard, enemies.ENEMY_CLASSES)


if __name__ == "__main__":
    unittest.main()
