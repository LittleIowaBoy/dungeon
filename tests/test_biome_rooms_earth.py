"""Phase 2.A — Earth biome rooms: stalagmite field + quicksand trap.

These rooms reuse the standard combat flow but replace the biome's default
mud terrain patches with hazard tiles handled by ``terrain_effects.py``.
The tests below assert template registration, terrain placement, and the
end-to-end damage/drown behaviour.
"""
import os
import random
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
    TILE_SIZE, HAZARD_TICK_MS, HAZARD_TICK_DAMAGE,
    STALAGMITE_STEP_DAMAGE, QUICKSAND_PULL_SPEED,
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
    def test_player_on_spike_patch_takes_step_entry_damage(self):
        """Stepping onto a spike tile deals one fixed STALAGMITE_STEP_DAMAGE hit.

        Standing motionless and stepping off do not deal damage; that
        full per-tile-entry contract is exercised in
        ``test_biome_room_phase1.test_spike_patch_damages_only_on_tile_entry``.
        Here we just confirm the field room actually wires through the
        new mechanic.
        """
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan("earth_stalagmite_field"),
        )
        cell = _find_tile(room, SPIKE_PATCH)
        self.assertIsNotNone(cell)
        col, row = cell
        # Place player on an adjacent FLOOR tile so the first frame
        # initialises the previous-tile pointer without damage.
        adj = None
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ac, ar = col + dc, row + dr
            if 0 <= ac < ROOM_COLS and 0 <= ar < ROOM_ROWS:
                if room.grid[ar][ac] == FLOOR:
                    adj = (ac, ar)
                    break
        self.assertIsNotNone(adj, "need a floor tile adjacent to a spike for the test")
        player = _make_player(*adj)
        hp_before = player.current_hp
        terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertEqual(player.current_hp, hp_before)
        # Step onto the spike tile.
        player.rect.center = (
            col * TILE_SIZE + TILE_SIZE // 2,
            row * TILE_SIZE + TILE_SIZE // 2,
        )
        terrain_effects.apply_terrain_effects(player, room, 16, 16)
        self.assertEqual(player.current_hp, hp_before - STALAGMITE_STEP_DAMAGE)

    def test_player_in_quicksand_is_pulled_toward_tile_centre(self):
        """Quicksand tiles in a real Earth room pull the player to centre.

        Replaces the legacy drowning-timer assertion: the new model is
        non-lethal terrain combined with a dodge-mash escape loop (the
        full pull / suppression contract is exercised in
        ``test_biome_room_phase1`` against the stub room).
        """
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan("earth_quicksand_trap"),
        )
        cell = _find_tile(room, QUICKSAND)
        self.assertIsNotNone(cell)
        col, row = cell
        player = _make_player(col, row)
        tile_centre_x = col * TILE_SIZE + TILE_SIZE // 2
        player.rect.centerx = tile_centre_x + 6
        player._invincible_until = 0  # clear spawn i-frames
        hp_before = player.current_hp
        diag = terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertTrue(diag["quicksand_pull"])
        self.assertLess(
            abs(player.rect.centerx - tile_centre_x),
            6,
            "player should drift toward the tile centre",
        )
        # Tile itself is not lethal under the new model.
        self.assertEqual(player.current_hp, hp_before)


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

    def test_room_spawns_twenty_to_thirty_mushroom_configs(self):
        room = self._build_room()
        mushrooms = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "spore_mushroom"
        ]
        self.assertGreaterEqual(len(mushrooms), 20)
        self.assertLessEqual(len(mushrooms), 30)

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
            room_plan=_plan("earth_boulder_run"),
        )

    def test_room_spawns_single_boulder_run_spawner(self):
        room = self._build_room()
        spawners = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "boulder_run_spawner"
        ]
        # Exactly one spawner per room; it owns the chosen source wall
        # and the door-column exclusion set used to keep traversal lanes
        # clear.
        self.assertEqual(len(spawners), 1)
        cfg = spawners[0]
        self.assertIn(cfg["source_wall"], ("top", "bottom"))
        # Door columns = the 3-tile-wide opening centred on mid_col.
        from settings import DOOR_WIDTH
        mid_col = ROOM_COLS // 2
        half = DOOR_WIDTH // 2
        expected = set(range(mid_col - half, mid_col + half + 1))
        self.assertEqual(set(cfg["door_columns"]), expected)

    def test_boulder_rolls_in_chosen_direction_and_despawns_offscreen(self):
        cfg = {
            "lane_x": 5 * TILE_SIZE + TILE_SIZE // 2,
            "direction": 1,  # spawned at top wall, rolls down
            "speed": 5,
            "damage": 10,
            "knockback_px": 0,
            "damage_cooldown_ms": 700,
        }
        boulder = Boulder(cfg)
        group = pygame.sprite.Group(boulder)
        # Spawned just above the room ceiling.
        self.assertLess(boulder.rect.centery, 0)
        y_before = boulder.rect.centery
        boulder.update(0)
        self.assertGreater(boulder.rect.centery, y_before)
        # Force boulder past the bottom wall — it should kill itself and
        # leave the sprite group on the next update.
        room_height = ROOM_ROWS * TILE_SIZE
        boulder.rect.centery = room_height + boulder.SIZE * 2
        boulder.update(0)
        self.assertNotIn(boulder, group)

    def test_boulder_damages_player_on_collision_with_cooldown(self):
        cfg = {
            "lane_x": 5 * TILE_SIZE + TILE_SIZE // 2,
            "direction": 1,
            "speed": 0,  # freeze in place for deterministic collision
            "damage": 10,
            "knockback_px": 0,
            "damage_cooldown_ms": 700,
        }
        boulder = Boulder(cfg)
        player = _make_player(5, 5)
        player._invincible_until = 0
        # Park the boulder onto the player.
        boulder.rect.center = player.rect.center
        hp_before = player.current_hp
        self.assertTrue(boulder.apply_player_pressure(player))
        self.assertLess(player.current_hp, hp_before)
        # Immediate re-hit is suppressed by the per-boulder cooldown.
        hp_after_first = player.current_hp
        self.assertFalse(boulder.apply_player_pressure(player))
        self.assertEqual(player.current_hp, hp_after_first)

    def test_spawner_emits_boulders_at_random_columns_excluding_doors(self):
        from objective_entities import BoulderRunSpawner
        from settings import DOOR_WIDTH
        mid_col = ROOM_COLS // 2
        half = DOOR_WIDTH // 2
        door_cols = set(range(mid_col - half, mid_col + half + 1))
        rng = random.Random(0)
        cfg = {
            "kind": "boulder_run_spawner",
            "source_wall": "top",
            "door_columns": door_cols,
            # Tight interval so several spawns fire in the test window.
            "interval_range": (1, 1),
            "speed_range": (5.0, 5.0),
            "rng": rng,
        }
        spawner = BoulderRunSpawner(cfg)
        group = pygame.sprite.Group(spawner)
        spawner.objective_group = group
        # First update schedules the first spawn — no boulder yet.
        spawner.update(0)
        self.assertEqual(spawner.spawned, 0)
        # Subsequent ticks fire boulders.  Run enough to cover most cols.
        for tick in range(1, 200):
            spawner.update(tick)
        self.assertGreater(spawner.spawned, 0)
        boulders = [s for s in group if isinstance(s, Boulder)]
        self.assertEqual(len(boulders), spawner.spawned)
        # No boulder should ever spawn on a door column.
        for boulder in boulders:
            col = boulder.lane_x // TILE_SIZE
            self.assertNotIn(col, door_cols)
        # All boulders rolling DOWN (direction=+1) since source_wall=top.
        for boulder in boulders:
            self.assertEqual(boulder.direction, 1)



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


class GolemArenaTemplateTests(unittest.TestCase):
    """Phase 4: Golem mini-boss arena is fully wired and enabled."""

    def test_template_registered_with_min_depth_two_and_finale_role(self):
        ids = {t["room_id"] for t in content_db.BASE_ROOM_TEMPLATES}
        self.assertIn("earth_golem_arena", ids)
        tmpl = next(
            t for t in content_db.BASE_ROOM_TEMPLATES
            if t["room_id"] == "earth_golem_arena"
        )
        self.assertEqual(tmpl["min_depth"], 2)
        self.assertEqual(tmpl["topology_role"], "finale")
        self.assertEqual(tmpl["terminal_preference"], "prefer")
        # Base template defaults stay disabled; the mud_caverns override
        # flips it on (verified separately via DUNGEON_ROOM_TEMPLATE_OVERRIDES).
        self.assertEqual(tmpl["enabled"], 0)
        self.assertEqual(tmpl["generation_weight"], 0)
        overrides = {
            t["room_id"]: t
            for t in content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES["mud_caverns"]
        }
        self.assertEqual(overrides["earth_golem_arena"]["enabled"], 1)

    def test_room_builder_emits_golem_arena_controller_config(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_golem_arena", objective_rule="clear_enemies"),
        )
        controllers = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "golem_arena_controller"
        ]
        self.assertEqual(len(controllers), 1)
        cfg = controllers[0]
        self.assertEqual(set(cfg["wave_specs"].keys()), {0.75, 0.5, 0.25})
        self.assertFalse(cfg["loot_granted"])

    def test_golem_arena_seeds_only_the_golem_in_enemy_configs(self):
        from enemies import Golem
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("earth_golem_arena", objective_rule="clear_enemies"),
        )
        self.assertEqual(len(room.enemy_configs), 1)
        cls, _pos = room.enemy_configs[0]
        self.assertIs(cls, Golem)


if __name__ == "__main__":
    unittest.main()
