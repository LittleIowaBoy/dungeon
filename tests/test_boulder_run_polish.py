"""Phase 2: Boulder Run room deepening.

Verifies the post-scaffold polish on the ``earth_boulder_run`` family:

* The room arena is left fully open (no random terrain patches) so the
  vertical boulder lanes never overlap mud / ice / water tiles.
* The spawner config exposes ``exit_wall`` (the wall opposite the
  ``source_wall``) so the HUD / route-hint code knows which side of the
  arena the player is meant to reach.
* The room template advertises an ``objective_label`` so the HUD chrome
  shows "Boulder Run" instead of the empty default.
"""

import os
import random
import sys
import unittest

import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import content_db  # noqa: E402
from room import (  # noqa: E402
    DOOR, FLOOR, MUD, ICE, WATER, ROOM_COLS, ROOM_ROWS, Room,
)
from room_plan import RoomPlan, RoomTemplate  # noqa: E402

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.init()
pygame.display.set_mode((1, 1))


def _template(room_id, objective_label=""):
    return RoomTemplate(
        room_id=room_id,
        display_name=room_id.replace("_", " ").title(),
        objective_kind="combat",
        combat_pressure="mid_high",
        decision_complexity="mid",
        topology_role="mid_run",
        min_depth=2,
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
        depth=2,
        path_kind="main_path",
        is_exit=False,
        template=_template(room_id),
        terrain_type="mud",
        enemy_count_range=(0, 0),
        enemy_type_weights=(50, 35, 15),
        objective_rule="clear_enemies",
        terrain_patch_count_range=(4, 6),
        terrain_patch_size_range=(2, 3),
    )


def _build_room(seed=0):
    random.seed(seed)
    return Room(
        {"top": True, "bottom": True, "left": False, "right": False},
        is_exit=False,
        room_plan=_plan("earth_boulder_run"),
    )


class _SeedRestoreMixin:
    def setUp(self):
        self._random_state = random.getstate()

    def tearDown(self):
        random.setstate(self._random_state)


class BoulderRunOpenArenaTests(_SeedRestoreMixin, unittest.TestCase):
    def test_no_terrain_patches_in_interior(self):
        forbidden = {MUD, ICE, WATER}
        for seed in range(20):
            room = _build_room(seed=seed)
            for r in range(1, ROOM_ROWS - 1):
                for c in range(1, ROOM_COLS - 1):
                    self.assertNotIn(
                        room.grid[r][c], forbidden,
                        f"seed {seed}: terrain {room.grid[r][c]} at ({c},{r})",
                    )

    def test_doors_still_carved(self):
        # Open-arena pass must NOT accidentally erase wall doors.
        room = _build_room(seed=0)
        door_count = sum(
            1 for r in range(ROOM_ROWS) for c in range(ROOM_COLS)
            if room.grid[r][c] == DOOR
        )
        self.assertGreater(door_count, 0)


class BoulderRunSpawnerConfigTests(_SeedRestoreMixin, unittest.TestCase):
    def test_spawner_exposes_exit_wall_opposite_of_source(self):
        for seed in range(20):
            room = _build_room(seed=seed)
            spawners = [
                cfg for cfg in room.objective_entity_configs
                if cfg["kind"] == "boulder_run_spawner"
            ]
            self.assertEqual(len(spawners), 1)
            cfg = spawners[0]
            self.assertIn(cfg["source_wall"], ("top", "bottom"))
            self.assertIn(cfg["exit_wall"], ("top", "bottom"))
            self.assertNotEqual(cfg["source_wall"], cfg["exit_wall"])


class BoulderRunObjectiveLabelTests(unittest.TestCase):
    def test_template_provides_hud_label(self):
        templates = {t["room_id"]: t for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertEqual(
            templates["earth_boulder_run"]["objective_label"],
            "Boulder Run",
        )


if __name__ == "__main__":
    unittest.main()
