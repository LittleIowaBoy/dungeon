"""Tests that enemies never spawn within the door buffer."""

import unittest

import pygame

from room import Room
from settings import ENEMY_DOOR_BUFFER_TILES, TILE_SIZE


pygame.init()
pygame.display.set_mode((1, 1))


class DoorSpawnBufferTests(unittest.TestCase):
    def test_random_floor_pos_respects_buffer(self):
        room = Room(
            doors={"left": True, "right": True, "top": True, "bottom": True},
            is_exit=False,
            enemy_count_range=(0, 0),
        )
        door_tiles = room._door_tile_set()
        self.assertTrue(door_tiles)
        for _ in range(200):
            px, py = room._random_floor_pos(margin=2)
            col = px // TILE_SIZE
            row = py // TILE_SIZE
            for dc, dr in door_tiles:
                cheby = max(abs(col - dc), abs(row - dr))
                self.assertGreater(cheby, ENEMY_DOOR_BUFFER_TILES)

    def test_generated_enemy_configs_clear_doors(self):
        room = Room(
            doors={"left": True, "right": True, "top": True, "bottom": True},
            is_exit=False,
            enemy_count_range=(8, 8),
            enemy_type_weights=[20, 20, 20, 20, 20],
        )
        door_tiles = room._door_tile_set()
        for _cls, (px, py) in room.enemy_configs:
            col = px // TILE_SIZE
            row = py // TILE_SIZE
            for dc, dr in door_tiles:
                cheby = max(abs(col - dc), abs(row - dr))
                self.assertGreater(cheby, ENEMY_DOOR_BUFFER_TILES)


if __name__ == "__main__":
    unittest.main()
