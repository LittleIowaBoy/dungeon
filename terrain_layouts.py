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
_WALL   = "wall"
_RUBBLE = "rubble"
_MUD    = "mud"
_ICE    = "ice"
_WATER  = "water"
_WALKABLE_HAZARDS = (_MUD, _ICE, _WATER)

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
              extra_passable: str = None) -> list:
    """BFS from *start* to *goal* treating _FLOOR (and *extra_passable*) as
    traversable.  Returns list of (col, row) inclusive, or None if unreachable.
    """
    if start == goal:
        return [start]
    from collections import deque
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
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
            if tile == _FLOOR or tile == extra_passable:
                visited.add((nc, nr))
                parents[(nc, nr)] = (c, r)
                queue.append((nc, nr))
    return None


def _ensure_connectivity(grid, doors: dict) -> None:
    """Carve _RUBBLE back to _FLOOR if any door entry cannot reach the room
    centre via game-walkable tiles (FLOOR or _WALKABLE_HAZARDS).
    Patterns that use only walkable hazards are already inherently connected;
    this only carves when genuine RUBBLE disconnection occurs.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    center = (cols // 2, rows // 2)
    for entry in _door_interior_entry(grid, doors):
        if entry == center:
            continue
        # Game-accurate check first: floor + walkable hazards both count.
        if _bfs_path_game(grid, entry, center) is not None:
            continue
        # Must carve through RUBBLE — genuine disconnect.
        path = _bfs_path(grid, entry, center, extra_passable=_RUBBLE)
        if path is None:
            continue
        for pc, pr in path:
            if grid[pr][pc] == _RUBBLE:
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
    """Always returns _RUBBLE — solid non-walkable cover tile."""
    return _RUBBLE


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
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _hazard_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    radius = max(3, min(rows, cols) // 4 + int(0.3 * density))
    # Place pool.
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if (c - cx) ** 2 + (r - cy) ** 2 <= radius * radius:
                _place_tile(grid, c, r, tile, buf)
    # Carve a zigzag 1-tile path through the pool.
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    if h_doors >= v_doors:
        # Winding V path (zigzag through cols)
        c_pos = cx + rng.choice([-1, 0, 1])
        for r in range(1, rows - 1):
            c_pos = max(2, min(cols - 3, c_pos))
            if grid[r][c_pos] == tile:
                grid[r][c_pos] = _FLOOR
            if r % 3 == 0:
                c_pos += rng.choice([-1, 1])
    else:
        # Winding H path (zigzag through rows)
        r_pos = cy + rng.choice([-1, 0, 1])
        for c in range(1, cols - 1):
            r_pos = max(2, min(rows - 3, r_pos))
            if grid[r_pos][c] == tile:
                grid[r_pos][c] = _FLOOR
            if c % 3 == 0:
                r_pos += rng.choice([-1, 1])
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
        # top/bottom travel → horizontal strips at 1/3 and 2/3 height
        for t in range(2):
            for c in range(2, cols - 2):
                _place_tile(grid, c, rows // 3 + t, tile, buf)
                _place_tile(grid, c, 2 * rows // 3 + t, tile, buf)
    else:
        # left/right travel (or neutral) → vertical strips at 1/3 and 2/3 width
        for t in range(2):
            for r in range(2, rows - 2):
                _place_tile(grid, cols // 3 + t, r, tile, buf)
                _place_tile(grid, 2 * cols // 3 + t, r, tile, buf)
    if tile == _RUBBLE:
        _ensure_connectivity(grid, doors)


def _pattern_fork_split(grid, doors, biome_terrain, rng, density):
    """V-shaped RUBBLE wedge whose apex faces the entry door and arms spread
    toward the far end.  Players see an open approach that funnels into two
    distinct lanes as they advance.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    cx, cy = cols // 2, rows // 2
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    if v_doors >= h_doors:
        # V opens toward top entry, arms spread toward bottom.
        arm_steps = max(1, rows - 2 - cy)
        for step in range(arm_steps):
            r = cy + step
            spread = 1 + (step * 2) // max(1, arm_steps)
            for c in range(cx - spread - 1, cx - spread + 2):
                _place_tile(grid, c, r, tile, buf)
            for c in range(cx + spread - 1, cx + spread + 2):
                _place_tile(grid, c, r, tile, buf)
    else:
        # V opens toward left entry, arms spread toward right.
        arm_steps = max(1, cols - 2 - cx)
        for step in range(arm_steps):
            c = cx + step
            spread = 1 + (step * 2) // max(1, arm_steps)
            for r in range(cy - spread - 1, cy - spread + 2):
                _place_tile(grid, c, r, tile, buf)
            for r in range(cy + spread - 1, cy + spread + 2):
                _place_tile(grid, c, r, tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_column_hall_grid(grid, doors, biome_terrain, rng, density):
    """Regular grid of 2×2 RUBBLE column clusters.  Provides even cover
    distribution with consistent sightline breaks in all directions.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    col_step = 4
    row_step = 3
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
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    col_step = 4
    row_step = 3
    for i, r in enumerate(range(3, rows - 2, row_step)):
        c_start = 3 + (col_step // 2 if i % 2 == 1 else 0)
        for c in range(c_start, cols - 2, col_step):
            _place_tile(grid, c,     r,     tile, buf)
            _place_tile(grid, c + 1, r,     tile, buf)
            _place_tile(grid, c,     r + 1, tile, buf)
            _place_tile(grid, c + 1, r + 1, tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_alcove_pockets(grid, doors, biome_terrain, rng, density):
    """Small 2×3 RUBBLE pockets along each wall (two per wall side) at
    quarter positions.  Natural kiting spots and retreat corners.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    q1c, q2c = cols // 4, 3 * cols // 4
    q1r, q2r = rows // 4, 3 * rows // 4
    pockets = [
        (2,         q1c - 1,  3,         q1c + 1),   # top-left
        (2,         q2c - 1,  3,         q2c + 1),   # top-right
        (rows - 4,  q1c - 1,  rows - 3,  q1c + 1),   # bottom-left
        (rows - 4,  q2c - 1,  rows - 3,  q2c + 1),   # bottom-right
        (q1r - 1,  2,         q1r + 1,  3),           # left-top
        (q2r - 1,  2,         q2r + 1,  3),           # left-bottom
        (q1r - 1,  cols - 4,  q1r + 1,  cols - 3),   # right-top
        (q2r - 1,  cols - 4,  q2r + 1,  cols - 3),   # right-bottom
    ]
    for r1, c1, r2, c2 in pockets:
        _fill_rect(grid, r1, c1, r2, c2, tile, buf)
    _ensure_connectivity(grid, doors)


def _pattern_fortress_courtyard(grid, doors, biome_terrain, rng, density):
    """Thick 2-tile RUBBLE ring set 2 tiles inset from outer walls with gaps
    only at door buffer zones — creates a 'fortress' feel with an exposed
    courtyard in the centre.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    outer = 2           # ring starts this many tiles from wall
    thickness = 2       # ring is this many tiles thick
    inner = outer + thickness
    for r in range(outer, rows - outer):
        for c in range(outer, cols - outer):
            # Skip the inner courtyard
            if inner <= r < rows - inner and inner <= c < cols - inner:
                continue
            _place_tile(grid, c, r, tile, buf)
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
    # Carve stepping-stone corridors from each door entry to room centre.
    center = (cols // 2, rows // 2)
    for entry in _door_interior_entry(grid, doors):
        path = _bfs_path(grid, entry, center, extra_passable=hazard)
        if path is None:
            continue
        for pc, pr in path:
            grid[pr][pc] = _FLOOR   # restore exactly the path — keep 1 tile wide


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
        grid[r][c] = hazard


def _pattern_island_cluster_dense(grid, doors, biome_terrain, rng, density):
    """Five 2×2 RUBBLE islands distributed through the interior with ~2-tile
    separation.  Creates leap-frog kiting opportunities at close range.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    buf = _door_buffer_mask(grid, doors, 2)
    tile = _cover_tile(biome_terrain)
    local_rng = random.Random(
        hash((tuple(sorted(doors.items())), "dense")) & 0xFFFFFFFF
    )
    island_sz = 2
    target = 5
    placed = []
    for _ in range(100):
        if len(placed) >= target:
            break
        c = local_rng.randint(3, cols - 4 - island_sz)
        r = local_rng.randint(3, rows - 4 - island_sz)
        cells = [(c + dc, r + dr) for dc in range(island_sz) for dr in range(island_sz)]
        if any((cc, rr) in buf for cc, rr in cells):
            continue
        if any(abs(c - pc) < island_sz + 2 and abs(r - pr) < island_sz + 2
               for pc, pr in placed):
            continue
        for cc, rr in cells:
            if grid[rr][cc] == _FLOOR:
                grid[rr][cc] = tile
        placed.append((c, r))
    _ensure_connectivity(grid, doors)


def _pattern_island_cluster_sparse(grid, doors, biome_terrain, rng, density):
    """Three 3×4 RUBBLE islands spread far apart.  Long exposed dashes
    between cover create high-risk decision moments.
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
    placed = []
    for _ in range(100):
        if len(placed) >= target:
            break
        c = local_rng.randint(3, cols - 4 - iw)
        r = local_rng.randint(3, rows - 4 - ih)
        cells = [(c + dc, r + dr) for dc in range(iw) for dr in range(ih)]
        if any((cc, rr) in buf for cc, rr in cells):
            continue
        if any(abs(c - pc) < iw + 3 and abs(r - pr) < ih + 3
               for pc, pr in placed):
            continue
        for cc, rr in cells:
            if grid[rr][cc] == _FLOOR:
                grid[rr][cc] = tile
        placed.append((c, r))
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
    pillar_tile = _RUBBLE
    cx, cy = cols // 2, rows // 2
    h_doors = int(bool(doors.get("left"))) + int(bool(doors.get("right")))
    v_doors = int(bool(doors.get("top"))) + int(bool(doors.get("bottom")))
    if h_doors > v_doors:
        # H doors → V river (vertical strip crossing middle columns)
        for r in range(1, rows - 1):
            for c in range(cx - 1, cx + 2):
                _place_tile(grid, c, r, river_tile, buf)
        # Pillars flanking the river
        for pr in (rows // 4, rows // 2, 3 * rows // 4):
            _place_tile(grid, cx - 3, pr, pillar_tile, buf)
            _place_tile(grid, cx + 3, pr, pillar_tile, buf)
    else:
        # V doors (or neutral) → H river (horizontal strip crossing middle rows)
        for r in range(cy - 1, cy + 2):
            for c in range(1, cols - 1):
                _place_tile(grid, c, r, river_tile, buf)
        # Pillars above and below river
        for pc in (cols // 4, cx, 3 * cols // 4):
            _place_tile(grid, pc, cy - 3, pillar_tile, buf)
            _place_tile(grid, pc, cy + 3, pillar_tile, buf)
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
    # Corner alcoves
    _fill_rect(grid, 2,         2,         3,         3,         tile, buf)
    _fill_rect(grid, 2,         cols - 4,  3,         cols - 3,  tile, buf)
    _fill_rect(grid, rows - 4,  2,         rows - 3,  3,         tile, buf)
    _fill_rect(grid, rows - 4,  cols - 4,  rows - 3,  cols - 3,  tile, buf)
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
        min_rows=11,
        min_cols=11,
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
