"""Phase 1: Stalagmite Field room polish.

Verifies the post-placement pass that:

* Clears spike tiles within ``STALAGMITE_FIELD_DOOR_BUFFER`` of any open
  door so the player never spawns onto damage.
* Guarantees a walkable path from each door entry tile to the room
  centre, even when the rectangle-cluster output isolates a door.
* Sprinkles isolated singleton spikes for visual texture.

Tests build the room many times with varied seeds so we exercise the
random placement path without relying on a single lucky seed.
"""

import os
import random
import sys
import unittest
from collections import deque

import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from room import (  # noqa: E402
    DOOR, FLOOR, SPIKE_PATCH, ROOM_COLS, ROOM_ROWS, Room,
)
from room_plan import RoomPlan, RoomTemplate  # noqa: E402
from settings import (  # noqa: E402
    STALAGMITE_FIELD_DOOR_BUFFER,
    STALAGMITE_FIELD_SINGLETON_COUNT_RANGE,
)

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
        objective_rule="immediate",
        terrain_patch_count_range=(4, 6),
        terrain_patch_size_range=(2, 3),
    )


def _build_field_room(seed=None, doors=None):
    if seed is not None:
        random.seed(seed)
    if doors is None:
        doors = {"top": True, "bottom": True, "left": True, "right": True}
    return Room(doors, is_exit=False, room_plan=_plan("earth_stalagmite_field"))


class _SeedRestoreMixin:
    """Save/restore the global random state so seeded builds don't leak."""

    def setUp(self):
        self._random_state = random.getstate()

    def tearDown(self):
        random.setstate(self._random_state)


def _door_entry_tiles(room):
    """Return the floor tiles immediately inside each open door."""
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
    """BFS treating SPIKE_PATCH as impassable (player would damage-step).

    Used in the test to assert connectivity over walkable tiles only.
    """
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
            tile = room.grid[nr][nc]
            # Players walk on FLOOR (and PORTAL/DOOR which won't appear
            # mid-room), spikes are passable but damaging — for the
            # connectivity guarantee we want a fully safe path.
            if tile != FLOOR:
                continue
            visited.add((nc, nr))
            queue.append((nc, nr))
    return False


class StalagmiteFieldDoorBufferTests(_SeedRestoreMixin, unittest.TestCase):
    def test_no_spike_within_door_buffer_across_seeds(self):
        for seed in range(20):
            room = _build_field_room(seed=seed)
            door_tiles = room._door_tile_set()
            for r in range(ROOM_ROWS):
                for c in range(ROOM_COLS):
                    if room.grid[r][c] != SPIKE_PATCH:
                        continue
                    for dc, dr in door_tiles:
                        chebyshev = max(abs(c - dc), abs(r - dr))
                        self.assertGreater(
                            chebyshev,
                            STALAGMITE_FIELD_DOOR_BUFFER,
                            f"seed {seed}: spike at ({c},{r}) "
                            f"within buffer of door ({dc},{dr})",
                        )


class StalagmiteFieldConnectivityTests(_SeedRestoreMixin, unittest.TestCase):
    def test_every_door_has_walkable_path_to_center(self):
        for seed in range(20):
            room = _build_field_room(seed=seed)
            for entry in _door_entry_tiles(room):
                self.assertTrue(
                    _bfs_walkable_to_center(room, entry),
                    f"seed {seed}: door entry {entry} cannot reach centre "
                    f"on safe floor tiles",
                )

    def test_subset_of_doors_also_connected(self):
        # Fewer doors must still get path-carved correctly.
        for doors in [
            {"top": True, "bottom": False, "left": False, "right": False},
            {"top": False, "bottom": False, "left": True, "right": True},
        ]:
            for seed in range(10):
                room = _build_field_room(seed=seed, doors=doors)
                for entry in _door_entry_tiles(room):
                    self.assertTrue(
                        _bfs_walkable_to_center(room, entry),
                        f"doors={doors} seed={seed}: entry {entry} unreachable",
                    )


class StalagmiteFieldDensityTests(_SeedRestoreMixin, unittest.TestCase):
    def test_room_keeps_some_spike_patches(self):
        # Polish must not strip every spike (otherwise the room is empty
        # of its hazard).  Across many seeds, at least one spike should
        # survive in each room.
        for seed in range(20):
            room = _build_field_room(seed=seed)
            spikes = sum(row.count(SPIKE_PATCH) for row in room.grid)
            self.assertGreaterEqual(
                spikes,
                STALAGMITE_FIELD_SINGLETON_COUNT_RANGE[0],
                f"seed {seed}: only {spikes} spikes survived polish",
            )


if __name__ == "__main__":
    unittest.main()
