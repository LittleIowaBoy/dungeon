"""Tests for the per-room palette cap of distinct enemy types."""

import unittest

import pygame

import enemies
from room import Room
from settings import ROOM_MAX_DISTINCT_ENEMY_TYPES


pygame.init()
pygame.display.set_mode((1, 1))


def _build_random_room(weights):
    return Room(
        doors={"left": True, "right": True, "top": True, "bottom": True},
        is_exit=False,
        enemy_count_range=(8, 8),
        enemy_type_weights=weights,
    )


class EnemyPaletteTests(unittest.TestCase):
    def test_at_most_three_distinct_types_per_room(self):
        # Equal weights across all 5 classes — every room should still
        # cap at 3 distinct types.
        for _ in range(40):
            room = _build_random_room([20, 20, 20, 20, 20])
            classes = {cls for (cls, _pos) in room.enemy_configs}
            self.assertLessEqual(len(classes), ROOM_MAX_DISTINCT_ENEMY_TYPES)

    def test_palette_cached_for_reinforcements(self):
        room = _build_random_room([20, 20, 20, 20, 20])
        first = room._build_enemy_palette()
        second = room._build_enemy_palette()
        self.assertIs(first, second)

    def test_palette_excludes_zero_weight_classes_when_possible(self):
        # Only Patrol + Random allowed.
        room = _build_random_room([50, 50, 0, 0, 0])
        palette_classes, _ = room._build_enemy_palette()
        self.assertTrue(set(palette_classes).issubset({enemies.PatrolEnemy, enemies.RandomEnemy}))

    def test_short_weight_list_padded(self):
        # Legacy-shaped 3-weight list should not crash and should still
        # cap to 3 distinct types.
        room = _build_random_room([50, 35, 15])
        classes = {cls for (cls, _pos) in room.enemy_configs}
        self.assertLessEqual(len(classes), ROOM_MAX_DISTINCT_ENEMY_TYPES)
        self.assertTrue(classes.issubset(set(enemies.ENEMY_CLASSES)))


if __name__ == "__main__":
    unittest.main()
