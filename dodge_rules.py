"""Dodge mechanic — invincibility roll on demand.

Player gains a short window of invincibility (and optionally pass-through
on enemies) when triggered, then enters a cooldown.  Runes (Slippery,
Ghost Step, Featherweight, Turtle Shell) modify the duration, cooldown,
and pass-through behaviour by patching the same fields.

State on the player:
- ``dodge_until``                — ticks timestamp; 0 when not dodging
- ``dodge_cooldown_until``       — ticks timestamp; 0 when ready
- ``dodge_pass_through``         — bool; True while phasing through enemies
- ``dodge_facing``               — (dx, dy) frozen direction during dodge
"""

# Baseline timing — runes will override these per-trigger.
DODGE_DURATION_MS = 220
DODGE_COOLDOWN_MS = 1500
DODGE_SPEED_MULTIPLIER = 2.4

import stat_runes  # noqa: E402  (placed after constants for readability)
from settings import SPARK_CHARGE_COOLDOWN_MULT


def reset_runtime_dodge(player):
    """Initialize/clear all dodge-related fields on *player*."""
    player.dodge_until = 0
    player.dodge_cooldown_until = 0
    player.dodge_pass_through = False
    player.dodge_facing = (0.0, 0.0)


def reset_bonus_dodges(player):
    """Refill bonus_dodges_remaining from oathbinder on room enter."""
    import armor_rules
    bonus = armor_rules.aggregate_equipped_stats(
        getattr(player, "progress", None)
    ).get("bonus_dodges_per_room", 0)
    player.bonus_dodges_remaining = int(bonus)


def is_dodging(player, now_ticks):
    return now_ticks < getattr(player, "dodge_until", 0)


def is_on_cooldown(player, now_ticks):
    return now_ticks < getattr(player, "dodge_cooldown_until", 0)


def can_dodge(player, now_ticks):
    return not is_dodging(player, now_ticks) and not is_on_cooldown(player, now_ticks)


def cooldown_remaining_ms(player, now_ticks):
    return max(0, getattr(player, "dodge_cooldown_until", 0) - now_ticks)


def cooldown_fraction_remaining(player, now_ticks):
    """Return 0.0 (ready) → 1.0 (just triggered) for HUD."""
    remaining = cooldown_remaining_ms(player, now_ticks)
    if remaining <= 0 or DODGE_COOLDOWN_MS <= 0:
        return 0.0
    return min(1.0, remaining / DODGE_COOLDOWN_MS)


def trigger_dodge(
    player,
    now_ticks,
    *,
    duration_ms=DODGE_DURATION_MS,
    cooldown_ms=DODGE_COOLDOWN_MS,
    pass_through=False,
):
    """Begin a dodge if eligible.  Returns True when the dodge starts.

    If the player has bonus_dodges_remaining > 0 (e.g. from Oathbinder),
    the dodge fires without consuming the normal cooldown.  Otherwise the
    standard cooldown applies.

    The dodge direction is captured from the player's current facing.
    If facing is zero (no key held) the dodge is rejected so the player
    cannot waste a cooldown standing still.
    """
    bonus_remaining = getattr(player, "bonus_dodges_remaining", 0)
    # If using a bonus dodge, skip the cooldown gate; otherwise require no cooldown.
    if bonus_remaining <= 0 and is_on_cooldown(player, now_ticks):
        return False
    if is_dodging(player, now_ticks):
        return False
    if not stat_runes.can_dodge(player):
        return False

    facing = (
        float(getattr(player, "facing_dx", 0.0) or 0.0),
        float(getattr(player, "facing_dy", 0.0) or 0.0),
    )
    if facing == (0.0, 0.0):
        return False

    cooldown_ms = stat_runes.dodge_cooldown_ms(player, cooldown_ms)
    if now_ticks < getattr(player, "spark_until", 0):
        cooldown_ms = int(cooldown_ms * SPARK_CHARGE_COOLDOWN_MULT)
    if stat_runes.dodge_grants_pass_through(player):
        pass_through = True

    player.dodge_facing = facing
    player.dodge_until = now_ticks + duration_ms
    if bonus_remaining > 0:
        # Consume a bonus dodge — don't set cooldown_until.
        player.bonus_dodges_remaining = bonus_remaining - 1
    else:
        player.dodge_cooldown_until = now_ticks + duration_ms + cooldown_ms
    player.dodge_pass_through = bool(pass_through)
    return True


def update_dodge_state(player, now_ticks):
    """Clear pass-through once the active phase ends.  Call every frame."""
    if not is_dodging(player, now_ticks) and getattr(player, "dodge_pass_through", False):
        player.dodge_pass_through = False
        player.dodge_facing = (0.0, 0.0)


def dodge_velocity(player, now_ticks, base_speed):
    """Return (vx, vy) the dodge wants to apply this frame, or None.

    Movement code can call this to override input-driven motion while
    the dodge is active so the player slides in the locked direction.
    """
    if not is_dodging(player, now_ticks):
        return None
    dx, dy = getattr(player, "dodge_facing", (0.0, 0.0))
    if dx == 0.0 and dy == 0.0:
        return None
    import behavior_runes  # local import to avoid circular dep
    import armor_rules
    dist_mult = 1.0 + armor_rules.aggregate_equipped_stats(
        getattr(player, "progress", None)
    ).get("dodge_distance_mult", 0.0)
    speed = base_speed * DODGE_SPEED_MULTIPLIER * stat_runes.dodge_speed_multiplier_bonus(player)
    speed *= behavior_runes.afterimage_dodge_distance_multiplier(player)
    speed *= dist_mult
    return (dx * speed, dy * speed)
