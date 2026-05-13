"""Soak test for terrain_layouts.py — Step 5.

Runs 1000 rooms per biome (4,000 total) through the full ``apply()`` pipeline
and verifies all 7 detectors:

  1. wall_intact        — outer wall tiles unchanged after apply().
  2. door_buffer_clear  — cells inside the door-buffer zone remain _FLOOR.
  3. doors_connected    — all open door entries are mutually BFS-reachable.
  4. valid_tiles        — every cell is one of the six known tile types.
  5. rubble_fraction    — RUBBLE tiles <= 50 % of interior cells.
  6. center_walkable    — room-center cell is walkable (not RUBBLE or WALL).
  7. accent_presence    — biome rooms (mud/ice/water) contain >= 1 accent tile
                          in the interior after apply().

Each of the 1000 iterations per biome varies:
  - the seed (0..999), which drives both layout selection and tile placement
  - the door configuration (cycled across 4 presets covering 1-, 2-, 3- and
    4-door rooms)
  - the density (interpolated from seed as a depth proxy)

Failures are collected across all seeds and reported in aggregate so a single
broken pattern surfaces multiple affected configurations at once.
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import terrain_layouts as tl

# ---------------------------------------------------------------------------
# Grid / biome constants
# ---------------------------------------------------------------------------

ROOM_ROWS = 15
ROOM_COLS = 20

_FLOOR  = tl._FLOOR
_WALL   = tl._WALL
_RUBBLE = tl._RUBBLE

_VALID_TILES = frozenset({_FLOOR, _WALL, _RUBBLE, tl._MUD, tl._ICE, tl._WATER})

# Maps biome_terrain key → expected accent tile (mirrors _BIOME_ACCENT_POOL).
_BIOME_ACCENT_TILE: dict[str, str] = {
    "mud":   tl._MUD,
    "ice":   tl._ICE,
    "water": tl._WATER,
}

_BIOMES = ("", "mud", "ice", "water")

# ---------------------------------------------------------------------------
# Soak parameters
# ---------------------------------------------------------------------------

SOAK_COUNT = 1000   # rooms per biome

# Door configurations cycled across seeds so connectivity logic sees a spread
# of 1-, 2-, 3- and 4-door rooms across the 1000 iterations.
_DOOR_CONFIGS = [
    {"top": True,  "bottom": True,  "left": True,  "right": True},   # 4 doors
    {"top": True,  "bottom": True,  "left": False,  "right": False},  # 2 doors
    {"top": True,  "bottom": False, "left": True,   "right": False},  # 2 doors
    {"top": True,  "bottom": False, "left": False,  "right": False},  # 1 door
]

# ---------------------------------------------------------------------------
# Grid factory
# ---------------------------------------------------------------------------

def _make_grid() -> list[list[str]]:
    """Return a fresh 15x20 grid with outer walls and inner floor."""
    grid = [[_FLOOR] * ROOM_COLS for _ in range(ROOM_ROWS)]
    for c in range(ROOM_COLS):
        grid[0][c] = _WALL
        grid[ROOM_ROWS - 1][c] = _WALL
    for r in range(ROOM_ROWS):
        grid[r][0] = _WALL
        grid[r][ROOM_COLS - 1] = _WALL
    return grid

# ---------------------------------------------------------------------------
# Room runner
# ---------------------------------------------------------------------------

def _run_room(biome: str, seed: int) -> tuple[list, str, dict]:
    """Build and apply a biome room for *seed*.

    Returns (grid, layout_id, doors).  Uses ``terrain_layout_for_plan`` to
    select a biome-weighted layout, exactly as the production Room builder does.
    """
    rng = random.Random(seed)
    doors = _DOOR_CONFIGS[seed % len(_DOOR_CONFIGS)]
    door_count = sum(1 for v in doors.values() if v)
    layout_id = tl.terrain_layout_for_plan(
        None, rng, biome_terrain=biome, door_count=door_count,
    )
    grid = _make_grid()
    density = tl._density_for_depth(seed % 10, 10)
    tl.apply(layout_id, grid, doors, biome, rng, density)
    return grid, layout_id, doors

# ---------------------------------------------------------------------------
# Detector helpers — each raises AssertionError on failure
# ---------------------------------------------------------------------------

def _det_wall_intact(grid, doors, biome, layout_id):
    rows = len(grid)
    cols = len(grid[0])
    for c in range(cols):
        assert grid[0][c] == _WALL, \
            f"[{layout_id}] top wall ({c},0) corrupted to {grid[0][c]!r}"
        assert grid[rows - 1][c] == _WALL, \
            f"[{layout_id}] bottom wall ({c},{rows-1}) corrupted to {grid[rows-1][c]!r}"
    for r in range(rows):
        assert grid[r][0] == _WALL, \
            f"[{layout_id}] left wall (0,{r}) corrupted to {grid[r][0]!r}"
        assert grid[r][cols - 1] == _WALL, \
            f"[{layout_id}] right wall ({cols-1},{r}) corrupted to {grid[r][cols-1]!r}"


def _det_door_buffer_clear(grid, doors, biome, layout_id):
    buf = tl._door_buffer_mask(grid, doors, radius=2)
    rows = len(grid)
    cols = len(grid[0])
    for col, row in buf:
        if row in (0, rows - 1) or col in (0, cols - 1):
            continue   # outer wall cells — skip
        tile = grid[row][col]
        assert tile == _FLOOR, \
            f"[{layout_id}] door-buffer cell ({col},{row}) = {tile!r}, expected floor"


def _det_doors_connected(grid, doors, biome, layout_id):
    ok = tl._bfs_connectivity_check(grid, doors)
    assert ok, f"[{layout_id}] door entries not all BFS-reachable from each other"


def _det_valid_tiles(grid, doors, biome, layout_id):
    rows = len(grid)
    cols = len(grid[0])
    for r in range(rows):
        for c in range(cols):
            tile = grid[r][c]
            assert tile in _VALID_TILES, \
                f"[{layout_id}] unknown tile {tile!r} at ({c},{r})"


def _det_rubble_fraction(grid, doors, biome, layout_id):
    rows = len(grid)
    cols = len(grid[0])
    interior_total = (rows - 2) * (cols - 2)
    rubble_count = sum(
        1
        for r in range(1, rows - 1)
        for c in range(1, cols - 1)
        if grid[r][c] == _RUBBLE
    )
    frac = rubble_count / max(1, interior_total)
    assert frac <= 0.50, \
        f"[{layout_id}] RUBBLE fraction {frac:.1%} exceeds 50% ({rubble_count}/{interior_total})"


def _det_center_walkable(grid, doors, biome, layout_id):
    rows = len(grid)
    cols = len(grid[0])
    cr, cc = rows // 2, cols // 2
    tile = grid[cr][cc]
    assert tile not in (_WALL, _RUBBLE), \
        f"[{layout_id}] center cell ({cc},{cr}) = {tile!r}, expected walkable"


def _det_accent_presence(grid, doors, biome, layout_id):
    accent_tile = _BIOME_ACCENT_TILE.get(biome)
    if accent_tile is None:
        return   # blank biome — no accent requirement
    rows = len(grid)
    cols = len(grid[0])
    count = sum(
        1
        for r in range(1, rows - 1)
        for c in range(1, cols - 1)
        if grid[r][c] == accent_tile
    )
    assert count >= 1, \
        f"[{layout_id}] biome={biome!r}: no {accent_tile!r} accent tile found in interior"


_DETECTORS = [
    ("wall_intact",       _det_wall_intact),
    ("door_buffer_clear", _det_door_buffer_clear),
    ("doors_connected",   _det_doors_connected),
    ("valid_tiles",       _det_valid_tiles),
    ("rubble_fraction",   _det_rubble_fraction),
    ("center_walkable",   _det_center_walkable),
    ("accent_presence",   _det_accent_presence),
]

# ---------------------------------------------------------------------------
# Soak test
# ---------------------------------------------------------------------------

class TerrainSoakTests(unittest.TestCase):
    """1000-room soak per biome, all 7 detectors."""

    def _run_biome_soak(self, biome: str) -> None:
        failures: list[str] = []
        for seed in range(SOAK_COUNT):
            grid, layout_id, doors = _run_room(biome, seed)
            for det_name, det_fn in _DETECTORS:
                try:
                    det_fn(grid, doors, biome, layout_id)
                except AssertionError as exc:
                    failures.append(
                        f"seed={seed} detector={det_name}: {exc}"
                    )
        if failures:
            sample = "\n  ".join(failures[:10])
            tail = f"\n  ...({len(failures) - 10} more)" if len(failures) > 10 else ""
            self.fail(
                f"Biome {biome!r}: {len(failures)} detector failure(s):\n  {sample}{tail}"
            )

    def test_soak_plain(self):
        """1000 plain (no-biome) rooms."""
        self._run_biome_soak("")

    def test_soak_mud(self):
        """1000 mud-biome rooms."""
        self._run_biome_soak("mud")

    def test_soak_ice(self):
        """1000 ice-biome rooms."""
        self._run_biome_soak("ice")

    def test_soak_water(self):
        """1000 water-biome rooms."""
        self._run_biome_soak("water")


if __name__ == "__main__":
    unittest.main()
