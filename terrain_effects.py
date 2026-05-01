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
    THIN_ICE_STEPS_TO_CRACK,
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
    }
    if room is None or player is None:
        return diag

    # Lazy import to avoid circular dependency (room imports from settings,
    # this imports from settings; player.py would create the cycle).
    from room import (
        QUICKSAND, SPIKE_PATCH, PIT_TILE, CURRENT, WATER, THIN_ICE,
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

    # ── THIN_ICE: cracking tile mechanic ─────────────────────────────────
    # Each time the player steps ONTO a new THIN_ICE tile, a per-tile
    # step counter on the room is incremented.  Once the counter for a
    # tile reaches THIN_ICE_STEPS_TO_CRACK, the tile collapses to
    # PIT_TILE instantly (lethal on the same frame if the player lingers).
    # Exiting and re-entering the room preserves collapsed tiles — the
    # step_counts dict is kept on the room object for its lifetime.
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
            # Immediately deal the PIT lethal damage so the player can't
            # survive the frame they crack through.
            if not invincible and player.current_hp > 0:
                player.take_damage(player.current_hp)
            return diag

    # ── PIT_TILE: instant lethal step ──────────────────────
    if tile == PIT_TILE:
        if not invincible and player.current_hp > 0:
            player.take_damage(player.current_hp)
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
