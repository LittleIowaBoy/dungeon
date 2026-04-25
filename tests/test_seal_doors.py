"""Tests for biome-themed seal doors that physically block movement."""

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from camera import Camera, SEAL_DOOR_THEMES  # noqa: E402
from enemies import PatrolEnemy  # noqa: E402
from room import Room  # noqa: E402
from settings import (  # noqa: E402
    DOOR_WIDTH,
    ROOM_COLS,
    ROOM_ROWS,
    TILE_SIZE,
)


def _build_plain_room(*, terrain_type=None, doors=None):
    if doors is None:
        doors = {"left": True, "right": True, "top": True, "bottom": True}
    return Room(doors=doors, is_exit=False, terrain_type=terrain_type)


class SealDoorRectTests(unittest.TestCase):
    def test_get_seal_door_rects_one_per_present_door(self):
        room = _build_plain_room(
            doors={"left": True, "right": False, "top": True, "bottom": False},
        )
        results = room.get_seal_door_rects()
        directions = {direction for direction, _rect in results}
        self.assertEqual(directions, {"left", "top"})

    def test_seal_door_rect_spans_door_opening_width(self):
        room = _build_plain_room(
            doors={"left": True, "right": False, "top": False, "bottom": False},
        )
        ((direction, rect),) = room.get_seal_door_rects()
        expected_span = (DOOR_WIDTH // 2 * 2 + 1) * TILE_SIZE
        self.assertEqual(direction, "left")
        self.assertEqual(rect.x, 0)
        self.assertEqual(rect.width, TILE_SIZE)
        self.assertEqual(rect.height, expected_span)
        # Vertically centered.
        self.assertEqual(rect.centery, (ROOM_ROWS // 2) * TILE_SIZE + TILE_SIZE // 2)

    def test_seal_door_rect_for_top_door_centered_horizontally(self):
        room = _build_plain_room(
            doors={"left": False, "right": False, "top": True, "bottom": False},
        )
        ((direction, rect),) = room.get_seal_door_rects()
        self.assertEqual(direction, "top")
        self.assertEqual(rect.y, 0)
        self.assertEqual(rect.height, TILE_SIZE)
        self.assertEqual(rect.centerx, (ROOM_COLS // 2) * TILE_SIZE + TILE_SIZE // 2)


class GetWallRectsIncludesSealDoorsTests(unittest.TestCase):
    def test_wall_rects_omits_door_rects_when_unsealed(self):
        room = _build_plain_room()
        # No enemies → not sealed.
        room.enemy_configs = []
        room.enemies_cleared = False
        self.assertFalse(room.doors_sealed)
        wall_rects = room.get_wall_rects()
        # None of the wall rects should overlap the door opening center.
        door_rects = [rect for _, rect in room.get_seal_door_rects()]
        for door_rect in door_rects:
            for wall in wall_rects:
                self.assertFalse(
                    wall.colliderect(door_rect)
                    and wall.center == door_rect.center,
                    f"door {door_rect} unexpectedly blocked by wall {wall}",
                )

    def test_wall_rects_includes_door_rects_when_sealed(self):
        room = _build_plain_room()
        room.enemy_configs = [(PatrolEnemy, (TILE_SIZE * 5, TILE_SIZE * 5))]
        room.enemies_cleared = False
        self.assertTrue(room.doors_sealed)

        wall_rects = room.get_wall_rects()
        for direction, door_rect in room.get_seal_door_rects():
            self.assertIn(
                door_rect, wall_rects,
                f"sealed {direction} door rect missing from wall rects",
            )


class BiomeTerrainExposureTests(unittest.TestCase):
    def test_biome_terrain_returns_constructor_terrain_type(self):
        for biome in ("mud", "ice", "water"):
            room = _build_plain_room(terrain_type=biome)
            self.assertEqual(room.biome_terrain, biome)

    def test_biome_terrain_none_when_unspecified(self):
        room = _build_plain_room(terrain_type=None)
        self.assertIsNone(room.biome_terrain)


class SealDoorThemeTests(unittest.TestCase):
    def test_themes_defined_for_every_biome_and_default(self):
        for key in ("mud", "ice", "water", None):
            self.assertIn(key, SEAL_DOOR_THEMES)
            theme = SEAL_DOOR_THEMES[key]
            self.assertIn("base", theme)
            self.assertIn("band", theme)
            self.assertIn("frame", theme)

    def test_each_biome_uses_distinct_base_color(self):
        bases = {
            key: SEAL_DOOR_THEMES[key]["base"]
            for key in ("mud", "ice", "water", None)
        }
        self.assertEqual(len(set(bases.values())), len(bases))


class CameraSealDoorRenderingTests(unittest.TestCase):
    def test_draw_sealed_door_markers_paints_themed_doors(self):
        pygame.init()
        surface = pygame.Surface((ROOM_COLS * TILE_SIZE, ROOM_ROWS * TILE_SIZE))
        # Solid magenta background to detect any draw.
        background = (255, 0, 255)
        surface.fill(background)

        room = _build_plain_room(terrain_type="mud")
        room.enemy_configs = [(PatrolEnemy, (TILE_SIZE * 5, TILE_SIZE * 5))]
        room.enemies_cleared = False
        dungeon = SimpleNamespace(current_room=room)

        Camera()._draw_sealed_door_markers(surface, dungeon)

        # Sample the center of every present door rect; it must no longer be
        # the magenta background and must match the mud theme's frame color
        # (the central stud).
        expected_center_color = SEAL_DOOR_THEMES["mud"]["frame"]
        for _direction, rect in room.get_seal_door_rects():
            cx, cy = rect.center
            sampled = surface.get_at((cx, cy))[:3]
            self.assertEqual(tuple(sampled), expected_center_color)

    def test_draw_sealed_door_markers_no_op_when_unsealed(self):
        pygame.init()
        surface = pygame.Surface((ROOM_COLS * TILE_SIZE, ROOM_ROWS * TILE_SIZE))
        background = (255, 0, 255)
        surface.fill(background)

        room = _build_plain_room(terrain_type="mud")
        room.enemy_configs = []
        room.enemies_cleared = False
        dungeon = SimpleNamespace(current_room=room)

        Camera()._draw_sealed_door_markers(surface, dungeon)

        # Background untouched.
        self.assertEqual(tuple(surface.get_at((10, 10))[:3]), background)


if __name__ == "__main__":
    unittest.main()
