"""Phase 1 biome-room infrastructure: hazard tiles + room buffs + fog-of-war."""
import os
import unittest

import pygame

import terrain_effects
from player import Player
from progress import PlayerProgress
from room import (
    FLOOR, WALL, QUICKSAND, SPIKE_PATCH, PIT_TILE, CURRENT,
    ROOM_COLS, ROOM_ROWS,
)
from settings import (
    TILE_SIZE, HAZARD_TICK_MS, HAZARD_TICK_DAMAGE, STALAGMITE_STEP_DAMAGE,
    QUICKSAND_PULL_SPEED, CURRENT_PUSH_SPEED,
)


def _empty_grid():
    return [[FLOOR for _ in range(ROOM_COLS)] for _ in range(ROOM_ROWS)]


def _wall_border_grid():
    grid = _empty_grid()
    for c in range(ROOM_COLS):
        grid[0][c] = WALL
        grid[ROOM_ROWS - 1][c] = WALL
    for r in range(ROOM_ROWS):
        grid[r][0] = WALL
        grid[r][ROOM_COLS - 1] = WALL
    return grid


class _StubRoom:
    """Minimal Room stand-in.

    Real :class:`Room` requires a populated content_db to construct.  The
    Phase 1 dispatcher only touches ``tile_at``, ``terrain_at_pixel``,
    ``current_vector_at_pixel``, ``get_wall_rects``, and the four buff /
    timer attributes — all stubbed here.
    """

    def __init__(self, grid=None, current_vectors=None):
        self.grid = grid if grid is not None else _wall_border_grid()
        self.current_vectors = current_vectors or {}
        self._quicksand_drown_ms = 0
        self._hazard_last_tick_ms = 0
        self._previous_player_tile: tuple[int, int] | None = None

    def tile_at(self, col, row):
        if 0 <= col < ROOM_COLS and 0 <= row < ROOM_ROWS:
            return self.grid[row][col]
        return WALL

    def terrain_at_pixel(self, px, py):
        col, row = int(px) // TILE_SIZE, int(py) // TILE_SIZE
        return self.tile_at(col, row)

    def current_vector_at_pixel(self, px, py):
        col, row = int(px) // TILE_SIZE, int(py) // TILE_SIZE
        if self.tile_at(col, row) != CURRENT:
            return None
        return self.current_vectors.get((col, row))

    def get_wall_rects(self):
        rects = []
        for r in range(ROOM_ROWS):
            for c in range(ROOM_COLS):
                if self.grid[r][c] == WALL:
                    rects.append(pygame.Rect(
                        c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        return rects


def _make_player(col, row):
    player = Player(col * TILE_SIZE + TILE_SIZE // 2,
                    row * TILE_SIZE + TILE_SIZE // 2)
    player.reset_for_dungeon(PlayerProgress())
    return player


class TerrainEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_floor_tile_is_no_op(self):
        room = _StubRoom()
        player = _make_player(5, 5)
        hp = player.current_hp
        diag = terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertEqual(diag["tile"], FLOOR)
        self.assertEqual(player.current_hp, hp)

    def test_pit_tile_is_lethal(self):
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        room = _StubRoom(grid=grid)
        player = _make_player(5, 5)
        terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertLessEqual(player.current_hp, 0)

    def test_spike_patch_damages_only_on_tile_entry(self):
        """SPIKE_PATCH deals damage on the frame the player moves ONTO it.

        Subsequent frames at the same tile coordinate are no-ops ("standing
        motionless"), and stepping OFF a spike tile does not damage.
        Walking from one spike tile to an adjacent spike tile triggers a
        new entry damage event.
        """
        grid = _wall_border_grid()
        grid[5][5] = SPIKE_PATCH
        grid[5][6] = SPIKE_PATCH  # adjacent spike for the cross-tile test
        room = _StubRoom(grid=grid)
        player = _make_player(4, 5)  # start on FLOOR adjacent to the spike
        hp_before = player.current_hp

        # Frame 1: player on FLOOR, no damage; pointer initialised.
        terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertEqual(player.current_hp, hp_before)

        # Step onto first spike tile: damage fires once.
        player.rect.center = (
            5 * TILE_SIZE + TILE_SIZE // 2,
            5 * TILE_SIZE + TILE_SIZE // 2,
        )
        terrain_effects.apply_terrain_effects(player, room, 16, 16)
        self.assertEqual(player.current_hp, hp_before - STALAGMITE_STEP_DAMAGE)

        # Standing motionless on the same spike tile: no further damage.
        player._invincible_until = 0  # bypass i-frames so we can verify
        for tick in range(2, 10):
            terrain_effects.apply_terrain_effects(player, room, tick * 16, 16)
        self.assertEqual(player.current_hp, hp_before - STALAGMITE_STEP_DAMAGE)

        # Stepping onto the adjacent spike tile triggers a new entry hit.
        player.rect.center = (
            6 * TILE_SIZE + TILE_SIZE // 2,
            5 * TILE_SIZE + TILE_SIZE // 2,
        )
        terrain_effects.apply_terrain_effects(player, room, 200, 16)
        self.assertEqual(player.current_hp, hp_before - 2 * STALAGMITE_STEP_DAMAGE)

        # Stepping OFF onto FLOOR: no damage.
        player._invincible_until = 0
        player.rect.center = (
            7 * TILE_SIZE + TILE_SIZE // 2,
            5 * TILE_SIZE + TILE_SIZE // 2,
        )
        terrain_effects.apply_terrain_effects(player, room, 300, 16)
        self.assertEqual(player.current_hp, hp_before - 2 * STALAGMITE_STEP_DAMAGE)

    def test_quicksand_pulls_player_toward_tile_centre(self):
        """Standing on a quicksand tile drifts the player toward its centre.

        The drowning timer model (lethal after a few seconds standing
        still) was replaced by a pull-to-centre + dodge-to-escape loop:
        no damage is dealt by the tile itself; the dodge ability is the
        intended escape mechanic (see ``test_quicksand_pull_suppressed_*``).
        """
        grid = _wall_border_grid()
        grid[5][5] = QUICKSAND
        room = _StubRoom(grid=grid)
        # Place player off-centre within the quicksand tile so the pull
        # has a non-zero direction.
        player = _make_player(5, 5)
        tile_centre = (5 * TILE_SIZE + TILE_SIZE // 2,
                       5 * TILE_SIZE + TILE_SIZE // 2)
        player.rect.center = (tile_centre[0] + 6, tile_centre[1])
        player._invincible_until = 0  # clear spawn i-frames
        hp_before = player.current_hp

        # A few ticks: player drifts strictly toward the tile centre and
        # never loses HP.  Stop short of reaching the centre so every
        # tick should still report ``quicksand_pull = True``.
        prev_dist_x = abs(player.rect.centerx - tile_centre[0])
        for _ in range(3):
            diag = terrain_effects.apply_terrain_effects(player, room, 0, 16)
            self.assertTrue(diag["quicksand_pull"])
            self.assertEqual(player.current_hp, hp_before)
            new_dist_x = abs(player.rect.centerx - tile_centre[0])
            self.assertLess(new_dist_x, prev_dist_x)
            prev_dist_x = new_dist_x

    def test_quicksand_pull_suppressed_when_invincible(self):
        """Dodge / spawn i-frames must let the player escape the pull.

        ``terrain_effects`` skips the pull while the player is invincible
        so the dodge ability (which grants i-frames + a 2.4x speed burst)
        always wins the tug-of-war.
        """
        grid = _wall_border_grid()
        grid[5][5] = QUICKSAND
        room = _StubRoom(grid=grid)
        player = _make_player(5, 5)
        tile_centre = (5 * TILE_SIZE + TILE_SIZE // 2,
                       5 * TILE_SIZE + TILE_SIZE // 2)
        player.rect.center = (tile_centre[0] + 6, tile_centre[1])
        # Force i-frames active for an absurd duration.
        player._invincible_until = 10 ** 9
        diag = terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertFalse(diag["quicksand_pull"])
        # Position unchanged — no pull while invincible.
        self.assertEqual(player.rect.centerx, tile_centre[0] + 6)

    def test_quicksand_pull_stops_when_stepping_off(self):
        """Stepping off the quicksand tile clears the pull diagnostic."""
        grid = _wall_border_grid()
        grid[5][5] = QUICKSAND
        room = _StubRoom(grid=grid)
        player = _make_player(5, 5)
        terrain_effects.apply_terrain_effects(player, room, 0, 16)
        # Step off onto floor.
        player.rect.center = (6 * TILE_SIZE + TILE_SIZE // 2,
                              5 * TILE_SIZE + TILE_SIZE // 2)
        player._invincible_until = 0  # clear spawn i-frames
        diag = terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertFalse(diag["quicksand_pull"])

    def test_current_pushes_player_along_vector(self):
        grid = _wall_border_grid()
        grid[5][5] = CURRENT
        room = _StubRoom(grid=grid, current_vectors={(5, 5): (1.0, 0.0)})
        player = _make_player(5, 5)
        x_before = player.rect.x
        diag = terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertTrue(diag["pushed"])
        self.assertEqual(player.rect.x, x_before + int(round(CURRENT_PUSH_SPEED)))

    def test_current_push_blocked_by_wall(self):
        grid = _wall_border_grid()
        # Place CURRENT next to right wall, pushing right.
        grid[5][ROOM_COLS - 2] = CURRENT
        room = _StubRoom(
            grid=grid,
            current_vectors={(ROOM_COLS - 2, 5): (1.0, 0.0)},
        )
        player = _make_player(ROOM_COLS - 2, 5)
        # Snug player up against the right wall.
        player.rect.right = (ROOM_COLS - 1) * TILE_SIZE
        terrain_effects.apply_terrain_effects(player, room, 0, 16)
        self.assertEqual(player.rect.right, (ROOM_COLS - 1) * TILE_SIZE)

    def test_invincible_player_ignores_hazards(self):
        grid = _wall_border_grid()
        grid[5][5] = SPIKE_PATCH
        room = _StubRoom(grid=grid)
        player = _make_player(4, 5)  # start adjacent so we can step onto spike
        # Force i-frames active for an absurd duration.
        player._invincible_until = 10 ** 9
        hp_before = player.current_hp
        # Initialise the previous-tile pointer.
        terrain_effects.apply_terrain_effects(player, room, 0, 16)
        # Step onto spike with i-frames active — no damage.
        player.rect.center = (
            5 * TILE_SIZE + TILE_SIZE // 2,
            5 * TILE_SIZE + TILE_SIZE // 2,
        )
        terrain_effects.apply_terrain_effects(player, room, HAZARD_TICK_MS, 16)
        self.assertEqual(player.current_hp, hp_before)


class RoomBuffRegistryTests(unittest.TestCase):
    """The buff registry helpers live on Room; verify them in isolation."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_room(self):
        # Defer the Room import until pygame is initialised so the
        # content_db fixture can be lazy-loaded.
        from room import Room
        return Room({})

    def test_buff_total_sums_active_entries(self):
        room = self._make_room()
        room.add_room_buff("damage", 0.10, expires_at=None)
        room.add_room_buff("damage", 0.25, expires_at=10_000)
        room.add_room_buff("speed", 0.50, expires_at=None)
        self.assertAlmostEqual(room.active_room_buff_total("damage", 5_000), 0.35)
        self.assertAlmostEqual(room.active_room_buff_total("speed", 5_000), 0.50)

    def test_buff_expires_after_timestamp(self):
        room = self._make_room()
        room.add_room_buff("damage", 0.50, expires_at=10_000)
        self.assertAlmostEqual(room.active_room_buff_total("damage", 9_999), 0.50)
        self.assertAlmostEqual(room.active_room_buff_total("damage", 10_001), 0.0)

    def test_prune_drops_expired_entries(self):
        room = self._make_room()
        room.add_room_buff("damage", 0.50, expires_at=10_000)
        room.add_room_buff("speed", 0.10, expires_at=None)
        room.prune_expired_room_buffs(10_001)
        self.assertEqual(len(room._room_buffs), 1)
        self.assertEqual(room._room_buffs[0]["stat"], "speed")

    def test_reset_clears_buffs_and_timers(self):
        room = self._make_room()
        room.add_room_buff("damage", 1.0, expires_at=None)
        room._quicksand_drown_ms = 1234
        room._hazard_last_tick_ms = 5678
        room.reset_room_buffs()
        self.assertEqual(room._room_buffs, [])
        self.assertEqual(room._quicksand_drown_ms, 0)
        self.assertEqual(room._hazard_last_tick_ms, 0)


class CameraFogOfWarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_fog_of_war_skipped_when_radius_unset(self):
        from camera import Camera
        cam = Camera()
        surface = pygame.Surface((100, 100))
        surface.fill((20, 20, 20))
        room = type("R", (), {"vision_radius": None})()
        player = type("P", (), {"rect": pygame.Rect(50, 50, 16, 16)})()
        cam._draw_fog_of_war(surface, room, player)
        # Untouched: corner pixel still matches the fill colour.
        self.assertEqual(surface.get_at((0, 0))[:3], (20, 20, 20))

    def test_fog_of_war_darkens_corners_and_clears_center(self):
        from camera import Camera
        cam = Camera()
        surface = pygame.Surface((100, 100))
        surface.fill((20, 20, 20))
        room = type("R", (), {"vision_radius": 16})()
        player = type("P", (), {"rect": pygame.Rect(50, 50, 16, 16)})()
        cam._draw_fog_of_war(surface, room, player)
        # Corner is darkened (the fog overlay is opaque at radius edge).
        self.assertLess(sum(surface.get_at((0, 0))[:3]), 60)
        # Player centre stays bright (transparent hole over the fill).
        self.assertEqual(surface.get_at((50, 50))[:3], (20, 20, 20))


if __name__ == "__main__":
    unittest.main()
