"""Stat rune effect resolution.

Pure functions that read ``player.equipped_runes`` and
``player.rune_state`` and return modifier values.  Engine modules
(`attack_rules`, `combat_rules`, `effect_state_rules`, `dodge_rules`,
``rpg.py``) call into here so the catalog of stat runes lives in one
place.

Per-room state is stored under ``player.rune_state["room"]`` (cleared
by ``rune_rules.on_room_enter``).  Persistent per-run state lives at
``player.rune_state``'s top level.
"""

import identity_runes
import rune_rules


# ── shared state helpers ────────────────────────────────
def _room_state(player):
    state = getattr(player, "rune_state", None)
    if state is None:
        player.rune_state = {}
        state = player.rune_state
    room = state.get("room")
    if room is None:
        room = {}
        state["room"] = room
    return room


def _has(player, rune_id):
    return rune_rules.has_rune(player, rune_id)


# ── outgoing damage ─────────────────────────────────────
def modify_outgoing_damage(player, enemy, base_damage):
    """Return *base_damage* after stat-rune modifiers for a single hit."""
    if base_damage <= 0:
        return base_damage
    # Identity override: Pacifist zeroes all outgoing damage.
    if identity_runes.is_pacifist(player):
        return 0
    multiplier = 1.0
    room = _room_state(player)

    if _has(player, "glass_cannon"):
        multiplier *= 1.80
    if _has(player, "thorns"):
        multiplier *= 0.75
    if _has(player, "iron_will"):
        multiplier *= 0.75

    if _has(player, "bloodthirst"):
        if not room.get("bloodthirst_landed"):
            multiplier *= 1.50
        else:
            multiplier *= 0.80

    if _has(player, "executioner"):
        max_hp = max(1, getattr(enemy, "max_hp", 1))
        ratio = getattr(enemy, "current_hp", 0) / max_hp
        if ratio < 0.25:
            multiplier *= 2.00
        else:
            multiplier *= 0.70

    if _has(player, "berserker"):
        kills = int(room.get("berserker_kills", 0))
        multiplier *= 1.0 + 0.05 * kills

    if _has(player, "heavy_hitter"):
        struck = room.setdefault("heavy_hitter_struck", set())
        if id(enemy) not in struck:
            multiplier *= 2.50

    if _has(player, "momentum"):
        seconds = float(player.rune_state.get("momentum_seconds", 0.0))
        multiplier *= 1.0 + 0.10 * seconds

    return max(0, int(base_damage * multiplier))


# ── post-hit hook ───────────────────────────────────────
def on_player_hit_landed(player, enemy, damage_dealt, killed):
    """Update room-scoped counters after a successful player hit."""
    room = _room_state(player)
    if _has(player, "bloodthirst"):
        room["bloodthirst_landed"] = True
    if _has(player, "heavy_hitter"):
        struck = room.setdefault("heavy_hitter_struck", set())
        struck.add(id(enemy))
    if _has(player, "momentum"):
        # Momentum stack resets on dealing damage.
        player.rune_state["momentum_seconds"] = 0.0
        player.rune_state["momentum_started_at"] = None
    if killed:
        if _has(player, "berserker"):
            room["berserker_kills"] = int(room.get("berserker_kills", 0)) + 1
        if _has(player, "vampire_lord"):
            heal = max(1, int(player.max_hp * 0.05))
            player.current_hp = min(player.max_hp, player.current_hp + heal)


# ── incoming damage ─────────────────────────────────────
def modify_incoming_damage(player, base_damage):
    """Return reduced damage after defensive stat-rune mitigation."""
    if base_damage <= 0:
        return base_damage
    multiplier = 1.0
    if _has(player, "turtle_shell"):
        multiplier *= 0.60
    if _has(player, "last_stand"):
        threshold = max(1, int(player.max_hp * 0.15))
        if player.current_hp <= threshold:
            multiplier *= 0.20  # 80% reduction at low HP (not full invuln)
    return max(0, int(base_damage * multiplier))


def on_player_damage_taken(player, amount):
    """Reset stacks broken by taking damage."""
    if amount <= 0:
        return
    room = _room_state(player)
    if _has(player, "berserker"):
        room["berserker_kills"] = 0


def compute_reflect(player, raw_damage_taken):
    """Return damage to reflect to the contact attacker."""
    if raw_damage_taken <= 0 or not _has(player, "thorns"):
        return 0
    return max(1, int(raw_damage_taken * 0.30))


# ── max HP ──────────────────────────────────────────────
def modify_max_hp(player, base_max_hp):
    # Glass Soul locks max HP at 1, overriding all stat modifiers.
    if identity_runes.is_glass_soul(player):
        return identity_runes.glass_soul_max_hp(player, base_max_hp)
    bonus = 0
    multiplier = 1.0
    if _has(player, "ironhide"):
        bonus += 60
    if _has(player, "glass_cannon"):
        multiplier *= 0.50
    if _has(player, "vampire_lord"):
        multiplier *= 0.70
    if _has(player, "featherweight"):
        multiplier *= 0.60
    return max(1, int(base_max_hp * multiplier) + bonus)


# ── speed multiplier ────────────────────────────────────
def modify_speed_multiplier(player, base_multiplier):
    multiplier = base_multiplier * identity_runes.pacifist_speed_multiplier(player)
    if _has(player, "ironhide"):
        multiplier *= 0.80
    if _has(player, "sprinter"):
        multiplier *= 1.50
    if _has(player, "momentum"):
        seconds = float(getattr(player, "rune_state", {}).get("momentum_seconds", 0.0))
        # Momentum doesn't change movement speed itself, only damage —
        # but reading the stack here is harmless.
        del seconds
    return multiplier


def update_movement_state(player, now_ticks, dt_ms, is_moving):
    """Tick momentum and similar movement-tracking timers.  Call per frame."""
    state = getattr(player, "rune_state", None)
    if state is None:
        player.rune_state = {}
        state = player.rune_state
    if _has(player, "momentum"):
        if is_moving:
            state["momentum_seconds"] = float(state.get("momentum_seconds", 0.0)) + dt_ms / 1000.0
        else:
            state["momentum_seconds"] = 0.0


# ── weapon cooldown ─────────────────────────────────────
def modify_weapon_cooldown(player, base_cooldown_ms):
    multiplier = 1.0
    if _has(player, "sprinter"):
        multiplier *= 1.43  # -30% attack speed
    if _has(player, "heavy_hitter"):
        multiplier *= 1.30
    return max(1, int(base_cooldown_ms * multiplier))


# ── dodge ───────────────────────────────────────────────
def can_dodge(player):
    return not _has(player, "turtle_shell")


def dodge_cooldown_ms(player, base_cooldown_ms):
    cd = base_cooldown_ms
    if _has(player, "slippery"):
        cd = 2000
    if _has(player, "featherweight"):
        cd = max(1, cd // 2)
    return cd


def dodge_grants_iframes(player):
    return not _has(player, "ghost_step")


def dodge_grants_pass_through(player):
    return _has(player, "ghost_step")


def dodge_speed_multiplier_bonus(player):
    """Multiplier to apply on top of dodge_rules.DODGE_SPEED_MULTIPLIER."""
    if _has(player, "slippery"):
        return 1.40
    return 1.0


# ── statuses ────────────────────────────────────────────
def is_status_immune(player):
    return _has(player, "iron_will")
