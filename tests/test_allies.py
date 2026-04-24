"""Tests for friendly NPCs (allies.py) — primarily the SkeletonAlly summoned by the Necromancer rune."""

import unittest
from types import SimpleNamespace

import pygame

import allies


def _setup_pygame():
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
        pygame.display.set_mode((1, 1))


class _Enemy(pygame.sprite.Sprite):
    """Minimal enemy stub: rect + take_damage."""

    def __init__(self, x, y, hp=100):
        super().__init__()
        self.image = pygame.Surface((26, 26))
        self.rect = self.image.get_rect(center=(x, y))
        self.current_hp = hp
        self.max_hp = hp
        self.took = []

    def take_damage(self, amount):
        self.took.append(amount)
        self.current_hp -= amount


class _Player:
    def __init__(self, x=200, y=200):
        self.rect = pygame.Rect(x - 16, y - 16, 32, 32)


class SkeletonAllyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _setup_pygame()

    def test_construct_sets_hp_and_position(self):
        ally = allies.SkeletonAlly(100, 200, spawn_ticks=500)
        self.assertEqual(ally.current_hp, allies.SKELETON_HP)
        self.assertEqual(ally.max_hp, allies.SKELETON_HP)
        self.assertEqual(ally.rect.center, (100, 200))

    def test_take_damage_kills_at_zero(self):
        group = pygame.sprite.Group()
        ally = allies.SkeletonAlly(0, 0)
        group.add(ally)
        ally.take_damage(allies.SKELETON_HP)
        self.assertNotIn(ally, group)

    def test_pick_target_returns_nearest_enemy(self):
        ally = allies.SkeletonAlly(0, 0)
        group = pygame.sprite.Group(_Enemy(500, 0), _Enemy(50, 0), _Enemy(300, 0))
        target = ally.pick_target(group)
        self.assertEqual(target.rect.centerx, 50)

    def test_pick_target_returns_none_for_empty_group(self):
        ally = allies.SkeletonAlly(0, 0)
        self.assertIsNone(ally.pick_target(pygame.sprite.Group()))

    def test_update_movement_steps_toward_target(self):
        ally = allies.SkeletonAlly(0, 0)
        target = pygame.Rect(100 - 13, 0 - 13, 26, 26)
        before = ally.rect.centerx
        ally.update_movement(target, [])
        self.assertGreater(ally.rect.centerx, before)

    def test_update_movement_none_holds_position(self):
        ally = allies.SkeletonAlly(0, 0)
        before = ally.rect.center
        ally.update_movement(None, [])
        self.assertEqual(ally.rect.center, before)

    def test_try_attack_lands_on_collision_when_ready(self):
        ally = allies.SkeletonAlly(100, 100)
        enemy = _Enemy(100, 100)  # overlapping
        landed = ally.try_attack(enemy, now_ticks=1000)
        self.assertTrue(landed)
        self.assertEqual(enemy.took, [allies.SKELETON_DAMAGE])

    def test_try_attack_skips_when_out_of_range(self):
        ally = allies.SkeletonAlly(0, 0)
        enemy = _Enemy(500, 500)
        self.assertFalse(ally.try_attack(enemy, now_ticks=1000))
        self.assertEqual(enemy.took, [])

    def test_try_attack_respects_cooldown(self):
        ally = allies.SkeletonAlly(100, 100)
        enemy = _Enemy(100, 100)
        ally.try_attack(enemy, now_ticks=1000)
        # cooldown not yet elapsed
        self.assertFalse(
            ally.try_attack(enemy, now_ticks=1000 + allies.SKELETON_ATTACK_COOLDOWN_MS - 1)
        )
        self.assertEqual(len(enemy.took), 1)
        # cooldown elapsed
        self.assertTrue(
            ally.try_attack(enemy, now_ticks=1000 + allies.SKELETON_ATTACK_COOLDOWN_MS)
        )
        self.assertEqual(len(enemy.took), 2)

    def test_expired_after_lifetime(self):
        ally = allies.SkeletonAlly(0, 0, spawn_ticks=0)
        self.assertFalse(ally.expired(now_ticks=allies.SKELETON_LIFETIME_MS - 1))
        self.assertTrue(ally.expired(now_ticks=allies.SKELETON_LIFETIME_MS))


class SpawnAndUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _setup_pygame()

    def test_spawn_skeleton_near_adds_to_group(self):
        group = pygame.sprite.Group()
        player = _Player(300, 300)
        ally = allies.spawn_skeleton_near(player, group, now_ticks=500, jitter=0)
        self.assertIn(ally, group)
        self.assertEqual(ally.rect.center, (300, 300))

    def test_update_allies_moves_ally_toward_enemy(self):
        ally_group = pygame.sprite.Group(allies.SkeletonAlly(0, 0))
        enemy_group = pygame.sprite.Group(_Enemy(400, 0))
        player = _Player(0, 0)
        before = next(iter(ally_group)).rect.centerx
        allies.update_allies(ally_group, enemy_group, player, [], now_ticks=100)
        after = next(iter(ally_group)).rect.centerx
        self.assertGreater(after, before)

    def test_update_allies_attacks_adjacent_enemy(self):
        ally = allies.SkeletonAlly(100, 100)
        enemy = _Enemy(100, 100)
        ally_group = pygame.sprite.Group(ally)
        enemy_group = pygame.sprite.Group(enemy)
        player = _Player(100, 100)
        allies.update_allies(ally_group, enemy_group, player, [], now_ticks=1000)
        self.assertEqual(enemy.took, [allies.SKELETON_DAMAGE])

    def test_update_allies_idles_near_player_when_no_enemies(self):
        # Place ally close to player → should not move.
        ally = allies.SkeletonAlly(200, 200)
        ally_group = pygame.sprite.Group(ally)
        player = _Player(200, 200)
        before = ally.rect.center
        allies.update_allies(
            ally_group, pygame.sprite.Group(), player, [], now_ticks=0
        )
        self.assertEqual(ally.rect.center, before)

    def test_update_allies_drifts_to_player_when_far(self):
        ally = allies.SkeletonAlly(0, 0)
        ally_group = pygame.sprite.Group(ally)
        player = _Player(500, 0)
        allies.update_allies(
            ally_group, pygame.sprite.Group(), player, [], now_ticks=0
        )
        self.assertGreater(ally.rect.centerx, 0)

    def test_update_allies_despawns_expired_allies(self):
        ally = allies.SkeletonAlly(0, 0, spawn_ticks=0)
        ally_group = pygame.sprite.Group(ally)
        allies.update_allies(
            ally_group, pygame.sprite.Group(), _Player(), [],
            now_ticks=allies.SKELETON_LIFETIME_MS,
        )
        self.assertNotIn(ally, ally_group)


if __name__ == "__main__":
    unittest.main()
