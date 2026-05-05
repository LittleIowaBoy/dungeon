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
    DAMAGE_TYPES,
    ARMOR_HP_BY_RARITY_BY_SLOT,
)


# ── Bonus table ─────────────────────────────────────────
# Each entry maps an equippable item id to the bonuses it contributes
# while equipped.  Unlisted items contribute nothing.
#
# Bonus keys (all optional, defaults shown):
#   ``max_hp_bonus``         — additive int added to base max HP
#   ``crit_chance``          — additive float in [0, 1]
#   ``damage_reduction``     — additive float in [0, 1] (capped at 0.95)
#   ``speed_bonus``          — additive float (movement multiplier += value)
#   ``outgoing_damage_bonus``— additive float (damage multiplier += value)
#   ``magic_find``           — additive float (enemy/chest drop quality boost)
#   ``attack_speed_bonus``   — additive float (attack cooldown multiplier)
#   ``dodge_cooldown_mult``  — additive float (negative = shorter cooldown)
#   ``dodge_distance_mult``  — additive float (positive = longer/faster dodge)
#   ``minimap_radius_bonus`` — additive int (extra minimap visibility radius)
#   ``damage_resistance``    — dict[str, float] (per-type resist; handled
#                              separately by aggregate_damage_resistances)
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
    # ── Wayfarer set (light) ────────────────────────────
    "wayfarer_hood": {
        "magic_find": 0.06,
    },
    "wayfarer_jerkin": {
        "speed_bonus": 0.05,
    },
    "wayfarer_wraps": {
        "attack_speed_bonus": 0.05,
    },
    "wayfarer_treads": {
        "speed_bonus":         0.10,
        "dodge_cooldown_mult": -0.15,
    },
    # ── Spellweave set (arcane) ─────────────────────────
    "spellweave_circlet": {
        "crit_chance":          0.08,
        "minimap_radius_bonus": 1,
    },
    "spellweave_robe": {
        "damage_resistance": {"arcane": 0.15},
    },
    "spellweave_cuffs": {
        "outgoing_damage_bonus": 0.08,
    },
    "spellweave_slippers": {
        "speed_bonus":        0.12,
        "dodge_distance_mult": 0.25,
    },
    # ── Ring accessories ─────────────────────────────────────────────────────
    "band_of_vigor": {
        "max_hp_bonus": 5,
    },
    "band_of_haste": {
        "speed_bonus": 0.03,
    },
    "band_of_focus": {
        "crit_chance": 0.03,
    },
    "band_of_grit": {
        "max_hp_bonus":     10,
        "damage_reduction": 0.02,
    },
    "ember_signet": {
        "outgoing_damage_bonus":  0.03,
        "damage_resistance": {"fire": 0.10},
    },
    "frostbound_ring": {
        "speed_bonus":  0.05,
        "crit_chance":  0.03,
        "damage_resistance": {"ice": 0.15},
    },
    "viper_loop": {
        "attack_speed_bonus": 0.05,
        "damage_resistance": {"poison": 0.15},
    },
    "stormcoil": {
        "crit_chance":         0.08,
        "dodge_cooldown_mult": -0.03,
        "damage_resistance": {"lightning": 0.20},
    },
    "arcane_circlet_ring": {
        "max_hp_bonus": 5,
        "magic_find":   0.05,
        "damage_resistance": {"arcane": 0.20},
    },
    "bloodstone_ring": {
        "outgoing_damage_bonus": 0.15,
        "lifesteal_on_kill":     5,
    },
    "wyrm_seal": {
        "max_hp_bonus": 20,
        "damage_resistance": {
            "fire": 0.15, "ice": 0.15, "poison": 0.15,
            "lightning": 0.15, "arcane": 0.15,
        },
    },
    "oathbinder": {
        "max_hp_bonus":          10,
        "speed_bonus":           0.10,
        "crit_chance":           0.10,
        "outgoing_damage_bonus": 0.10,
        "bonus_dodges_per_room": 1,
    },
    # ── Pendant accessories ──────────────────────────────────────────────────
    "tarnished_amulet": {
        "damage_resistance": {"physical": 0.05},
    },
    "cinder_pendant": {
        "damage_resistance": {"fire": 0.15},
    },
    "glacial_locket": {
        "damage_resistance": {"ice": 0.15},
    },
    "serpent_charm": {
        "damage_resistance": {"poison": 0.20},
    },
    "stormcaller_pendant": {
        "damage_resistance": {"lightning": 0.20},
    },
    "wardstone": {
        "damage_resistance": {
            "arcane": 0.25,
            "physical": 0.05, "fire": 0.05, "ice": 0.05,
            "poison": 0.05, "lightning": 0.05, "blunt": 0.05, "pierce": 0.05,
        },
    },
    "aegis_of_the_deep": {
        "max_hp_bonus": 15,
        "damage_resistance": {"physical": 0.30},
    },
    "prismatic_pendant": {
        "damage_resistance": {
            "physical": 0.20, "fire": 0.20, "ice": 0.20,
            "poison": 0.20, "lightning": 0.20, "arcane": 0.20,
            "blunt": 0.20, "pierce": 0.20,
        },
    },
}

# ── Belt per-piece bonus table ───────────────────────────────────────────────
# Belts grant bonuses that scale with the number of equipped body-armor pieces
# (helmet/chest/arms/legs) whose ``theme_tag`` matches the belt's theme.
# ``theme_match=None`` means every equipped armor piece counts.
#
# Each entry may contain scalar bonus keys (summed × piece_count) and/or a
# nested ``damage_resistance`` dict (values also scaled × piece_count).
BELT_PER_PIECE_BONUSES: dict[str, dict] = {
    "leather_strap": {
        "theme_match": None,
        "max_hp_bonus": 2,
    },
    "bulwark_belt": {
        "theme_match": "heavy",
        "damage_reduction": 0.03,
    },
    "runner_sash": {
        "theme_match": "light",
        "speed_bonus": 0.03,
    },
    "mage_cord": {
        "theme_match": "arcane",
        "damage_resistance": {"arcane": 0.05},
        "magic_find": 0.05,
    },
    "phoenix_girdle": {
        "theme_match": "heavy",
        "damage_reduction": 0.05,
        "damage_resistance": {"fire": 0.04},
        "max_hp_bonus": 2,
    },
}

_ARMOR_BODY_SLOTS = ("helmet", "chest", "arms", "legs")


def _count_armor_pieces_with_theme(progress, theme) -> int:
    """Count body armor slots (helmet/chest/arms/legs) matching *theme*.

    If *theme* is ``None`` every non-empty slot counts.
    """
    from item_catalog import ITEM_DATABASE
    equipped = getattr(progress, "equipped_slots", None) or {}
    count = 0
    for slot in _ARMOR_BODY_SLOTS:
        item_id = equipped.get(slot)
        if item_id is None:
            continue
        if theme is None:
            count += 1
        else:
            item_data = ITEM_DATABASE.get(item_id, {})
            if item_data.get("theme_tag") == theme:
                count += 1
    return count


def _belt_bonus_stats(progress) -> dict:
    """Return a bonus dict (scaled by matching piece count) for the equipped belt.

    Returns an empty dict when no belt is equipped or no pieces match.
    The dict may contain both scalar keys and a ``damage_resistance`` sub-dict.
    """
    equipped = getattr(progress, "equipped_slots", None) or {}
    belt_id = equipped.get("belt")
    if belt_id is None:
        return {}
    belt_def = BELT_PER_PIECE_BONUSES.get(belt_id)
    if belt_def is None:
        return {}
    theme = belt_def.get("theme_match")
    count = _count_armor_pieces_with_theme(progress, theme)
    if count == 0:
        return {}
    result: dict = {}
    for key, value in belt_def.items():
        if key == "theme_match":
            continue
        if isinstance(value, dict):
            result[key] = {k: v * count for k, v in value.items()}
        else:
            result[key] = value * count
    return result


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
    Includes dynamically-scaled belt bonuses.
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
            # Skip non-scalar bonus keys (e.g. ``damage_resistance`` dicts
            # handled by ``aggregate_damage_resistances``).
            if not isinstance(value, (int, float)):
                continue
            agg[key] = agg.get(key, 0.0) + value
    # Merge belt per-piece scalar bonuses.
    belt_bonus = _belt_bonus_stats(progress)
    for key, value in belt_bonus.items():
        if isinstance(value, (int, float)):
            agg[key] = agg.get(key, 0.0) + value
    # Clamp values that must stay in [0, 1].
    agg["crit_chance"]      = max(0.0, min(1.0, agg["crit_chance"]))
    agg["damage_reduction"] = max(0.0, min(0.95, agg["damage_reduction"]))
    return agg


def _player_aggregate(player) -> dict[str, float]:
    progress = getattr(player, "progress", None)
    return aggregate_equipped_stats(progress)


def _player_progress(player):
    return getattr(player, "progress", None)


# ── Per-type damage resistance ───────────────────────────────────────────────
# Items may declare ``"damage_resistance": {"fire": 0.15, "ice": 0.10}`` in
# EQUIPMENT_STAT_BONUSES.  These are summed per type across all slots and
# capped at 85% to prevent full immunity.

_DAMAGE_RESISTANCE_CAP = 0.85


def aggregate_damage_resistances(progress) -> dict[str, float]:
    """Sum ``damage_resistance`` dicts across all equipped items.

    Includes dynamically-scaled belt resistance bonuses.
    Returns a dict keyed by damage type (only types with non-zero totals
    are included).  Safe to call with ``None`` progress.
    """
    totals: dict[str, float] = {}
    if progress is None:
        return totals
    equipped = getattr(progress, "equipped_slots", None) or {}
    for item_id in equipped.values():
        if item_id is None:
            continue
        bonuses = EQUIPMENT_STAT_BONUSES.get(item_id)
        if not bonuses:
            continue
        resist_map = bonuses.get("damage_resistance")
        if not resist_map:
            continue
        for dtype, value in resist_map.items():
            totals[dtype] = totals.get(dtype, 0.0) + value
    # Merge belt per-piece resistance bonuses.
    belt_bonus = _belt_bonus_stats(progress)
    resist_map = belt_bonus.get("damage_resistance") or {}
    for dtype, value in resist_map.items():
        totals[dtype] = totals.get(dtype, 0.0) + value
    return totals


def total_damage_resistance(progress, damage_type: str) -> float:
    """Return the capped resistance fraction (0.0–0.85) for *damage_type*.

    Returns 0.0 if the player has no resistance to that damage type.
    """
    totals = aggregate_damage_resistances(progress)
    raw = totals.get(damage_type, 0.0)
    return max(0.0, min(_DAMAGE_RESISTANCE_CAP, raw))


# ── Armor HP helpers ─────────────────────────────────────────────────────────
# Each equipped armor piece contributes a rarity+slot-scaled HP pool that
# absorbs incoming damage (progress.armor_hp) and is refilled at the start
# of each dungeon floor.


def armor_hp_for_item(item_id: str) -> int:
    """Return the armor HP contributed by *item_id* based on its rarity and slot.

    Returns 0 for weapons, consumables, or items not in a body armor slot.
    """
    from item_catalog import ITEM_DATABASE  # local to avoid circular import
    item = ITEM_DATABASE.get(item_id)
    if item is None:
        return 0
    slots = item.get("equipment_slots", [])
    if not slots:
        return 0
    slot = slots[0]
    if slot not in _ARMOR_BODY_SLOTS:
        return 0
    rarity = item.get("rarity", "common")
    table = ARMOR_HP_BY_RARITY_BY_SLOT.get(rarity, {})
    return table.get(slot, 0)


def compute_total_armor_hp(progress) -> int:
    """Sum armor HP across all equipped body-armor slots for *progress*.

    Returns 0 when no armor is equipped or progress is None.
    """
    if progress is None:
        return 0
    equipped = getattr(progress, "equipped_slots", None) or {}
    total = 0
    for slot, item_id in equipped.items():
        if item_id is None or slot not in _ARMOR_BODY_SLOTS:
            continue
        total += armor_hp_for_item(item_id)
    return total


def refill_armor_hp(progress) -> None:
    """Set progress.armor_hp to the total computed from equipped armor.

    Called on dungeon-floor entry and on armor purchases in the shop.
    """
    if progress is None:
        return
    progress.armor_hp = compute_total_armor_hp(progress)


# ── Magic find ───────────────────────────────────────────────────────────────
_MAGIC_FIND_CAP = 0.50


def apply_magic_find(base_chance: float, progress) -> float:
    """Return *base_chance* boosted by the player's magic_find equipment bonus.

    The combined magic_find multiplier is capped at 50% above base.
    Safe to call with None progress (returns base_chance unchanged).
    """
    bonuses = aggregate_equipped_stats(progress)
    mf = min(_MAGIC_FIND_CAP, bonuses.get("magic_find", 0.0))
    return min(1.0, base_chance * (1.0 + mf))


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


def apply_incoming_damage_multiplier(player, base_damage: int, damage_type: str | None = None) -> int:
    """Return *base_damage* reduced by armor damage-reduction multipliers.

    Flat ``damage_reduction`` from equipment always applies.
    If *damage_type* is supplied, the per-type resistance for that damage
    type is also applied, capped independently at 85%.
    """
    if base_damage <= 0:
        return base_damage
    dr = _player_aggregate(player)["damage_reduction"]
    if dr > 0.0:
        base_damage = max(0, int(base_damage * (1.0 - dr)))
    if damage_type is not None and base_damage > 0:
        resist = total_damage_resistance(_player_progress(player), damage_type)
        if resist > 0.0:
            base_damage = max(0, int(base_damage * (1.0 - resist)))
    return base_damage


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
