"""Phase 3: Quicksand Trap room deepening.

Verifies the post-placement polish on the ``earth_quicksand_trap``
family:

* The door buffer (chebyshev radius :data:`QUICKSAND_TRAP_DOOR_BUFFER`)
  around every open door is fully clear of QUICKSAND tiles, so the
  player never spawns into a pull zone.
* Every open door has a fully walkable (no-quicksand) path to the room
  centre, even when the random patch placement would otherwise wall off
  the entrance.
* The polish preserves the quicksand mechanic — at least some QUICKSAND
  tiles survive the cleanup so the room still has its hazard.
* The template advertises an ``objective_label`` so the HUD chrome
  shows "Quicksand Trap" instead of the empty default.
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
    DOOR, FLOOR, QUICKSAND, ROOM_COLS, ROOM_ROWS, Room,
)
from room_plan import RoomPlan, RoomTemplate  # noqa: E402
from settings import QUICKSAND_TRAP_DOOR_BUFFER  # noqa: E402

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
        terrain_type="mud",
        enemy_count_range=(0, 0),
        enemy_type_weights=(50, 35, 15),
        objective_rule="clear_enemies",
        terrain_patch_count_range=(2, 4),
        terrain_patch_size_range=(2, 3),
    )


def _build_room(seed=0, doors=None):
    if seed is not None:
        random.seed(seed)
    if doors is None:
        doors = {"top": True, "bottom": True, "left": True, "right": True}
    return Room(doors, is_exit=False, room_plan=_plan("earth_quicksand_trap"))


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
    """BFS over FLOOR-only tiles (quicksand is impassable for the safe path)."""
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


class QuicksandTrapDoorBufferTests(_SeedRestoreMixin, unittest.TestCase):
    def test_no_quicksand_within_door_buffer_across_seeds(self):
        for seed in range(20):
            room = _build_room(seed=seed)
            door_tiles = room._door_tile_set()
            for r in range(ROOM_ROWS):
                for c in range(ROOM_COLS):
                    if room.grid[r][c] != QUICKSAND:
                        continue
                    for dc, dr in door_tiles:
                        chebyshev = max(abs(c - dc), abs(r - dr))
                        self.assertGreater(
                            chebyshev,
                            QUICKSAND_TRAP_DOOR_BUFFER,
                            f"seed {seed}: quicksand at ({c},{r}) "
                            f"within buffer of door ({dc},{dr})",
                        )


class QuicksandTrapConnectivityTests(_SeedRestoreMixin, unittest.TestCase):
    def test_every_door_has_walkable_path_to_center(self):
        for seed in range(20):
            room = _build_room(seed=seed)
            for entry in _door_entry_tiles(room):
                self.assertTrue(
                    _bfs_walkable_to_center(room, entry),
                    f"seed {seed}: door entry {entry} cannot reach centre "
                    f"via floor-only path",
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


class QuicksandTrapDensityTests(_SeedRestoreMixin, unittest.TestCase):
    def test_room_keeps_some_quicksand_tiles(self):
        # Polish must not strip every quicksand tile or the room loses
        # its hazard.  Across many seeds, at least one quicksand survives.
        survivors = []
        for seed in range(20):
            room = _build_room(seed=seed)
            count = sum(row.count(QUICKSAND) for row in room.grid)
            survivors.append(count)
        self.assertTrue(
            all(c > 0 for c in survivors),
            f"some seeds lost all quicksand: {survivors}",
        )


class QuicksandTrapObjectiveLabelTests(unittest.TestCase):
    def test_template_provides_hud_label(self):
        templates = {t["room_id"]: t for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertEqual(
            templates["earth_quicksand_trap"]["objective_label"],
            "Quicksand Trap",
        )


if __name__ == "__main__":
    unittest.main()
