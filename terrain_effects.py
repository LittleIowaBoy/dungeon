"""Per-frame tile-effect dispatcher for biome-room hazard tiles.

Phase 1 of the biome-room expansion introduces several walkable hazard
tiles (``QUICKSAND``, ``SPIKE_PATCH``, ``PIT_TILE``, ``CURRENT``, etc.).
This module owns the runtime side of those tiles: every frame, after
:meth:`Player.update`, the runtime calls :func:`apply_terrain_effects`
which inspects the tile under the player's center and triggers the
appropriate effect (tick damage, drowning, push, lethal-on-step).

Effects are deliberately simple and additive to existing movement.  More
complex hazards (cave-in, thin-ice collapse, tremors) are implemented as
telegraphed entities in :mod:`objective_entities` — not here.
"""
from settings import (
    HAZARD_TICK_MS, HAZARD_TICK_DAMAGE, STALAGMITE_STEP_DAMAGE,
    QUICKSAND_PULL_SPEED, CURRENT_PUSH_SPEED, TILE_SIZE,
    WATER_SUBMERSION_DELAY_MS, WATER_SUBMERSION_TICK_MS, WATER_SUBMERSION_TICK_DAMAGE,
    ENEMY_CURRENT_PUSH_FACTOR,
    THIN_ICE_STEPS_TO_CRACK, THIN_ICE_RESPAWN_MS,
    PIT_FALL_SLIDE_MS, PIT_FALL_SHRINK_MS, PIT_FALL_PAUSE_MS,
    PIT_FALL_ANIM_TOTAL_MS, PIT_FALL_RESPAWN_IFRAMES_MS, PIT_FALL_HP_PENALTY,
)


def apply_terrain_effects(player, room, now_ticks, dt_ms):
    """Run per-tile effects for the player.

    Parameters
    ----------
    player : Player
        Live player instance.  Must expose ``rect``, ``current_hp``,
        ``take_damage(int)`` and ``is_invincible`` (read-only).
    room : Room
        Current room.  Reads tile via ``room.tile_at`` / ``terrain_at_pixel``
        and current-vector data via ``room.current_vector_at_pixel``.
    now_ticks : int
        ``pygame.time.get_ticks()`` value for this frame.
    dt_ms : int
        Frame delta in milliseconds (used by the drowning timer).

    Returns
    -------
    dict
        Diagnostics for tests/HUD (``{"tile": str, "quicksand_pull": bool,
        "tick_damage": int, "pushed": bool}``).  Stable contract.
    """
    diag = {
        "tile": "floor",
        "quicksand_pull": False,
        "tick_damage": 0,
        "pushed": False,
        "submerged": False,
        "thin_ice_cracked": False,
        "pit_fall_triggered": False,
    }
    if room is None or player is None:
        return diag

    # Lazy import to avoid circular dependency (room imports from settings,
    # this imports from settings; player.py would create the cycle).
    from room import (
        QUICKSAND, SPIKE_PATCH, PIT_TILE, CURRENT, WATER, THIN_ICE,
        SLIDE, TRAIL_FREEZE,
    )

    tile = room.terrain_at_pixel(player.rect.centerx, player.rect.centery)
    diag["tile"] = tile
    invincible = bool(getattr(player, "is_invincible", False))

    # Per-tile transition tracking.  Computed up-front so all branches
    # share a single source of truth and so the previous-tile pointer is
    # advanced exactly once per frame.
    cur_tile_coord = (
        int(player.rect.centerx) // TILE_SIZE,
        int(player.rect.centery) // TILE_SIZE,
    )
    prev_tile_coord = getattr(room, "_previous_player_tile", None)
    stepped_to_new_tile = (
        prev_tile_coord is not None and prev_tile_coord != cur_tile_coord
    )
    # Always advance the pointer for next frame, regardless of which
    # branches below early-return.
    room._previous_player_tile = cur_tile_coord

    # Reset the submersion timer whenever the player is NOT on a WATER tile
    # so leaving the pool immediately cancels any in-progress drowning.
    if tile != WATER:
        room._water_entry_ticks = None

    # ── SLIDE: direction-commitment tile ──────────────────────────────────
    # When the player first steps ONTO a SLIDE tile their current velocity
    # direction is recorded.  movement_rules.py reads ``player._slide_committed``
    # to override input until the player leaves the tile or dodges.
    # Clearing the committed flag here (when no longer on SLIDE) ensures
    # movement rules resume normally on the first non-slide frame.
    if tile == SLIDE:
        if not getattr(player, "_on_slide", False):
            # Just stepped onto a slide tile — record committed direction from
            # current velocity; movement_rules will lock to this direction.
            vx = getattr(player, "velocity_x", 0.0)
            vy = getattr(player, "velocity_y", 0.0)
            mag = (vx * vx + vy * vy) ** 0.5
            if mag > 0:
                player._slide_dir = (vx / mag, vy / mag)
            else:
                player._slide_dir = None   # no velocity — no lock
            player._on_slide = True
    else:
        # Left slide — clear committed state.
        player._on_slide = False
        player._slide_dir = None

    # ── TRAIL_FREEZE: walkable until expiry ───────────────────────────────
    # TRAIL_FREEZE tiles are ordinary floor while fresh.  advance_trail_freeze_tiles
    # (called from the game loop) converts them to PIT_TILE when their timer
    # expires; the pit-fall animation then fires normally on the next frame.
    # No per-frame effect here; only clear the "on slide" state if somehow
    # the player is on TRAIL_FREEZE (already handled above since tile != SLIDE).

    # ── THIN_ICE: cracking tile mechanic ─────────────────────────────────
    # Each time the player steps ONTO a new THIN_ICE tile, a per-tile
    # step counter on the room is incremented.  Once the counter for a
    # tile reaches THIN_ICE_STEPS_TO_CRACK, the tile collapses to
    # PIT_TILE.  The crack timestamp (room._thin_ice_crack_times) is
    # stored so advance_thin_ice_respawn() can regenerate the tile after
    # THIN_ICE_RESPAWN_MS.
    if tile == THIN_ICE and stepped_to_new_tile:
        counts = getattr(room, "_thin_ice_step_counts", None)
        if counts is None:
            room._thin_ice_step_counts = {}
            counts = room._thin_ice_step_counts
        counts[cur_tile_coord] = counts.get(cur_tile_coord, 0) + 1
        if counts[cur_tile_coord] >= THIN_ICE_STEPS_TO_CRACK:
            col, row = cur_tile_coord
            room.grid[row][col] = PIT_TILE
            diag["thin_ice_cracked"] = True
            # Track total pit collapses for the Intact Floor bonus.
            room._thin_ice_pits_created = getattr(room, "_thin_ice_pits_created", 0) + 1
            # Record when this tile cracked so it can respawn later.
            crack_times = getattr(room, "_thin_ice_crack_times", None)
            if crack_times is None:
                room._thin_ice_crack_times = {}
            room._thin_ice_crack_times[cur_tile_coord] = now_ticks
            # Trigger the pit fall animation instead of instant death.
            if not invincible:
                _start_pit_fall(player, col, row, prev_tile_coord, now_ticks)
                diag["pit_fall_triggered"] = True
            return diag

    # ── PIT_TILE: trigger fall animation (or skip if already falling / invincible)
    if tile == PIT_TILE:
        if not invincible and getattr(player, "_pit_fall_phase", None) is None:
            pit_col, pit_row = cur_tile_coord
            _start_pit_fall(player, pit_col, pit_row, prev_tile_coord, now_ticks)
            diag["pit_fall_triggered"] = True
        return diag

    # ── QUICKSAND: pull toward tile centre ─────────────
    # Each frame the player stands on a quicksand tile, push them a small
    # amount toward the tile's pixel centre.  Combined with the slow
    # ``TERRAIN_SPEED['quicksand']`` multiplier this creates a sticky
    # "trap" feel: standing still drifts the player into the centre of
    # the patch and ordinary movement is too slow to escape.
    #
    # Pull is suppressed while the player is invincible (dodge / spawn
    # i-frames) so the dodge ability always wins the tug-of-war — this
    # is the intended escape mechanic ("mash dodge to break free").
    if tile == QUICKSAND:
        if not invincible:
            cx, cy = cur_tile_coord
            tile_cx = cx * TILE_SIZE + TILE_SIZE // 2
            tile_cy = cy * TILE_SIZE + TILE_SIZE // 2
            dx = tile_cx - player.rect.centerx
            dy = tile_cy - player.rect.centery
            mag = (dx * dx + dy * dy) ** 0.5
            if mag > 0.5:
                pull_x = (dx / mag) * QUICKSAND_PULL_SPEED
                pull_y = (dy / mag) * QUICKSAND_PULL_SPEED
                _push_player(player, room, pull_x, pull_y)
                diag["quicksand_pull"] = True
        return diag

    # ── SPIKE_PATCH: per-tile-entry damage ─────────────────
    # Damage fires only on the frame the player moves ONTO a new spike
    # tile.  Standing motionless on a spike tile and stepping OFF a
    # spike tile do not deal damage.  Walking from one spike tile to
    # an adjacent spike tile does damage on the transition (each
    # "step onto" is its own event).
    if tile == SPIKE_PATCH:
        if stepped_to_new_tile and not invincible:
            player.take_damage(STALAGMITE_STEP_DAMAGE)
            diag["tick_damage"] = STALAGMITE_STEP_DAMAGE

    # ── CURRENT: directional push (additive to movement) ───
    if tile == CURRENT:
        vec = room.current_vector_at_pixel(player.rect.centerx, player.rect.centery)
        if vec is not None:
            dx, dy = vec
            mag = (dx * dx + dy * dy) ** 0.5
            if mag > 0:
                push_x = (dx / mag) * CURRENT_PUSH_SPEED
                push_y = (dy / mag) * CURRENT_PUSH_SPEED
                _push_player(player, room, push_x, push_y)
                diag["pushed"] = True

    # ── WATER: submersion hazard ────────────────────────────────────────────
    # The speed slow-down is handled by TERRAIN_SPEED in movement_rules.
    # Here we track how long the player has stood in water; after
    # WATER_SUBMERSION_DELAY_MS, we fire a damage tick every
    # WATER_SUBMERSION_TICK_MS.  Invincibility (dodge i-frames) suppresses
    # each individual tick so dodging through pools is always safe.
    if tile == WATER:
        if getattr(room, "_water_entry_ticks", None) is None:
            room._water_entry_ticks = now_ticks
            room._water_next_tick_ms = now_ticks + WATER_SUBMERSION_DELAY_MS
        if now_ticks >= getattr(room, "_water_next_tick_ms", 0):
            diag["submerged"] = True
            if not invincible:
                player.take_damage(WATER_SUBMERSION_TICK_DAMAGE)
                diag["tick_damage"] = WATER_SUBMERSION_TICK_DAMAGE
            room._water_next_tick_ms = now_ticks + WATER_SUBMERSION_TICK_MS

    return diag


def apply_current_to_enemies(enemies, room, now_ticks):
    """Push enemies standing on CURRENT tiles in the current direction.

    Called once per frame from the runtime after enemy movement so that
    enemies in river rooms are swept downstream just like the player, but
    at a reduced magnitude (ENEMY_CURRENT_PUSH_FACTOR × CURRENT_PUSH_SPEED).
    Frozen enemies and enemies with active immobilise status are skipped so
    freeze mechanics still lock enemies in place.
    """
    import status_effects as _se
    from room import CURRENT

    walls = room.get_wall_rects()
    for enemy in list(enemies):
        if getattr(enemy, "is_frozen", False):
            continue
        if _se.is_immobilized(enemy, now_ticks):
            continue
        vec = room.current_vector_at_pixel(enemy.rect.centerx, enemy.rect.centery)
        if vec is None:
            continue
        dx, dy = vec
        mag = (dx * dx + dy * dy) ** 0.5
        if mag <= 0:
            continue
        push_x = (dx / mag) * CURRENT_PUSH_SPEED * ENEMY_CURRENT_PUSH_FACTOR
        push_y = (dy / mag) * CURRENT_PUSH_SPEED * ENEMY_CURRENT_PUSH_FACTOR
        # X axis
        if push_x:
            enemy.rect.x += int(round(push_x))
            for wall in walls:
                if enemy.rect.colliderect(wall):
                    if push_x > 0:
                        enemy.rect.right = wall.left
                    else:
                        enemy.rect.left = wall.right
                    break
        # Y axis
        if push_y:
            enemy.rect.y += int(round(push_y))
            for wall in walls:
                if enemy.rect.colliderect(wall):
                    if push_y > 0:
                        enemy.rect.bottom = wall.top
                    else:
                        enemy.rect.top = wall.bottom
                    break


def _push_player(player, room, dx, dy):
    """Move the player by (dx, dy), respecting wall collisions.

    Used by CURRENT tiles.  Splits the push into axis-aligned steps so
    a wall on one axis doesn't block movement on the other.
    """
    walls = room.get_wall_rects()
    # X axis.
    if dx:
        player.rect.x += int(round(dx))
        for wall in walls:
            if player.rect.colliderect(wall):
                if dx > 0:
                    player.rect.right = wall.left
                else:
                    player.rect.left = wall.right
                break
    # Y axis.
    if dy:
        player.rect.y += int(round(dy))
        for wall in walls:
            if player.rect.colliderect(wall):
                if dy > 0:
                    player.rect.bottom = wall.top
                else:
                    player.rect.top = wall.bottom
                break


# ── Pit fall animation helpers ───────────────────────────────────────────────

def _start_pit_fall(player, pit_col, pit_row, prev_tile_coord, now_ticks):
    """Arm the pit fall animation on *player*.

    Records the pit tile, the entry tile (used as the respawn candidate), and
    the player's current pixel position (used as the slide start point).
    Sets ``_invincible_until`` to cover the entire animation so damage is
    blocked for the full fall duration.
    """
    player._pit_fall_phase = "falling"
    player._pit_fall_started_at = now_ticks
    player._pit_fall_pit_col = pit_col
    player._pit_fall_pit_row = pit_row
    player._pit_fall_start_x = player.rect.centerx
    player._pit_fall_start_y = player.rect.centery
    player._pit_fall_shrink_t = 0.0
    # Record where the player came from so we can respawn them there.
    if prev_tile_coord is not None and prev_tile_coord != (pit_col, pit_row):
        player._pit_entry_col, player._pit_entry_row = prev_tile_coord
    else:
        # No previous-tile data available — default to the tile above the pit.
        player._pit_entry_col = pit_col
        player._pit_entry_row = max(0, pit_row - 1)
    # Cover the entire animation with i-frames so enemies / hazards cannot
    # deal additional damage while the player is helplessly falling.
    player._invincible_until = now_ticks + PIT_FALL_ANIM_TOTAL_MS


def advance_pit_fall_animation(player, room, now_ticks):
    """Drive one frame of the pit fall state machine.

    Must be called every frame while ``player._pit_fall_phase is not None``.
    Returns ``True`` while the animation is running, ``False`` once it has
    finished (phase reset to ``None`` after respawn completes).

    Animation phases:
    - "falling"  : player slides to the pit tile center over PIT_FALL_SLIDE_MS.
    - "shrinking": sprite shrinks (visual handled by player_visual_rules) over
                   PIT_FALL_SHRINK_MS.  Player position is locked to pit center.
    - "pause"    : player is fully shrunk and invisible for PIT_FALL_PAUSE_MS
                   before the respawn fires.
    """
    phase = getattr(player, "_pit_fall_phase", None)
    if phase is None:
        return False

    elapsed = now_ticks - player._pit_fall_started_at
    pit_cx = player._pit_fall_pit_col * TILE_SIZE + TILE_SIZE // 2
    pit_cy = player._pit_fall_pit_row * TILE_SIZE + TILE_SIZE // 2

    if phase == "falling":
        t = min(1.0, elapsed / PIT_FALL_SLIDE_MS)
        sx, sy = player._pit_fall_start_x, player._pit_fall_start_y
        player.rect.centerx = int(sx + (pit_cx - sx) * t)
        player.rect.centery = int(sy + (pit_cy - sy) * t)
        if elapsed >= PIT_FALL_SLIDE_MS:
            player._pit_fall_phase = "shrinking"
            player._pit_fall_started_at = now_ticks

    elif phase == "shrinking":
        player._pit_fall_shrink_t = min(1.0, elapsed / PIT_FALL_SHRINK_MS)
        # Lock position to pit center throughout the shrink.
        player.rect.centerx = pit_cx
        player.rect.centery = pit_cy
        if elapsed >= PIT_FALL_SHRINK_MS:
            player._pit_fall_shrink_t = 1.0
            player._pit_fall_phase = "pause"
            player._pit_fall_started_at = now_ticks

    elif phase == "pause":
        # Player is fully invisible — wait for the pause window then respawn.
        if elapsed >= PIT_FALL_PAUSE_MS:
            _complete_pit_respawn(player, room, now_ticks)

    return player._pit_fall_phase is not None


def _complete_pit_respawn(player, room, now_ticks):
    """Teleport the player to the best nearby non-pit tile and grant i-frames."""
    rc, rr = _find_pit_respawn_pos(player, room)
    player.rect.centerx = rc * TILE_SIZE + TILE_SIZE // 2
    player.rect.centery = rr * TILE_SIZE + TILE_SIZE // 2
    # Apply HP penalty but never kill the player.
    penalty = min(PIT_FALL_HP_PENALTY, max(0, player.current_hp - 1))
    player.current_hp = max(1, player.current_hp - penalty)
    # Grant extended i-frames — the standard flash visual in player_visual_rules
    # will blink the player for the entire RESPAWN_IFRAMES_MS window, giving a
    # clear signal that the player is temporarily invulnerable.
    player._invincible_until = now_ticks + PIT_FALL_RESPAWN_IFRAMES_MS
    # Clear animation state so the normal game loop resumes.
    player._pit_fall_phase = None
    player._pit_fall_shrink_t = 0.0


def _find_pit_respawn_pos(player, room):
    """Return ``(col, row)`` of the nearest walkable, non-pit tile.

    Priority:
    1. The tile the player stepped from before entering the pit
       (``_pit_entry_col`` / ``_pit_entry_row``).
    2. BFS from the pit tile outward — first non-blocked tile found.

    Tiles in ``_BLOCKED`` are never used as a respawn destination.
    THIN_ICE is intentionally excluded: respawning onto thin ice that is
    about to crack would immediately re-trigger the fall animation.
    """
    from room import PIT_TILE, WALL, THIN_ICE
    from collections import deque

    _BLOCKED = {PIT_TILE, WALL, THIN_ICE}

    # First preference: the tile the player came from.
    entry_col = getattr(player, "_pit_entry_col", None)
    entry_row = getattr(player, "_pit_entry_row", None)
    if entry_col is not None and entry_row is not None:
        if room.tile_at(entry_col, entry_row) not in _BLOCKED:
            return (entry_col, entry_row)

    # Fallback: BFS expanding from the pit tile.
    pit_col = player._pit_fall_pit_col
    pit_row = player._pit_fall_pit_row
    visited = {(pit_col, pit_row)}
    queue = deque([(pit_col, pit_row)])
    while queue:
        col, row = queue.popleft()
        for dc, dr in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nc, nr = col + dc, row + dr
            if (nc, nr) in visited:
                continue
            visited.add((nc, nr))
            t = room.tile_at(nc, nr)
            if t not in _BLOCKED:
                return (nc, nr)
            queue.append((nc, nr))

    # Ultimate fallback — pit tile itself (should be unreachable in practice).
    return (pit_col, pit_row)


def advance_thin_ice_respawn(room, now_ticks):
    """Restore cracked thin-ice pits whose THIN_ICE_RESPAWN_MS window has expired.

    Called every frame from the runtime.  Iterates ``room._thin_ice_crack_times``
    (populated by the THIN_ICE crack handler in :func:`apply_terrain_effects`)
    and, for each tile whose crack timestamp is old enough:

    - Sets ``room.grid[row][col]`` back to ``THIN_ICE``.
    - Removes the entry from ``_thin_ice_crack_times``.
    - Resets the step count for that tile to 0 so the player gets a fresh
      cracking progression on the regenerated tile.

    Tiles that are currently occupied by the player (mid-fall animation) are
    skipped until the fall finishes so the grid never changes under an
    in-progress pit-fall.
    """
    crack_times = getattr(room, "_thin_ice_crack_times", None)
    if not crack_times:
        return

    from room import THIN_ICE, PIT_TILE

    expired = [
        coord for coord, cracked_at in crack_times.items()
        if now_ticks - cracked_at >= THIN_ICE_RESPAWN_MS
    ]
    for coord in expired:
        col, row = coord
        # Only restore tiles that are still PIT_TILE — if the room was
        # reloaded or the tile was overwritten by something else, skip.
        if room.tile_at(col, row) == PIT_TILE:
            room.grid[row][col] = THIN_ICE
        del crack_times[coord]
        # Reset the step counter so the regenerated tile starts fresh.
        step_counts = getattr(room, "_thin_ice_step_counts", None)
        if step_counts is not None:
            step_counts.pop(coord, None)


def thin_ice_crack_stage(room, col, row):
    """Return the 0-based crack stage for a THIN_ICE tile (0 = untouched).

    Used by the renderer to choose the correct crack-overlay colour.
    Returns 0 when the tile has never been stepped on or the room has no
    step-count data.  The maximum return value is
    ``THIN_ICE_STEPS_TO_CRACK - 1`` (one step before collapse).
    """
    counts = getattr(room, "_thin_ice_step_counts", None)
    if counts is None:
        return 0
    return counts.get((col, row), 0)


def advance_trail_freeze_tiles(room, now_ticks):
    """Collapse expired TRAIL_FREEZE tiles to PIT_TILE.

    IceSpirit enemies write ``room._trail_freeze_tiles[(col, row)] = spawn_ticks``
    when they drop a trail tile.  Each frame this function checks whether any
    trail tile has exceeded ``TRAIL_FREEZE_DURATION_MS`` and, if so, converts it
    to a PIT_TILE so the normal pit-fall animation triggers.

    Tiles already overwritten (e.g. the player stepped on them and the tile
    was manually converted to PIT_TILE by cracking logic) are removed from
    the registry without any further grid mutation.
    """
    from settings import TRAIL_FREEZE_DURATION_MS
    from room import TRAIL_FREEZE, PIT_TILE

    tile_map = getattr(room, "_trail_freeze_tiles", None)
    if not tile_map:
        return

    expired = [
        coord for coord, spawn_t in tile_map.items()
        if now_ticks - spawn_t >= TRAIL_FREEZE_DURATION_MS
    ]
    for coord in expired:
        col, row = coord
        if room.tile_at(col, row) == TRAIL_FREEZE:
            room.grid[row][col] = PIT_TILE
            # Track collapses for the Spirit Swarm "Clean Floor" bonus.
            room._trail_freeze_pits_created = getattr(room, "_trail_freeze_pits_created", 0) + 1
        del tile_map[coord]


def emit_trail_freeze_tile(room, col, row, now_ticks):
    """Place a TRAIL_FREEZE tile at ``(col, row)`` and register its expiry.

    Called by IceSpirit enemies at their configured emit interval.  No-ops
    if the target cell is already a hazard tile or is out of bounds.
    """
    from room import FLOOR, ICE, TRAIL_FREEZE

    if room.tile_at(col, row) not in (FLOOR, ICE):
        return
    room.grid[row][col] = TRAIL_FREEZE
    tile_map = getattr(room, "_trail_freeze_tiles", None)
    if tile_map is None:
        room._trail_freeze_tiles = {}
        tile_map = room._trail_freeze_tiles
    tile_map[(col, row)] = now_ticks
