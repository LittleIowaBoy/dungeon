"""Active ability slot — generic engine for rune-supplied abilities.

A rune (Overclock, Time Anchor, etc.) registers a callable into the
player's active ability slot when equipped.  Pressing the bound key
calls ``activate(player)`` if the cooldown has elapsed.

State on the player:
- ``active_ability_id``         — str | None; identifier of equipped ability
- ``active_ability_cooldown_ms`` — int; cooldown set by the ability
- ``ability_cooldown_until``    — ticks timestamp; 0 when ready
- ``ability_handlers``          — dict[str, callable]; activation callbacks

Handlers are registered at module level via ``register_ability`` so
runes need only declare their id; engine code does not import rune
modules directly.
"""

# Registry: ability_id -> (activate(player, now_ticks) -> bool, cooldown_ms)
_ABILITIES = {}


def register_ability(ability_id, activate, cooldown_ms):
    """Register an ability handler.  Idempotent overwrite is allowed."""
    _ABILITIES[ability_id] = (activate, int(cooldown_ms))


def unregister_ability(ability_id):
    _ABILITIES.pop(ability_id, None)


def known_ability_ids():
    return tuple(_ABILITIES.keys())


def reset_runtime_ability(player):
    """Initialize/clear all ability fields on *player*."""
    player.active_ability_id = None
    player.active_ability_cooldown_ms = 0
    player.ability_cooldown_until = 0


def equip_ability(player, ability_id):
    """Bind *ability_id* into the player's active slot.

    Returns True on success, False if unknown.  Equipping an ability
    resets the cooldown so the player can fire it immediately.
    """
    if ability_id is None:
        reset_runtime_ability(player)
        return True
    entry = _ABILITIES.get(ability_id)
    if entry is None:
        return False
    _, cooldown_ms = entry
    player.active_ability_id = ability_id
    player.active_ability_cooldown_ms = cooldown_ms
    player.ability_cooldown_until = 0
    return True


def has_ability(player):
    return getattr(player, "active_ability_id", None) is not None


def is_on_cooldown(player, now_ticks):
    return now_ticks < getattr(player, "ability_cooldown_until", 0)


def can_activate(player, now_ticks):
    return has_ability(player) and not is_on_cooldown(player, now_ticks)


def cooldown_remaining_ms(player, now_ticks):
    return max(0, getattr(player, "ability_cooldown_until", 0) - now_ticks)


def cooldown_fraction_remaining(player, now_ticks):
    """Return 0.0 (ready) → 1.0 (just triggered) for HUD ring."""
    cd = getattr(player, "active_ability_cooldown_ms", 0) or 0
    if cd <= 0:
        return 0.0
    return min(1.0, cooldown_remaining_ms(player, now_ticks) / cd)


def activate_ability(player, now_ticks):
    """Trigger the equipped ability.

    Returns True when the ability fired and the cooldown started.  If
    the handler returns falsy (e.g. preconditions not met) the cooldown
    is NOT consumed.
    """
    import behavior_runes  # local import to avoid circular dep
    if not can_activate(player, now_ticks):
        return False
    ability_id = player.active_ability_id
    activate, cooldown_ms = _ABILITIES[ability_id]
    if not activate(player, now_ticks):
        return False
    if behavior_runes.should_double_fire(player):
        # Fire a second time immediately; ignore its return value.
        activate(player, now_ticks)
    cooldown_ms = int(cooldown_ms * behavior_runes.ability_cooldown_multiplier(player))
    player.ability_cooldown_until = now_ticks + cooldown_ms
    return True
