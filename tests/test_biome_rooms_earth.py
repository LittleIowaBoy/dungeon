"""Phase 2.A — Earth biome rooms: stalagmite field + quicksand trap.

These rooms reuse the standard combat flow but replace the biome's default
mud terrain patches with hazard tiles handled by ``terrain_effects.py``.
The tests below assert template registration, terrain placement, and the
end-to-end damage/drown behaviour.
"""
import os
import unittest

import pygame

import content_db
import status_effects
import terrain_effects
from objective_entities import (
    BurrowSpawner,
    CollapseEmitter,
    MiningCart,
    SporeMushroom,
    TremorEmitter,
    VeinCrystal,
    Boulder,
    ShrineGlyph,
)
from player import Player
from progress import PlayerProgress
from room import (
    CART_RAIL, FLOOR, GLYPH_TILE, HEARTH, MUD, PIT_TILE, QUICKSAND, SPIKE_PATCH,
    ROOM_COLS, ROOM_ROWS, Room,
)
from room_plan import RoomPlan, RoomTemplate
from settings import (
    TILE_SIZE, HAZARD_TICK_MS, HAZARD_TICK_DAMAGE, QUICKSAND_DROWN_MS,
)


# Initialise pygame video so Player / sprite construction works headless.
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


def _plan(room_id, *, terrain_type="mud", objective_rule="immediate"):
    return RoomPlan(
        position=(0, 0),
        depth=1,
        path_kind="main_path",
        is_exit=False,
        template=_template(room_id),
        terrain_type=terrain_type,
        enemy_count_range=(0, 0),
        enemy_type_weights=(50, 35, 15),
        objective_rule=objective_rule,
        # Tightly bound the patch placement so the test can locate one.
        terrain_patch_count_range=(2, 3),
        terrain_patch_size_range=(2, 3),
    )


def _make_player(col, row):
    player = Player(
        col * TILE_SIZE + TILE_SIZE // 2,
        row * TILE_SIZE + TILE_SIZE // 2,
    )
    player.reset_for_dungeon(PlayerProgress())
    return player


def _find_tile(room, kind):
    for r in range(ROOM_ROWS):
        for c in range(ROOM_COLS):
            if room.grid[r][c] == kind:
                return c, r
    return None


class HazardTerrainPlacementTests(unittest.TestCase):
    def test_stalagmite_field_places_spike_tiles_not_mud(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan("earth_stalagmite_field"),
        )
        spike_count = sum(row.count(SPIKE_PATCH) for row in room.grid)
        mud_count = sum(row.count(MUD) for row in room.grid)
        self.assertGreater(spike_count, 0)
        self.assertEqual(mud_count, 0)

    def test_quicksand_trap_places_quicksand_tiles_not_mud(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan("earth_quicksand_trap"),
        )
        quicksand_count = sum(row.count(QUICKSAND) for row in room.grid)
        mud_count = sum(row.count(MUD) for row in room.grid)
        self.assertGreater(quicksand_count, 0)
        self.assertEqual(mud_count, 0)


class HazardEffectIntegrationTests(unittest.TestCase):
    def test_player_on_spike_patch_takes_tick_damage(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan("earth_stalagmite_field"),
        )
        cell = _find_tile(room, SPIKE_PATCH)
        self.assertIsNotNone(cell)
        col, row = cell
        player = _make_player(col, row)
        hp_before = player.current_hp
        terrain_effects.apply_terrain_effects(player, room, HAZARD_TICK_MS, 16)
        self.assertEqual(player.current_hp, hp_before - HAZARD_TICK_DAMAGE)

    def test_player_in_quicksand_drowns_after_threshold(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan("earth_quicksand_trap"),
        )
        cell = _find_tile(room, QUICKSAND)
        self.assertIsNotNone(cell)
        col, row = cell
        player = _make_player(col, row)

        # Tick repeatedly until drowning meter exceeds threshold.
        elapsed = 0
        dt = 100
        ticks = 0
        while elapsed <= QUICKSAND_DROWN_MS and player.current_hp > 0:
            ticks += dt
            elapsed += dt
            player._invincible_until = 0  # bypass i-frames between ticks
            terrain_effects.apply_terrain_effects(player, room, ticks, dt)
        self.assertEqual(player.current_hp, 0)


class CrystalVeinTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_crystal_vein", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_crystal_vein"]["enabled"], 1)

    def _build_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_crystal_vein", objective_rule="clear_enemies"),
        )

    def test_room_spawns_three_to_four_vein_crystal_configs(self):
        room = self._build_room()
        crystals = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "vein_crystal"
        ]
        self.assertGreaterEqual(len(crystals), 3)
        self.assertLessEqual(len(crystals), 4)
        for cfg in crystals:
            self.assertIn(cfg["buff_stat"], ("damage", "speed", "armor"))

    def test_destroying_crystal_grants_room_buff_via_update_objective(self):
        room = self._build_room()
        crystal_cfg = next(
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "vein_crystal"
        )
        crystal = VeinCrystal(crystal_cfg)
        crystal.take_damage(crystal.max_hp)
        self.assertTrue(crystal_cfg["destroyed"])
        # Drive the rule branch — the buff is applied lazily on the next tick.
        room.update_objective(now_ticks=1000, enemy_group=[])
        total = room.active_room_buff_total(crystal_cfg["buff_stat"], 1000)
        self.assertAlmostEqual(total, crystal_cfg["buff_magnitude"])
        self.assertTrue(crystal_cfg["buff_applied"])

    def test_buff_application_is_idempotent_across_ticks(self):
        room = self._build_room()
        crystal_cfg = next(
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "vein_crystal"
        )
        crystal_cfg["destroyed"] = True
        room.update_objective(now_ticks=500, enemy_group=[])
        room.update_objective(now_ticks=600, enemy_group=[])
        room.update_objective(now_ticks=700, enemy_group=[])
        total = room.active_room_buff_total(crystal_cfg["buff_stat"], 700)
        self.assertAlmostEqual(total, crystal_cfg["buff_magnitude"])


class TremorChamberTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_tremor_chamber", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_tremor_chamber"]["enabled"], 1)

    def _build_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan("earth_tremor_chamber", objective_rule="clear_enemies"),
        )

    def test_tremor_chamber_places_hearth_tiles_not_mud(self):
        room = self._build_room()
        hearth_count = sum(row.count(HEARTH) for row in room.grid)
        mud_count = sum(row.count(MUD) for row in room.grid)
        self.assertGreater(hearth_count, 0)
        self.assertEqual(mud_count, 0)

    def test_tremor_emitter_spawned(self):
        room = self._build_room()
        emitters = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "tremor_emitter"
        ]
        self.assertEqual(len(emitters), 1)

    def test_emitter_strike_phase_stuns_player_off_hearth(self):
        room = self._build_room()
        emitter_cfg = next(
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "tremor_emitter"
        )
        emitter = TremorEmitter(emitter_cfg)
        # Place player on a non-HEARTH FLOOR cell.
        floor_cell = _find_tile(room, FLOOR)
        self.assertIsNotNone(floor_cell)
        col, row = floor_cell
        player = _make_player(col, row)
        # Tick to a strike phase (phase = telegraph_ms .. telegraph_ms+strike_ms).
        strike_now = emitter.telegraph_ms + 100
        emitter.update(strike_now)
        self.assertTrue(emitter.striking)
        emitter.apply_player_pressure(player)
        self.assertTrue(
            status_effects.has_status(player, status_effects.STUNNED, strike_now)
        )

    def test_emitter_strike_phase_skips_player_on_hearth(self):
        room = self._build_room()
        emitter_cfg = next(
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "tremor_emitter"
        )
        emitter = TremorEmitter(emitter_cfg)
        hearth_cell = _find_tile(room, HEARTH)
        self.assertIsNotNone(hearth_cell)
        col, row = hearth_cell
        player = _make_player(col, row)
        strike_now = emitter.telegraph_ms + 100
        emitter.update(strike_now)
        emitter.apply_player_pressure(player)
        self.assertFalse(
            status_effects.has_status(player, status_effects.STUNNED, strike_now)
        )


class MushroomGroveTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_mushroom_grove", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_mushroom_grove"]["enabled"], 1)

    def _build_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_mushroom_grove", objective_rule="clear_enemies"),
        )

    def test_room_spawns_three_to_four_mushroom_configs(self):
        room = self._build_room()
        mushrooms = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "spore_mushroom"
        ]
        self.assertGreaterEqual(len(mushrooms), 3)
        self.assertLessEqual(len(mushrooms), 4)

    def test_pulse_inside_radius_applies_poisoned(self):
        cfg = {
            "kind": "spore_mushroom",
            "pos": (5 * TILE_SIZE, 5 * TILE_SIZE),
            "max_hp": 3,
            "current_hp": 3,
            "pulse_cycle_ms": 3000,
            "pulse_active_ms": 700,
            "pulse_offset_ms": 0,
            "pulse_radius": 80,
            "poison_duration_ms": 5000,
            "destroyed": False,
        }
        mushroom = SporeMushroom(cfg)
        # Place player near the mushroom so they're inside pulse_radius.
        player = Player(5 * TILE_SIZE + 16, 5 * TILE_SIZE)
        player.reset_for_dungeon(PlayerProgress())
        # Tick into the pulse window (phase 0 => active).
        mushroom.update(100)
        self.assertTrue(mushroom.pulse_active)
        mushroom.apply_player_pressure(player)
        self.assertTrue(
            status_effects.has_status(player, status_effects.POISONED, 100)
        )

    def test_destroyed_mushroom_stops_pulsing(self):
        cfg = {
            "kind": "spore_mushroom",
            "pos": (5 * TILE_SIZE, 5 * TILE_SIZE),
            "max_hp": 1,
            "current_hp": 1,
            "pulse_cycle_ms": 3000,
            "pulse_active_ms": 700,
            "pulse_offset_ms": 0,
            "pulse_radius": 80,
            "poison_duration_ms": 5000,
            "destroyed": False,
        }
        mushroom = SporeMushroom(cfg)
        mushroom.take_damage(1)
        self.assertTrue(cfg["destroyed"])
        mushroom.update(100)
        self.assertFalse(mushroom.pulse_active)


class CaveInTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_cave_in", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_cave_in"]["enabled"], 1)

    def _build_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_cave_in", objective_rule="clear_enemies"),
        )

    def test_collapse_emitter_spawned(self):
        room = self._build_room()
        emitters = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "collapse_emitter"
        ]
        self.assertEqual(len(emitters), 1)

    def test_strike_converts_floor_to_pit_and_increments_count(self):
        room = self._build_room()
        cfg = next(
            c for c in room.objective_entity_configs if c["kind"] == "collapse_emitter"
        )
        emitter = CollapseEmitter(cfg)
        # Telegraph: pick a target during the windup window.
        emitter.update(100)
        self.assertIsNotNone(emitter._pending_cell)
        target_col, target_row = emitter._pending_cell
        self.assertEqual(room.grid[target_row][target_col], FLOOR)
        # Strike: tick past the telegraph window into the strike phase.
        emitter.update(emitter.telegraph_ms + 100)
        self.assertEqual(room.grid[target_row][target_col], PIT_TILE)
        self.assertEqual(emitter.collapses_done, 1)

    def test_collapse_cap_prevents_unbounded_growth(self):
        room = self._build_room()
        cfg = next(
            c for c in room.objective_entity_configs if c["kind"] == "collapse_emitter"
        )
        emitter = CollapseEmitter(cfg)
        # Drive through more cycles than max_collapses to confirm the cap holds.
        for cycle in range(emitter.max_collapses + 3):
            base = cycle * emitter.cycle_ms
            emitter.update(base + 100)  # telegraph
            emitter.update(base + emitter.telegraph_ms + 100)  # strike
        self.assertEqual(emitter.collapses_done, emitter.max_collapses)


class MiningCartsTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_mining_carts", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_mining_carts"]["enabled"], 1)

    def _build_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_mining_carts", objective_rule="clear_enemies"),
        )

    def test_mining_carts_room_lays_cart_rails(self):
        room = self._build_room()
        rail_count = sum(row.count(CART_RAIL) for row in room.grid)
        self.assertGreater(rail_count, 0)

    def test_mining_carts_room_spawns_two_to_three_carts(self):
        room = self._build_room()
        carts = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "mining_cart"
        ]
        self.assertGreaterEqual(len(carts), 2)
        self.assertLessEqual(len(carts), 3)

    def test_cart_collision_damages_player(self):
        cfg = {
            "kind": "mining_cart",
            "pos": (5 * TILE_SIZE, 5 * TILE_SIZE),
            "speed": 2.4,
            "damage": 8,
            "knockback_px": 24,
            "damage_cooldown_ms": 600,
        }
        cart = MiningCart(cfg)
        player = Player(5 * TILE_SIZE, 5 * TILE_SIZE)
        player.reset_for_dungeon(PlayerProgress())
        player._invincible_until = 0
        starting_hp = player.current_hp
        hit = cart.apply_player_pressure(player)
        self.assertTrue(hit)
        self.assertEqual(player.current_hp, starting_hp - cart.damage)

    def test_cart_wraps_horizontally_when_off_screen(self):
        cfg = {
            "kind": "mining_cart",
            "pos": (ROOM_COLS * TILE_SIZE - 5, 5 * TILE_SIZE),
            "speed": 50,  # large step to clear the room in a single tick
            "damage": 8,
            "knockback_px": 24,
            "damage_cooldown_ms": 600,
        }
        cart = MiningCart(cfg)
        cart.update(0)
        self.assertLessEqual(cart.rect.left, ROOM_COLS * TILE_SIZE)
        self.assertGreaterEqual(cart.rect.right, 0)


class BurrowerDenTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_burrower_den", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_burrower_den"]["enabled"], 1)

    def _build_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_burrower_den", objective_rule="clear_enemies"),
        )

    def test_room_spawns_three_to_four_burrow_spawner_configs(self):
        room = self._build_room()
        spawners = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "burrow_spawner"
        ]
        self.assertGreaterEqual(len(spawners), 3)
        self.assertLessEqual(len(spawners), 4)

    def test_strike_arms_pending_spawn_and_room_emits_spawn_enemies(self):
        room = self._build_room()
        # Force a single spawner with offset_ms=0 for deterministic timing.
        cfg = {
            "kind": "burrow_spawner",
            "pos": (5 * TILE_SIZE, 5 * TILE_SIZE),
            "cycle_ms": 4500,
            "telegraph_ms": 1500,
            "max_spawns": 4,
            "offset_ms": 0,
            "spawns_done": 0,
            "pending_spawn": False,
        }
        room.objective_entity_configs = [cfg]
        spawner = BurrowSpawner(cfg)
        # Telegraph: in windup, no spawn armed yet.
        spawner.update(100)
        self.assertTrue(spawner.telegraphing)
        self.assertFalse(cfg["pending_spawn"])
        # Strike: leave the telegraph window — pending spawn should arm.
        spawner.update(spawner.telegraph_ms + 100)
        self.assertTrue(cfg["pending_spawn"])
        self.assertEqual(spawner.spawns_done, 1)
        # Room.update_objective harvests the pending flag and emits spawn_enemies.
        update = room.update_objective(now_ticks=2000, enemy_group=[1])  # non-empty
        self.assertIsNotNone(update)
        self.assertEqual(update["kind"], "spawn_enemies")
        self.assertEqual(update["source"], "burrower_den")
        self.assertEqual(len(update["enemy_configs"]), 1)
        self.assertFalse(cfg["pending_spawn"])  # cleared by room

    def test_max_spawns_cap_holds(self):
        cfg = {
            "kind": "burrow_spawner",
            "pos": (5 * TILE_SIZE, 5 * TILE_SIZE),
            "cycle_ms": 4500,
            "telegraph_ms": 1500,
            "max_spawns": 2,
            "offset_ms": 0,
            "spawns_done": 0,
            "pending_spawn": False,
        }
        spawner = BurrowSpawner(cfg)
        for cycle in range(spawner.max_spawns + 3):
            base = cycle * spawner.cycle_ms
            spawner.update(base + 100)  # telegraph
            spawner.update(base + spawner.telegraph_ms + 100)  # strike
            cfg["pending_spawn"] = False  # simulate room consumption
        self.assertEqual(spawner.spawns_done, spawner.max_spawns)


class EchoCavernTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_echo_cavern", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_echo_cavern"]["enabled"], 1)

    def test_echo_cavern_sets_vision_radius_for_fog_of_war(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_echo_cavern", objective_rule="clear_enemies"),
        )
        self.assertIsNotNone(room.vision_radius)
        self.assertGreater(room.vision_radius, 0)


class BoulderRunTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_boulder_run", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_boulder_run"]["enabled"], 1)

    def _build_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_boulder_run", objective_rule="clear_enemies"),
        )

    def test_room_spawns_two_to_three_boulder_configs_with_lanes(self):
        room = self._build_room()
        boulders = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "boulder"
        ]
        self.assertGreaterEqual(len(boulders), 2)
        self.assertLessEqual(len(boulders), 3)
        # Each lane has a unique row and direction alternates.
        lane_ys = [cfg["lane_y"] for cfg in boulders]
        self.assertEqual(len(set(lane_ys)), len(boulders))
        directions = [cfg["direction"] for cfg in boulders]
        self.assertIn(1, directions)

    def test_boulder_telegraph_then_strike_phases(self):
        cfg = {
            "kind": "boulder",
            "lane_y": 6 * TILE_SIZE + TILE_SIZE // 2,
            "pos": (-1000, 6 * TILE_SIZE + TILE_SIZE // 2),
            "direction": 1,
            "cycle_ms": 3600,
            "telegraph_ms": 900,
            "speed": 6,
            "damage": 10,
            "knockback_px": 32,
            "damage_cooldown_ms": 700,
            "offset_ms": 0,
        }
        boulder = Boulder(cfg)
        # Telegraph window: parked offscreen, telegraphing flag on.
        boulder.update(100)
        self.assertTrue(boulder.telegraphing)
        self.assertFalse(boulder.rolling)
        # Past telegraph window: enters strike phase, starts rolling.
        boulder.update(boulder.telegraph_ms + 50)
        self.assertFalse(boulder.telegraphing)
        self.assertTrue(boulder.rolling)
        # Boulder advances each subsequent tick.
        x_before = boulder.rect.centerx
        boulder.update(boulder.telegraph_ms + 100)
        self.assertGreater(boulder.rect.centerx, x_before)

    def test_boulder_only_damages_during_strike_phase(self):
        cfg = {
            "kind": "boulder",
            "lane_y": 6 * TILE_SIZE + TILE_SIZE // 2,
            "pos": (-1000, 6 * TILE_SIZE + TILE_SIZE // 2),
            "direction": 1,
            "cycle_ms": 3600,
            "telegraph_ms": 900,
            "speed": 0,  # freeze position so collision is deterministic
            "damage": 10,
            "knockback_px": 0,
            "damage_cooldown_ms": 700,
            "offset_ms": 0,
        }
        boulder = Boulder(cfg)
        # Telegraph phase — parked offscreen, even an overlapping player
        # rect should not get hit.
        boulder.update(100)
        player = _make_player(2, 6)
        player._invincible_until = 0
        # Force-overlap by parking player at boulder position.
        player.rect.center = boulder.rect.center
        hp_before = player.current_hp
        boulder.apply_player_pressure(player)
        self.assertEqual(player.current_hp, hp_before)
        # Strike phase: position the boulder onto the player.
        boulder.update(boulder.telegraph_ms + 50)
        boulder.rect.center = player.rect.center
        boulder.apply_player_pressure(player)
        self.assertLess(player.current_hp, hp_before)


class ShrineCircleTests(unittest.TestCase):
    def test_template_registered_and_enabled_in_mud_caverns(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_shrine_circle", ids)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_shrine_circle"]["enabled"], 1)

    def _build_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_shrine_circle", objective_rule="clear_enemies"),
        )

    def test_room_lays_glyph_tiles_and_spawns_shrine_glyph(self):
        room = self._build_room()
        glyph_cells = [
            (c, r)
            for r in range(ROOM_ROWS)
            for c in range(ROOM_COLS)
            if room.grid[r][c] == GLYPH_TILE
        ]
        self.assertGreater(len(glyph_cells), 0)
        shrines = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "shrine_glyph"
        ]
        self.assertEqual(len(shrines), 1)
        self.assertEqual(set(shrines[0]["glyph_tiles"]), set(glyph_cells))

    def test_shrine_slows_enemies_only_when_player_stands_on_glyph(self):
        # Build a shrine entity with a known glyph tile coord.
        glyph_col, glyph_row = 10, 7
        cfg = {
            "kind": "shrine_glyph",
            "pos": (glyph_col * TILE_SIZE + TILE_SIZE // 2,
                    glyph_row * TILE_SIZE + TILE_SIZE // 2),
            "glyph_tiles": {(glyph_col, glyph_row)},
            "slow_ms": 600,
        }
        shrine = ShrineGlyph(cfg)

        # A bare-bones enemy stub — status_effects only needs an object
        # mutable enough to attach the status dict.
        class _FakeEnemy:
            def __init__(self, x, y):
                self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        enemy = _FakeEnemy(2 * TILE_SIZE, 2 * TILE_SIZE)
        enemy_group = [enemy]

        # Player not on glyph: no slow applied, shrine inactive.
        player_off = _make_player(2, 2)
        applied = shrine.apply_room_pressure(player_off, enemy_group)
        self.assertFalse(applied)
        self.assertFalse(shrine.active)
        now = pygame.time.get_ticks()
        self.assertFalse(status_effects.has_status(enemy, status_effects.SLOWED, now))

        # Player on glyph: slow applied, shrine active.
        player_on = _make_player(glyph_col, glyph_row)
        applied = shrine.apply_room_pressure(player_on, enemy_group)
        self.assertTrue(applied)
        self.assertTrue(shrine.active)
        now = pygame.time.get_ticks()
        self.assertTrue(status_effects.has_status(enemy, status_effects.SLOWED, now))


if __name__ == "__main__":
    unittest.main()
