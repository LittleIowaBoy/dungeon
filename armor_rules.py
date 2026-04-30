"""Equipment-derived stat bonuses (Phase 0e: Golem armor set).

This module owns the *static* mapping from equippable item ids to the
runtime stat bonuses they grant when slotted into a Player loadout.
Earlier armor pieces (``iron_helmet``/``iron_bracers``/``traveler_boots``
and the legacy ``armor`` chest-piece) carry no entries here — their only
effect is to fill the slot, which is intentional baseline behaviour.

Bonuses are aggregated per Player (via :func:`aggregate_equipped_stats`)
and applied through small ``apply_*`` shims invoked from the existing
combat / movement pipelines:

* ``apply_max_hp_bonus``         → :func:`combat_rules.reset_runtime_combat`
* ``apply_speed_multiplier``     → :func:`effect_state_rules.effective_speed_multiplier`
* ``apply_outgoing_damage_multiplier`` → :func:`rpg.RPG._apply_player_hit`
* ``apply_incoming_damage_multiplier`` → :func:`combat_rules.take_damage`
* ``roll_crit_multiplier``       → :func:`rpg.RPG._apply_player_hit`

Boss-loot rolls (Earth biome Golem defeat) live in
:func:`roll_boss_loot`; they consume an injected ``rng`` so tests stay
deterministic.
"""

from __future__ import annotations

import random
from typing import Iterable

from settings import (
    GOLEM_SET_HP_PER_PIECE, GOLEM_HUSK_HP_BONUS,
    GOLEM_CROWN_CRIT_CHANCE, GOLEM_HUSK_DR_FRACTION,
    GOLEM_STRIDE_SPEED_BONUS, GOLEM_FISTS_DAMAGE_BONUS,
    GOLEM_CRIT_MULTIPLIER,
    GOLEM_LOOT_PRIMARY_CHANCE, GOLEM_LOOT_SECONDARY_CHANCE,
)


# ── Bonus table ─────────────────────────────────────────
# Each entry maps an equippable item id to the bonuses it contributes
# while equipped.  Unlisted items contribute nothing.
#
# Bonus keys (all optional, defaults shown):
#   ``max_hp_bonus``         — additive int added to base max HP
#   ``crit_chance``          — additive float in [0, 1]
#   ``damage_reduction``     — additive float in [0, 1] (multiplicatively combined)
#   ``speed_bonus``          — additive float (movement multiplier += value)
#   ``outgoing_damage_bonus``— additive float (damage multiplier += value)
EQUIPMENT_STAT_BONUSES: dict[str, dict[str, float]] = {
    "golem_crown": {
        "max_hp_bonus": GOLEM_SET_HP_PER_PIECE,
        "crit_chance":  GOLEM_CROWN_CRIT_CHANCE,
    },
    "golem_husk": {
        "max_hp_bonus":     GOLEM_HUSK_HP_BONUS,
        "damage_reduction": GOLEM_HUSK_DR_FRACTION,
    },
    "golem_stride": {
        "max_hp_bonus": GOLEM_SET_HP_PER_PIECE,
        "speed_bonus":  GOLEM_STRIDE_SPEED_BONUS,
    },
    "golem_fists": {
        "max_hp_bonus":          GOLEM_SET_HP_PER_PIECE,
        "outgoing_damage_bonus": GOLEM_FISTS_DAMAGE_BONUS,
    },
}

GOLEM_SET_ITEM_IDS = (
    "golem_crown", "golem_husk", "golem_stride", "golem_fists",
)


def _empty_aggregate() -> dict[str, float]:
    return {
        "max_hp_bonus":          0,
        "crit_chance":           0.0,
        "damage_reduction":      0.0,
        "speed_bonus":           0.0,
        "outgoing_damage_bonus": 0.0,
    }


def aggregate_equipped_stats(progress) -> dict[str, float]:
    """Sum all bonuses contributed by *progress*'s equipped slots.

    Safe to call with a ``None`` progress (returns an empty aggregate).
    """
    agg = _empty_aggregate()
    if progress is None:
        return agg
    equipped = getattr(progress, "equipped_slots", None) or {}
    for item_id in equipped.values():
        if item_id is None:
            continue
        bonuses = EQUIPMENT_STAT_BONUSES.get(item_id)
        if not bonuses:
            continue
        for key, value in bonuses.items():
            agg[key] = agg[key] + value
    # Clamp values that must stay in [0, 1].
    agg["crit_chance"]      = max(0.0, min(1.0, agg["crit_chance"]))
    agg["damage_reduction"] = max(0.0, min(0.95, agg["damage_reduction"]))
    return agg


def _player_aggregate(player) -> dict[str, float]:
    progress = getattr(player, "progress", None)
    return aggregate_equipped_stats(progress)


# ── Stat application shims ──────────────────────────────
def apply_max_hp_bonus(player, base_max_hp: int) -> int:
    """Return *base_max_hp* with equipped armor HP bonuses added."""
    bonus = _player_aggregate(player)["max_hp_bonus"]
    return max(1, int(base_max_hp + bonus))


def apply_speed_multiplier(player, base_multiplier: float) -> float:
    """Return *base_multiplier* increased by additive armor speed bonuses."""
    bonus = _player_aggregate(player)["speed_bonus"]
    return base_multiplier * (1.0 + bonus)


def apply_outgoing_damage_multiplier(player, base_damage: int) -> int:
    """Return *base_damage* scaled by additive armor damage bonuses."""
    if base_damage <= 0:
        return base_damage
    bonus = _player_aggregate(player)["outgoing_damage_bonus"]
    return max(0, int(round(base_damage * (1.0 + bonus))))


def apply_incoming_damage_multiplier(player, base_damage: int) -> int:
    """Return *base_damage* reduced by armor damage-reduction multipliers."""
    if base_damage <= 0:
        return base_damage
    dr = _player_aggregate(player)["damage_reduction"]
    if dr <= 0.0:
        return base_damage
    return max(0, int(base_damage * (1.0 - dr)))


def roll_crit_multiplier(player, rng: random.Random | None = None) -> float:
    """Return ``GOLEM_CRIT_MULTIPLIER`` if a crit lands, else ``1.0``.

    *rng* is injected for deterministic tests; defaults to the module's
    global ``random``.
    """
    chance = _player_aggregate(player)["crit_chance"]
    if chance <= 0.0:
        return 1.0
    roller = rng if rng is not None else random
    return GOLEM_CRIT_MULTIPLIER if roller.random() < chance else 1.0


# ── Boss loot ───────────────────────────────────────────
def _golem_set_drop_pool(progress, exclude: Iterable[str] = ()) -> list[str]:
    """Return Golem set ids the player does not yet own (anywhere)."""
    excluded = set(exclude)
    out = []
    for item_id in GOLEM_SET_ITEM_IDS:
        if item_id in excluded:
            continue
        if progress is None:
            out.append(item_id)
            continue
        if progress.total_owned(item_id) > 0:
            continue
        out.append(item_id)
    return out


def roll_boss_loot(progress, rng: random.Random | None = None) -> list[str]:
    """Return up to 2 Golem set item ids dropped by a single defeat.

    Drop math: a primary roll at :data:`GOLEM_LOOT_PRIMARY_CHANCE`,
    followed by a secondary roll at :data:`GOLEM_LOOT_SECONDARY_CHANCE`
    if the primary succeeded.  Pieces the player already owns are
    excluded from the pool so each defeat advances the set.
    """
    roller = rng if rng is not None else random
    drops: list[str] = []
    pool = _golem_set_drop_pool(progress)
    if not pool:
        return drops
    if roller.random() >= GOLEM_LOOT_PRIMARY_CHANCE:
        return drops
    drops.append(roller.choice(pool))
    pool = _golem_set_drop_pool(progress, exclude=drops)
    if pool and roller.random() < GOLEM_LOOT_SECONDARY_CHANCE:
        drops.append(roller.choice(pool))
    return drops


def grant_boss_loot(progress, drops: Iterable[str]) -> list[str]:
    """Add each id in *drops* to the player's equipment storage.

    Returns the granted ids (echoes input) so callers can drive HUD /
    log lines from the same call.
    """
    granted: list[str] = []
    if progress is None:
        return granted
    for item_id in drops:
        progress.add_to_equipment_storage(item_id, 1)
        granted.append(item_id)
    return granted
