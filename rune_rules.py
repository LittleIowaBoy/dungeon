"""Pure helpers for managing rune loadouts and per-room rune state.

The rune system stores its persistent loadout on
:class:`progress.PlayerProgress` and a parallel runtime mirror on the
:class:`player.Player`.  All mutation flows through the helpers in this
module so that snapshot/restore, save/load, and altar interactions stay
consistent.

Effect resolution (damage modifiers, ability triggers, etc.) is handled
by individual rule modules that inspect ``player.equipped_runes`` and
``player.rune_state`` via :func:`has_rune` and the ``rune_state`` helpers
defined here.
"""

from rune_catalog import (
    RUNE_CATEGORIES,
    RUNE_CATEGORY_BEHAVIOR,
    RUNE_CATEGORY_IDENTITY,
    RUNE_CATEGORY_STAT,
    RUNE_DATABASE,
    RUNE_RARITY_WEIGHTS,
    RUNE_SLOT_CAPACITY,
    get_rune,
    runes_by_category,
)


# ── slot model ──────────────────────────────────────────
def empty_loadout():
    """Return a fresh empty equipped-rune mapping."""
    return {category: [] for category in RUNE_CATEGORIES}


def normalize_loadout(loadout):
    """Return a defensive copy of *loadout* with all categories present.

    Unknown rune ids are dropped.  Ordering within each category is
    preserved.  Excess entries beyond category capacity are truncated.
    """
    if not isinstance(loadout, dict):
        loadout = {}
    normalized = empty_loadout()
    for category in RUNE_CATEGORIES:
        capacity = RUNE_SLOT_CAPACITY[category]
        seen = set()
        for rune_id in loadout.get(category, ()):
            if rune_id in seen:
                continue
            rune = get_rune(rune_id)
            if rune is None or rune.category != category:
                continue
            normalized[category].append(rune_id)
            seen.add(rune_id)
            if len(normalized[category]) >= capacity:
                break
    return normalized


def serialize_loadout(loadout):
    """Return a plain ``dict[str, list[str]]`` safe for persistence."""
    normalized = normalize_loadout(loadout)
    return {category: list(ids) for category, ids in normalized.items()}


# ── query ───────────────────────────────────────────────
def equipped_runes(holder):
    """Return the equipped-runes mapping on *holder* (player or progress).

    Falls back to an empty loadout if the attribute is missing.
    """
    return getattr(holder, "equipped_runes", None) or empty_loadout()


def has_rune(holder, rune_id):
    """Return True if *holder* has *rune_id* equipped in any category."""
    rune = get_rune(rune_id)
    if rune is None:
        return False
    loadout = equipped_runes(holder)
    return rune_id in loadout.get(rune.category, ())


def equipped_rune_ids(holder):
    """Yield every equipped rune id on *holder* across all categories."""
    loadout = equipped_runes(holder)
    for category in RUNE_CATEGORIES:
        for rune_id in loadout.get(category, ()):
            yield rune_id


def slot_is_full(holder, category):
    """Return True if *category* on *holder* is at capacity."""
    capacity = RUNE_SLOT_CAPACITY.get(category, 0)
    loadout = equipped_runes(holder)
    return len(loadout.get(category, ())) >= capacity


# ── mutate ──────────────────────────────────────────────
def equip_rune(holder, rune_id, *, replace_index=None):
    """Equip *rune_id* on *holder*.

    Returns ``True`` on success, ``False`` if the rune is unknown, the
    holder already has it, or the slot is full and *replace_index* is
    ``None``.

    When *replace_index* is provided and the slot is full, the existing
    rune at that index is swapped out.
    """
    rune = get_rune(rune_id)
    if rune is None:
        return False

    loadout = equipped_runes(holder)
    category_runes = loadout.setdefault(rune.category, [])

    if rune_id in category_runes:
        return False

    capacity = RUNE_SLOT_CAPACITY[rune.category]
    if len(category_runes) >= capacity:
        if replace_index is None or not (0 <= replace_index < len(category_runes)):
            return False
        category_runes[replace_index] = rune_id
    else:
        category_runes.append(rune_id)

    setattr(holder, "equipped_runes", loadout)
    return True


def unequip_rune(holder, rune_id):
    """Remove *rune_id* from *holder*. Returns True if removed."""
    rune = get_rune(rune_id)
    if rune is None:
        return False
    loadout = equipped_runes(holder)
    category_runes = loadout.get(rune.category, [])
    if rune_id not in category_runes:
        return False
    category_runes.remove(rune_id)
    setattr(holder, "equipped_runes", loadout)
    return True


def clear_loadout(holder):
    """Wipe every equipped rune on *holder*. Used on dungeon end/death."""
    setattr(holder, "equipped_runes", empty_loadout())


# ── runtime mirror sync ─────────────────────────────────
def sync_runtime_to_progress(player, progress):
    """Copy *progress*'s equipped runes onto *player* and reset rune state."""
    player.equipped_runes = serialize_loadout(getattr(progress, "equipped_runes", None))
    player.rune_state = {}


def sync_progress_to_runtime(progress, player):
    """Persist *player*'s current rune loadout back onto *progress*."""
    progress.equipped_runes = serialize_loadout(getattr(player, "equipped_runes", None))


# ── per-room state reset ────────────────────────────────
def on_room_enter(player):
    """Reset rune-specific per-room counters (kill stacks, first-hit, etc.).

    Effect modules read/write keys under ``player.rune_state``; this hook
    clears the room-scoped subspace so each room starts fresh.
    """
    if not hasattr(player, "rune_state") or player.rune_state is None:
        player.rune_state = {}
    player.rune_state["room"] = {}
    # Drop any in-flight boomerang returns — their saved positions are
    # in the previous room's coordinate context.
    player.rune_state["boomerang_pending"] = []


# ── altar offer generation ──────────────────────────────
_DEFAULT_OFFER_CATEGORIES = (
    RUNE_CATEGORY_STAT,
    RUNE_CATEGORY_BEHAVIOR,
    RUNE_CATEGORY_IDENTITY,
)


def _weighted_choice(rng, runes):
    """Pick one rune from *runes* weighted by rarity. Returns ``None`` if empty."""
    pool = tuple(runes)
    if not pool:
        return None
    weights = [RUNE_RARITY_WEIGHTS.get(rune.rarity, 1) for rune in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def generate_altar_offer(rng, *, exclude_ids=(), category_order=_DEFAULT_OFFER_CATEGORIES):
    """Return up to 3 rune ids — one per category in *category_order*.

    Picks within each category are rarity-weighted.  Any rune id in
    *exclude_ids* (typically the player's currently equipped runes) is
    skipped so the altar never offers a rune the player already holds.
    Falls back across categories if a category has no eligible runes.
    """
    excluded = set(exclude_ids)
    chosen = []
    for category in category_order:
        eligible = tuple(
            rune for rune in runes_by_category(category)
            if rune.rune_id not in excluded
        )
        pick = _weighted_choice(rng, eligible)
        if pick is None:
            continue
        chosen.append(pick.rune_id)
        excluded.add(pick.rune_id)
    return tuple(chosen)


def equip_altar_pick(player, progress, rune_id):
    """Equip *rune_id* from an altar pick onto both player and progress.

    If the target category is full, the rune at index 0 is replaced
    (FIFO).  Returns ``True`` on success.
    """
    rune = get_rune(rune_id)
    if rune is None:
        return False

    replace_index = 0 if slot_is_full(progress, rune.category) else None
    if not equip_rune(progress, rune_id, replace_index=replace_index):
        return False
    sync_runtime_to_progress(player, progress)
    return True
