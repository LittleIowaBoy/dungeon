"""Time-scale framework — for runes that slow or freeze world time.

Stored as a float multiplier in ``player.rune_state["time_scale"]``.
1.0 = normal time, 0.2 = world moves at 20% speed, 0.0 = frozen.

The Time Anchor identity rune sets this to 0.2 when the player is
stationary, then briefly back to 0.0 (full freeze) on release.

Scope: applies to enemy AI velocity and player movement velocity.
Cooldowns and animations remain on real time so the UI stays
responsive — runes that need enemy "freeze" use status_effects.FROZEN.
"""

DEFAULT_TIME_SCALE = 1.0


def reset_time_scale(player):
    state = getattr(player, "rune_state", None)
    if state is None:
        player.rune_state = {}
        state = player.rune_state
    state["time_scale"] = DEFAULT_TIME_SCALE


def set_time_scale(player, scale):
    state = getattr(player, "rune_state", None)
    if state is None:
        player.rune_state = {}
        state = player.rune_state
    state["time_scale"] = max(0.0, float(scale))


def get_time_scale(player):
    state = getattr(player, "rune_state", None) or {}
    try:
        scale = float(state.get("time_scale", DEFAULT_TIME_SCALE))
    except (TypeError, ValueError):
        return DEFAULT_TIME_SCALE
    return max(0.0, scale)


def is_world_slowed(player):
    return get_time_scale(player) < DEFAULT_TIME_SCALE
