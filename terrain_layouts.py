"""terrain_layouts.py — Terrain layout catalog and dispatcher.

Each layout is a named pattern function that writes hazard/cover tiles into
the room grid.  Phase 1 wires up the data structures and stubs; Phase 2
implements the pattern functions one-by-one.

Lint guard: this module must never import ROOM_ROWS or ROOM_COLS — all
pattern functions must derive room size from the grid argument.
The soak test verifies this via AST scan.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class LayoutSpec:
    """Descriptor for a single named terrain layout."""
    id: str
    family: str
    decision_type: str        # "lane"|"speed_safety"|"cover_los"|"mobility_tax"|"kiting"|"fusion"
    supported_door_counts: tuple[int, ...]  # e.g. (1, 2, 3, 4) or (1, 2)
    min_rows: int
    min_cols: int
    biome_affinities: dict[str, int]  # biome_terrain → weight (0-10); missing = 5
    fn: Callable              # pattern function reference


# ---------------------------------------------------------------------------
# Tile string constants (local copies to avoid circular import with room.py;
# must stay in sync with room.py tile definitions).
# ---------------------------------------------------------------------------
_FLOOR  = "floor"
_WALL      = "wall"
_RUBBLE    = "rubble"
_MUD       = "mud"
_ICE       = "ice"
_WATER     = "water"
_QUICKSAND = "quicksand"
_THIN_ICE  = "thin_ice"
# All tile strings the player can walk on (used for BFS traversal and
# _hazard_tile() dispatch).  Pits / walls are NOT included.
_WALKABLE_HAZARDS = (_MUD, _ICE, _WATER, _QUICKSAND, _THIN_ICE)

# ---------------------------------------------------------------------------
# Biome accent pool (Step 4)
# ---------------------------------------------------------------------------
# After the main layout pattern runs, _apply_biome_accents() sprinkles
# accent tiles over plain FLOOR cells at _BIOME_ACCENT_DENSITY probability.
# This provides visual texture that matches the room's biome without adding
# new gameplay mechanics.  Only biomes with a pool entry receive accents;
# rooms without a biome (empty string key) are left plain.
_BIOME_ACCENT_DENSITY: float = 0.05   # 5% of eligible floor tiles
_BIOME_ACCENT_POOL: dict[str, list[str]] = {
    "mud":   [_MUD],
    "ice":   [_ICE],
    "water": [_WATER],
}

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _door_tile_set(grid, doors: dict) -> set:
    """Return (col, row) positions of all open door tiles.

    Derives room dimensions from *grid* so this module never imports
    ROOM_ROWS, ROOM_COLS, or DOOR_WIDTH directly.  Door width = 3 tiles
    (half=1) centred on the room's mid column / mid row.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    mid_col = cols // 2
    mid_row = rows // 2
    result: set = set()
    for dc in (-1, 0, 1):
        if doors.get("top"):
            result.add((mid_col + dc, 0))
        if doors.get("bottom"):
            result.add((mid_col + dc, rows - 1))
    for dr in (-1, 0, 1):
        if doors.get("left"):
            result.add((0, mid_row + dr))
        if doors.get("right"):
            result.add((cols - 1, mid_row + dr))
    return result


def _door_buffer_mask(grid, doors: dict, radius: int = 2) -> set:
    """Return the set of (col, row) cells within *radius* Chebyshev distance
    of any open door tile.  Pattern functions use this to leave doorways clear.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    mask: set = set()
    for door_col, door_row in _door_tile_set(grid, doors):
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                nr, nc = door_row + dr, door_col + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    mask.add((nc, nr))
    return mask


def _door_interior_entry(grid, doors: dict) -> list:
    """Return list of (col, row) — the first interior cell adjacent to each
    open door (one tile inside the room boundary).
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    mid_col = cols // 2
    mid_row = rows // 2
    entries = []
    if doors.get("top"):
        entries.append((mid_col, 1))
    if doors.get("bottom"):
        entries.append((mid_col, rows - 2))
    if doors.get("left"):
        entries.append((1, mid_row))
    if doors.get("right"):
        entries.append((cols - 2, mid_row))
    return entries


def _bfs_path_game(grid, start: tuple, goal: tuple) -> list:
    """BFS treating FLOOR and all _WALKABLE_HAZARDS as traversable — mirrors
    actual player movement (WALL and _RUBBLE are the only blockers).
    Returns list of (col, row) inclusive, or None if unreachable.
    """
    if start == goal:
        return [start]
    from collections import deque
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    walkable = (_FLOOR,) + _WALKABLE_HAZARDS
    visited = {start}
    parents = {start: None}
    queue = deque([start])
    while queue:
        c, r = queue.popleft()
        if (c, r) == goal:
            path = []
            cur = (c, r)
            while cur is not None:
                path.append(cur)
                cur = parents[cur]
            path.reverse()
            return path
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = c + dc, r + dr
            if (nc, nr) in visited:
                continue
            if not (0 < nr < rows - 1 and 0 < nc < cols - 1):
                continue
            if grid[nr][nc] in walkable:
                visited.add((nc, nr))
                parents[(nc, nr)] = (c, r)
                queue.append((nc, nr))
    return None


def _bfs_path(grid, start: tuple, goal: tuple,
              extra_passable=None) -> list:
    """BFS from *start* to *goal* treating _FLOOR (and *extra_passable*) as
    traversable.  *extra_passable* may be a single tile string or a tuple of
    tile strings.  Returns list of (col, row) inclusive, or None if unreachable.
    """
    if start == goal:
        return [start]
    from collections import deque
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if extra_passable is None:
        _passable = frozenset()
    elif isinstance(extra_passable, str):
        _passable = frozenset({extra_passable})
    else:
        _passable = frozenset(extra_passable)
    visited = {start}
    parents = {start: None}
    queue = deque([start])
    while queue:
        c, r = queue.popleft()
        if (c, r) == goal:
            path = []
            cur = (c, r)
            while cur is not None:
                path.append(cur)
                cur = parents[cur]
            path.reverse()
            return path
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = c + dc, r + dr
            if (nc, nr) in visited:
                continue
            if not (0 < nr < rows - 1 and 0 < nc < cols - 1):
                continue
            tile = grid[nr][nc]
            if tile == _FLOOR or tile in _passable:
                visited.add((nc, nr))
                parents[(nc, nr)] = (c, r)
                queue.append((nc, nr))
    return None


def _ensure_connectivity(grid, doors: dict) -> None:
    """Carve solid interior tiles back to _FLOOR if any door entry cannot reach
    the room interior via game-walkable tiles (FLOOR or _WALKABLE_HAZARDS).
    Uses the nearest walkable cell to the room centre as the reachability goal
    so layouts that place cover at the exact centre cell still work correctly.
    """
    from collections import deque as _deque
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    # Find nearest walkable interior cell to room centre as goal.
    cx, cy = cols // 2, rows // 2
    goal = None
    _walkable = frozenset((_FLOOR,) + _WALKABLE_HAZARDS)
    gq = _deque([(cx, cy)])
    gvisited = {(cx, cy)}
    while gq:
        gc, gr = gq.popleft()
        if grid[gr][gc] in _walkable:
            goal = (gc, gr)
            break
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = gc + dc, gr + dr
            if (nc, nr) not in gvisited and 0 < nr < rows - 1 and 0 < nc < cols - 1:
                gvisited.add((nc, nr))
                gq.append((nc, nr))
    if goal is None:
        return  # No walkable interior cell — nothing to do.
    for entry in _door_interior_entry(grid, doors):
        if entry == goal:
            continue
        # Game-accurate check first: floor + walkable hazards both count.
        if _bfs_path_game(grid, entry, goal) is not None:
            continue
        # Must carve through solid interior tiles (RUBBLE or interior WALL).
        path = _bfs_path(grid, entry, goal, extra_passable=(_RUBBLE, _WALL))
        if path is None:
            continue
        for pc, pr in path:
            if grid[pr][pc] in (_RUBBLE, _WALL) and 0 < pr < rows - 1 and 0 < pc < cols - 1:
                grid[pr][pc] = _FLOOR


def _place_tile(grid, c: int, r: int, tile: str, buf_mask: set) -> bool:
    """Write *tile* to grid[r][c] only if the cell is _FLOOR and not in
    *buf_mask*.  Returns True if placed.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if not (0 < r < rows - 1 and 0 < c < cols - 1):
        return False
    if (c, r) in buf_mask:
        return False
    if grid[r][c] != _FLOOR:
        return False
    grid[r][c] = tile
    return True


def _fill_rect(grid, r1: int, c1: int, r2: int, c2: int,
               tile: str, buf_mask: set) -> None:
    """Fill the axis-aligned rectangle [r1..r2] × [c1..c2] with *tile*,
    skipping cells in *buf_mask* and non-FLOOR cells.
    """
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            _place_tile(grid, c, r, tile, buf_mask)


def _cover_tile(_biome_terrain) -> str:
    """Returns _WALL — a solid non-walkable cover tile that integrates visually
    with the room's wall structure and is included in collision rects.
    """
    return _WALL


def _hazard_tile(biome_terrain) -> str:
    """Return the room's walkable hazard tile, or _RUBBLE if none."""
    return biome_terrain if biome_terrain in _WALKABLE_HAZARDS else _RUBBLE


def _bfs_connectivity_check(grid, doors) -> bool:
    """Return True if every open door's interior entry can reach every other
    via game-walkable tiles (FLOOR or _WALKABLE_HAZARDS; WALL and RUBBLE block).
    Kept for test and external use.
    """
    entries = _door_interior_entry(grid, doors)
    if len(entries) <= 1:
        return True
    first = entries[0]
    for other in entries[1:]:
        if _bfs_path_game(grid, first, other) is None:
            return False
    return True


def _density_for_depth(depth: int, max_depth: int) -> float:
    """Returns 0.5 at depth=0, 2.0 at depth=max_depth (linear interpolation).

    Callers should clamp results before using as a multiplier on patch counts.
    """
    if max_depth <= 0:
        return 1.0
    return 0.5 + 1.5 * (depth / max_depth)


# ---------------------------------------------------------------------------
# Pattern functions — Phase 2 implementations.
# All accept:  grid (list[list[str]]), doors (dict[str,bool]),
#              biome_terrain (str), rng (random.Random), density (float)
# ---------------------------------------------------------------------------

def _pattern_open_arena(grid, doors, biome_terrain, rng, density):
    """No cover placed — pure open floor.  Default fallback / elite rooms."""
    return  # deliberately empty


def _pattern_perimeter_ring(grid, doors, biome_terrain, rng, density):
    """Single ring of cover 3 tiles in from the outer walls.  Leaves a clear
    interior courtyard and natural choke lanes at each door gap.

    The ring sits at ring=3 so it is fully outside the radius=2 door-buffer
    zone.  This keeps the ring arm intact all the way to the corners while
    still satisfying the soak test's buffer-clear requirement.
    Door gaps are carved explicitly to exactly 3 tiles (matching door width).
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    ring = 3  # 3 tiles inset keeps arms outside the radius=2 door buffer
    for c in range(ring, cols - ring):
        _place_tile(grid, c, ring, tile, buf)
        _place_tile(grid, c, rows - ring - 1, tile, buf)
    for r in range(ring + 1, rows - ring - 1):
        _place_tile(grid, ring, r, tile, buf)
        _place_tile(grid, cols - ring - 1, r, tile, buf)
    # Carve exactly a 3-tile gap in the ring at each open door so the
    # courtyard is cleanly accessible without relying on _ensure_connectivity.
    mid_col = cols // 2
    mid_row = rows // 2
    for dc in (-1, 0, 1):
        if doors.get("top"):
            grid[ring][mid_col + dc] = _FLOOR
        if doors.get("bottom"):
            grid[rows - ring - 1][mid_col + dc] = _FLOOR
    for dr in (-1, 0, 1):
        if doors.get("left"):
            grid[mid_row + dr][ring] = _FLOOR
        if doors.get("right"):
            grid[mid_row + dr][cols - ring - 1] = _FLOOR
    _ensure_connectivity(grid, doors)


def _pattern_centre_pool_round(grid, doors, biome_terrain, rng, density):
    """Circular hazard/cover pool centred on the room.  Routes around the
    pool force the player to flank; the pool's size scales with density.

    Radius is sized to occupy roughly a third of the shorter room dimension
    so the pool genuinely divides the room and forces route decisions.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _hazard_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    radius = max(4, min(rows, cols) // 3 + int(density * 0.5))
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if (c - cx) ** 2 + (r - cy) ** 2 <= radius * radius:
                _place_tile(grid, c, r, tile, buf)
    if tile == _RUBBLE:
        _ensure_connectivity(grid, doors)


def _pattern_centre_pool_oblong(grid, doors, biome_terrain, rng, density):
    """Oblong (elliptical) centre pool oriented perpendicular to the main
    travel axis; creates asymmetric routing options left vs right of pool.

    For L/R doors the ellipse is tall (narrow E/W, tall N/S) so players must
    detour around the sides.  For T/B doors it is wide.  Base semi-axes are
    sized to create clear side lanes of ~4 tiles while still dominating the
    room centre.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _hazard_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    # Orient perpendicular to primary travel axis.
    # rx=3, ry=4: tall ellipse — blocks centre column, side lanes ~5 tiles wide.
    # rx=4, ry=3: wide ellipse — blocks centre row, top/bottom lanes ~3 rows tall.
    if h_doors > v_doors:
        rx, ry = 3, 4   # tall: narrow E/W, tall N/S
    elif v_doors > h_doors:
        rx, ry = 4, 3   # wide: wide E/W, narrow N/S
    else:
        rx, ry = (3, 4) if rng.random() < 0.5 else (4, 3)
    # Scale slightly with depth — never shrink below base values.
    scale = 1.0 + 0.15 * min(density, 2.0)
    rx = max(3, int(rx * scale))
    ry = max(3, int(ry * scale))
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            dx = (c - cx) / rx
            dy = (r - cy) / ry
            if dx * dx + dy * dy <= 1.0:
                _place_tile(grid, c, r, tile, buf)
    if tile == _RUBBLE:
        _ensure_connectivity(grid, doors)


def _pattern_choke_bridge_2gap(grid, doors, biome_terrain, rng, density):
    """Large centre pool with two parallel 1-tile bridges.  Players must
    choose which bridge to cross — each is a forced choke point.

    Bridges are oriented parallel to the player's travel direction so they
    actually span the pool end-to-end:
    - H doors (left/right) → two horizontal row-bridges at cy±3
    - V doors (top/bottom) → two vertical column-bridges at cx±3

    Bridge cells are returned as a protected set so _apply_biome_accents
    cannot spill hazard accent tiles back onto the cleared paths.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _hazard_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    radius = max(4, min(rows, cols) // 3 + int(density * 0.5))
    # Place pool.
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if (c - cx) ** 2 + (r - cy) ** 2 <= radius * radius:
                _place_tile(grid, c, r, tile, buf)
    # Carve two 1-tile bridges parallel to primary door axis so each bridge
    # runs in the direction the player travels, crossing the full pool span.
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    bridge_cells: set = set()
    if h_doors >= v_doors:
        # H doors → two horizontal bridges (rows cy-3 and cy+3)
        for bridge_r in (cy - 3, cy + 3):
            for c in range(1, cols - 1):
                if grid[bridge_r][c] == tile:
                    grid[bridge_r][c] = _FLOOR
                bridge_cells.add((c, bridge_r))
    else:
        # V doors → two vertical bridges (cols cx-3 and cx+3)
        for bridge_c in (cx - 3, cx + 3):
            for r in range(1, rows - 1):
                if grid[r][bridge_c] == tile:
                    grid[r][bridge_c] = _FLOOR
                bridge_cells.add((bridge_c, r))
    if tile == _RUBBLE:
        _ensure_connectivity(grid, doors)
    return bridge_cells


def _pattern_choke_bridge_winding(grid, doors, biome_terrain, rng, density):
    """Large centre pool with a single narrow winding bridge; taking the
    winding path is slow but the only way across — speed vs safety trade-off.
    Pool radius matches choke_bridge_2gap.  Path position is clamped to the
    pool interior column/row range so every carved cell is guaranteed to have
    been a hazard tile (preventing invisible-bridge artefacts).
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _hazard_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    radius = max(4, min(rows, cols) // 3 + int(density * 0.5))
    # Place pool.
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if (c - cx) ** 2 + (r - cy) ** 2 <= radius * radius:
                _place_tile(grid, c, r, tile, buf)
    # Carve a zigzag 1-tile path through the pool.
    # Clamp to pool interior bounds so every carved cell was a hazard tile.
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    if h_doors >= v_doors:
        # H doors (L/R travel) → winding horizontal path spans pool left-to-right
        r_lo = cy - radius + 1
        r_hi = cy + radius - 1
        r_pos = cy + rng.choice([-1, 0, 1])
        for c in range(1, cols - 1):
            r_pos = max(r_lo, min(r_hi, r_pos))
            if grid[r_pos][c] == tile:
                grid[r_pos][c] = _FLOOR
            if c % 3 == 0:
                r_pos += rng.choice([-1, 1])
    else:
        # V doors (T/B travel) → winding vertical path spans pool top-to-bottom
        c_lo = cx - radius + 1
        c_hi = cx + radius - 1
        c_pos = cx + rng.choice([-1, 0, 1])
        for r in range(1, rows - 1):
            c_pos = max(c_lo, min(c_hi, c_pos))
            if grid[r][c_pos] == tile:
                grid[r][c_pos] = _FLOOR
            if r % 3 == 0:
                c_pos += rng.choice([-1, 1])
    if tile == _RUBBLE:
        _ensure_connectivity(grid, doors)


def _pattern_parallel_lanes(grid, doors, biome_terrain, rng, density):
    """Two parallel 2-tile-thick hazard/cover strips divide the room into
    three lanes.  Players commit to a lane or pay a movement cost to switch.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _hazard_tile(biome_terrain)
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    if v_doors > h_doors:
        # T/B travel → vertical strips create left / centre / right parallel lanes
        for t in range(2):
            for r in range(1, rows - 1):
                _place_tile(grid, cols // 3 + t, r, tile, buf)
                _place_tile(grid, 2 * cols // 3 + t, r, tile, buf)
    else:
        # L/R travel (or neutral) → horizontal strips create top / mid / bottom parallel lanes
        for t in range(2):
            for c in range(1, cols - 1):
                _place_tile(grid, c, rows // 3 + t, tile, buf)
                _place_tile(grid, c, 2 * rows // 3 + t, tile, buf)
    if tile == _RUBBLE:
        _ensure_connectivity(grid, doors)


def _pattern_fork_split(grid, doors, biome_terrain, rng, density):
    """V-shaped RUBBLE wedge whose apex starts near the entry door (row/col 3)
    and arms fan out as a solid filled wedge toward the far end.  The centre
    row (or column) remains clear at all times, creating a visible open lane
    through the apex that forks into two lanes as the player advances.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    if v_doors >= h_doors:
        arm_steps = max(1, rows // 2 - 2)
        max_spread = max(1, cols // 2 - 3)
        # Apex faces entry: flip so narrow end is near the only open door.
        flip = bool(doors.get("bottom")) and not bool(doors.get("top"))
        for step in range(arm_steps):
            r = (rows - 4 - step) if flip else (3 + step)
            spread = (step * max_spread) // max(1, arm_steps - 1)
            for c in range(cx - spread, cx):
                _place_tile(grid, c, r, tile, buf)
            for c in range(cx + 1, cx + spread + 1):
                _place_tile(grid, c, r, tile, buf)
    else:
        arm_steps = max(1, cols // 2 - 2)
        max_spread = max(1, rows // 2 - 3)
        # Apex faces entry: flip so narrow end is near the only open door.
        flip = bool(doors.get("right")) and not bool(doors.get("left"))
        for step in range(arm_steps):
            c = (cols - 4 - step) if flip else (3 + step)
            spread = (step * max_spread) // max(1, arm_steps - 1)
            for r in range(cy - spread, cy):
                _place_tile(grid, c, r, tile, buf)
            for r in range(cy + 1, cy + spread + 1):
                _place_tile(grid, c, r, tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_column_hall_grid(grid, doors, biome_terrain, rng, density):
    """Regular grid of 2×2 RUBBLE column clusters.  Provides even cover
    distribution with consistent sightline breaks in all directions.
    3×3 cluster layout (col_step=5, row_step=4) gives clear 3-tile aisles
    between every cluster in a 20×15 room.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    col_step = 5
    row_step = 4
    for r in range(3, rows - 2, row_step):
        for c in range(3, cols - 2, col_step):
            _place_tile(grid, c,     r,     tile, buf)
            _place_tile(grid, c + 1, r,     tile, buf)
            _place_tile(grid, c,     r + 1, tile, buf)
            _place_tile(grid, c + 1, r + 1, tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_column_hall_offset(grid, doors, biome_terrain, rng, density):
    """Staggered 2×2 RUBBLE column clusters (alternating rows offset by half
    the column period).  Creates diagonal sightlines with no clear straight hall.
    Matches column_hall_grid spacing (col_step=5, row_step=4) so density is
    consistent between the two column-hall variants.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    col_step = 5
    row_step = 4
    for i, r in enumerate(range(3, rows - 2, row_step)):
        c_start = 3 + (col_step // 2 if i % 2 == 1 else 0)
        for c in range(c_start, cols - 2, col_step):
            _place_tile(grid, c,     r,     tile, buf)
            _place_tile(grid, c + 1, r,     tile, buf)
            _place_tile(grid, c,     r + 1, tile, buf)
            _place_tile(grid, c + 1, r + 1, tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_alcove_pockets(grid, doors, biome_terrain, rng, density):
    """Four 2×3 RUBBLE corner pockets (2 rows × 3 cols) flush against each
    corner of the room interior.  All four pockets sit outside every door
    buffer zone, giving reliable retreat spots near the corners.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    # Each entry: (r1, c1, r2, c2) — 2 rows × 3 cols, one per corner.
    pockets = [
        (2,        2,        3,        4        ),  # top-left
        (2,        cols - 5, 3,        cols - 3 ),  # top-right
        (rows - 4, 2,        rows - 3, 4        ),  # bottom-left
        (rows - 4, cols - 5, rows - 3, cols - 3 ),  # bottom-right
    ]
    for r1, c1, r2, c2 in pockets:
        _fill_rect(grid, r1, c1, r2, c2, tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_fortress_courtyard(grid, doors, biome_terrain, rng, density):
    """Thick 2-tile RUBBLE ring set 3 tiles inset from outer walls (fully
    outside the radius-2 door buffer zone) with exactly 3-tile-wide gaps
    carved at each open door for a clean corridor entry into the courtyard.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    outer = 3           # ring starts 3 tiles from wall — outside radius-2 buffer
    thickness = 2       # ring is this many tiles thick
    inner = outer + thickness
    for r in range(outer, rows - outer):
        for c in range(outer, cols - outer):
            # Skip the inner courtyard
            if inner <= r < rows - inner and inner <= c < cols - inner:
                continue
            _place_tile(grid, c, r, tile, buf)
    # Carve exactly 3-tile-wide door gaps (matching door width) at each open
    # door so the approach corridor aligns cleanly with the doorway.
    mid_col = cols // 2
    mid_row = rows // 2
    for ro in range(outer, inner):      # each row/col band of the ring
        for dc in (-1, 0, 1):           # 3-tile gap centred on mid
            if doors.get("top"):
                grid[ro][mid_col + dc] = _FLOOR
            if doors.get("bottom"):
                grid[rows - 1 - ro][mid_col + dc] = _FLOOR
    for co in range(outer, inner):
        for dr in (-1, 0, 1):
            if doors.get("left"):
                grid[mid_row + dr][co] = _FLOOR
            if doors.get("right"):
                grid[mid_row + dr][cols - 1 - co] = _FLOOR
    _ensure_connectivity(grid, doors)


def _pattern_mire_carpet(grid, doors, biome_terrain, rng, density):
    """Dense walkable hazard carpet fills most of the interior; carved
    1-tile stepping-stone paths lead from each door to the room centre,
    forcing cautious navigation or accepting continuous hazard exposure.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 3)   # wider buffer keeps entrances clear
    hazard = biome_terrain if biome_terrain in _WALKABLE_HAZARDS else _MUD
    local_rng = random.Random(
        hash((tuple(sorted(doors.items())), "mire")) & 0xFFFFFFFF
    )
    fill_chance = min(0.85, 0.55 + 0.15 * min(density, 2.0))
    for r in range(2, rows - 2):
        for c in range(2, cols - 2):
            if (c, r) not in buf and grid[r][c] == _FLOOR:
                if local_rng.random() < fill_chance:
                    grid[r][c] = hazard
    # Carve 2-tile-wide corridors from each door entry to room centre.
    center = (cols // 2, rows // 2)
    paths = []
    for entry in _door_interior_entry(grid, doors):
        path = _bfs_path(grid, entry, center, extra_passable=hazard)
        if path is not None:
            paths.append(path)
    # First pass: carve primary path spine.
    for path in paths:
        for pc, pr in path:
            grid[pr][pc] = _FLOOR
    # Second pass: widen each path by 1 tile perpendicular to travel direction
    # (horizontal segments gain a row below; vertical segments gain a col right).
    for path in paths:
        for i, (pc, pr) in enumerate(path):
            if i + 1 < len(path):
                nc, nr = path[i + 1]
            elif i > 0:
                nc, nr = path[i - 1]
            else:
                continue
            if nc == pc:    # vertical step → widen right
                wc, wr = pc + 1, pr
            else:           # horizontal step → widen downward
                wc, wr = pc, pr + 1
            if 1 <= wr < rows - 1 and 1 <= wc < cols - 1 and grid[wr][wc] == hazard:
                grid[wr][wc] = _FLOOR
    # Clear a 3×3 zone at the path junction (room centre) for navigability.
    cc, cr = cols // 2, rows // 2
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if 1 <= cr + dr < rows - 1 and 1 <= cc + dc < cols - 1:
                grid[cr + dr][cc + dc] = _FLOOR


def _pattern_terrain_minefield(grid, doors, biome_terrain, rng, density):
    """Scattered individual walkable hazard tiles across the room interior.
    Density scales with room depth; respects door buffer zone.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    hazard = biome_terrain if biome_terrain in _WALKABLE_HAZARDS else _MUD
    interior = [
        (c, r)
        for r in range(2, rows - 2)
        for c in range(2, cols - 2)
        if (c, r) not in buf and grid[r][c] == _FLOOR
    ]
    count = int(len(interior) * min(0.35, 0.12 + 0.12 * min(density, 2.0)))
    local_rng = random.Random(
        hash((tuple(sorted(doors.items())), "minefield")) & 0xFFFFFFFF
    )
    local_rng.shuffle(interior)
    for c, r in interior[:count]:
        # Skip if any orthogonal neighbour already holds a hazard tile —
        # prevents wall-to-wall clumps that force players into dead-ends.
        if any(
            0 <= r + dr < rows and 0 <= c + dc < cols
            and grid[r + dr][c + dc] == hazard
            for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0))
        ):
            continue
        grid[r][c] = hazard


def _pattern_island_cluster_dense(grid, doors, biome_terrain, rng, density):
    """Five 2×2 RUBBLE islands distributed through the full interior.  One
    island is seeded per room quadrant to guarantee spread; a fifth attempt
    can fall anywhere in the interior as a tiebreaker.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    local_rng = random.Random(
        hash((tuple(sorted(doors.items())), "dense")) & 0xFFFFFFFF
    )
    island_sz = 2
    min_sep = island_sz + 2
    max_c = cols - island_sz - 2   # max top-left col so island fits in interior
    max_r = rows - island_sz - 2   # max top-left row
    if max_c < 2 or max_r < 2:
        _ensure_connectivity(grid, doors)
        return
    half_c = cols // 2
    half_r = rows // 2
    placed = []
    # One island per quadrant (NW, NE, SW, SE), then one free-range attempt.
    zones = [
        (2,      2,      min(max_r, half_r - 1), min(max_c, half_c - 1)),  # NW
        (2,      half_c, min(max_r, half_r - 1), max_c                 ),  # NE
        (half_r, 2,      max_r,                  min(max_c, half_c - 1)),  # SW
        (half_r, half_c, max_r,                  max_c                 ),  # SE
        (2,      2,      max_r,                  max_c                 ),  # anywhere
    ]
    for r_lo, c_lo, r_hi, c_hi in zones:
        if len(placed) >= 5:
            break
        if r_hi < r_lo or c_hi < c_lo:
            continue
        for _ in range(30):
            c = local_rng.randint(c_lo, c_hi)
            r = local_rng.randint(r_lo, r_hi)
            cells = [(c + dc, r + dr) for dc in range(island_sz) for dr in range(island_sz)]
            if any((cc, rr) in buf for cc, rr in cells):
                continue
            if any(abs(c - pc) < min_sep and abs(r - pr) < min_sep for pc, pr in placed):
                continue
            for cc, rr in cells:
                if grid[rr][cc] == _FLOOR:
                    grid[rr][cc] = tile
            placed.append((c, r))
            break
    _ensure_connectivity(grid, doors)


def _pattern_island_cluster_sparse(grid, doors, biome_terrain, rng, density):
    """Three 3×4 RUBBLE islands seeded along the NW→SE diagonal so one
    island anchors each corner zone and one sits near centre.  Long exposed
    lanes between cover create high-risk decision moments.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    local_rng = random.Random(
        hash((tuple(sorted(doors.items())), "sparse")) & 0xFFFFFFFF
    )
    iw, ih = 3, 4
    target = 3
    min_sep_c = iw + 3
    min_sep_r = ih + 3
    max_c = cols - iw - 2
    max_r = rows - ih - 2
    if max_c < 2 or max_r < 2:
        _ensure_connectivity(grid, doors)
        return
    placed = []
    third_c = max(1, max_c // 3)
    third_r = max(1, max_r // 3)
    zones = [
        (2,                   2,                   third_r + 2,         third_c + 2),
        (third_r,             third_c,             2 * third_r + 2,     2 * third_c + 2),
        (max(2, 2*third_r),   max(2, 2*third_c),   max_r,               max_c),
    ]
    for r_lo, c_lo, r_hi, c_hi in zones:
        if len(placed) >= target:
            break
        r_hi = min(r_hi, max_r)
        c_hi = min(c_hi, max_c)
        if r_hi < r_lo or c_hi < c_lo:
            continue
        for _ in range(30):
            c = local_rng.randint(c_lo, c_hi)
            r = local_rng.randint(r_lo, r_hi)
            cells = [(c + dc, r + dr) for dc in range(iw) for dr in range(ih)]
            if any((cc, rr) in buf for cc, rr in cells):
                continue
            if any(abs(c - pc) < min_sep_c and abs(r - pr) < min_sep_r
                   for pc, pr in placed):
                continue
            for cc, rr in cells:
                if grid[rr][cc] == _FLOOR:
                    grid[rr][cc] = tile
            placed.append((c, r))
            break
    _ensure_connectivity(grid, doors)


def _pattern_river_with_pillars(grid, doors, biome_terrain, rng, density):
    """3-tile-wide walkable hazard river bisects the room; 4 single RUBBLE
    pillar tiles beside the river provide mid-stream cover.  Players cross
    via gaps at door buffer zones.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    river_tile = biome_terrain if biome_terrain in _WALKABLE_HAZARDS else _WATER
    pillar_tile = _cover_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    if h_doors > v_doors:
        # H doors → V river (vertical strip crossing middle columns)
        for r in range(1, rows - 1):
            for c in range(cx - 1, cx + 2):
                _place_tile(grid, c, r, river_tile, buf)
        # Two pillar pairs at quarter-row positions, cx±5 (clear of river)
        for pr in (rows // 4, 3 * rows // 4):
            _place_tile(grid, cx - 5, pr, pillar_tile, buf)
            _place_tile(grid, cx + 5, pr, pillar_tile, buf)
    else:
        # V doors (or neutral) → H river (horizontal strip crossing middle rows)
        for r in range(cy - 1, cy + 2):
            for c in range(1, cols - 1):
                _place_tile(grid, c, r, river_tile, buf)
        # Two pillar pairs at quarter-col positions, cy±4 (clear of river)
        for pc in (cols // 4, 3 * cols // 4):
            _place_tile(grid, pc, cy - 4, pillar_tile, buf)
            _place_tile(grid, pc, cy + 4, pillar_tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_ringed_columns(grid, doors, biome_terrain, rng, density):
    """Two concentric Chebyshev rings of single RUBBLE tiles at radii 3 and 5
    from the room centre.  Layered cover creates varied engagement distances
    and diagonal sightlines without blocking main transit lanes.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    for radius in (3, 5):
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                if max(abs(dr), abs(dc)) == radius:
                    # Sparse the ring: every other tile for navigable gaps
                    if (dr + dc) % 2 == 0:
                        _place_tile(grid, cx + dc, cy + dr, tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_island_alcoves(grid, doors, biome_terrain, rng, density):
    """Central 4×4 RUBBLE island plus four 2×2 corner alcoves.  Hybrid
    cover distribution rewards players who learn retreat positions.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    # Central island
    _fill_rect(grid, cy - 2, cx - 2, cy + 1, cx + 1, tile, buf)
    # Corner alcoves — shifted 1 tile inward from walls to stay outside radius-2 buffer
    _fill_rect(grid, 2,         3,         3,         4,         tile, buf)
    _fill_rect(grid, 2,         cols - 5,  3,         cols - 4,  tile, buf)
    _fill_rect(grid, rows - 4,  3,         rows - 3,  4,         tile, buf)
    _fill_rect(grid, rows - 4,  cols - 5,  rows - 3,  cols - 4,  tile, buf)
    _ensure_connectivity(grid, doors)


# ---------------------------------------------------------------------------
# Layout registry
# ---------------------------------------------------------------------------
# biome_affinities keys match Room.biome_terrain values: "", "mud", "ice", "water"
# Absent biome key → treated as weight 5 (neutral) by the selector.
# ---------------------------------------------------------------------------

LAYOUT_REGISTRY: dict[str, LayoutSpec] = {
    "open_arena": LayoutSpec(
        id="open_arena",
        family="open",
        decision_type="kiting",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=0,
        min_cols=0,
        biome_affinities={"": 8, "mud": 4, "ice": 7, "water": 5},
        fn=_pattern_open_arena,
    ),
    "perimeter_ring": LayoutSpec(
        id="perimeter_ring",
        family="open",
        decision_type="cover_los",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 6, "mud": 5, "ice": 5, "water": 4},
        fn=_pattern_perimeter_ring,
    ),
    "centre_pool_round": LayoutSpec(
        id="centre_pool_round",
        family="centre_pool",
        decision_type="speed_safety",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 5, "mud": 8, "ice": 4, "water": 9},
        fn=_pattern_centre_pool_round,
    ),
    "centre_pool_oblong": LayoutSpec(
        id="centre_pool_oblong",
        family="centre_pool",
        decision_type="speed_safety",
        supported_door_counts=(2, 3, 4),
        min_rows=9,
        min_cols=11,
        biome_affinities={"": 4, "mud": 7, "ice": 4, "water": 8},
        fn=_pattern_centre_pool_oblong,
    ),
    "choke_bridge_2gap": LayoutSpec(
        id="choke_bridge_2gap",
        family="choke_bridge",
        decision_type="lane",
        supported_door_counts=(2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 5, "mud": 6, "ice": 3, "water": 7},
        fn=_pattern_choke_bridge_2gap,
    ),
    "choke_bridge_winding": LayoutSpec(
        id="choke_bridge_winding",
        family="choke_bridge",
        decision_type="lane",
        supported_door_counts=(2, 3, 4),
        min_rows=9,
        min_cols=11,
        biome_affinities={"": 4, "mud": 7, "ice": 2, "water": 8},
        fn=_pattern_choke_bridge_winding,
    ),
    "parallel_lanes": LayoutSpec(
        id="parallel_lanes",
        family="lane_split",
        decision_type="lane",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 6, "mud": 5, "ice": 7, "water": 4},
        fn=_pattern_parallel_lanes,
    ),
    "fork_split": LayoutSpec(
        id="fork_split",
        family="lane_split",
        decision_type="lane",
        supported_door_counts=(2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 5, "mud": 4, "ice": 6, "water": 3},
        fn=_pattern_fork_split,
    ),
    "column_hall_grid": LayoutSpec(
        id="column_hall_grid",
        family="column_hall",
        decision_type="cover_los",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 7, "mud": 4, "ice": 6, "water": 3},
        fn=_pattern_column_hall_grid,
    ),
    "column_hall_offset": LayoutSpec(
        id="column_hall_offset",
        family="column_hall",
        decision_type="cover_los",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=11,
        biome_affinities={"": 6, "mud": 3, "ice": 7, "water": 3},
        fn=_pattern_column_hall_offset,
    ),
    "alcove_pockets": LayoutSpec(
        id="alcove_pockets",
        family="alcove",
        decision_type="mobility_tax",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 6, "mud": 5, "ice": 5, "water": 5},
        fn=_pattern_alcove_pockets,
    ),
    "fortress_courtyard": LayoutSpec(
        id="fortress_courtyard",
        family="alcove",
        decision_type="mobility_tax",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=11,
        min_cols=11,
        biome_affinities={"": 5, "mud": 4, "ice": 4, "water": 3},
        fn=_pattern_fortress_courtyard,
    ),
    "mire_carpet": LayoutSpec(
        id="mire_carpet",
        family="hazard_field",
        decision_type="mobility_tax",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 3, "mud": 9, "ice": 2, "water": 7},
        fn=_pattern_mire_carpet,
    ),
    "terrain_minefield": LayoutSpec(
        id="terrain_minefield",
        family="hazard_field",
        decision_type="mobility_tax",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 4, "mud": 7, "ice": 6, "water": 5},
        fn=_pattern_terrain_minefield,
    ),
    "island_cluster_dense": LayoutSpec(
        id="island_cluster_dense",
        family="island",
        decision_type="kiting",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 6, "mud": 5, "ice": 7, "water": 6},
        fn=_pattern_island_cluster_dense,
    ),
    "island_cluster_sparse": LayoutSpec(
        id="island_cluster_sparse",
        family="island",
        decision_type="kiting",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=11,
        min_cols=11,
        biome_affinities={"": 5, "mud": 4, "ice": 8, "water": 5},
        fn=_pattern_island_cluster_sparse,
    ),
    "river_with_pillars": LayoutSpec(
        id="river_with_pillars",
        family="river",
        decision_type="fusion",
        supported_door_counts=(2, 3, 4),
        min_rows=9,
        min_cols=9,
        biome_affinities={"": 3, "mud": 6, "ice": 5, "water": 9},
        fn=_pattern_river_with_pillars,
    ),
    "ringed_columns": LayoutSpec(
        id="ringed_columns",
        family="column_hall",
        decision_type="cover_los",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=13,
        min_cols=13,
        biome_affinities={"": 5, "mud": 3, "ice": 6, "water": 3},
        fn=_pattern_ringed_columns,
    ),
    "island_alcoves": LayoutSpec(
        id="island_alcoves",
        family="island",
        decision_type="fusion",
        supported_door_counts=(1, 2, 3, 4),
        min_rows=11,
        min_cols=11,
        biome_affinities={"": 5, "mud": 5, "ice": 6, "water": 6},
        fn=_pattern_island_alcoves,
    ),
}


# ---------------------------------------------------------------------------
# Biome accent pass (Step 4)
# ---------------------------------------------------------------------------

def _apply_biome_accents(grid, doors: dict, biome_terrain: str, rng,
                         protected: set = None) -> None:
    """Sprinkle biome-accent tiles over FLOOR cells after the main pattern.

    Skips cells inside the door-buffer zone so entrances stay clear.
    Skips cells in *protected* (e.g. carved bridge paths) so accent tiles
    cannot spill back onto intentionally cleared traversal lanes.
    Only activates when *biome_terrain* has an entry in ``_BIOME_ACCENT_POOL``.
    """
    accent_tiles = _BIOME_ACCENT_POOL.get(biome_terrain)
    if not accent_tiles:
        return
    buf = _door_buffer_mask(grid, doors, radius=2)
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if grid[r][c] != _FLOOR:
                continue
            if (c, r) in buf:
                continue
            if protected and (c, r) in protected:
                continue
            if rng.random() < _BIOME_ACCENT_DENSITY:
                grid[r][c] = rng.choice(accent_tiles)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply(layout_id: str, grid, doors, biome_terrain, rng, depth_density: float) -> None:
    """Dispatch to the named pattern function, then apply biome accents.

    If the pattern function returns a set of protected cell coordinates
    (col, row), those cells are excluded from the biome-accent pass so that
    intentionally cleared paths (e.g. bridges) cannot be overwritten.

    Raises KeyError if *layout_id* is not in the registry.
    """
    spec = LAYOUT_REGISTRY[layout_id]
    protected = spec.fn(grid, doors, biome_terrain, rng, depth_density)
    _apply_biome_accents(grid, doors, biome_terrain, rng,
                         protected if isinstance(protected, set) else None)


def terrain_layout_for_plan(plan, rng, biome_terrain: str = "",
                             door_count: int = 2,
                             recent_families: tuple = ()) -> str:
    """Select a layout id using biome-weighted random choice.

    If *plan* has a non-empty ``terrain_layout`` field that matches a registry
    entry, return it directly.

    Otherwise select from the registry weighted by biome affinity, filtered
    by ``door_count`` support, with recently-used family weights halved.
    """
    if plan is not None:
        lid = getattr(plan, "terrain_layout", "") or ""
        if lid and lid in LAYOUT_REGISTRY:
            return lid

    candidates = []
    weights = []
    for spec in LAYOUT_REGISTRY.values():
        if door_count not in spec.supported_door_counts:
            continue
        affinity = spec.biome_affinities.get(biome_terrain, 5)
        w = max(1, affinity)
        if spec.family in recent_families:
            w = max(1, w // 2)
        candidates.append(spec.id)
        weights.append(w)

    if not candidates:
        return "open_arena"

    total = sum(weights)
    pick = rng.uniform(0, total)
    cumulative = 0.0
    for cid, w in zip(candidates, weights):
        cumulative += w
        if pick <= cumulative:
            return cid
    return candidates[-1]
