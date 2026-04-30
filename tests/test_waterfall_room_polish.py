"""Phase 2: Water Waterfall Room polish.

Verifies the waterfall builder's layout invariants:

* A vertical CURRENT band hugs one side wall (left or right).
* Every CURRENT tile in the cascade pushes downward (vector dy > 0).
* A WATER pool exists at the bottom of the cascade.
* The guaranteed chest sits inside the cascade at the TOP of the
  band (player must push UP against the current to reach it).
* Door buffers are clear of CURRENT tiles.
* The sunken_ruins override flips the template enabled with weight > 0.
"""
import os
import random
import sys
import unittest

import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import content_db  # noqa: E402
from room import (  # noqa: E402
    CURRENT, DOOR, FLOOR, ROOM_COLS, ROOM_ROWS, Room, WATER,
)
from room_plan import RoomPlan, RoomTemplate  # noqa: E402
from settings import (  # noqa: E402
    TILE_SIZE, WATER_WATERFALL_BAND_WIDTH, WATER_WATERFALL_DOOR_BUFFER,
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
        branch_preference="branch",
        generation_weight=1,
        enabled=True,
        implementation_status="prototype",
        objective_variant="",
        notes="",
    )


def _plan(room_id, guaranteed_chest=True):
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
        guaranteed_chest=guaranteed_chest,
    )


def _build_room(seed=0, doors=None):
    if seed is not None:
        random.seed(seed)
    if doors is None:
        doors = {"top": True, "bottom": True, "left": True, "right": True}
    return Room(doors, is_exit=False, room_plan=_plan("water_waterfall_room"))


class _SeedRestoreMixin:
    def setUp(self):
        self._random_state = random.getstate()

    def tearDown(self):
        random.setstate(self._random_state)


class WaterfallBandTests(_SeedRestoreMixin, unittest.TestCase):
    def test_cascade_present_against_one_side_wall(self):
        for seed in range(20):
            room = _build_room(seed=seed)
            current_cols = {
                c
                for r in range(ROOM_ROWS)
                for c in range(ROOM_COLS)
                if room.grid[r][c] == CURRENT
            }
            self.assertTrue(current_cols, f"seed {seed}: no CURRENT tiles laid")
            # All CURRENT tiles should sit in a contiguous column range
            # against either the left or the right wall.
            min_c, max_c = min(current_cols), max(current_cols)
            self.assertLessEqual(
                max_c - min_c + 1, WATER_WATERFALL_BAND_WIDTH,
                f"seed {seed}: cascade spread across {max_c - min_c + 1} cols",
            )
            on_left = min_c <= 1 + WATER_WATERFALL_BAND_WIDTH
            on_right = max_c >= ROOM_COLS - 2 - WATER_WATERFALL_BAND_WIDTH
            self.assertTrue(
                on_left or on_right,
                f"seed {seed}: cascade not against a side wall (cols {min_c}-{max_c})",
            )

    def test_every_current_tile_pushes_downward(self):
        for seed in range(10):
            room = _build_room(seed=seed)
            for r in range(ROOM_ROWS):
                for c in range(ROOM_COLS):
                    if room.grid[r][c] != CURRENT:
                        continue
                    vec = room.current_vectors.get((c, r))
                    self.assertIsNotNone(vec)
                    dx, dy = vec
                    self.assertGreater(
                        dy, 0,
                        f"seed {seed}: CURRENT at ({c},{r}) doesn't push down",
                    )


class WaterfallPoolTests(_SeedRestoreMixin, unittest.TestCase):
    def test_water_pool_present_at_base(self):
        for seed in range(10):
            room = _build_room(seed=seed)
            water_count = sum(row.count(WATER) for row in room.grid)
            self.assertGreater(
                water_count, 0,
                f"seed {seed}: no WATER pool tiles laid",
            )
            # Pool should sit in the lower half of the room.
            water_rows = [
                r for r in range(ROOM_ROWS)
                for c in range(ROOM_COLS) if room.grid[r][c] == WATER
            ]
            self.assertGreater(
                min(water_rows), ROOM_ROWS // 2,
                f"seed {seed}: WATER pool not at base of cascade",
            )


class WaterfallChestTests(_SeedRestoreMixin, unittest.TestCase):
    def test_chest_placed_inside_cascade_at_top(self):
        for seed in range(10):
            room = _build_room(seed=seed)
            self.assertIsNotNone(
                room.chest_pos,
                f"seed {seed}: guaranteed chest not placed",
            )
            cx, cy = room.chest_pos
            chest_col = cx // TILE_SIZE
            chest_row = cy // TILE_SIZE
            # Chest pocket should be in the top quarter of the room
            # (forcing the player to push up through the cascade).
            self.assertLessEqual(
                chest_row, ROOM_ROWS // 4,
                f"seed {seed}: chest at row {chest_row} not at top",
            )
            # Chest tile itself is FLOOR (carved pocket).
            self.assertEqual(room.grid[chest_row][chest_col], FLOOR)


class WaterfallDoorBufferTests(_SeedRestoreMixin, unittest.TestCase):
    def test_no_current_within_door_buffer(self):
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
                            chebyshev, WATER_WATERFALL_DOOR_BUFFER,
                            f"seed {seed}: CURRENT at ({c},{r}) within "
                            f"buffer of door ({dc},{dr})",
                        )


class WaterfallOverrideTests(unittest.TestCase):
    def test_sunken_ruins_override_enables_waterfall_with_weight(self):
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["sunken_ruins"]
        }
        self.assertIn("water_waterfall_room", overrides)
        wf = overrides["water_waterfall_room"]
        self.assertEqual(wf["enabled"], 1)
        self.assertGreater(wf["generation_weight"], 0)


if __name__ == "__main__":
    unittest.main()
