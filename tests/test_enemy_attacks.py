"""Tests for telegraphed-attack hitbox geometry on base enemies."""

import unittest
from types import SimpleNamespace

import pygame

import enemies
from enemies import (
    ATTACK_IDLE, ATTACK_STRIKE, ATTACK_TELEGRAPH,
)
from settings import (
    PATROL_ATTACK_RADIUS, PATROL_ATTACK_TRIGGER,
    RANDOM_ATTACK_RANGE, RANDOM_ATTACK_TRIGGER, RANDOM_ATTACK_WIDTH,
    CHASER_ATTACK_OFFSET, CHASER_ATTACK_SIZE, CHASE_RADIUS,
    TILE_SIZE,
)


pygame.init()
pygame.display.set_mode((1, 1))


def _player_rect_at(x, y, w=20, h=20):
    rect = pygame.Rect(0, 0, w, h)
    rect.center = (x, y)
    return rect


def _force_strike(enemy, player_rect, now=1000):
    """Drive an enemy through TELEGRAPH → STRIKE so hitboxes are active."""
    enemy.update_attack_state(player_rect, now)
    self_state = enemy._attack_state
    if self_state == ATTACK_IDLE:
        return False
    enemy.update_attack_state(player_rect, now + enemy.attack_windup_ms + 1)
    return enemy._attack_state == ATTACK_STRIKE


class PatrolAttackTests(unittest.TestCase):
    def test_patrol_strike_is_360_square_around_self(self):
        e = enemies.PatrolEnemy(200, 200)
        player_rect = _player_rect_at(200 + int(PATROL_ATTACK_TRIGGER) - 4, 200)
        self.assertTrue(_force_strike(e, player_rect))
        boxes = e.active_hitboxes()
        self.assertEqual(len(boxes), 1)
        rect = boxes[0]
        self.assertEqual(rect.width, int(PATROL_ATTACK_RADIUS * 2))
        self.assertEqual(rect.center, e.rect.center)


class RandomAttackTests(unittest.TestCase):
    def test_random_strike_is_long_thin_line(self):
        e = enemies.RandomEnemy(200, 200)
        # Player to the right.
        player_rect = _player_rect_at(200 + int(RANDOM_ATTACK_TRIGGER) - 4, 200)
        self.assertTrue(_force_strike(e, player_rect))
        boxes = e.active_hitboxes()
        rect = boxes[0]
        self.assertEqual(rect.width, int(RANDOM_ATTACK_RANGE))
        self.assertEqual(rect.height, RANDOM_ATTACK_WIDTH)
        # Attack should originate at the enemy and extend toward the player.
        self.assertEqual(rect.midleft, e.rect.center)


class ChaserAttackTests(unittest.TestCase):
    def test_chaser_strike_is_front_square(self):
        e = enemies.ChaserEnemy(200, 200)
        # Place player one tile to the right and trigger chase.
        player_rect = _player_rect_at(200 + TILE_SIZE, 200)
        # update_movement promotes chasing flag and sets _facing.
        e.update_movement(player_rect, [])
        self.assertTrue(_force_strike(e, player_rect))
        boxes = e.active_hitboxes()
        rect = boxes[0]
        self.assertEqual(rect.width, CHASER_ATTACK_SIZE)
        self.assertEqual(rect.height, CHASER_ATTACK_SIZE)
        self.assertGreater(rect.centerx, e.rect.centerx)


if __name__ == "__main__":
    unittest.main()
