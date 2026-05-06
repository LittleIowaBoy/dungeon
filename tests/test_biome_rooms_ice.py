"""Ice biome (Frozen Depths) room tests.

Covers:
- Template registration (scaffold asserts)
- ice_thin_ice_field: THIN_ICE terrain placed, door buffers cleared,
  connectivity guaranteed
- ice_crystal_room: IceCrystalEnemy fixtures placed, door buffers respected
- IceCrystalEnemy: immortality, freeze-pulse emission, update_attack_state
"""
import os
import random
import unittest

import pygame

import content_db
import status_effects
import terrain_effects
from enemies import IceCrystalEnemy
from player import Player
from progress import PlayerProgress
from room import FLOOR, THIN_ICE, PIT_TILE, ROOM_COLS, ROOM_ROWS, Room, DOOR
from room_plan import RoomPlan, RoomTemplate
from settings import (
    TILE_SIZE,
    ICE_THIN_ICE_FIELD_DOOR_BUFFER,
    ICE_CRYSTAL_ROOM_CRYSTAL_COUNT,
    ICE_CRYSTAL_ROOM_DOOR_BUFFER,
    ICE_CRYSTAL_PULSE_RADIUS,
    ICE_CRYSTAL_FREEZE_DURATION_MS,
    ICE_CRYSTAL_PULSE_WINDUP_MS,
    ICE_CRYSTAL_PULSE_STRIKE_MS,
    ICE_CRYSTAL_PULSE_COOLDOWN_MS,
    THIN_ICE_STEPS_TO_CRACK,
)


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.init()
pygame.display.set_mode((1, 1))


# ── helpers ───────────────────────────────────────────────────────────────

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


def _plan(room_id, *, terrain_type="ice", objective_rule="immediate"):
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
        terrain_patch_count_range=(2, 3),
        terrain_patch_size_range=(2, 3),
    )


def _build_room(room_id, open_dirs=("north", "south")):
    plan = _plan(room_id)
    doors = {
        "top": "north" in open_dirs,
        "bottom": "south" in open_dirs,
        "left": "west" in open_dirs,
        "right": "east" in open_dirs,
    }
    return Room(doors, is_exit=False, room_plan=plan)


def _door_tiles(room):
    tiles = set()
    for r in range(ROOM_ROWS):
        for c in range(ROOM_COLS):
            if room.grid[r][c] == DOOR:
                tiles.add((c, r))
    return tiles


# ── scaffold tests ────────────────────────────────────────────────────────

class IceTemplateScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.by_id = {t["room_id"]: t for t in content_db.BASE_ROOM_TEMPLATES}

    def test_both_templates_registered(self):
        for room_id in ("ice_thin_ice_field", "ice_crystal_room"):
            self.assertIn(room_id, self.by_id, f"Missing scaffold: {room_id}")

    def test_scaffolds_disabled_prototype(self):
        for room_id in ("ice_thin_ice_field", "ice_crystal_room"):
            t = self.by_id[room_id]
            self.assertEqual(t["enabled"], 0)
            self.assertEqual(t["generation_weight"], 0)
            self.assertEqual(t["implementation_status"], "prototype")

    def test_frozen_depths_enables_both(self):
        overrides = content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES.get("frozen_depths", ())
        ids = {o["room_id"] for o in overrides}
        self.assertIn("ice_thin_ice_field", ids)
        self.assertIn("ice_crystal_room", ids)

    def test_frozen_depths_overrides_have_positive_weight(self):
        overrides = content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES.get("frozen_depths", ())
        by_id = {o["room_id"]: o for o in overrides}
        for room_id in ("ice_thin_ice_field", "ice_crystal_room"):
            self.assertGreater(by_id[room_id]["generation_weight"], 0)
            self.assertEqual(by_id[room_id]["enabled"], 1)


# ── thin ice field polish tests ───────────────────────────────────────────

class ThinIceFieldPolishTests(unittest.TestCase):
    def setUp(self):
        self.room = _build_room("ice_thin_ice_field")

    def test_thin_ice_tiles_present(self):
        flat = [self.room.grid[r][c] for r in range(ROOM_ROWS) for c in range(ROOM_COLS)]
        self.assertIn(THIN_ICE, flat, "Room should contain THIN_ICE tiles after polish")

    def test_door_buffer_clear(self):
        door_tiles = _door_tiles(self.room)
        buf = ICE_THIN_ICE_FIELD_DOOR_BUFFER
        for dc, dr in door_tiles:
            for r in range(ROOM_ROWS):
                for c in range(ROOM_COLS):
                    if max(abs(c - dc), abs(r - dr)) <= buf:
                        self.assertNotEqual(
                            self.room.grid[r][c], THIN_ICE,
                            f"THIN_ICE at ({c},{r}) is too close to door ({dc},{dr})",
                        )

    def test_connectivity_from_doors_to_center(self):
        """BFS from every door interior tile to room centre must succeed
        treating THIN_ICE as passable (same BFS used by the polish method)."""
        from room import WALL
        center = (ROOM_COLS // 2, ROOM_ROWS // 2)
        door_tiles = _door_tiles(self.room)
        room = self.room

        for dc, dr in sorted(door_tiles):
            # find first interior neighbour
            for (dx, dy) in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nc, nr = dc + dx, dr + dy
                if 0 <= nr < ROOM_ROWS and 0 <= nc < ROOM_COLS:
                    if room.grid[nr][nc] != WALL and room.grid[nr][nc] != DOOR:
                        entry = (nc, nr)
                        break
            else:
                continue
            path = room._bfs_path_through_hazard(entry, center, THIN_ICE)
            self.assertIsNotNone(
                path, f"No path from door at ({dc},{dr}) to room centre"
            )


# ── ice crystal room polish tests ─────────────────────────────────────────

class IceCrystalRoomPolishTests(unittest.TestCase):
    def setUp(self):
        self.room = _build_room("ice_crystal_room")

    def test_correct_crystal_count(self):
        crystal_cfgs = [
            cfg for cfg in self.room.enemy_configs
            if cfg[0] is IceCrystalEnemy
        ]
        self.assertEqual(len(crystal_cfgs), ICE_CRYSTAL_ROOM_CRYSTAL_COUNT)

    def test_crystals_not_in_door_buffer(self):
        door_tiles = _door_tiles(self.room)
        buf = ICE_CRYSTAL_ROOM_DOOR_BUFFER
        for _, (px, py) in self.room.enemy_configs:
            c = px // TILE_SIZE
            r = py // TILE_SIZE
            for dc, dr in door_tiles:
                self.assertGreater(
                    max(abs(c - dc), abs(r - dr)), buf,
                    f"Crystal at tile ({c},{r}) is within door buffer of ({dc},{dr})",
                )

    def test_crystals_on_floor_tiles(self):
        for cls, (px, py) in self.room.enemy_configs:
            if cls is not IceCrystalEnemy:
                continue
            c = px // TILE_SIZE
            r = py // TILE_SIZE
            self.assertEqual(
                self.room.grid[r][c], FLOOR,
                f"Crystal placed on non-FLOOR tile at ({c},{r})",
            )


# ── IceCrystalEnemy unit tests ────────────────────────────────────────────

class IceCrystalEnemyTests(unittest.TestCase):
    def _make_crystal(self, x=200, y=200):
        return IceCrystalEnemy(x, y)

    def test_immortal_take_damage(self):
        c = self._make_crystal()
        c.take_damage(9999)
        self.assertGreater(c.current_hp, 0)

    def test_no_freeze_pulse_initially(self):
        c = self._make_crystal()
        self.assertFalse(c.consume_freeze_pulses())

    def test_pulse_emitted_at_strike(self):
        c = self._make_crystal()
        player_rect = pygame.Rect(200 - 10, 200 - 10, 20, 20)

        # Fast-forward past the initial interval guard.
        c._next_pulse_at = 0
        c._attack_state = "idle"  # use string constant from enemies

        # Simulate: telegraph start → strike start.
        c._on_telegraph_start(player_rect, 0)
        c._on_strike_start(player_rect, 0)
        self.assertTrue(c.consume_freeze_pulses())

    def test_consume_clears_flag(self):
        c = self._make_crystal()
        c._freeze_pulse_pending = True
        self.assertTrue(c.consume_freeze_pulses())
        self.assertFalse(c.consume_freeze_pulses())

    def test_update_movement_is_noop(self):
        c = self._make_crystal()
        pos_before = c.rect.topleft
        c.update_movement(None, [])
        self.assertEqual(c.rect.topleft, pos_before)


# ── I1 THIN_ICE cracking mechanic (terrain_effects) ──────────────────────

class _StubRoom:
    def __init__(self, tile):
        cols, rows = ROOM_COLS, ROOM_ROWS
        self.grid = [[tile] * cols for _ in range(rows)]
        self._quicksand_drown_ms = 0
        self._hazard_last_tick_ms = 0
        self._previous_player_tile = None

    def tile_at(self, col, row):
        if 0 <= col < ROOM_COLS and 0 <= row < ROOM_ROWS:
            return self.grid[row][col]
        return "wall"

    def terrain_at_pixel(self, px, py):
        col, row = int(px) // TILE_SIZE, int(py) // TILE_SIZE
        return self.tile_at(col, row)

    def current_vector_at_pixel(self, px, py):
        return None

    def get_tile(self, col, row):
        return self.tile_at(col, row)


class _FakePlayer(pygame.sprite.Sprite):
    def __init__(self, tile_col, tile_row):
        super().__init__()
        self.rect = pygame.Rect(
            tile_col * TILE_SIZE + TILE_SIZE // 4,
            tile_row * TILE_SIZE + TILE_SIZE // 4,
            TILE_SIZE // 2,
            TILE_SIZE // 2,
        )
        self.current_hp = 10
        self.max_hp = 10
        self._invincible_until = 0
        self._status_effects: dict = {}
        self._is_dead = False

    @property
    def is_invincible(self):
        return False

    def take_damage(self, amount, damage_type=None):
        self.current_hp = max(0, self.current_hp - amount)

    def is_dead(self):
        return self.current_hp <= 0


class ThinIceCrackingTests(unittest.TestCase):
    def _room_with_thin_ice(self):
        return _StubRoom(THIN_ICE)

    def _player_on_tile(self, col, row):
        return _FakePlayer(col, row)

    def test_tile_cracks_after_enough_steps(self):
        room = self._room_with_thin_ice()
        col, row = 5, 5
        player = self._player_on_tile(col, row)
        # position player on tile (col, row)
        player.rect.x = col * TILE_SIZE + TILE_SIZE // 4
        player.rect.y = row * TILE_SIZE + TILE_SIZE // 4
        for i in range(THIN_ICE_STEPS_TO_CRACK - 1):
            # Simulate entering (col, row) from a neighbouring tile.
            room._previous_player_tile = (col + 1, row)
            terrain_effects.apply_terrain_effects(player, room, i * 100, 16)
        # final step should crack the tile
        room._previous_player_tile = (col + 1, row)
        diag = terrain_effects.apply_terrain_effects(player, room, THIN_ICE_STEPS_TO_CRACK * 100, 16)
        self.assertTrue(diag.get("thin_ice_cracked", False))
        self.assertEqual(room.grid[row][col], PIT_TILE)

    def test_cracking_triggers_fall_animation(self):
        # Cracking through thin ice no longer kills instantly; it starts the
        # pit fall animation so the player survives and is respawned nearby.
        room = self._room_with_thin_ice()
        col, row = 5, 5
        player = self._player_on_tile(col, row)
        player.rect.x = col * TILE_SIZE + TILE_SIZE // 4
        player.rect.y = row * TILE_SIZE + TILE_SIZE // 4
        player.current_hp = 5
        player._invincible_until = 0
        for i in range(THIN_ICE_STEPS_TO_CRACK - 1):
            room._previous_player_tile = (col + 1, row)
            terrain_effects.apply_terrain_effects(player, room, i * 100, 16)
        room._previous_player_tile = (col + 1, row)
        terrain_effects.apply_terrain_effects(player, room, THIN_ICE_STEPS_TO_CRACK * 100, 16)
        self.assertEqual(player._pit_fall_phase, "falling")
        self.assertGreater(player.current_hp, 0)

    def test_no_crack_without_new_step(self):
        room = self._room_with_thin_ice()
        col, row = 5, 5
        player = self._player_on_tile(col, row)
        player.rect.x = col * TILE_SIZE + TILE_SIZE // 4
        player.rect.y = row * TILE_SIZE + TILE_SIZE // 4
        # _previous_player_tile == current tile each time → no new step
        room._previous_player_tile = (col, row)
        for i in range(THIN_ICE_STEPS_TO_CRACK * 5):
            diag = terrain_effects.apply_terrain_effects(player, room, i * 100, 16)
            self.assertFalse(diag.get("thin_ice_cracked", False))
        self.assertEqual(room.grid[row][col], THIN_ICE)


# ── Phase C: ice bespoke room payoff bonuses ─────────────────────────────

class ThinIceIntactFloorBonusTests(unittest.TestCase):
    """C1 — ice_thin_ice_field bonus chest for low pit-crack count."""

    def _build_room(self):
        return _build_room("ice_thin_ice_field")

    # helper: mark a room as having all enemies cleared
    @staticmethod
    def _clear(room):
        room.enemies_cleared = True

    def test_bonus_chest_spawns_when_pits_at_threshold(self):
        from settings import THIN_ICE_CRACK_BONUS_MAX_PITS
        import pygame
        room = self._build_room()
        self._clear(room)
        # pits at exactly the threshold
        room._thin_ice_pits_created = THIN_ICE_CRACK_BONUS_MAX_PITS
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "spawn_reward_chest")

    def test_no_bonus_when_pits_exceed_threshold(self):
        from settings import THIN_ICE_CRACK_BONUS_MAX_PITS
        import pygame
        room = self._build_room()
        self._clear(room)
        room._thin_ice_pits_created = THIN_ICE_CRACK_BONUS_MAX_PITS + 1
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_no_bonus_before_enemies_cleared(self):
        import pygame
        room = self._build_room()
        room._thin_ice_pits_created = 0   # zero pits — would qualify
        # enemies NOT cleared yet
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_bonus_fires_only_once(self):
        import pygame
        room = self._build_room()
        self._clear(room)
        room._thin_ice_pits_created = 0
        result1 = room.update_objective(1000, pygame.sprite.Group())
        result2 = room.update_objective(2000, pygame.sprite.Group())
        self.assertIsNotNone(result1)
        self.assertIsNone(result2)

    def test_pit_counter_incremented_by_terrain_effects(self):
        """terrain_effects should bump _thin_ice_pits_created on crack."""
        room = _StubRoom(THIN_ICE)
        col, row = 4, 4
        player = _FakePlayer(col, row)
        player.rect.x = col * TILE_SIZE + TILE_SIZE // 4
        player.rect.y = row * TILE_SIZE + TILE_SIZE // 4
        for i in range(THIN_ICE_STEPS_TO_CRACK - 1):
            room._previous_player_tile = (col + 1, row)
            terrain_effects.apply_terrain_effects(player, room, i * 100, 16)
        # final step — tile collapses
        room._previous_player_tile = (col + 1, row)
        terrain_effects.apply_terrain_effects(
            player, room, THIN_ICE_STEPS_TO_CRACK * 100, 16
        )
        self.assertEqual(getattr(room, "_thin_ice_pits_created", 0), 1)


class AvalanchePillarGuardianBonusTests(unittest.TestCase):
    """C2 — ice_avalanche_run bonus chest when an IcePillar survives."""

    def _build_room(self):
        return _build_room("ice_avalanche_run")

    @staticmethod
    def _clear(room):
        room.enemies_cleared = True

    def test_bonus_when_pillar_alive(self):
        import pygame
        room = self._build_room()
        self._clear(room)
        room._pillar_count_alive = 1    # at least one pillar survived
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "spawn_reward_chest")

    def test_no_bonus_when_all_pillars_destroyed(self):
        import pygame
        room = self._build_room()
        self._clear(room)
        room._pillar_count_alive = 0    # all pillars gone
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_no_bonus_before_enemies_cleared(self):
        import pygame
        room = self._build_room()
        room._pillar_count_alive = 2    # pillars still up, but room not clear
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_bonus_fires_only_once(self):
        import pygame
        room = self._build_room()
        self._clear(room)
        room._pillar_count_alive = 1
        result1 = room.update_objective(1000, pygame.sprite.Group())
        result2 = room.update_objective(2000, pygame.sprite.Group())
        self.assertIsNotNone(result1)
        self.assertIsNone(result2)


# ── Phase D: ice bespoke room payoff bonuses (crystal / aura / spirit) ────

class CrystalRoomUnshakenBonusTests(unittest.TestCase):
    """D1 — ice_crystal_room bonus chest when player was never FROZEN."""

    def _build_room(self):
        return _build_room("ice_crystal_room")

    @staticmethod
    def _clear(room):
        room.enemies_cleared = True

    def test_bonus_when_never_frozen(self):
        room = self._build_room()
        self._clear(room)
        # _player_froze never set → should award bonus
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "spawn_reward_chest")

    def test_no_bonus_when_frozen(self):
        room = self._build_room()
        self._clear(room)
        room._player_froze = True        # player was frozen during combat
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_no_bonus_before_enemies_cleared(self):
        room = self._build_room()
        # enemies NOT cleared, player was never frozen — still no bonus yet
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_bonus_fires_only_once(self):
        room = self._build_room()
        self._clear(room)
        result1 = room.update_objective(1000, pygame.sprite.Group())
        result2 = room.update_objective(2000, pygame.sprite.Group())
        self.assertIsNotNone(result1)
        self.assertIsNone(result2)


class FreezeAuraRoomUnattunedBonusTests(unittest.TestCase):
    """D2 — ice_freeze_aura_room bonus chest when player was never FROZEN."""

    def _build_room(self):
        return _build_room("ice_freeze_aura_room")

    @staticmethod
    def _clear(room):
        room.enemies_cleared = True

    def test_bonus_when_never_frozen(self):
        room = self._build_room()
        self._clear(room)
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "spawn_reward_chest")

    def test_no_bonus_when_frozen(self):
        room = self._build_room()
        self._clear(room)
        room._player_froze = True
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_no_bonus_before_enemies_cleared(self):
        room = self._build_room()
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_bonus_fires_only_once(self):
        room = self._build_room()
        self._clear(room)
        result1 = room.update_objective(1000, pygame.sprite.Group())
        result2 = room.update_objective(2000, pygame.sprite.Group())
        self.assertIsNotNone(result1)
        self.assertIsNone(result2)


class SpiritSwarmCleanFloorBonusTests(unittest.TestCase):
    """D3 — ice_spirit_swarm_room bonus chest for low trail-pit count."""

    def _build_room(self):
        return _build_room("ice_spirit_swarm_room")

    @staticmethod
    def _clear(room):
        room.enemies_cleared = True

    def test_bonus_when_pits_at_threshold(self):
        from settings import SPIRIT_SWARM_TRAIL_PIT_BONUS_MAX
        room = self._build_room()
        self._clear(room)
        room._trail_freeze_pits_created = SPIRIT_SWARM_TRAIL_PIT_BONUS_MAX
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "spawn_reward_chest")

    def test_no_bonus_when_pits_exceed_threshold(self):
        from settings import SPIRIT_SWARM_TRAIL_PIT_BONUS_MAX
        room = self._build_room()
        self._clear(room)
        room._trail_freeze_pits_created = SPIRIT_SWARM_TRAIL_PIT_BONUS_MAX + 1
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_no_bonus_before_enemies_cleared(self):
        room = self._build_room()
        room._trail_freeze_pits_created = 0
        result = room.update_objective(1000, pygame.sprite.Group())
        self.assertIsNone(result)

    def test_bonus_fires_only_once(self):
        room = self._build_room()
        self._clear(room)
        room._trail_freeze_pits_created = 0
        result1 = room.update_objective(1000, pygame.sprite.Group())
        result2 = room.update_objective(2000, pygame.sprite.Group())
        self.assertIsNotNone(result1)
        self.assertIsNone(result2)

    def test_trail_freeze_pits_tracked_by_terrain_effects(self):
        """advance_trail_freeze_tiles should bump _trail_freeze_pits_created."""
        from room import TRAIL_FREEZE
        from settings import TRAIL_FREEZE_DURATION_MS
        stub = _StubRoom(FLOOR)
        # Place a TRAIL_FREEZE tile and register it as already expired.
        col, row = 5, 5
        stub.grid[row][col] = TRAIL_FREEZE
        stub._trail_freeze_tiles = {(col, row): 0}
        # now_ticks well past expiry
        terrain_effects.advance_trail_freeze_tiles(stub, TRAIL_FREEZE_DURATION_MS + 1)
        self.assertEqual(stub.grid[row][col], PIT_TILE)
        self.assertEqual(getattr(stub, "_trail_freeze_pits_created", 0), 1)


if __name__ == "__main__":
    unittest.main()
