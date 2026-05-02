"""Tests for the pit fall animation and respawn system.

Covers:
- apply_terrain_effects triggers the animation (not instant death) on PIT_TILE.
- thin-ice crack also triggers the animation instead of instant death.
- advance_pit_fall_animation drives all three phases correctly.
- _find_pit_respawn_pos never returns a PIT_TILE coordinate.
- _find_pit_respawn_pos prefers the tile the player stepped from.
- Respawn grants invincibility and applies the HP penalty without killing.
- Player is never placed on a pit when surrounded by many pit tiles.
"""
import os
import unittest

import pygame

import terrain_effects
from terrain_effects import advance_pit_fall_animation, _find_pit_respawn_pos
from player import Player
from room import FLOOR, WALL, PIT_TILE, THIN_ICE, ROOM_COLS, ROOM_ROWS
from settings import (
    TILE_SIZE,
    PIT_FALL_SLIDE_MS, PIT_FALL_SHRINK_MS, PIT_FALL_PAUSE_MS,
    PIT_FALL_ANIM_TOTAL_MS, PIT_FALL_RESPAWN_IFRAMES_MS, PIT_FALL_HP_PENALTY,
    THIN_ICE_STEPS_TO_CRACK,
)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.init()
pygame.display.set_mode((1, 1))


# ── helpers ─────────────────────────────────────────────────────────────────

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
    """Minimal room stand-in for terrain_effects tests."""

    def __init__(self, grid=None):
        self.grid = grid if grid is not None else _wall_border_grid()
        self._previous_player_tile = None
        self._water_entry_ticks = None
        self._thin_ice_step_counts = {}

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
        rects = []
        for r in range(ROOM_ROWS):
            for c in range(ROOM_COLS):
                if self.grid[r][c] == WALL:
                    rects.append(pygame.Rect(
                        c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE
                    ))
        return rects


def _make_player(col, row):
    p = Player(col * TILE_SIZE + TILE_SIZE // 2,
               row * TILE_SIZE + TILE_SIZE // 2)
    p._invincible_until = 0
    return p


def _run_terrain(player, room, now=1000, dt=16):
    return terrain_effects.apply_terrain_effects(player, room, now, dt)


# ── trigger tests ────────────────────────────────────────────────────────────

class TestPitFallTrigger(unittest.TestCase):

    def _pit_grid(self, pit_col=5, pit_row=5):
        grid = _wall_border_grid()
        grid[pit_row][pit_col] = PIT_TILE
        return grid, pit_col, pit_row

    def test_pit_tile_sets_falling_phase(self):
        grid, pc, pr = self._pit_grid()
        room = _StubRoom(grid)
        player = _make_player(pc, pr)
        _run_terrain(player, room)
        self.assertEqual(player._pit_fall_phase, "falling")

    def test_pit_tile_sets_pit_fall_triggered_diag(self):
        grid, pc, pr = self._pit_grid()
        room = _StubRoom(grid)
        player = _make_player(pc, pr)
        diag = _run_terrain(player, room)
        self.assertTrue(diag["pit_fall_triggered"])

    def test_pit_tile_does_not_kill_player(self):
        grid, pc, pr = self._pit_grid()
        room = _StubRoom(grid)
        player = _make_player(pc, pr)
        _run_terrain(player, room)
        self.assertGreater(player.current_hp, 0)

    def test_pit_fall_blocks_further_damage_via_iframes(self):
        """_invincible_until should be set to at least the animation total."""
        grid, pc, pr = self._pit_grid()
        room = _StubRoom(grid)
        player = _make_player(pc, pr)
        now = 5000
        _run_terrain(player, room, now=now)
        self.assertGreaterEqual(player._invincible_until, now + PIT_FALL_ANIM_TOTAL_MS)

    def test_pit_fall_not_triggered_when_already_invincible(self):
        """Invincible players (dodge i-frames etc.) skip the trigger."""
        grid, pc, pr = self._pit_grid()
        room = _StubRoom(grid)
        player = _make_player(pc, pr)
        player._invincible_until = 10 ** 9   # invincible
        _run_terrain(player, room)
        self.assertIsNone(player._pit_fall_phase)

    def test_pit_fall_not_re_triggered_when_already_falling(self):
        """Second call while animation is active does not restart the state."""
        grid, pc, pr = self._pit_grid()
        room = _StubRoom(grid)
        player = _make_player(pc, pr)
        _run_terrain(player, room, now=1000)
        original_started_at = player._pit_fall_started_at
        # Second frame — still on the pit tile
        _run_terrain(player, room, now=1016)
        self.assertEqual(player._pit_fall_started_at, original_started_at)

    def test_thin_ice_crack_triggers_fall_not_death(self):
        """Cracking through thin ice starts the fall animation."""
        grid = _wall_border_grid()
        grid[5][5] = THIN_ICE
        room = _StubRoom(grid)
        player = _make_player(5, 5)
        # Step on the same thin-ice tile THIN_ICE_STEPS_TO_CRACK times.
        for i in range(THIN_ICE_STEPS_TO_CRACK - 1):
            # Simulate stepping from a fresh adjacent tile to tile (5,5)
            room._previous_player_tile = (5, 4)
            room._thin_ice_step_counts[(5, 5)] = i
            # Move slightly so stepped_to_new_tile fires
            player.rect.center = (5 * TILE_SIZE + TILE_SIZE // 2,
                                  5 * TILE_SIZE + TILE_SIZE // 2)
            _run_terrain(player, room, now=1000 + i * 100)
        # Final step — should crack and trigger animation
        room._previous_player_tile = (5, 4)
        room._thin_ice_step_counts[(5, 5)] = THIN_ICE_STEPS_TO_CRACK - 1
        diag = _run_terrain(player, room, now=5000)
        self.assertTrue(diag["thin_ice_cracked"])
        self.assertEqual(player._pit_fall_phase, "falling")
        self.assertGreater(player.current_hp, 0)


# ── animation phase tests ────────────────────────────────────────────────────

class TestAdvancePitFallAnimation(unittest.TestCase):

    def _make_falling_player(self, pit_col=5, pit_row=5, start_col=5, start_row=4,
                              now=1000):
        """Build a player already in the 'falling' phase."""
        grid = _wall_border_grid()
        grid[pit_row][pit_col] = PIT_TILE
        room = _StubRoom(grid)
        player = _make_player(start_col, start_row)
        _run_terrain(player, room, now=now)
        # Ensure phase triggered
        player._pit_fall_phase = "falling"
        player._pit_fall_started_at = now
        player._pit_fall_pit_col = pit_col
        player._pit_fall_pit_row = pit_row
        player._pit_fall_start_x = start_col * TILE_SIZE + TILE_SIZE // 2
        player._pit_fall_start_y = start_row * TILE_SIZE + TILE_SIZE // 2
        player._pit_entry_col = start_col
        player._pit_entry_row = start_row
        return player, room

    def test_falling_phase_returns_true(self):
        player, room = self._make_falling_player()
        result = advance_pit_fall_animation(player, room, 1050)
        self.assertTrue(result)

    def test_falling_phase_moves_player_toward_pit_center(self):
        player, room = self._make_falling_player(
            pit_col=5, pit_row=5, start_col=5, start_row=4, now=1000
        )
        pit_cx = 5 * TILE_SIZE + TILE_SIZE // 2
        pit_cy = 5 * TILE_SIZE + TILE_SIZE // 2
        start_cy = player._pit_fall_start_y
        # Advance halfway through the slide
        advance_pit_fall_animation(player, room, 1000 + PIT_FALL_SLIDE_MS // 2)
        # Center-y should be between start and pit center
        self.assertGreater(player.rect.centery, start_cy)
        self.assertLess(player.rect.centery, pit_cy)

    def test_falling_transitions_to_shrinking_after_slide_ms(self):
        player, room = self._make_falling_player(now=1000)
        advance_pit_fall_animation(player, room, 1000 + PIT_FALL_SLIDE_MS)
        self.assertEqual(player._pit_fall_phase, "shrinking")

    def test_shrinking_phase_updates_shrink_t(self):
        player, room = self._make_falling_player(now=1000)
        # Jump to shrinking
        advance_pit_fall_animation(player, room, 1000 + PIT_FALL_SLIDE_MS)
        shrink_start = player._pit_fall_started_at
        # Advance halfway through shrink
        advance_pit_fall_animation(
            player, room, shrink_start + PIT_FALL_SHRINK_MS // 2
        )
        self.assertGreater(player._pit_fall_shrink_t, 0.0)
        self.assertLess(player._pit_fall_shrink_t, 1.0)

    def test_shrinking_transitions_to_pause_after_shrink_ms(self):
        player, room = self._make_falling_player(now=1000)
        advance_pit_fall_animation(player, room, 1000 + PIT_FALL_SLIDE_MS)
        shrink_start = player._pit_fall_started_at
        advance_pit_fall_animation(player, room, shrink_start + PIT_FALL_SHRINK_MS)
        self.assertEqual(player._pit_fall_phase, "pause")
        self.assertAlmostEqual(player._pit_fall_shrink_t, 1.0)

    def test_pause_phase_completes_and_resets_to_none(self):
        player, room = self._make_falling_player(now=1000)
        # Drive through all phases
        advance_pit_fall_animation(player, room, 1000 + PIT_FALL_SLIDE_MS)
        shrink_start = player._pit_fall_started_at
        advance_pit_fall_animation(player, room, shrink_start + PIT_FALL_SHRINK_MS)
        pause_start = player._pit_fall_started_at
        advance_pit_fall_animation(player, room, pause_start + PIT_FALL_PAUSE_MS)
        self.assertIsNone(player._pit_fall_phase)

    def test_animation_returns_false_after_completion(self):
        player, room = self._make_falling_player(now=1000)
        advance_pit_fall_animation(player, room, 1000 + PIT_FALL_SLIDE_MS)
        shrink_start = player._pit_fall_started_at
        advance_pit_fall_animation(player, room, shrink_start + PIT_FALL_SHRINK_MS)
        pause_start = player._pit_fall_started_at
        result = advance_pit_fall_animation(
            player, room, pause_start + PIT_FALL_PAUSE_MS
        )
        self.assertFalse(result)

    def test_no_op_when_phase_is_none(self):
        grid = _wall_border_grid()
        room = _StubRoom(grid)
        player = _make_player(5, 5)
        result = advance_pit_fall_animation(player, room, 1000)
        self.assertFalse(result)


# ── respawn safety tests ─────────────────────────────────────────────────────

class TestPitRespawnPosition(unittest.TestCase):

    def _player_at_pit(self, pit_col, pit_row, entry_col, entry_row):
        """Return a player whose fall fields point at the given pit."""
        player = _make_player(pit_col, pit_row)
        player._pit_fall_phase = "pause"  # just before respawn
        player._pit_fall_pit_col = pit_col
        player._pit_fall_pit_row = pit_row
        player._pit_entry_col = entry_col
        player._pit_entry_row = entry_row
        return player

    def test_respawn_pos_is_never_a_pit_tile(self):
        """Even when surrounded by pits, respawn never lands on a PIT_TILE."""
        # Build a 3×3 pit cluster in the centre; entry tile is also a pit.
        grid = _wall_border_grid()
        pit_col, pit_row = 7, 7
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                grid[pit_row + dr][pit_col + dc] = PIT_TILE
        room = _StubRoom(grid)
        player = self._player_at_pit(pit_col, pit_row,
                                     entry_col=pit_col, entry_row=pit_row - 1)
        rc, rr = _find_pit_respawn_pos(player, room)
        self.assertNotEqual(room.tile_at(rc, rr), PIT_TILE)

    def test_respawn_pos_is_never_a_pit_when_entry_tile_is_also_pit(self):
        """Entry tile itself is a pit — BFS must find a safe neighbour."""
        grid = _wall_border_grid()
        # Pit at (5,5) and (5,4) — entry tile is also a pit.
        grid[5][5] = PIT_TILE
        grid[4][5] = PIT_TILE
        room = _StubRoom(grid)
        player = self._player_at_pit(5, 5, entry_col=5, entry_row=4)
        rc, rr = _find_pit_respawn_pos(player, room)
        self.assertNotEqual(room.tile_at(rc, rr), PIT_TILE)

    def test_respawn_prefers_entry_tile_when_valid(self):
        """When the entry tile is clear floor the player respawns there."""
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        room = _StubRoom(grid)
        player = self._player_at_pit(5, 5, entry_col=5, entry_row=4)
        rc, rr = _find_pit_respawn_pos(player, room)
        self.assertEqual((rc, rr), (5, 4))

    def test_respawn_pos_never_on_wall(self):
        """BFS never returns a WALL tile."""
        grid = _wall_border_grid()
        # Pit in corner adjacent to the border wall
        grid[1][1] = PIT_TILE
        room = _StubRoom(grid)
        player = self._player_at_pit(1, 1, entry_col=1, entry_row=0)  # wall row
        rc, rr = _find_pit_respawn_pos(player, room)
        self.assertNotEqual(room.tile_at(rc, rr), WALL)
        self.assertNotEqual(room.tile_at(rc, rr), PIT_TILE)

    def test_respawn_pos_never_on_thin_ice(self):
        """Respawn avoids THIN_ICE to prevent immediate re-trigger."""
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        grid[4][5] = THIN_ICE   # entry tile is thin ice
        room = _StubRoom(grid)
        player = self._player_at_pit(5, 5, entry_col=5, entry_row=4)
        rc, rr = _find_pit_respawn_pos(player, room)
        self.assertNotEqual(room.tile_at(rc, rr), THIN_ICE)
        self.assertNotEqual(room.tile_at(rc, rr), PIT_TILE)

    def test_full_animation_respawn_not_on_pit(self):
        """Drive the full animation to completion and check the final position."""
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        room = _StubRoom(grid)
        player = _make_player(5, 4)
        # Arm the animation manually (player steps from (5,4) onto (5,5)).
        player._pit_fall_phase = "falling"
        player._pit_fall_started_at = 1000
        player._pit_fall_pit_col = 5
        player._pit_fall_pit_row = 5
        player._pit_fall_start_x = 5 * TILE_SIZE + TILE_SIZE // 2
        player._pit_fall_start_y = 4 * TILE_SIZE + TILE_SIZE // 2
        player._pit_entry_col = 5
        player._pit_entry_row = 4
        player._pit_fall_shrink_t = 0.0
        player._invincible_until = 1000 + PIT_FALL_ANIM_TOTAL_MS

        # Drive through all three phases.
        advance_pit_fall_animation(player, room, 1000 + PIT_FALL_SLIDE_MS)
        shrink_start = player._pit_fall_started_at
        advance_pit_fall_animation(player, room, shrink_start + PIT_FALL_SHRINK_MS)
        pause_start = player._pit_fall_started_at
        advance_pit_fall_animation(player, room, pause_start + PIT_FALL_PAUSE_MS)

        self.assertIsNone(player._pit_fall_phase)
        col = player.rect.centerx // TILE_SIZE
        row = player.rect.centery // TILE_SIZE
        self.assertNotEqual(room.tile_at(col, row), PIT_TILE)


# ── respawn consequence tests ────────────────────────────────────────────────

class TestPitRespawnConsequences(unittest.TestCase):

    def _drive_to_respawn(self, player, room, start_ticks=1000):
        """Run the animation to completion and return the final tick."""
        advance_pit_fall_animation(player, room, start_ticks + PIT_FALL_SLIDE_MS)
        t2 = player._pit_fall_started_at
        advance_pit_fall_animation(player, room, t2 + PIT_FALL_SHRINK_MS)
        t3 = player._pit_fall_started_at
        advance_pit_fall_animation(player, room, t3 + PIT_FALL_PAUSE_MS)
        return t3 + PIT_FALL_PAUSE_MS

    def _arm_player(self, player, pit_col=5, pit_row=5, entry_col=5, entry_row=4,
                    now=1000):
        player._pit_fall_phase = "falling"
        player._pit_fall_started_at = now
        player._pit_fall_pit_col = pit_col
        player._pit_fall_pit_row = pit_row
        player._pit_fall_start_x = entry_col * TILE_SIZE + TILE_SIZE // 2
        player._pit_fall_start_y = entry_row * TILE_SIZE + TILE_SIZE // 2
        player._pit_entry_col = entry_col
        player._pit_entry_row = entry_row
        player._pit_fall_shrink_t = 0.0
        player._invincible_until = now + PIT_FALL_ANIM_TOTAL_MS

    def test_respawn_grants_invincibility(self):
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        room = _StubRoom(grid)
        player = _make_player(5, 4)
        self._arm_player(player, now=1000)
        end_ticks = self._drive_to_respawn(player, room, start_ticks=1000)
        self.assertGreater(player._invincible_until, end_ticks)

    def test_respawn_iframes_at_least_respawn_duration(self):
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        room = _StubRoom(grid)
        player = _make_player(5, 4)
        self._arm_player(player, now=1000)
        end_ticks = self._drive_to_respawn(player, room, start_ticks=1000)
        self.assertGreaterEqual(
            player._invincible_until, end_ticks + PIT_FALL_RESPAWN_IFRAMES_MS - 1
        )

    def test_respawn_applies_hp_penalty(self):
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        room = _StubRoom(grid)
        player = _make_player(5, 4)
        hp_before = player.current_hp
        self._arm_player(player, now=1000)
        self._drive_to_respawn(player, room, start_ticks=1000)
        self.assertLess(player.current_hp, hp_before)

    def test_respawn_never_kills_player(self):
        """HP penalty must leave the player at >= 1 HP even at minimum health."""
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        room = _StubRoom(grid)
        player = _make_player(5, 4)
        player.current_hp = 1   # already at minimum
        self._arm_player(player, now=1000)
        self._drive_to_respawn(player, room, start_ticks=1000)
        self.assertGreaterEqual(player.current_hp, 1)

    def test_respawn_clears_shrink_t(self):
        grid = _wall_border_grid()
        grid[5][5] = PIT_TILE
        room = _StubRoom(grid)
        player = _make_player(5, 4)
        self._arm_player(player, now=1000)
        self._drive_to_respawn(player, room, start_ticks=1000)
        self.assertAlmostEqual(player._pit_fall_shrink_t, 0.0)


if __name__ == "__main__":
    unittest.main()
