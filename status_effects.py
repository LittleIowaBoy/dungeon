"""Status effects framework — burning, frozen, stunned, poisoned, slowed.

Both Player and Enemy hold a ``statuses`` dict keyed by status id.  Each
entry is a dict with at minimum ``expires_at``; DOT statuses also carry
``tick_interval_ms``, ``tick_damage``, ``last_tick_at``; movement
modifier statuses carry ``magnitude`` (e.g. slowed → speed multiplier).

Effects are inert until something applies them (Chain Reaction rune,
trap, etc.).  Default game state has no statuses, so existing behaviour
is unchanged.
"""

# ── status ids ──────────────────────────────────────────
BURNING = "burning"
FROZEN = "frozen"
STUNNED = "stunned"
POISONED = "poisoned"
SLOWED = "slowed"

IMMOBILIZING_STATUSES = (FROZEN, STUNNED)
SILENCING_STATUSES = (FROZEN, STUNNED)  # blocks attack

# Default tunings for built-in statuses.  apply_status() may override.
_DEFAULTS = {
    BURNING:  {"duration_ms": 3000, "tick_interval_ms": 500, "tick_damage": 1},
    POISONED: {"duration_ms": 5000, "tick_interval_ms": 1000, "tick_damage": 1, "magnitude": 0.7},
    FROZEN:   {"duration_ms": 1500},
    STUNNED:  {"duration_ms": 1000},
    SLOWED:   {"duration_ms": 2000, "magnitude": 0.5},
}


def reset_statuses(holder):
    holder.statuses = {}


def _ensure_statuses(holder):
    if not hasattr(holder, "statuses") or holder.statuses is None:
        holder.statuses = {}
    return holder.statuses


def apply_status(holder, status_id, now_ticks, *, duration_ms=None,
                 tick_interval_ms=None, tick_damage=None, magnitude=None):
    """Apply *status_id* to *holder*.  Re-applying refreshes duration.

    Returns True when applied, False if the status_id is unknown.
    """
    if status_id not in _DEFAULTS:
        return False
    # Identity rune: Glass Soul dies instantly when stunned.
    import identity_runes  # local to avoid circular dep
    if status_id == STUNNED and identity_runes.glass_soul_stun_kills(holder):
        if hasattr(holder, "current_hp"):
            holder.current_hp = 0
            return True
    spec = _DEFAULTS[status_id]
    statuses = _ensure_statuses(holder)
    entry = {
        "expires_at": now_ticks + (duration_ms if duration_ms is not None else spec["duration_ms"]),
    }
    if "tick_interval_ms" in spec:
        entry["tick_interval_ms"] = (
            tick_interval_ms if tick_interval_ms is not None else spec["tick_interval_ms"]
        )
        entry["tick_damage"] = (
            tick_damage if tick_damage is not None else spec["tick_damage"]
        )
        entry["last_tick_at"] = now_ticks
    if "magnitude" in spec:
        entry["magnitude"] = (
            magnitude if magnitude is not None else spec["magnitude"]
        )
    statuses[status_id] = entry
    return True


def remove_status(holder, status_id):
    statuses = _ensure_statuses(holder)
    return statuses.pop(status_id, None) is not None


def has_status(holder, status_id, now_ticks=None):
    statuses = getattr(holder, "statuses", None) or {}
    entry = statuses.get(status_id)
    if entry is None:
        return False
    if now_ticks is not None and entry["expires_at"] <= now_ticks:
        return False
    return True


def is_immobilized(holder, now_ticks):
    return any(has_status(holder, s, now_ticks) for s in IMMOBILIZING_STATUSES)


def is_silenced(holder, now_ticks):
    return any(has_status(holder, s, now_ticks) for s in SILENCING_STATUSES)


def speed_multiplier(holder, now_ticks):
    """Combined slow factor from active speed-debuff statuses."""
    statuses = getattr(holder, "statuses", None) or {}
    multiplier = 1.0
    for status_id in (SLOWED, POISONED):
        entry = statuses.get(status_id)
        if entry is None or entry["expires_at"] <= now_ticks:
            continue
        if "magnitude" in entry:
            multiplier *= entry["magnitude"]
    return multiplier


def tick_statuses(holder, now_ticks, damage_fn):
    """Advance DOT timers and expire stale statuses.

    *damage_fn(holder, amount)* is called for each DOT tick.  Caller is
    responsible for routing damage through the holder's normal damage
    pipeline so i-frames / armor / death handling apply.
    """
    statuses = getattr(holder, "statuses", None)
    if not statuses:
        return
    for status_id, entry in list(statuses.items()):
        if entry["expires_at"] <= now_ticks:
            statuses.pop(status_id, None)
            continue
        interval = entry.get("tick_interval_ms")
        if interval is None:
            continue
        last = entry.get("last_tick_at", now_ticks)
        if now_ticks - last >= interval:
            damage_fn(holder, entry.get("tick_damage", 0))
            entry["last_tick_at"] = now_ticks
