"""Behavior rune effect resolution.

Pure-function hooks for the 9 behavior runes.  Engine modules call into
here to query whether a rune modifies a pipeline (`attack_rules`,
`ability_rules`, `dodge_rules`, `status_effects`, ``rpg.py`` hit/kill
sites, `consumable_rules`).

Per-room scratch state lives under ``player.rune_state["room"]`` (reset
by ``rune_rules.on_room_enter``).  Persistent per-run state lives at
``player.rune_state``'s top level.
"""

import math

import rune_rules
from settings import TILE_SIZE


# ── helpers ─────────────────────────────────────────────
def _has(player, rune_id):
    return rune_rules.has_rune(player, rune_id)


def _state(player):
    state = getattr(player, "rune_state", None)
    if state is None:
        player.rune_state = {}
        state = player.rune_state
    return state


def _room(player):
    state = _state(player)
    room = state.get("room")
    if room is None:
        room = {}
        state["room"] = room
    return room


# ── ricochet ────────────────────────────────────────────
RICOCHET_RADIUS = 4 * TILE_SIZE


def find_ricochet_target(player, hitbox, primary, enemies):
    """Return the next enemy to hit after *primary* (or ``None``).

    Looks for the closest enemy within ``RICOCHET_RADIUS`` of the
    primary hit, that has not already been hit by *hitbox* and is alive.
    """
    if not _has(player, "ricochet"):
        return None
    px = primary.rect.centerx
    py = primary.rect.centery
    already = getattr(hitbox, "_hit_enemies", set())
    best = None
    best_d2 = (RICOCHET_RADIUS + 1) ** 2
    for enemy in enemies:
        if enemy is primary:
            continue
        if id(enemy) in already:
            continue
        if getattr(enemy, "current_hp", 0) <= 0:
            continue
        d2 = (enemy.rect.centerx - px) ** 2 + (enemy.rect.centery - py) ** 2
        if d2 < best_d2:
            best = enemy
            best_d2 = d2
    return best


# ── shockwave ───────────────────────────────────────────
SHOCKWAVE_DAMAGE_MULTIPLIER = 1.5
SHOCKWAVE_DURATION_MULTIPLIER = 3.0
SHOCKWAVE_COOLDOWN_MULTIPLIER = 1.5  # tradeoff: 50% slower attacks


def shockwave_damage_multiplier(player):
    return SHOCKWAVE_DAMAGE_MULTIPLIER if _has(player, "shockwave") else 1.0


def shockwave_duration_multiplier(player):
    return SHOCKWAVE_DURATION_MULTIPLIER if _has(player, "shockwave") else 1.0


def shockwave_cooldown_multiplier(player):
    return SHOCKWAVE_COOLDOWN_MULTIPLIER if _has(player, "shockwave") else 1.0


# ── vampiric strike ─────────────────────────────────────
VAMPIRIC_HEAL_PER_KILL = 8


def vampiric_kill_heal_amount(player):
    return VAMPIRIC_HEAL_PER_KILL if _has(player, "vampiric_strike") else 0


def blocks_health_pickup(player):
    """Vampiric Strike disables potions and healing shrines."""
    return _has(player, "vampiric_strike")


# ── afterimage ──────────────────────────────────────────
AFTERIMAGE_DURATION_MS = 2000
AFTERIMAGE_DAMAGE = 4
AFTERIMAGE_RADIUS = TILE_SIZE
AFTERIMAGE_TICK_MS = 250


def spawns_afterimage(player):
    return _has(player, "afterimage")


def afterimage_dodge_distance_multiplier(player):
    """Afterimage halves dodge distance as a tradeoff."""
    return 0.5 if _has(player, "afterimage") else 1.0


def make_afterimage_hitbox(center, color=(180, 100, 220, 140)):
    """Build a stationary damaging decoy at *center*.

    Returns an :class:`weapons.AttackHitbox` ready to be added to the
    dungeon's hitbox group.
    """
    import pygame
    from weapons import AttackHitbox
    size = AFTERIMAGE_RADIUS * 2
    rect = pygame.Rect(0, 0, size, size)
    rect.center = center
    return AttackHitbox(
        rect, AFTERIMAGE_DAMAGE, AFTERIMAGE_DURATION_MS, color,
        weapon_id="afterimage", damage_type="behavior_rune",
    )


# ── overclock ───────────────────────────────────────────
OVERCLOCK_COOLDOWN_MULTIPLIER = 3.0


def should_double_fire(player):
    return _has(player, "overclock")


def ability_cooldown_multiplier(player):
    return OVERCLOCK_COOLDOWN_MULTIPLIER if _has(player, "overclock") else 1.0


# ── chain reaction ──────────────────────────────────────
CHAIN_REACTION_RADIUS = 3 * TILE_SIZE


def chain_reaction_targets(player, source_rect, enemies):
    """Return list of enemies (excluding *source*) within chain radius."""
    if not _has(player, "chain_reaction"):
        return []
    cx, cy = source_rect.center
    r2 = CHAIN_REACTION_RADIUS ** 2
    out = []
    for enemy in enemies:
        ex, ey = enemy.rect.center
        if (ex == cx and ey == cy):
            continue
        if (ex - cx) ** 2 + (ey - cy) ** 2 <= r2:
            out.append(enemy)
    return out


def chain_reaction_self_applies(player):
    """Tradeoff: any status you apply also affects you."""
    return _has(player, "chain_reaction")


def apply_status_with_chain(player, target, status_id, now_ticks, enemies, **kwargs):
    """Apply *status_id* to *target* and (if Chain Reaction equipped) to
    nearby enemies and the player themselves.

    Returns the count of holders the status was applied to.
    """
    import status_effects  # local import to avoid circular dep
    applied = 0
    if status_effects.apply_status(target, status_id, now_ticks, **kwargs):
        applied += 1
    for nearby in chain_reaction_targets(player, target.rect, enemies):
        if status_effects.apply_status(nearby, status_id, now_ticks, **kwargs):
            applied += 1
    if chain_reaction_self_applies(player):
        if status_effects.apply_status(player, status_id, now_ticks, **kwargs):
            applied += 1
    return applied


# ── shrapnel burst ──────────────────────────────────────
SHRAPNEL_RADIUS = 2 * TILE_SIZE
SHRAPNEL_DAMAGE_FRACTION = 0.80
SHRAPNEL_SELF_FRACTION = 0.50


def shrapnel_burst_damage(player, weapon_damage):
    if not _has(player, "shrapnel_burst"):
        return 0
    return max(1, int(weapon_damage * SHRAPNEL_DAMAGE_FRACTION))


def shrapnel_burst_self_damage(player, weapon_damage):
    if not _has(player, "shrapnel_burst"):
        return 0
    blast = shrapnel_burst_damage(player, weapon_damage)
    return max(1, int(blast * SHRAPNEL_SELF_FRACTION))


def shrapnel_burst_targets(player, kill_rect, enemies):
    """Return enemies within blast radius of *kill_rect* (excluding the killed)."""
    if not _has(player, "shrapnel_burst"):
        return []
    cx, cy = kill_rect.center
    r2 = SHRAPNEL_RADIUS ** 2
    out = []
    for enemy in enemies:
        if getattr(enemy, "current_hp", 0) <= 0:
            continue
        ex, ey = enemy.rect.center
        if (ex - cx) ** 2 + (ey - cy) ** 2 <= r2:
            out.append(enemy)
    return out


def player_in_shrapnel_blast(player, kill_rect):
    if not _has(player, "shrapnel_burst"):
        return False
    cx, cy = kill_rect.center
    px, py = player.rect.center
    return (px - cx) ** 2 + (py - cy) ** 2 <= SHRAPNEL_RADIUS ** 2


# ── static charge ───────────────────────────────────────
STATIC_CHARGE_BUILD_PER_SEC = 1.0          # full charge in 1s of motion
STATIC_CHARGE_DISSIPATE_PER_SEC = 2.0      # standing dissipates 2x faster
STATIC_CHARGE_MAX = 1.0
STATIC_CHARGE_BONUS_AT_FULL = 3.0          # +200% damage → x3.0 multiplier


def update_static_charge(player, dt_ms, is_moving):
    if not _has(player, "static_charge"):
        return
    state = _state(player)
    charge = float(state.get("static_charge", 0.0))
    seconds = dt_ms / 1000.0
    if is_moving:
        charge = min(STATIC_CHARGE_MAX, charge + STATIC_CHARGE_BUILD_PER_SEC * seconds)
    else:
        charge = max(0.0, charge - STATIC_CHARGE_DISSIPATE_PER_SEC * seconds)
    state["static_charge"] = charge


def static_charge_value(player):
    if not _has(player, "static_charge"):
        return 0.0
    return float(_state(player).get("static_charge", 0.0))


def consume_static_charge(player):
    """Return outgoing-damage multiplier for the current attack and reset."""
    if not _has(player, "static_charge"):
        return 1.0
    state = _state(player)
    charge = float(state.get("static_charge", 0.0))
    state["static_charge"] = 0.0
    if charge >= STATIC_CHARGE_MAX:
        return STATIC_CHARGE_BONUS_AT_FULL
    if charge <= 0.0:
        return 1.0
    # linear ramp 1.0 → 3.0 across charge 0..1
    return 1.0 + (STATIC_CHARGE_BONUS_AT_FULL - 1.0) * charge


# ── boomerang ───────────────────────────────────────────
BOOMERANG_RETURN_DELAY_MS = 350
BOOMERANG_RETURN_DURATION_MS = 280
BOOMERANG_RETURN_DAMAGE_FRACTION = 1.0
BOOMERANG_RETURN_RADIUS = TILE_SIZE
BOOMERANG_RETURN_COLOR = (160, 200, 255, 150)


def boomerang_outbound_multiplier(player):
    """Boomerang zeroes outbound damage; full damage lands on return trip."""
    return 0.0 if _has(player, "boomerang") else 1.0


def has_boomerang(player):
    return _has(player, "boomerang")


def queue_boomerang_return(player, center, base_damage, now_ticks):
    """Schedule a return-trip hitbox to spawn after the outbound delay."""
    if not _has(player, "boomerang"):
        return
    state = _state(player)
    pending = state.get("boomerang_pending")
    if pending is None:
        pending = []
        state["boomerang_pending"] = pending
    damage = max(1, int(base_damage * BOOMERANG_RETURN_DAMAGE_FRACTION))
    pending.append({
        "spawn_at": now_ticks + BOOMERANG_RETURN_DELAY_MS,
        "center": (int(center[0]), int(center[1])),
        "damage": damage,
    })


def make_boomerang_return_hitbox(center, damage):
    """Build the return-trip damaging hitbox at *center*."""
    import pygame
    from weapons import AttackHitbox
    size = BOOMERANG_RETURN_RADIUS * 2
    rect = pygame.Rect(0, 0, size, size)
    rect.center = center
    return AttackHitbox(
        rect, damage, BOOMERANG_RETURN_DURATION_MS, BOOMERANG_RETURN_COLOR,
        weapon_id="boomerang", damage_type="behavior_rune",
    )


def update_boomerang_returns(player, hitbox_group, now_ticks):
    """Spawn any return hitboxes whose delay has elapsed.

    Returns the list of hitboxes spawned (mainly for tests).
    """
    state = getattr(player, "rune_state", None)
    if not state:
        return []
    pending = state.get("boomerang_pending")
    if not pending:
        return []
    spawned = []
    remaining = []
    for entry in pending:
        if now_ticks >= entry["spawn_at"]:
            hb = make_boomerang_return_hitbox(entry["center"], entry["damage"])
            hitbox_group.add(hb)
            spawned.append(hb)
        else:
            remaining.append(entry)
    state["boomerang_pending"] = remaining
    return spawned
