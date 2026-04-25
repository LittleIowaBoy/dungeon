"""Tests for the per-instance ``is_frozen`` flag on enemies."""

import unittest
from types import SimpleNamespace

import pygame

import enemies
import enemy_collision_rules


pygame.init()
# Headless display for sprite operations.
pygame.display.set_mode((1, 1))


class FrozenEnemyMovementTests(unittest.TestCase):
    def test_default_is_not_frozen(self):
        enemy = enemies.PatrolEnemy(64, 64)
        self.assertFalse(enemy.is_frozen)

    def test_constructor_accepts_is_frozen(self):
        enemy = enemies.PatrolEnemy(64, 64, is_frozen=True)
        self.assertTrue(enemy.is_frozen)

    def test_random_and_chaser_constructors_accept_is_frozen(self):
        rand = enemies.RandomEnemy(64, 64, is_frozen=True)
        chaser = enemies.ChaserEnemy(64, 64, is_frozen=True)
        self.assertTrue(rand.is_frozen)
        self.assertTrue(chaser.is_frozen)


class FrozenEnemyCollisionTests(unittest.TestCase):
    def test_frozen_attacker_skipped(self):
        attacker = enemies.PatrolEnemy(50, 50, is_frozen=True)
        victim = enemies.PatrolEnemy(50, 50)
        # Force overlap.
        attacker.rect.center = (50, 50)
        victim.rect.center = (50, 50)
        group = pygame.sprite.Group(attacker, victim)
        events = enemy_collision_rules.apply_enemy_collisions(group, 1.0, now_ticks=100)
        self.assertEqual(events, [])

    def test_frozen_victim_skipped(self):
        attacker = enemies.PatrolEnemy(50, 50)
        victim = enemies.PatrolEnemy(50, 50, is_frozen=True)
        attacker.rect.center = (50, 50)
        victim.rect.center = (50, 50)
        group = pygame.sprite.Group(attacker, victim)
        events = enemy_collision_rules.apply_enemy_collisions(group, 1.0, now_ticks=100)
        self.assertEqual(events, [])

    def test_unfrozen_pair_still_collides(self):
        a = enemies.PatrolEnemy(50, 50)
        b = enemies.PatrolEnemy(50, 50)
        a.rect.center = (50, 50)
        b.rect.center = (50, 50)
        group = pygame.sprite.Group(a, b)
        events = enemy_collision_rules.apply_enemy_collisions(group, 1.0, now_ticks=100)
        self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
