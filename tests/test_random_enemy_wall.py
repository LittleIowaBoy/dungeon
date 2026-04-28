"""Regression tests for the RandomEnemy wall-stuck bug."""

import unittest

import pygame

import enemies
from settings import TILE_SIZE


pygame.init()
pygame.display.set_mode((1, 1))


def _corner_walls():
    """Return wall rects forming an L-shape pinning a small corner."""
    walls = []
    # Vertical wall at x=0, full height.
    walls.append(pygame.Rect(-TILE_SIZE, 0, TILE_SIZE, 600))
    # Horizontal wall along the top.
    walls.append(pygame.Rect(0, -TILE_SIZE, 600, TILE_SIZE))
    return walls


class RandomEnemyWallTests(unittest.TestCase):
    def test_does_not_stay_pinned_to_corner(self):
        walls = _corner_walls()
        # Spawn directly against the top-left corner.
        enemy = enemies.RandomEnemy(20, 20)
        # Force a known stuck direction (NW) so the test is deterministic.
        enemy._dx = -1.0
        enemy._dy = -1.0
        enemy._timer = 1000  # avoid timer-driven re-pick
        start_x = enemy.rect.x
        start_y = enemy.rect.y

        max_pin_streak = 0
        streak = 0
        moved_far = False
        for _ in range(600):
            prev_x, prev_y = enemy.rect.x, enemy.rect.y
            enemy.update_movement(None, walls)
            if (enemy.rect.x, enemy.rect.y) == (prev_x, prev_y):
                streak += 1
                max_pin_streak = max(max_pin_streak, streak)
            else:
                streak = 0
            if abs(enemy.rect.x - start_x) > 2 * TILE_SIZE or abs(enemy.rect.y - start_y) > 2 * TILE_SIZE:
                moved_far = True
                break

        self.assertTrue(moved_far, f"enemy never escaped corner; max pin streak={max_pin_streak}")
        self.assertLess(max_pin_streak, 30)


if __name__ == "__main__":
    unittest.main()
