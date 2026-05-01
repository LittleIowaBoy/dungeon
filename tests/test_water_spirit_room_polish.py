"""Tests for the Water Spirit Room polish and override.

Validates that:
- The sunken_ruins override enables water_spirit_room (enabled=1, weight>0).
- _polish_water_spirit_room places WATER tiles in the interior.
- Spirits are added to enemy_configs.
- No WATER pool tiles appear within WATER_SPIRIT_DOOR_BUFFER of any door.
"""
import os
import sys
import random
import unittest

import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.init()
pygame.display.set_mode((1, 1))

import content_db
from room import Room, WATER, DOOR, FLOOR, ROOM_COLS, ROOM_ROWS
from room_plan import RoomPlan, RoomTemplate
from settings import WATER_SPIRIT_DOOR_BUFFER, WATER_SPIRIT_POOL_COUNT_RANGE


def _template():
    return RoomTemplate(
        room_id="water_spirit_room",
        display_name="Water Spirit Room",
        objective_kind="combat",
        combat_pressure="mid_high",
        decision_complexity="mid",
        topology_role="mid_run",
        min_depth=2,
        max_depth=None,
        branch_preference="either",
        generation_weight=2,
        enabled=True,
        implementation_status="prototype",
        objective_variant="",
        notes="",
    )


def _build_spirit_room(seed=0):
    if seed is not None:
        random.seed(seed)
    plan = RoomPlan(
        position=(0, 0),
        depth=2,
        path_kind="main_path",
        is_exit=False,
        template=_template(),
        terrain_type="water",
        enemy_count_range=(0, 0),
        enemy_type_weights=(50, 35, 15),
        objective_rule="clear_enemies",
        terrain_patch_count_range=(0, 0),
        terrain_patch_size_range=(0, 0),
    )
    doors = {"top": True, "bottom": True, "left": True, "right": True}
    return Room(doors, is_exit=False, room_plan=plan)


class WaterSpiritRoomOverrideTests(unittest.TestCase):
    def test_sunken_ruins_enables_spirit_room(self):
        catalog = content_db.load_room_catalog("sunken_ruins")
        by_id = {r["room_id"]: r for r in catalog}
        self.assertIn("water_spirit_room", by_id)
        row = by_id["water_spirit_room"]
        self.assertEqual(row["enabled"], 1)
        self.assertGreater(row["generation_weight"], 0)

    def test_base_template_still_disabled(self):
        by_id = {t["room_id"]: t for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertEqual(by_id["water_spirit_room"]["enabled"], 0)


class WaterSpiritRoomPolishTests(unittest.TestCase):
    def setUp(self):
        self.room = _build_spirit_room()

    def test_water_tiles_placed_in_interior(self):
        water_count = sum(
            1 for r in range(1, ROOM_ROWS - 1)
            for c in range(1, ROOM_COLS - 1)
            if self.room.grid[r][c] == WATER
        )
        self.assertGreater(water_count, 0, "Expected WATER tiles after spirit-room polish")

    def test_spirit_enemies_added_to_configs(self):
        from enemies import WaterSpiritEnemy
        spirit_configs = [(cls, pos) for cls, pos in self.room.enemy_configs
                          if cls is WaterSpiritEnemy]
        self.assertGreater(len(spirit_configs), 0,
                           "Expected at least one WaterSpiritEnemy in enemy_configs")

    def test_no_water_within_door_buffer(self):
        door_tiles = self.room._door_tile_set()
        buffer = WATER_SPIRIT_DOOR_BUFFER
        for r in range(ROOM_ROWS):
            for c in range(ROOM_COLS):
                if self.room.grid[r][c] != WATER:
                    continue
                for dc, dr in door_tiles:
                    chebyshev = max(abs(c - dc), abs(r - dr))
                    self.assertGreater(
                        chebyshev, buffer,
                        f"WATER tile at ({c},{r}) is within door buffer of door at ({dc},{dr})"
                    )

    def test_pool_count_within_range(self):
        from enemies import WaterSpiritEnemy
        spirit_configs = [(cls, pos) for cls, pos in self.room.enemy_configs
                          if cls is WaterSpiritEnemy]
        lo, hi = WATER_SPIRIT_POOL_COUNT_RANGE
        self.assertGreaterEqual(len(spirit_configs), lo)
        self.assertLessEqual(len(spirit_configs), hi)


class WaterSpiritAnchorCycleTests(unittest.TestCase):
    """W3: WaterSpiritEnemy anchor (vulnerability) cycle."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_spirit(self, immortal=True):
        from enemies import WaterSpiritEnemy
        cx = 5 * 32 + 16
        cy = 5 * 32 + 16
        return WaterSpiritEnemy(cx, cy, immortal=immortal)

    def test_spirit_starts_immortal(self):
        spirit = self._make_spirit(immortal=True)
        self.assertTrue(spirit.immortal)

    def test_anchor_window_opens_after_interval(self):
        from settings import WATER_SPIRIT_ANCHOR_INTERVAL_MS
        spirit = self._make_spirit()
        # First call initialises the timer
        spirit.update_anchor_cycle(0)
        self.assertTrue(spirit.immortal, "Still immortal immediately after init")
        # Advance past the interval
        spirit.update_anchor_cycle(WATER_SPIRIT_ANCHOR_INTERVAL_MS)
        self.assertFalse(spirit.immortal, "Spirit should become mortal at anchor window")

    def test_hp_set_to_anchor_hp_during_window(self):
        from settings import WATER_SPIRIT_ANCHOR_INTERVAL_MS, WATER_SPIRIT_ANCHOR_HP
        spirit = self._make_spirit()
        spirit.update_anchor_cycle(0)
        spirit.update_anchor_cycle(WATER_SPIRIT_ANCHOR_INTERVAL_MS)
        self.assertEqual(spirit.current_hp, WATER_SPIRIT_ANCHOR_HP)

    def test_damage_taken_during_window(self):
        from settings import WATER_SPIRIT_ANCHOR_INTERVAL_MS, WATER_SPIRIT_ANCHOR_HP
        spirit = self._make_spirit()
        spirit.update_anchor_cycle(0)
        spirit.update_anchor_cycle(WATER_SPIRIT_ANCHOR_INTERVAL_MS)
        spirit.take_damage(10)
        self.assertEqual(spirit.current_hp, WATER_SPIRIT_ANCHOR_HP - 10)

    def test_immortal_restored_after_window(self):
        from settings import (
            WATER_SPIRIT_ANCHOR_INTERVAL_MS, WATER_SPIRIT_ANCHOR_DURATION_MS,
        )
        spirit = self._make_spirit()
        spirit.update_anchor_cycle(0)
        spirit.update_anchor_cycle(WATER_SPIRIT_ANCHOR_INTERVAL_MS)
        self.assertFalse(spirit.immortal)
        # Advance past the duration to close the window
        t_end = WATER_SPIRIT_ANCHOR_INTERVAL_MS + WATER_SPIRIT_ANCHOR_DURATION_MS
        spirit.update_anchor_cycle(t_end)
        self.assertTrue(spirit.immortal, "Spirit should return to immortal after anchor window")

    def test_hp_restored_after_window(self):
        from settings import (
            WATER_SPIRIT_ANCHOR_INTERVAL_MS, WATER_SPIRIT_ANCHOR_DURATION_MS,
            WATER_SPIRIT_HP,
        )
        spirit = self._make_spirit()
        spirit.update_anchor_cycle(0)
        spirit.update_anchor_cycle(WATER_SPIRIT_ANCHOR_INTERVAL_MS)
        spirit.take_damage(10)  # partial damage during window
        t_end = WATER_SPIRIT_ANCHOR_INTERVAL_MS + WATER_SPIRIT_ANCHOR_DURATION_MS
        spirit.update_anchor_cycle(t_end)
        self.assertEqual(spirit.current_hp, WATER_SPIRIT_HP,
                         "HP should reset to base value after anchor window")

    def test_mortal_spirit_skips_anchor_cycle(self):
        """Wave-spawned spirits (immortal=False) must never cycle."""
        spirit = self._make_spirit(immortal=False)
        self.assertFalse(spirit._can_anchor)
        spirit.update_anchor_cycle(0)
        spirit.update_anchor_cycle(999999)
        self.assertFalse(spirit.immortal, "Mortal spirit should stay mortal")


if __name__ == "__main__":
    unittest.main()
