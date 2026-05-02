"""Tests for thin-ice progressive cracking and timed respawn.

Covers:
- crack stage 0 on an untouched tile
- crack stage increments with each step
- tile collapses to PIT_TILE at THIN_ICE_STEPS_TO_CRACK steps
- crack timestamp is recorded when tile collapses
- advance_thin_ice_respawn does NOT restore tile before timeout
- advance_thin_ice_respawn restores tile after THIN_ICE_RESPAWN_MS
- step count is cleared on respawn (tile starts fresh)
- restored tile can be cracked again
- thin_ice_crack_stage returns 0 for tiles with no step count data
"""
import os
import unittest

import pygame

import terrain_effects
from terrain_effects import (
    advance_thin_ice_respawn,
    thin_ice_crack_stage,
)
from player import Player
from room import FLOOR, WALL, PIT_TILE, THIN_ICE, ROOM_COLS, ROOM_ROWS
from settings import (
    TILE_SIZE,
    THIN_ICE_STEPS_TO_CRACK,
    THIN_ICE_RESPAWN_MS,
)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.init()
pygame.display.set_mode((1, 1))


# ── helpers ──────────────────────────────────────────────────────────────────

def _empty_grid():
    return [[FLOOR for _ in range(ROOM_COLS)] for _ in range(ROOM_ROWS)]


class _StubRoom:
    """Minimal room stand-in for terrain_effects tests."""

    def __init__(self, grid=None):
        self.grid = grid if grid is not None else _empty_grid()
        self._previous_player_tile = None
        self._water_entry_ticks = None
        self._thin_ice_step_counts = {}
        self._thin_ice_crack_times = {}

    def tile_at(self, col, row):
        if 0 <= col < ROOM_COLS and 0 <= row < ROOM_ROWS:
            return self.grid[row][col]
        return WALL

    def terrain_at_pixel(self, px, py):
        col = int(px) // TILE_SIZE
        row = int(py) // TILE_SIZE
        return self.tile_at(col, row)

    def current_vector_at_pixel(self, px, py):
        return None

    def get_wall_rects(self):
        return []


def _make_player(col, row):
    p = Player(col * TILE_SIZE + TILE_SIZE // 2,
               row * TILE_SIZE + TILE_SIZE // 2)
    p._invincible_until = 0
    return p


def _run_terrain(player, room, now=1000, dt=16):
    return terrain_effects.apply_terrain_effects(player, room, now, dt)


def _ice_room(ice_col=5, ice_row=5):
    """Build a room with a single THIN_ICE tile at (ice_col, ice_row)."""
    grid = _empty_grid()
    grid[ice_row][ice_col] = THIN_ICE
    return _StubRoom(grid)


def _step_player_onto(room, col, row, now=1000):
    """Place a fresh player on the tile and run terrain effects once.

    Sets ``room._previous_player_tile`` to an adjacent coordinate so the
    ``stepped_to_new_tile`` guard in terrain_effects fires correctly.
    """
    player = _make_player(col, row)
    # Simulate arriving from the tile above so the step guard is satisfied.
    room._previous_player_tile = (col, max(0, row - 1)) if row > 0 else (col, row + 1)
    return player, _run_terrain(player, room, now=now)


def _fully_crack(room, col, row, start_now=1000):
    """Step a new player onto THIN_ICE tile THIN_ICE_STEPS_TO_CRACK times.

    Each step uses a fresh player so the 'new tile' guard fires every time.
    Returns the tick value used for the final cracking step.
    """
    now = start_now
    for _ in range(THIN_ICE_STEPS_TO_CRACK):
        player, _ = _step_player_onto(room, col, row, now=now)
        now += 100
    return now - 100  # tick of the final (collapsing) step


# ── crack stage tests ─────────────────────────────────────────────────────────

class TestThinIceCrackStage(unittest.TestCase):

    def test_untouched_tile_returns_zero(self):
        room = _ice_room()
        self.assertEqual(thin_ice_crack_stage(room, 5, 5), 0)

    def test_returns_zero_if_no_step_count_attr(self):
        room = _ice_room()
        del room._thin_ice_step_counts  # simulate missing attribute
        self.assertEqual(thin_ice_crack_stage(room, 5, 5), 0)

    def test_stage_increments_after_first_step(self):
        room = _ice_room(5, 5)
        _step_player_onto(room, 5, 5)
        self.assertEqual(thin_ice_crack_stage(room, 5, 5), 1)

    def test_stage_increments_to_two_on_second_step(self):
        room = _ice_room(5, 5)
        _step_player_onto(room, 5, 5, now=1000)
        _step_player_onto(room, 5, 5, now=1100)
        self.assertEqual(thin_ice_crack_stage(room, 5, 5), 2)

    def test_adjacent_tile_stage_unaffected(self):
        room = _ice_room(5, 5)
        grid = room.grid
        grid[5][6] = THIN_ICE  # second ice tile adjacent
        _step_player_onto(room, 5, 5)
        self.assertEqual(thin_ice_crack_stage(room, 6, 5), 0)


# ── collapse tests ────────────────────────────────────────────────────────────

class TestThinIceCollapse(unittest.TestCase):

    def test_tile_becomes_pit_at_crack_limit(self):
        room = _ice_room(5, 5)
        _fully_crack(room, 5, 5)
        self.assertEqual(room.grid[5][5], PIT_TILE)

    def test_crack_time_recorded_on_collapse(self):
        room = _ice_room(5, 5)
        crack_tick = _fully_crack(room, 5, 5)
        self.assertIn((5, 5), room._thin_ice_crack_times)
        # The recorded tick should be at or after the collapse step tick.
        self.assertGreaterEqual(room._thin_ice_crack_times[(5, 5)], crack_tick)

    def test_diag_thin_ice_cracked_set_on_final_step(self):
        room = _ice_room(5, 5)
        # Step up to the penultimate count manually.
        for _ in range(THIN_ICE_STEPS_TO_CRACK - 1):
            _step_player_onto(room, 5, 5)
        # Final step should crack it.
        _, diag = _step_player_onto(room, 5, 5)
        self.assertTrue(diag.get("thin_ice_cracked"))

    def test_no_crack_time_before_collapse(self):
        room = _ice_room(5, 5)
        _step_player_onto(room, 5, 5)  # only 1 step, not yet collapsed
        self.assertNotIn((5, 5), room._thin_ice_crack_times)


# ── respawn tests ─────────────────────────────────────────────────────────────

class TestThinIceRespawn(unittest.TestCase):

    def test_no_respawn_before_timeout(self):
        room = _ice_room(5, 5)
        collapse_tick = 1000
        _fully_crack(room, 5, 5, start_now=collapse_tick)
        # Check just before the timeout.
        advance_thin_ice_respawn(room, collapse_tick + THIN_ICE_RESPAWN_MS - 1)
        self.assertEqual(room.grid[5][5], PIT_TILE)

    def test_respawn_at_exact_timeout(self):
        room = _ice_room(5, 5)
        collapse_tick = 1000
        _fully_crack(room, 5, 5, start_now=collapse_tick)
        # Advance to exactly the timeout boundary.
        advance_thin_ice_respawn(
            room, room._thin_ice_crack_times[(5, 5)] + THIN_ICE_RESPAWN_MS
        )
        self.assertEqual(room.grid[5][5], THIN_ICE)

    def test_respawn_after_timeout(self):
        room = _ice_room(5, 5)
        collapse_tick = 5000
        _fully_crack(room, 5, 5, start_now=collapse_tick)
        cracked_at = room._thin_ice_crack_times[(5, 5)]
        advance_thin_ice_respawn(room, cracked_at + THIN_ICE_RESPAWN_MS + 5000)
        self.assertEqual(room.grid[5][5], THIN_ICE)

    def test_crack_time_entry_removed_after_respawn(self):
        room = _ice_room(5, 5)
        _fully_crack(room, 5, 5)
        cracked_at = room._thin_ice_crack_times[(5, 5)]
        advance_thin_ice_respawn(room, cracked_at + THIN_ICE_RESPAWN_MS)
        self.assertNotIn((5, 5), room._thin_ice_crack_times)

    def test_step_count_cleared_after_respawn(self):
        room = _ice_room(5, 5)
        _fully_crack(room, 5, 5)
        cracked_at = room._thin_ice_crack_times[(5, 5)]
        advance_thin_ice_respawn(room, cracked_at + THIN_ICE_RESPAWN_MS)
        self.assertEqual(room._thin_ice_step_counts.get((5, 5), 0), 0)

    def test_crack_stage_zero_after_respawn(self):
        room = _ice_room(5, 5)
        _fully_crack(room, 5, 5)
        cracked_at = room._thin_ice_crack_times[(5, 5)]
        advance_thin_ice_respawn(room, cracked_at + THIN_ICE_RESPAWN_MS)
        self.assertEqual(thin_ice_crack_stage(room, 5, 5), 0)

    def test_noop_on_room_with_no_crack_times(self):
        room = _ice_room(5, 5)
        # Never cracked – should not raise.
        advance_thin_ice_respawn(room, 99999)
        self.assertEqual(room.grid[5][5], THIN_ICE)

    # ── re-cracking after respawn ─────────────────────────────────────────

    def test_respawned_tile_can_be_cracked_again(self):
        room = _ice_room(5, 5)
        # First crack cycle.
        _fully_crack(room, 5, 5, start_now=1000)
        cracked_at = room._thin_ice_crack_times[(5, 5)]
        advance_thin_ice_respawn(room, cracked_at + THIN_ICE_RESPAWN_MS)
        self.assertEqual(room.grid[5][5], THIN_ICE)

        # Second crack cycle – step up to the penultimate count.
        for _ in range(THIN_ICE_STEPS_TO_CRACK - 1):
            _step_player_onto(room, 5, 5)
        self.assertEqual(thin_ice_crack_stage(room, 5, 5), THIN_ICE_STEPS_TO_CRACK - 1)

        # Final step collapses it again.
        _, diag = _step_player_onto(room, 5, 5)
        self.assertTrue(diag.get("thin_ice_cracked"))
        self.assertEqual(room.grid[5][5], PIT_TILE)

    def test_multiple_tiles_respawn_independently(self):
        """Two adjacent thin-ice tiles should respawn at their own times."""
        room = _ice_room(5, 5)
        room.grid[5][6] = THIN_ICE  # second tile at (6, 5)

        _fully_crack(room, 5, 5, start_now=1000)
        cracked_at_55 = room._thin_ice_crack_times[(5, 5)]

        # Crack second tile later.
        _fully_crack(room, 6, 5, start_now=5000)
        cracked_at_65 = room._thin_ice_crack_times[(6, 5)]

        # Advance to just after first tile's timeout but before second's.
        mid_tick = cracked_at_55 + THIN_ICE_RESPAWN_MS + 100
        if mid_tick < cracked_at_65 + THIN_ICE_RESPAWN_MS:
            advance_thin_ice_respawn(room, mid_tick)
            self.assertEqual(room.grid[5][5], THIN_ICE)
            self.assertEqual(room.grid[5][6], PIT_TILE)

        # Advance past both.
        advance_thin_ice_respawn(room, cracked_at_65 + THIN_ICE_RESPAWN_MS + 1)
        self.assertEqual(room.grid[5][6], THIN_ICE)
