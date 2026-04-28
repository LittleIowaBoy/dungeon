"""Tests for LauncherEnemy + LauncherProjectile behaviour."""

import unittest

import pygame

import enemies
import enemy_attack_rules
from settings import (
    LAUNCHER_ATTACK_WINDUP_MS, LAUNCHER_PROJECTILE_DAMAGE,
    LAUNCHER_RANGE, TILE_SIZE,
)


pygame.init()
pygame.display.set_mode((1, 1))


class _Player:
    def __init__(self, x, y, hp=100):
        self.rect = pygame.Rect(0, 0, 22, 22)
        self.rect.center = (x, y)
        self.current_hp = hp
        self.is_invincible = False

    def take_damage(self, amount):
        self.current_hp -= amount


def _player_rect(x, y):
    rect = pygame.Rect(0, 0, 22, 22)
    rect.center = (x, y)
    return rect


class LauncherFiringTests(unittest.TestCase):
    def test_launcher_fires_projectile_after_telegraph(self):
        e = enemies.LauncherEnemy(200, 200)
        player_rect = _player_rect(200 + int(LAUNCHER_RANGE) - 4, 200)
        e.update_attack_state(player_rect, 1000)
        self.assertEqual(e._attack_state, enemies.ATTACK_TELEGRAPH)
        # No projectile yet during telegraph.
        self.assertEqual(e.consume_emitted_projectiles(), [])
        e.update_attack_state(player_rect, 1000 + LAUNCHER_ATTACK_WINDUP_MS + 1)
        self.assertEqual(e._attack_state, enemies.ATTACK_STRIKE)
        projectiles = e.consume_emitted_projectiles()
        self.assertEqual(len(projectiles), 1)
        proj = projectiles[0]
        # Aimed roughly at the player.
        self.assertGreater(proj._vx, 0)


class LauncherProjectileTests(unittest.TestCase):
    def test_projectile_damages_player(self):
        proj = enemies.LauncherProjectile(100, 100, 0, 0)
        player = _Player(100, 100, hp=100)
        group = pygame.sprite.Group(proj)
        enemy_attack_rules.apply_launcher_projectiles(group, player, None, [])
        self.assertEqual(player.current_hp, 100 - LAUNCHER_PROJECTILE_DAMAGE)
        self.assertFalse(proj.alive())

    def test_projectile_ignores_other_enemies(self):
        proj = enemies.LauncherProjectile(100, 100, 0, 0)
        other = enemies.PatrolEnemy(100, 100)
        group = pygame.sprite.Group(proj)
        # No player or allies — should not damage other enemy.
        events = enemy_attack_rules.apply_launcher_projectiles(group, None, None, [])
        self.assertEqual(events, [])
        self.assertGreater(other.current_hp, 0)

    def test_projectile_despawns_on_wall(self):
        proj = enemies.LauncherProjectile(100, 100, 1, 0)
        wall = pygame.Rect(80, 80, TILE_SIZE * 2, TILE_SIZE * 2)
        group = pygame.sprite.Group(proj)
        enemy_attack_rules.apply_launcher_projectiles(group, None, None, [wall])
        self.assertFalse(proj.alive())


if __name__ == "__main__":
    unittest.main()
