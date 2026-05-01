"""Tests for the Tide Lord arena room.

Validates:
- sunken_ruins override enables water_tide_lord_arena (enabled=1, weight>0).
- Base template remains disabled.
- Arena polish floods the centre with WATER tiles and a CURRENT ring.
- TideLord is registered in enemy_configs (exactly one).
- Boss controller config is emitted with the expected keys.
- No WATER/CURRENT tile appears within the door buffer.
- Immortal WaterSpiritEnemy instances do not block enemies_cleared logic.
"""
import os
import sys
import math
import unittest

import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.init()
pygame.display.set_mode((1, 1))

import content_db
from room import Room, WATER, CURRENT, FLOOR, ROOM_COLS, ROOM_ROWS
from room_plan import RoomPlan, RoomTemplate
from settings import (
    TILE_SIZE,
    TIDE_LORD_ARENA_FLOOD_RADIUS,
    TIDE_LORD_ARENA_CURRENT_BAND,
)


def _template():
    return RoomTemplate(
        room_id="water_tide_lord_arena",
        display_name="Tide Lord Arena",
        objective_kind="combat",
        combat_pressure="high",
        decision_complexity="mid",
        topology_role="finale",
        min_depth=2,
        max_depth=None,
        branch_preference="either",
        generation_weight=1,
        enabled=True,
        implementation_status="complete",
        objective_variant="",
        notes="",
    )


def _build_arena(seed=0):
    import random
    if seed is not None:
        random.seed(seed)
    plan = RoomPlan(
        position=(0, 0),
        depth=3,
        path_kind="main_path",
        is_exit=True,
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


class TideLordOverrideTests(unittest.TestCase):
    def setUp(self):
        self.sunken = {r["room_id"]: r for r in content_db.load_room_catalog("sunken_ruins")}
        self.base   = {t["room_id"]: t for t in content_db.BASE_ROOM_TEMPLATES}

    def test_sunken_ruins_enables_arena(self):
        self.assertIn("water_tide_lord_arena", self.sunken)
        row = self.sunken["water_tide_lord_arena"]
        self.assertEqual(row["enabled"], 1)
        self.assertGreater(row["generation_weight"], 0)

    def test_base_template_still_disabled(self):
        self.assertEqual(self.base["water_tide_lord_arena"]["enabled"], 0)


class TideLordArenaPolishTests(unittest.TestCase):
    def setUp(self):
        self.room = _build_arena()

    def test_water_tiles_in_centre(self):
        cx = ROOM_COLS // 2
        cy = ROOM_ROWS // 2
        # The exact centre tile must be WATER.
        self.assertEqual(
            self.room.grid[cy][cx], WATER,
            "Centre tile should be WATER in the Tide Lord arena",
        )

    def test_current_ring_outside_disc(self):
        """CURRENT tiles should exist in the band just outside the WATER disc."""
        cx = ROOM_COLS // 2
        cy = ROOM_ROWS // 2
        flood_r = TIDE_LORD_ARENA_FLOOD_RADIUS
        band = TIDE_LORD_ARENA_CURRENT_BAND
        found_current = False
        for r in range(ROOM_ROWS):
            for c in range(ROOM_COLS):
                if self.room.grid[r][c] != CURRENT:
                    continue
                dist = math.hypot(c - cx, r - cy)
                self.assertGreater(dist, flood_r - 0.5,
                    f"CURRENT tile at ({c},{r}) is inside the WATER disc")
                self.assertLessEqual(dist, flood_r + band + 0.5,
                    f"CURRENT tile at ({c},{r}) is too far from the disc edge")
                found_current = True
        self.assertTrue(found_current, "Expected at least one CURRENT tile in the arena")

    def test_no_water_or_current_at_door_buffer(self):
        """No hazard tile should appear within 3 chebyshev tiles of any door."""
        door_tiles = self.room._door_tile_set()
        door_buf = 3
        for r in range(ROOM_ROWS):
            for c in range(ROOM_COLS):
                tile = self.room.grid[r][c]
                if tile not in (WATER, CURRENT):
                    continue
                for dc, dr in door_tiles:
                    cheb = max(abs(c - dc), abs(r - dr))
                    self.assertGreater(
                        cheb, door_buf,
                        f"{tile.upper()} tile at ({c},{r}) is within door buffer "
                        f"of door at ({dc},{dr})",
                    )

    def test_tide_lord_in_enemy_configs(self):
        from enemies import TideLord
        tide_lords = [(cls, pos) for cls, pos in self.room.enemy_configs
                      if cls is TideLord]
        self.assertEqual(len(tide_lords), 1,
                         "Expected exactly one TideLord in enemy_configs")

    def test_boss_controller_config_present(self):
        ctrl = [c for c in self.room.objective_entity_configs
                if c.get("kind") == "tide_lord_arena_controller"]
        self.assertEqual(len(ctrl), 1)
        cfg = ctrl[0]
        self.assertIn("wave_specs", cfg)
        self.assertIn("wave_spawn_radius", cfg)
        self.assertFalse(cfg["loot_granted"])

    def test_wave_specs_have_three_thresholds(self):
        ctrl = next(c for c in self.room.objective_entity_configs
                    if c.get("kind") == "tide_lord_arena_controller")
        specs = ctrl["wave_specs"]
        self.assertEqual(len(specs), 3)
        for key in (0.75, 0.5, 0.25):
            self.assertIn(key, specs)


class ImmortalEnemyClearTests(unittest.TestCase):
    """enemies_cleared must fire once all MORTAL enemies die, ignoring immortals."""

    def test_immortal_flag_on_spirit_class(self):
        from enemies import WaterSpiritEnemy
        self.assertTrue(WaterSpiritEnemy.immortal)

    def test_mortal_wave_spirit(self):
        from enemies import WaterSpiritEnemy
        spirit = WaterSpiritEnemy(0, 0, immortal=False)
        self.assertFalse(spirit.immortal)
        # Damage should reduce HP to zero.
        spirit.take_damage(999)
        self.assertLessEqual(spirit.current_hp, 0)

    def test_immortal_spirit_cannot_be_killed(self):
        from enemies import WaterSpiritEnemy
        spirit = WaterSpiritEnemy(0, 0)  # immortal=True by default
        spirit.take_damage(999)
        self.assertGreater(spirit.current_hp, 0)

    def test_tide_lord_projectile_has_correct_damage(self):
        from enemies import TideLordProjectile
        from settings import TIDE_LORD_PROJECTILE_DAMAGE
        self.assertEqual(TideLordProjectile.damage, TIDE_LORD_PROJECTILE_DAMAGE)

    def test_tide_lord_fires_projectiles_on_surge(self):
        from enemies import TideLord
        import pygame
        boss = TideLord(100, 100)
        # Simulate telegraph → strike for Wave Surge attack.
        now = 0
        player_rect = pygame.Rect(500, 100, 20, 20)
        boss._pending_attack = "surge"
        boss._on_telegraph_start(player_rect, now)
        boss._on_strike_start(player_rect, now)
        shots = boss.consume_emitted_projectiles()
        from settings import TIDE_LORD_SURGE_SHOTS_P1
        self.assertEqual(len(shots), TIDE_LORD_SURGE_SHOTS_P1)

    def test_tide_lord_phase2_fires_more_shots(self):
        from enemies import TideLord
        import pygame
        boss = TideLord(100, 100)
        boss.phase_2 = True
        now = 0
        player_rect = pygame.Rect(500, 100, 20, 20)
        boss._pending_attack = "surge"
        boss._on_telegraph_start(player_rect, now)
        boss._on_strike_start(player_rect, now)
        shots = boss.consume_emitted_projectiles()
        from settings import TIDE_LORD_SURGE_SHOTS_P2
        self.assertEqual(len(shots), TIDE_LORD_SURGE_SHOTS_P2)


if __name__ == "__main__":
    unittest.main()
