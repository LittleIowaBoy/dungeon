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
    diag = {"tile": "floor", "quicksand_pull": False, "tick_damage": 0, "pushed": False}
    if room is None or player is None:
        return diag

    # Lazy import to avoid circular dependency (room imports from settings,
    # this imports from settings; player.py would create the cycle).
    from room import (
        QUICKSAND, SPIKE_PATCH, PIT_TILE, CURRENT,
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

    return diag


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
