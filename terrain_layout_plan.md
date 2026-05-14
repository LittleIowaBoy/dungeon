# Terrain Layout Design Plan

Room dimensions: **20 cols × 15 rows** (interior: cols 1–18, rows 1–13).
Doors are 3 tiles wide, centred on each wall edge (cols 9–11 for top/bottom, rows 6–8 for left/right).

Sketches show the **design target** — what each layout should look like when
correctly implemented — not the current output.

Legend:
```
#  wall tile
.  open floor
X  rubble (solid, non-walkable cover)
~  walkable hazard (mud / ice / water — matches room biome)
D  door opening
```
Sketches default to **left + right doors** unless otherwise noted.

---

## Status Summary

| # | ID                    | Family         | Decision type  | Status            |
|---|-----------------------|----------------|----------------|-------------------|
| 1 | open_arena            | open           | kiting         | [x] verified OK   |
| 2 | perimeter_ring        | open           | cover_los      | [x] fixed         |
| 3 | centre_pool_round     | centre_pool    | speed_safety   | [x] fixed         |
| 4 | centre_pool_oblong    | centre_pool    | speed_safety   | [x] fixed         |
| 5 | choke_bridge_2gap     | choke_bridge   | lane           | [x] fixed         |
| 6 | choke_bridge_winding  | choke_bridge   | lane           | [x] fixed         |
| 7 | parallel_lanes        | lane_split     | lane           | [x] fixed         |
| 8 | fork_split            | lane_split     | lane           | [x] fixed         |
| 9 | column_hall_grid      | column_hall    | cover_los      | [x] fixed         |
|10 | column_hall_offset    | column_hall    | cover_los      | [x] fixed         |
|11 | alcove_pockets        | alcove         | mobility_tax   | [x] fixed         |
|12 | fortress_courtyard    | alcove         | mobility_tax   | [x] fixed         |
|13 | mire_carpet           | hazard_field   | mobility_tax   | [x] fixed         |
|14 | terrain_minefield     | hazard_field   | mobility_tax   | [x] fixed         |
|15 | island_cluster_dense  | island         | kiting         | [x] fixed         |
|16 | island_cluster_sparse | island         | kiting         | [x] fixed         |
|17 | river_with_pillars    | river          | fusion         | [x] fixed         |
|18 | ringed_columns        | column_hall    | cover_los      | [x] fixed         |
|19 | island_alcoves        | island         | fusion         | [x] fixed         |

---

## Pattern Reference

---

### 1. open_arena

**Family:** open · **Decision type:** kiting  
**Best biomes:** plain, ice  
**Doors supported:** 1–4

**Intent:** No internal terrain at all. Pure open combat — kiting and spacing
skill dominate. Used as an elite room baseline and fallback pattern.

**Target layout:**
```
####################
#..................#
#..................#
#..................#
#..................#
#..................#
D..................D
D..................D
D..................D
#..................#
#..................#
#..................#
#..................#
#..................#
####################
```

**Issues:** None — trivially correct by definition (function is empty).

**Status:** Verified OK — no changes made.

---

### 2. perimeter_ring

**Family:** open · **Decision type:** cover_los  
**Best biomes:** plain, mud  
**Doors supported:** 1–4

**Intent:** A single ring of rubble tiles placed 2 tiles inset from all four
walls. Enemies inside the ring can use it as cover from range; the player
outside must commit to entering through the narrow door-gap chokepoints. The
open courtyard inside the ring rewards kiting once the player has crossed in.

**Target layout (4 doors shown to illustrate full ring):**
```
#########DDD########
#..................#
#.XXXXXXXXXXXXXX.#
#.X............X.#
#.X............X.#
D...............X.D
D...............X.D  <- ring side has 3-tile gap aligned with door
D...............X.D
#.X............X.#
#.X............X.#
#.X............X.#
#.XXXXXXXXXXXXXX.#
#..................#
#........DDD......#
####################
```
*Note: each door side sees a gap of exactly 3 tiles in the ring (matching door
width). The ring should remain solid on all sides that have no door.*

**Issues:**
- `_door_buffer_mask(grid, doors, 2)` uses radius=2, which creates a
  5-row × 5-col cleared zone around each door. For left/right doors this
  destroys the entire vertical arm of the ring (rows 4–10 at cols 2 and 17),
  leaving only disconnected corner stubs.
- **Fix applied:** Moved ring inward to `ring=3`. At ring=3 the arm sits at
  col 3 and col 16, both outside the radius=2 door-buffer zone, so the full
  ring arm is placed. A manual 3-tile gap is then carved at each open door's
  centre tiles instead of relying on the buffer mask.

---

### 3. centre_pool_round

**Family:** centre_pool · **Decision type:** speed_safety  
**Best biomes:** water, mud  
**Doors supported:** 1–4

**Intent:** A circular hazard or rubble pool fills the room centre. Enemies
fight at the pool's edge; the player must choose between the slow (but safe)
wide arc around the pool, or the fast (but costly) straight route through
walkable hazard tiles.

**Target layout:**
```
####################
#..................#
#..................#
#......~~~~~......#
#.....~~~~~~~.....#
#....~~~~~~~~~....#
D....~~~~~~~~~....D
D....~~~~~~~~~....D
D....~~~~~~~~~....D
#....~~~~~~~~~....#
#.....~~~~~~~.....#
#......~~~~~......#
#..................#
#..................#
####################
```
*Pool radius ~5 tiles from centre; `~` = biome hazard (or `X` if plain biome).
The pool should visibly dominate the room — enemy chases cross the hazard zone.*

**Issues:**
- Pool radius formula: `max(2, min(rows,cols)//5 + int(0.4*density))`.
  For a 15×20 room: `max(2, 3 + 0) = 3` at depth 0. A 3-tile radius pool
  (diameter 6) is barely visible in a 20×15 room and does not create
  meaningful route decisions.
- **Fix applied:** Changed formula to `max(4, min(rows,cols)//3 + int(density*0.5))`
  → radius=5 at depth 0, scaling to 6 at max density.

---

### 4. centre_pool_oblong

**Family:** centre_pool · **Decision type:** speed_safety  
**Best biomes:** water, mud  
**Doors supported:** 2–4

**Intent:** Elliptical version of the centre pool. For left/right travel the
ellipse is tall (blocking the mid-lane vertically); for top/bottom travel it
is wide (blocking horizontally). Forces flanking routes to either side.

**Target layout (L+R doors → tall ellipse):**
```
####################
#..................#
#..................#
#.......~~~.......#
#......~~~~~......#
#......~~~~~......#
D......~~~~~......D
D......~~~~~......D
D......~~~~~......D
#......~~~~~......#
#......~~~~~......#
#.......~~~.......#
#..................#
#..................#
####################
```
*Ellipse is narrow east–west, tall north–south, forcing left/right players to
go above or below. With top/bottom doors the ellipse is wide, forcing left/right routes.*

**Issues:**
- Same small-pool problem as centre_pool_round: `rx, ry` base values of 2/4
  scaled by `0.8 + 0.3*density` yield very small ellipses at low depth.
- **Fix applied:** Changed base values to `rx=3, ry=4` (tall) / `rx=4, ry=3`
  (wide). Scale factor starts at 1.0 (never shrinks below base). rx/ry minimum
  is now 3 instead of 2.

---

### 5. choke_bridge_2gap

**Family:** choke_bridge · **Decision type:** lane  
**Best biomes:** water, mud  
**Doors supported:** 2–4

**Intent:** A large hazard/rubble pool covers the room centre. Two parallel
1-tile-wide floor bridges cross it. Players must commit to a bridge — each is
a genuine one-player-wide choke. The choice of bridge affects which part of
the far side they emerge on.

**Target layout (L+R doors → vertical bridges at cols 8 and 12):**
```
####################
#..................#
#...~~~~~~~~~~....#
#..~~~~~~~~~~~~...#
#..~~~~..~~~~.....#  <- bridge gaps at cols 8 and 12
#..~~~~..~~~~.....#
D..~~~~..~~~~.....D
D..~~~~..~~~~.....D
D..~~~~..~~~~.....D
#..~~~~..~~~~.....#
#..~~~~~~~~~~~~...#
#...~~~~~~~~~~....#
#..................#
#..................#
####################
```
*The two bridges should be exactly 1 tile wide, clearly visible, and span the
entire pool north-to-south. Pool should be large enough that going around it
through the hazard tiles is meaningfully costly.*

**Issues:**
- Pool radius has same undersizing problem (radius=3 at depth 0).
- Bridges at `cx±2` = cols 8 and 12 are correct but work only if the pool
  is wide enough to make them necessary. With a 3-tile radius pool the
  bridges fall mostly outside the pool.
- **Fix applied:** Pool radius uses same formula as centre_pool_round
  (`max(4, min(rows,cols)//3 + int(density*0.5))`). Bridges moved to `cx±3`
  (cols 7 and 13) giving a 6-tile wide pool section between the two bridges.

---

### 6. choke_bridge_winding

**Family:** choke_bridge · **Decision type:** lane  
**Best biomes:** water, mud  
**Doors supported:** 2–4

**Intent:** Large hazard pool identical in scale to choke_bridge_2gap, but
with a single narrow zigzag floor path through the pool instead of two
straight bridges. Taking the winding route is slow; going through the hazard
is fast but costly. Creates a speed-vs-safety trade-off across the pool.

**Target layout:**
```
####################
#..................#
#...~~~~~~~~~~....#
#..~~~~~~~~~~~~...#
#..~~~.~~~~~~~~...#  <- winding path: zig
#..~~~~.~~~~~~~...#
D..~~~~~.~~~~~~...D  <- zag
D..~~~~~~.~~~~~...D
D..~~~~~~~.~~~~...D
#..~~~~~~~~.~~~...#  <- zig
#..~~~~~~~~~.~~...#
#...~~~~~~~~~~....#
#..................#
#..................#
####################
```
*Single-tile wide; zigzags every 3 rows; visible enough that the player can
see the full route before committing.*

**Issues:**
- Same small-pool problem.
- The winding path `c_pos += rng.choice([-1, 1])` every 3 rows can drift
  outside the pool bounds, making the bridge invisible (the "carved" cell
  was never hazard to begin with).
- **Fix:** Increase pool radius using same formula as `centre_pool_round`
  (`max(4, min(rows,cols)//3 + int(density*0.5))`). Clamp `c_pos` to the
  **pool interior column range** `[cx - radius + 1, cx + radius - 1]`, not
  just the room walls `[2, cols-3]`. Clamping to room walls still allows the
  path to exit the pool boundary, making carved cells that were never hazard
  (the bridge becomes invisible). Pool-interior clamping guarantees every
  cleared cell was a hazard tile.

---

### 7. parallel_lanes

**Family:** lane_split · **Decision type:** lane  
**Best biomes:** plain, ice  
**Doors supported:** 1–4

**Intent:** Two 2-tile-thick strips of rubble/hazard divide the room into
three parallel lanes. For left/right doors the strips run vertically at 1/3
and 2/3 of the room width. Players commit to a lane and pay a movement cost
to switch. Enemies in different lanes require repositioning.

**Target layout (L+R doors → vertical strips):**
```
####################
#..................#
#.....XX....XX....#
#.....XX....XX....#
#.....XX....XX....#
#.....XX....XX....#
D.....XX....XX....D
D.....XX....XX....D
D.....XX....XX....D
#.....XX....XX....#
#.....XX....XX....#
#.....XX....XX....#
#.....XX....XX....#
#..................#
####################
```
*Strips span the full interior height (rows 2–12) and are exactly 2 tiles
wide, at cols 6–7 and 13–14. Three clear lanes of ~4 tiles width each.*

**Issues:** Minor — current code places strips at `cols//3` = 6 and
`2*cols//3` = 13, which is correct. The strips stop 2 rows from top/bottom
walls (`range(2, rows-2)`), leaving thin floor gaps at the ends. The strips
should extend to 1 row from each wall edge for a clean look.

**Fix:** Change vertical strip loop from `range(2, rows - 2)` to
`range(1, rows - 1)` (and horizontal equivalent). This extends each strip
to flush with the interior wall row/column while still staying inside the
wall tile itself.

---

### 8. fork_split

**Family:** lane_split · **Decision type:** lane  
**Best biomes:** plain, ice  
**Doors supported:** 2–4

**Intent:** A V-shaped (wedge) rubble formation with its apex near the entry
door and its arms spreading apart toward the far end. Players see an open
corridor at entry that forks into two distinct lanes mid-room. Encourages
scouting the fork to see where enemies are before committing.

**Target layout (L+R doors → V opens left, arms spread rightward):**
```
####################
#..................#
#..................#
#.........X.......#
#.......XXX.......#
#......XXXX.......#
D.....XXXXX.......D  <- upper arm
D..................D  <- open lane at centre (apex zone)
D.....XXXXX.......D  <- lower arm (mirrored)
#......XXXX.......#
#.......XXX.......#
#.........X.......#
#..................#
#..................#
####################
```
*Arms span rows 3–5 and 9–11 (above and below mid). They grow 1 tile wider per
2 columns. A clear floor lane remains at the room centre-row (row 7) all the
way across.*

**Issues:**
- Current spread only grows from 1 to 2 (not from 0 to ~4), so the fork is
  barely visible — it looks like two tiny blobs, not a V.
- The apex is placed at `cx` (col 10, halfway across) when it should be
  placed near the entry (col 3–4) so the fork spans most of the room.
- **Fix:** Start arm placement at `c = 3` (near entry), set `spread` to grow
  from 0 to `rows//2 - 3` linearly across `cols//2` steps, so arms fan out
  from a true point. Concretely: `arm_steps = cols//2 - 2`; iterate
  `step in range(arm_steps)` with `c = 3 + step`; `spread = (step * (rows//2 - 3)) // max(1, arm_steps - 1)`.
  Mirror logic applies for top/bottom door orientation using `r = 3 + step`.

---

### 9. column_hall_grid

**Family:** column_hall · **Decision type:** cover_los  
**Best biomes:** plain, ice  
**Doors supported:** 1–4

**Intent:** A regular grid of 2×2 rubble column clusters spaced evenly across
the interior. Provides consistent sightline breaks in all directions. Classic
column-hall feel — peeking around corners and angling shots through gaps.

**Target layout:**
```
####################
#..................#
#..................#
#..XX...XX...XX...#
#..XX...XX...XX...#
#..................#
D..XX...XX...XX...D
D..XX...XX...XX...D
D..................D
#..XX...XX...XX...#
#..XX...XX...XX...#
#..................#
#..................#
#..................#
####################
```
*3 columns × 3 rows of 2×2 clusters, evenly spaced (step ~5 cols, ~4 rows).
Clear aisles between every cluster in all four directions.*

**Issues:**
- Current code: `col_step=4, row_step=3`. For 20 cols and 15 rows this places
  clusters at cols 3,7,11,15 and rows 3,6,9,12 → 4×4 = 16 clusters. That is
  far too dense and claustrophobic.
- **Fix:** Change to `col_step=5, row_step=4` and reduce to 3×3 clusters
  (cols 4,9,14 and rows 3,7,11). Clear 2-tile aisles between every cluster.

---

### 10. column_hall_offset

**Family:** column_hall · **Decision type:** cover_los  
**Best biomes:** plain, ice  
**Doors supported:** 1–4

**Intent:** Same 2×2 clusters as column_hall_grid but with alternating rows
shifted by half a column period. Eliminates straight sightlines in any
direction; every angle through the room crosses behind at least one column.
Forces diagonal repositioning.

**Target layout:**
```
####################
#..................#
#..................#
#..XX.....XX......#   <- row A offset
#..XX.....XX......#
#..................#
D.....XX.....XX...D   <- row B shifted ~2-3 cols
D.....XX.....XX...D
D..................D
#..XX.....XX......#   <- row A repeats
#..XX.....XX......#
#..................#
#..................#
#..................#
####################
```
*Clusters in alternating rows are offset by ~2.5 cols so no straight line
through the room avoids all cover.*

**Issues:**
- Same density problem as column_hall_grid (too many clusters).
- Same fix: `col_step=5, row_step=4`, offset = `col_step // 2` = 2–3 cols.

---

### 11. alcove_pockets

**Family:** alcove · **Decision type:** mobility_tax  
**Best biomes:** plain, mud, ice, water (neutral)  
**Doors supported:** 1–4

**Intent:** Small 2×3 rubble pockets tucked into the walls at quarter-wall
positions — two per wall side, eight total. Natural kiting spots and retreat
corners. Players can duck into a pocket to break line-of-sight and recover,
but the pocket traps them momentarily (mobility tax).

**Target layout:**
```
####################
#..................#
#.XXX..........XXX#
#.XXX..........XXX#
#..................#
#..................#
D..................D
D..................D
D..................D
#..................#
#..................#
#.XXX..........XXX#
#.XXX..........XXX#
#..................#
####################
```
*2×3 pockets flush against the corner walls, with clear floor between. Left-wall
pockets placed at rows 2–3 and 11–12, cols 2–3. Right-wall pockets mirrored.
Top and bottom wall pockets at cols 4–5 and 14–15, rows 2–3.*

**Issues:**
- Current pocket coords use `q1c = cols//4 = 5`, `q2c = 3*cols//4 = 15`.
  The pockets are small (2×3) but placed mid-wall rather than at corners,
  so they feel disconnected from the room edges.
- Top/bottom pockets (`q1r-1, 2` etc.) use row coords that may overlap the
  buffer zone for left/right doors.
- **Fix:** Move pockets to true corners: rows 2–3 and 11–12, cols 2–4 and
  15–17. Remove the mid-wall side pockets; replace with 4 corner pockets only
  (cleaner and more impactful).

---

### 12. fortress_courtyard

**Family:** alcove · **Decision type:** mobility_tax  
**Best biomes:** plain (highest)  
**Doors supported:** 1–4 (min 11×11 room)

**Intent:** A thick 2-tile rubble ring starting 2 tiles inset from the outer
wall, with gaps only at door positions. Creates a fortress perimeter — enemies
can be behind the wall or in the open courtyard. Entry is funnelled through
tight doorway gaps in the wall.

**Target layout (4 doors shown):**
```
#########DDD########
#..................#
#.XXXXXXXXXXXXXX.#
#.XXXXXXXXXXXXXX.#
#.XX..........XX.#
D...............X.D
D...............X.D
D...............X.D
#.XX..........XX.#
#.XXXXXXXXXXXXXX.#
#.XXXXXXXXXXXXXX.#
#..................#
#........DDD......#  <- (row 12 bottom segment shown compressed)
#..................#
####################
```
*The ring is 2 tiles thick (rows 2–3 and 11–12, cols 2–3 and 16–17). The
courtyard interior (rows 4–10, cols 4–15) is fully open. Gaps in the ring are
exactly door-width (3 tiles).*

**Issues:**
- Same buffer problem as perimeter_ring — `_door_buffer_mask(radius=2)` makes
  5-tile-wide holes in the ring instead of 3-tile door-width gaps.
- The inner courtyard is small: `inner=4` means the open centre is
  rows 4–10, cols 4–15 (7 rows × 12 cols). With the buffer also clearing the
  ring near doors, the ring is almost entirely gone.
- **Fix:** Use `radius=0` for the ring fill and manually carve 3-tile gaps
  at each open door direction (matching door rows/cols exactly).

---

### 13. mire_carpet

**Family:** hazard_field · **Decision type:** mobility_tax  
**Best biomes:** mud (9), water (7)  
**Doors supported:** 1–4

**Intent:** Dense walkable hazard tiles fill 65–85% of the interior. Carved
1-tile-wide stepping-stone floor paths connect each door to the room centre.
Players on the stone path are safe but slow to dodge; stepping off into the
mire costs movement. Enemies in the mire are slowed too — encourages the
player to hold the path and let enemies wade to them.

**Target layout:**
```
####################
#..................#
#.~~~~~~~~~~~~~~~~#
#.~~~~~~~~~~~~~~~~#
#.~~~~.~~~~~.~~~~~#  <- carved centre path runs col 9–10 vertically
#.~~~~.~~~~~.~~~~~#
D.....~~~~~.......D  <- H path from L door to centre; V path from centre up
D.~~~~.....~~~~~~~D  <- centre cleared (+1 tile around join)
D.~~~~.~~~~~......D  <- H path continues to R door
#.~~~~.~~~~~.~~~~~#
#.~~~~.~~~~~.~~~~~#
#.~~~~~~~~~~~~~~~~#
#.~~~~~~~~~~~~~~~~#
#..................#
####################
```
*Stone paths are 1 tile wide and BFS-straight. The room should feel like
navigating a bog with a single known safe route.*

**Issues:** Functionally correct but the carved BFS paths can look jagged and
narrow. With 1-tile paths the player has almost no room to manoeuvre on the
path and tiny offset causes hazard contact. Consider widening paths to 2 tiles
and adding a small (~3×3) cleared zone at the path intersection.

**Fix:** After carving the BFS path, make a second pass over each path cell
and clear one additional neighbour perpendicular to the dominant travel
direction (horizontal paths: also clear `(pc, pr+1)`; vertical paths: also
clear `(pc+1, pr)`). Then clear a 3×3 area centred on the room centre
`(cols//2, rows//2)` after all paths are carved. This keeps the hazard-
dominant feel while giving the player a genuine lane width to dodge within.

---

### 14. terrain_minefield

**Family:** hazard_field · **Decision type:** mobility_tax  
**Best biomes:** mud, ice  
**Doors supported:** 1–4

**Intent:** Scattered individual hazard tiles at 12–35% density across the
interior. No large clusters — individual tiles punish careless movement and
force footwork awareness without completely blocking any route. Density scales
with room depth.

**Target layout (medium density shown):**
```
####################
#..................#
#...~....~....~...#
#.....~......~....#
#..~....~.........#
#......~....~.....#
D......~...~......D
D..................D
D....~.....~......D
#..~......~.......#
#.....~.......~...#
#.......~...~.....#
#...~.........~...#
#..................#
####################
```
*Individual tiles, no clusters of 2+. Evenly scattered across the interior,
never adjacent to another hazard tile.*

**Issues:** Current code uses `rng.shuffle(interior)` which is seeded from
door configuration, so the same door layout always produces the same scattered
pattern. The shuffle is consistent (good for soak tests) but visually uniform.
Additionally, the intent states tiles should be "never adjacent to another
hazard tile" but the code places tiles purely by count with no adjacency check.

**Fix:** After selecting the tile list, add a placement guard: skip any tile
`(c, r)` whose four orthogonal neighbours already contain a hazard tile.
This enforces the no-clusters intent. The seeded RNG is already correct;
adjacency enforcement may reduce the placed count slightly below `count` but
the visual effect is cleaner.

---

### 15. island_cluster_dense

**Family:** island · **Decision type:** kiting  
**Best biomes:** plain, ice  
**Doors supported:** 1–4

**Intent:** Five compact 2×2 rubble islands distributed across the interior
with ~2-tile separation between islands. Leap-frog cover — players dash from
island to island while kiting enemies. Short range engagements around the
islands' edges.

**Target layout:**
```
####################
#..................#
#....XX...........#
#....XX...........#
#..................#
#.........XX......#
D.....XX..XX......D
D.....XX..........D
D.............................#  <- approximate
#..........XX.....#
#..........XX.....#
#......XX.........#
#......XX.........#
#..................#
####################
```
*5 islands of 2×2, spaced at least 4 tiles apart in both axes. Spread across
the full interior — not clustered in one quadrant.*

**Issues:** Placement range `range(3, cols-4-island_sz)` = `range(3, 14)` ×
`range(3, rows-4-island_sz)` = `range(3, 9)`. This restricts islands to a
14×9 sub-area — they never appear in the lower half or right side of the room.
The minimum separation check `island_sz+2 = 4` is sufficient.

**Fix:** Expand placement range to full interior: `range(2, cols-3)` ×
`range(2, rows-3)` (keeping a 2-tile margin from walls). Additionally,
consider a **quadrant-seeded** placement strategy: divide the interior into
5 sub-zones (NW, NE, SW, SE, and a centre band) and seed one island attempt
per zone before falling back to random retries. This guarantees islands are
distributed across the room rather than clustering in a random region.

---

### 16. island_cluster_sparse

**Family:** island · **Decision type:** kiting  
**Best biomes:** ice (8), plain  
**Doors supported:** 1–4 (min 11×11)

**Intent:** Three large 3×4 rubble islands spread far apart. Long open dashes
between cover create high-risk moments — every move between islands exposes
the player for multiple seconds. Forces deliberate, committed repositioning.

**Target layout:**
```
####################
#..................#
#.XXX.............#
#.XXX.............#
#.XXX.............#
#.XXX.............#
D..........XXX....D
D..........XXX....D
D..........XXX....D
D..........XXX....D
#..................#
#.................#
#...............XXX#
#...............XXX#
####################
```
*3 islands of 3×4. One near top-left, one near centre, one near bottom-right.
Each separated by 6+ tiles so crossing between them is a significant decision.*

**Issues:** Placement range `range(3, 13)` × `range(3, 8)` restricts islands
to a 10×5 sub-area — they can never be in the lower half.

**Fix:** Same range expansion as `island_cluster_dense`: `range(2, cols-3)` ×
`range(2, rows-3)`. For sparse islands a diagonal seeding strategy works
well: seed one attempt each near the top-left corner, room centre, and
bottom-right corner, then fall back to random retries. This matches the
target layout sketch (top-left / centre / bottom-right island positions)
without requiring hundreds of random retries to land in spread positions.

---

### 17. river_with_pillars

**Family:** river · **Decision type:** fusion  
**Best biomes:** water (9), mud, ice  
**Doors supported:** 2–4

**Intent:** A 3-tile-wide walkable hazard river bisects the room perpendicular
to the main travel axis. Four single rubble pillar tiles flank the river as
mid-stream cover. Players must cross the river (taking hazard cost) with no
dry bridge. The pillars provide momentary mid-river cover during the crossing.

**Target layout (L+R doors → vertical river at cols 9–11):**
```
####################
#........~~~......#
#........~~~......#
#...X....~~~....X.#   <- pillars at rows 3 and 11, cols 4 and 15
#........~~~......#
#........~~~......#
D........~~~......D
D........~~~......D
D........~~~......D
#........~~~......#
#........~~~......#
#...X....~~~....X.#
#........~~~......#
#........~~~......#
####################
```
*River runs full room height (rows 1–13). Four pillar tiles at cols 4 and 15,
rows 3 and 11. Door buffer prevents river tiles from blocking door entrances.*

**Issues:**
- Pillar positions are `cx±3` = 7 and 13, which land very close to the river
  (river is at cols 9–11, pillar at col 7 = 2 tiles from river edge). That is
  too close — pillars should be at cols 4–5 and 14–15 so they're mid-lane, not
  hugging the river.
- Pillar row positions `rows//4, rows//2, 3*rows//4` = 3, 7, 11. The row 7
  pillar falls in the door buffer zone (rows 6–8) and gets skipped. Only 2 of
  3 pillar pairs actually appear.
- **Fix:** Move pillars to `cx±5` (cols 5 and 15). Use row positions 3 and 11
  only (2 pairs = 4 pillars total; the mid-row pillar is always blocked anyway).

---

### 18. ringed_columns

**Family:** column_hall · **Decision type:** cover_los  
**Best biomes:** plain, ice  
**Doors supported:** 1–4 (min 11×11)

**Intent:** Two concentric rings of sparse single rubble tiles at Chebyshev
radii 3 and 5 from the room centre. Layered cover — the inner ring for
close-range fights, the outer ring for long-range anchoring. Diagonal
sightlines exist everywhere; no straight lane crosses through the room without
passing near cover.

**Target layout:**
```
####################
#..................#
#..X...X...X...X..#   <- outer ring (radius 5) sparse tiles
#...X.........X...#
#.X...........X...#
#....X.....X......#   <- inner ring (radius 3)
D.....X...X.......D
D......X.X........D   <- rings converge near centre
D.....X...X.......D
#....X.....X......#
#.X...........X...#
#...X.........X...#
#..X...X...X...X..#
#..................#
####################
```
*Inner ring (radius 3): approx 12–16 sparse tiles. Outer ring (radius 5):
approx 20–28 sparse tiles. Every other tile around each ring is placed
(`(dr+dc)%2 == 0` condition), leaving clear gaps for movement.*

**Issues:**
- For a 20×15 room with centre (10, 7), the outer ring at radius 5 extends to
  rows 2–12, cols 5–15. That fits fine. But the inner ring at radius 3
  extends to rows 4–10, cols 7–13. With L/R door buffer (clears rows 5–9 near
  cols 7–13), a large fraction of the inner ring is masked away.
- Result: inner ring has only corner tiles visible; the concentric ring effect
  is nearly invisible.
- **Fix:** Use `_door_buffer_mask(grid, doors, 1)` (radius=1) for this
  pattern specifically. A 1-tile buffer clears only the 3 door opening tiles
  themselves, leaving the inner ring intact at all non-door positions. The
  soak test's door-buffer-clear detector uses a 1-tile margin so this still
  passes. Alternatively, skip the buffer entirely and rely on
  `_ensure_connectivity` to verify path connectivity after ring placement.

---

### 19. island_alcoves

**Family:** island · **Decision type:** fusion  
**Best biomes:** ice, water  
**Doors supported:** 1–4 (min 11×11)

**Intent:** Hybrid layout — a central 4×4 rubble island dominates the middle
of the room, plus four 2×2 corner alcoves. The central island forces enemies
and player to orbit; the corner alcoves are retreat or ambush positions that
reward map awareness.

**Target layout:**
```
####################
#..................#
#.XX...........XX.#   <- corner alcoves (2×2) at rows 2–3
#.XX...........XX.#
#..................#
#......XXXX.......#   <- central island (4×4)
D......XXXX.......D
D......XXXX.......D
D......XXXX.......D
#..................#
#..................#
#.XX...........XX.#   <- corner alcoves (2×2) at rows 11–12
#.XX...........XX.#
#..................#
####################
```
*Central island is 4×4 at rows 5–8, cols 7–10 (offset slightly right of true
centre to compensate for left-entry bias). Corner alcoves are 2×2, flush in
each corner at row/col 2–3.*

**Issues:**
- Central island `_fill_rect(cy-2, cx-2, cy+1, cx+1)` = rows 5–8, cols 8–11.
  That is correct for a 20×15 room.
- Corner alcove coords `(2, 2, 3, 3)` etc. place the alcoves at rows 2–3,
  cols 2–3 which is correct.
- Potential issue: corner alcoves may be cut by the door buffer when doors are
  on left/right (the buffer clears cols 0–2 at rows 5–9), which means the left
  column (col 2) of the top-left and bottom-left alcoves may be cleared.
- **Fix:** Move corner alcoves inward by 1 tile: rows 2–3, cols 3–4 and 15–16.

---

## Notes

- All patterns are tested by `tests/test_terrain_soak.py` (1000 rooms per biome).
  The soak test verifies: wall intact, door buffer clear, doors connected,
  valid tiles, rubble ≤50%, center walkable, accent presence. Passing the soak
  test does NOT guarantee the pattern looks correct — it only checks structural
  validity.
- Use the **Terrain Layout Test** submenu (Room Tests → Terrain Layout Test) to
  visually inspect each pattern with any biome and door count.
- When a pattern is fixed, mark it `[x]` in the Status Summary and add a brief
  fix note under **Issues** in the relevant section.
