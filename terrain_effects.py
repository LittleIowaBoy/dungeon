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
    HAZARD_TICK_MS, HAZARD_TICK_DAMAGE,
    QUICKSAND_DROWN_MS, CURRENT_PUSH_SPEED,
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
        Diagnostics for tests/HUD (``{"tile": str, "drown_ms": int,
        "tick_damage": int, "pushed": bool}``).  Stable contract.
    """
    diag = {"tile": "floor", "drown_ms": 0, "tick_damage": 0, "pushed": False}
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

    # ── PIT_TILE: instant lethal step ──────────────────────
    if tile == PIT_TILE:
        if not invincible and player.current_hp > 0:
            player.take_damage(player.current_hp)
        return diag

    # ── QUICKSAND: drowning timer ──────────────────────────
    if tile == QUICKSAND:
        room._quicksand_drown_ms += int(dt_ms)
        diag["drown_ms"] = room._quicksand_drown_ms
        if room._quicksand_drown_ms >= QUICKSAND_DROWN_MS:
            if not invincible and player.current_hp > 0:
                player.take_damage(player.current_hp)
            room._quicksand_drown_ms = 0
        return diag
    # Reset drowning the moment the player steps off.
    if room._quicksand_drown_ms:
        room._quicksand_drown_ms = 0

    # ── SPIKE_PATCH: passive tick damage ───────────────────
    if tile == SPIKE_PATCH:
        if now_ticks - room._hazard_last_tick_ms >= HAZARD_TICK_MS:
            room._hazard_last_tick_ms = now_ticks
            if not invincible:
                player.take_damage(HAZARD_TICK_DAMAGE)
                diag["tick_damage"] = HAZARD_TICK_DAMAGE

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
