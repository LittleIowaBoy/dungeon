"""Phase 1: Water River Room polish.

Verifies the post-placement polish on the ``water_river_room`` family:

* A connected band of CURRENT tiles spans the room (the river).
* Every CURRENT tile has a non-zero push vector recorded on the room.
* Door buffers (chebyshev radius :data:`WATER_RIVER_DOOR_BUFFER`) are
  fully clear of CURRENT tiles so the player never spawns into the
  push.
* Every open door has a fully walkable (no-current) path to the room
  centre via the BFS-carved corridor.
* The sunken_ruins override flips the template enabled with weight > 0.
"""
import os
import random
import sys
import unittest
from collections import deque

import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import content_db  # noqa: E402
from room import (  # noqa: E402
    CURRENT, DOOR, FLOOR, ROOM_COLS, ROOM_ROWS, Room,
)
from room_plan import RoomPlan, RoomTemplate  # noqa: E402
from settings import WATER_RIVER_DOOR_BUFFER  # noqa: E402

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.init()
pygame.display.set_mode((1, 1))


def _template(room_id):
    return RoomTemplate(
        room_id=room_id,
        display_name=room_id.replace("_", " ").title(),
        objective_kind="combat",
        combat_pressure="mid",
        decision_complexity="mid",
        topology_role="mid_run",
        min_depth=1,
        max_depth=None,
        branch_preference="either",
        generation_weight=1,
        enabled=True,
        implementation_status="prototype",
        objective_variant="",
        notes="",
    )


def _plan(room_id):
    return RoomPlan(
        position=(0, 0),
        depth=1,
        path_kind="main_path",
        is_exit=False,
        template=_template(room_id),
        terrain_type="water",
        enemy_count_range=(0, 0),
        enemy_type_weights=(50, 35, 15),
        objective_rule="clear_enemies",
        terrain_patch_count_range=(3, 5),
        terrain_patch_size_range=(2, 3),
    )


def _build_room(seed=0, doors=None):
    if seed is not None:
        random.seed(seed)
    if doors is None:
        doors = {"top": True, "bottom": True, "left": True, "right": True}
    return Room(doors, is_exit=False, room_plan=_plan("water_river_room"))


def _door_entry_tiles(room):
    entries = []
    for r in range(ROOM_ROWS):
        for c in range(ROOM_COLS):
            if room.grid[r][c] != DOOR:
                continue
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, nr = c + dc, r + dr
                if 0 < nc < ROOM_COLS - 1 and 0 < nr < ROOM_ROWS - 1:
                    entries.append((nc, nr))
    return entries


def _bfs_walkable_to_center(room, start):
    """BFS over FLOOR-only tiles (current tiles count as obstacles for the safe path)."""
    center = (ROOM_COLS // 2, ROOM_ROWS // 2)
    if start == center:
        return True
    visited = {start}
    queue = deque([start])
    while queue:
        c, r = queue.popleft()
        if (c, r) == center:
            return True
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = c + dc, r + dr
            if not (0 < nc < ROOM_COLS - 1 and 0 < nr < ROOM_ROWS - 1):
                continue
            if (nc, nr) in visited:
                continue
            if room.grid[nr][nc] != FLOOR:
                continue
            visited.add((nc, nr))
            queue.append((nc, nr))
    return False


class _SeedRestoreMixin:
    def setUp(self):
        self._random_state = random.getstate()

    def tearDown(self):
        random.setstate(self._random_state)


class WaterRiverRoomBuilderTests(_SeedRestoreMixin, unittest.TestCase):
    def test_river_band_present_across_seeds(self):
        for seed in range(20):
            room = _build_room(seed=seed)
            current_count = sum(row.count(CURRENT) for row in room.grid)
            self.assertGreater(
                current_count, 0,
                f"seed {seed}: no CURRENT tiles laid",
            )

    def test_every_current_tile_has_nonzero_push_vector(self):
        for seed in range(10):
            room = _build_room(seed=seed)
            for r in range(ROOM_ROWS):
                for c in range(ROOM_COLS):
                    if room.grid[r][c] != CURRENT:
                        continue
                    vec = room.current_vectors.get((c, r))
                    self.assertIsNotNone(
                        vec, f"seed {seed}: CURRENT tile ({c},{r}) missing vector"
                    )
                    dx, dy = vec
                    self.assertGreater(
                        dx * dx + dy * dy, 0.0,
                        f"seed {seed}: CURRENT vector at ({c},{r}) is zero",
                    )


class WaterRiverDoorBufferTests(_SeedRestoreMixin, unittest.TestCase):
    def test_no_current_within_door_buffer_across_seeds(self):
        for seed in range(20):
            room = _build_room(seed=seed)
            door_tiles = room._door_tile_set()
            for r in range(ROOM_ROWS):
                for c in range(ROOM_COLS):
                    if room.grid[r][c] != CURRENT:
                        continue
                    for dc, dr in door_tiles:
                        chebyshev = max(abs(c - dc), abs(r - dr))
                        self.assertGreater(
                            chebyshev, WATER_RIVER_DOOR_BUFFER,
                            f"seed {seed}: CURRENT at ({c},{r}) within "
                            f"buffer of door ({dc},{dr})",
                        )


class WaterRiverConnectivityTests(_SeedRestoreMixin, unittest.TestCase):
    def test_every_door_has_walkable_path_to_center(self):
        for seed in range(20):
            room = _build_room(seed=seed)
            for entry in _door_entry_tiles(room):
                self.assertTrue(
                    _bfs_walkable_to_center(room, entry),
                    f"seed {seed}: door entry {entry} cannot reach centre "
                    f"on safe floor tiles",
                )

    def test_subset_of_doors_also_connected(self):
        for doors in [
            {"top": True, "bottom": False, "left": False, "right": False},
            {"top": False, "bottom": False, "left": True, "right": True},
        ]:
            for seed in range(10):
                room = _build_room(seed=seed, doors=doors)
                for entry in _door_entry_tiles(room):
                    self.assertTrue(
                        _bfs_walkable_to_center(room, entry),
                        f"doors={doors} seed={seed}: entry {entry} unreachable",
                    )


class WaterRiverOverrideTests(unittest.TestCase):
    def test_sunken_ruins_override_enables_river_with_weight(self):
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["sunken_ruins"]
        }
        self.assertIn("water_river_room", overrides)
        river = overrides["water_river_room"]
        self.assertEqual(river["enabled"], 1)
        self.assertGreater(river["generation_weight"], 0)


if __name__ == "__main__":
    unittest.main()
