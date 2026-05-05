"""Tests for the PulsatorEnemy and PulsatorRing damage rings."""

import unittest
from types import SimpleNamespace

import pygame

import enemies
import enemy_attack_rules
from settings import (
    PULSATOR_RING_DAMAGE, PULSATOR_RING_THICKNESS, PULSATOR_WINDUP_MS,
)


pygame.init()
pygame.display.set_mode((1, 1))


def _make_player(x, y, hp=100):
    rect = pygame.Rect(0, 0, 22, 22)
    rect.center = (x, y)
    return SimpleNamespace(
        rect=rect,
        current_hp=hp,
        is_invincible=False,
        take_damage=lambda amount, _self=None: None,
    )


class _Player:
    def __init__(self, x, y, hp=100):
        self.rect = pygame.Rect(0, 0, 22, 22)
        self.rect.center = (x, y)
        self.current_hp = hp
        self.is_invincible = False

    def take_damage(self, amount, damage_type=None):
        self.current_hp -= amount


class PulsatorRingTests(unittest.TestCase):
    def test_ring_hits_player_once(self):
        ring = enemies.PulsatorRing((100, 100))
        # Force ring radius to overlap player at (140, 100).
        player = _Player(140, 100)
        ring.radius = 40.0
        struck = ring.hit_targets([player])
        self.assertEqual(struck, [player])
        # Same target should not be struck again by the same ring.
        struck_again = ring.hit_targets([player])
        self.assertEqual(struck_again, [])

    def test_ring_ignores_other_enemies(self):
        ring = enemies.PulsatorRing((100, 100))
        ring.radius = 40.0
        player = _Player(140, 100)
        other = enemies.PatrolEnemy(140, 100)
        # Even when other enemy is in the band, apply_pulsator_rings only
        # damages the player+allies passed in (not the enemy_group).
        group = pygame.sprite.Group(ring)
        events = enemy_attack_rules.apply_pulsator_rings(group, player, None)
        damaged = [evt[1] for evt in events]
        self.assertIn(player, damaged)
        self.assertNotIn(other, damaged)

    def test_apply_pulsator_rings_deals_damage(self):
        ring = enemies.PulsatorRing((100, 100))
        ring.radius = 40.0
        player = _Player(140, 100, hp=100)
        group = pygame.sprite.Group(ring)
        enemy_attack_rules.apply_pulsator_rings(group, player, None)
        self.assertEqual(player.current_hp, 100 - PULSATOR_RING_DAMAGE)


class PulsatorTelegraphTests(unittest.TestCase):
    def test_pulsator_emits_ring_after_telegraph(self):
        e = enemies.PulsatorEnemy(100, 100)
        # Snap onto first anchor so _can_begin_attack triggers.
        e.rect.center = e._anchor_points[0]
        e.update_attack_state(None, 1000)
        self.assertEqual(e._attack_state, enemies.ATTACK_TELEGRAPH)
        # Advance past telegraph windup.
        e.update_attack_state(None, 1000 + PULSATOR_WINDUP_MS + 1)
        self.assertEqual(e._attack_state, enemies.ATTACK_STRIKE)
        rings = e.consume_emitted_rings()
        self.assertEqual(len(rings), 1)


if __name__ == "__main__":
    unittest.main()
