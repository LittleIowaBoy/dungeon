"""Tests for terrain_layouts.py — Phase 2.

Verifies each pattern function:
  - Runs without error on a minimal 15×20 floor grid with all 4 doors open.
  - Does not corrupt wall tiles.
  - Leaves all door buffer cells as _FLOOR.
  - Preserves connectivity between all open door entries (covers RUBBLE-placing
    patterns; walkable-hazard patterns are inherently connected).
  - Does not import ROOM_ROWS or ROOM_COLS (lint guard — AST scan).
"""
import ast
import os
import random
import sys
import unittest

# Ensure the project root is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import terrain_layouts as tl

ROOM_ROWS = 15
ROOM_COLS = 20
_FLOOR = tl._FLOOR
_WALL  = tl._WALL

ALL_DOORS = {"top": True, "bottom": True, "left": True, "right": True}
LAYOUT_IDS = list(tl.LAYOUT_REGISTRY.keys())


def _make_grid():
    """Return a fresh 15×20 grid with outer walls and inner floor."""
    grid = [[_FLOOR] * ROOM_COLS for _ in range(ROOM_ROWS)]
    for c in range(ROOM_COLS):
        grid[0][c] = _WALL
        grid[ROOM_ROWS - 1][c] = _WALL
    for r in range(ROOM_ROWS):
        grid[r][0] = _WALL
        grid[r][ROOM_COLS - 1] = _WALL
    return grid


def _apply(layout_id, doors=None, biome_terrain="", density=1.0, seed=42):
    """Apply layout to a fresh grid and return it."""
    if doors is None:
        doors = ALL_DOORS
    grid = _make_grid()
    rng = random.Random(seed)
    tl.apply(layout_id, grid, doors, biome_terrain, rng, density)
    return grid


class TestLintGuard(unittest.TestCase):
    """terrain_layouts.py must never import ROOM_ROWS or ROOM_COLS."""

    def test_no_room_dimension_imports(self):
        src_path = os.path.join(os.path.dirname(__file__), "..", "terrain_layouts.py")
        with open(src_path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        forbidden = {"ROOM_ROWS", "ROOM_COLS"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    self.assertNotIn(
                        alias.name, forbidden,
                        f"terrain_layouts.py must not import {alias.name}",
                    )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, forbidden)


class TestRegistryCompleteness(unittest.TestCase):
    def test_all_ids_have_fn(self):
        for lid, spec in tl.LAYOUT_REGISTRY.items():
            self.assertIsNotNone(spec.fn, f"{lid} has no fn")
            self.assertTrue(callable(spec.fn), f"{lid} fn not callable")

    def test_19_entries(self):
        self.assertEqual(len(tl.LAYOUT_REGISTRY), 19)

    def test_all_families_set(self):
        for lid, spec in tl.LAYOUT_REGISTRY.items():
            self.assertTrue(spec.family, f"{lid} missing family")


class TestWallIntegrity(unittest.TestCase):
    """No layout should modify outer-wall tiles."""

    def test_walls_intact(self):
        for lid in LAYOUT_IDS:
            with self.subTest(layout=lid):
                grid = _apply(lid)
                for c in range(ROOM_COLS):
                    self.assertEqual(grid[0][c], _WALL, f"{lid}: top wall [0][{c}]")
                    self.assertEqual(grid[ROOM_ROWS - 1][c], _WALL,
                                     f"{lid}: bottom wall [{ROOM_ROWS-1}][{c}]")
                for r in range(ROOM_ROWS):
                    self.assertEqual(grid[r][0], _WALL, f"{lid}: left wall [{r}][0]")
                    self.assertEqual(grid[r][ROOM_COLS - 1], _WALL,
                                     f"{lid}: right wall [{r}][{ROOM_COLS-1}]")


class TestDoorBufferRespected(unittest.TestCase):
    """Interior cells within radius 2 of each open door must remain _FLOOR."""

    def test_buffer_clear(self):
        buf = tl._door_buffer_mask(_make_grid(), ALL_DOORS, radius=2)
        for lid in LAYOUT_IDS:
            with self.subTest(layout=lid):
                grid = _apply(lid)
                for col, row in buf:
                    # Skip outer-wall positions — they are _WALL by design.
                    if row in (0, ROOM_ROWS - 1) or col in (0, ROOM_COLS - 1):
                        continue
                    tile = grid[row][col]
                    self.assertEqual(
                        tile, _FLOOR,
                        f"{lid}: buffer cell ({col},{row}) = {tile!r}, expected floor",
                    )


class TestConnectivity(unittest.TestCase):
    """All door entries must remain mutually reachable on floor tiles."""

    def test_all_doors_connected(self):
        for lid in LAYOUT_IDS:
            with self.subTest(layout=lid):
                grid = _apply(lid)
                self.assertTrue(
                    tl._bfs_connectivity_check(grid, ALL_DOORS),
                    f"{lid}: door entries not all connected",
                )

    def test_two_doors(self):
        two_doors = {"top": True, "bottom": True, "left": False, "right": False}
        for lid in LAYOUT_IDS:
            spec = tl.LAYOUT_REGISTRY[lid]
            if 2 not in spec.supported_door_counts:
                continue
            with self.subTest(layout=lid):
                grid = _apply(lid, doors=two_doors)
                self.assertTrue(
                    tl._bfs_connectivity_check(grid, two_doors),
                    f"{lid} (2 doors): entries not connected",
                )


class TestBiomeVariants(unittest.TestCase):
    """All patterns must run without error for each biome_terrain value."""

    def test_biome_variants(self):
        for biome in ("", "mud", "ice", "water"):
            for lid in LAYOUT_IDS:
                with self.subTest(layout=lid, biome=biome):
                    try:
                        _apply(lid, biome_terrain=biome)
                    except Exception as exc:
                        self.fail(f"{lid} biome={biome!r} raised {exc!r}")


class TestDensityRange(unittest.TestCase):
    """Patterns must not raise for low (0.5) or high (2.0) density."""

    def test_density_extremes(self):
        for lid in LAYOUT_IDS:
            for density in (0.5, 2.0):
                with self.subTest(layout=lid, density=density):
                    try:
                        _apply(lid, density=density)
                    except Exception as exc:
                        self.fail(f"{lid} density={density} raised {exc!r}")


class TestHelpersDirectly(unittest.TestCase):
    def test_door_tile_set_all_open(self):
        grid = _make_grid()
        tiles = tl._door_tile_set(grid, ALL_DOORS)
        # expect 12 door tile positions (4 doors × 3 tiles each)
        self.assertEqual(len(tiles), 12)

    def test_door_tile_set_no_doors(self):
        grid = _make_grid()
        tiles = tl._door_tile_set(grid, {"top": False, "bottom": False, "left": False, "right": False})
        self.assertEqual(len(tiles), 0)

    def test_bfs_path_trivial(self):
        grid = _make_grid()
        result = tl._bfs_path(grid, (1, 1), (1, 1))
        self.assertEqual(result, [(1, 1)])

    def test_bfs_path_unreachable(self):
        grid = _make_grid()
        # Wall off a cell.
        for c in range(ROOM_COLS):
            grid[7][c] = _WALL
        result = tl._bfs_path(grid, (1, 1), (1, 12))
        self.assertIsNone(result)

    def test_density_for_depth(self):
        self.assertAlmostEqual(tl._density_for_depth(0, 10), 0.5)
        self.assertAlmostEqual(tl._density_for_depth(10, 10), 2.0)
        self.assertAlmostEqual(tl._density_for_depth(0, 0), 1.0)

    def test_ensure_connectivity_carves(self):
        grid = _make_grid()
        doors = {"top": True, "bottom": True, "left": False, "right": False}
        # Fill rows 3..11 with RUBBLE — completely blocks top half from bottom.
        # Rows 1-2 and 12-13 (entry zones) remain floor.
        for r in range(3, 12):
            for c in range(2, ROOM_COLS - 2):
                grid[r][c] = tl._RUBBLE
        tl._ensure_connectivity(grid, doors)
        # After the carve, door entries must be game-connected.
        self.assertTrue(tl._bfs_connectivity_check(grid, doors))


class TestTerrainLayoutForPlan(unittest.TestCase):
    def test_returns_valid_id_no_plan(self):
        rng = random.Random(0)
        lid = tl.terrain_layout_for_plan(None, rng)
        self.assertIn(lid, tl.LAYOUT_REGISTRY)

    def test_honours_plan_terrain_layout(self):
        class FakePlan:
            terrain_layout = "column_hall_grid"
        rng = random.Random(0)
        lid = tl.terrain_layout_for_plan(FakePlan(), rng)
        self.assertEqual(lid, "column_hall_grid")

    def test_biome_weighted(self):
        class FakePlan:
            terrain_layout = ""
        rng = random.Random(0)
        counts = {}
        for _ in range(200):
            lid = tl.terrain_layout_for_plan(FakePlan(), rng, biome_terrain="mud")
            counts[lid] = counts.get(lid, 0) + 1
        # mire_carpet has affinity 9 for mud — should be among top selections
        self.assertGreater(counts.get("mire_carpet", 0), 0)


if __name__ == "__main__":
    unittest.main()
