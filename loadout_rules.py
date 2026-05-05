"""Loadout and equipment rules for PlayerProgress."""

import status_effects
from item_catalog import (
    DEFAULT_EQUIPPED_SLOTS,
    EQUIPMENT_SLOTS,
    ITEM_DATABASE,
    RING_EQUIPMENT_SLOTS,
    STARTER_WEAPON_IDS,
    UPGRADEABLE_WEAPON_IDS,
    WEAPON_EQUIPMENT_SLOTS,
)


def ensure_loadout_state(progress):
    normalize_equipped_slots(progress)
    normalize_weapon_upgrades(progress)
    ensure_starter_weapons_owned(progress)


# ── Ring slot unlock helpers ────────────────────────────────────────────────
def unlocked_ring_slot_count(progress) -> int:
    """Return the number of ring slots currently available (1-4).

    One slot is always unlocked; each meta_keystone owned unlocks one more,
    up to a maximum of 4.
    """
    keystones = getattr(progress, "meta_keystones", 0)
    return 1 + min(keystones, 3)


def is_ring_slot_unlocked(progress, slot: str) -> bool:
    """Return True if *slot* is a ring slot that is currently unlocked."""
    if slot not in RING_EQUIPMENT_SLOTS:
        return True  # non-ring slots are always "unlocked"
    slot_index = RING_EQUIPMENT_SLOTS.index(slot)  # 0-based
    return slot_index < unlocked_ring_slot_count(progress)


def normalize_equipped_slots(progress):
    normalized_slots = {
        slot: progress.equipped_slots.get(slot, DEFAULT_EQUIPPED_SLOTS.get(slot))
        for slot in EQUIPMENT_SLOTS
    }
    seen_weapons = set()

    for slot, item_id in tuple(normalized_slots.items()):
        if item_id is None:
            continue

        item_data = ITEM_DATABASE.get(item_id)
        if item_data is None or not item_data.get("is_equippable"):
            normalized_slots[slot] = None
            continue

        valid_slots = item_data.get("equipment_slots", [])
        if slot not in valid_slots:
            progress.add_to_equipment_storage(item_id)
            normalized_slots[slot] = None
            continue

        if slot in WEAPON_EQUIPMENT_SLOTS:
            if item_id in seen_weapons:
                progress.add_to_equipment_storage(item_id)
                normalized_slots[slot] = None
                continue
            seen_weapons.add(item_id)

    progress.equipped_slots = normalized_slots


def normalize_weapon_upgrades(progress):
    normalized_upgrades = {}
    for weapon_id in UPGRADEABLE_WEAPON_IDS:
        try:
            tier = int(progress.weapon_upgrades.get(weapon_id, 0))
        except (TypeError, ValueError):
            tier = 0
        normalized_upgrades[weapon_id] = max(0, tier)
    progress.weapon_upgrades = normalized_upgrades


def ensure_starter_weapons_owned(progress):
    for weapon_id in STARTER_WEAPON_IDS:
        if progress.total_owned(weapon_id) > 0:
            continue
        default_slot = next(
            (
                slot_name
                for slot_name, default_item_id in DEFAULT_EQUIPPED_SLOTS.items()
                if default_item_id == weapon_id
            ),
            None,
        )
        if default_slot and progress.equipped_slots.get(default_slot) is None:
            progress.equipped_slots[default_slot] = weapon_id
        else:
            progress.add_to_equipment_storage(weapon_id)


def build_runtime_weapon_state(progress, weapon_factory):
    ensure_loadout_state(progress)

    weapon_ids = []
    weapons = []
    for slot_key in WEAPON_EQUIPMENT_SLOTS:
        weapon_id = progress.equipped_slots.get(slot_key)
        weapon = weapon_factory(weapon_id)
        if weapon is None:
            continue
        weapon_ids.append(weapon_id)
        weapons.append(weapon)

    return {
        "weapon_ids": weapon_ids,
        "weapons": weapons,
        "weapon_upgrade_tiers": resolve_runtime_weapon_upgrade_tiers(progress),
    }


def resolve_runtime_weapon_upgrade_tiers(progress):
    return dict(getattr(progress, "weapon_upgrades", {}))


def can_equip(progress, slot, item_id):
    if slot not in progress.equipped_slots:
        return False
    item_data = ITEM_DATABASE.get(item_id)
    if item_data is None or not item_data.get("is_equippable"):
        return False
    if slot not in item_data.get("equipment_slots", []):
        return False
    if progress.equipped_slots.get(slot) == item_id:
        return True
    if slot in WEAPON_EQUIPMENT_SLOTS:
        other_slot = "weapon_2" if slot == "weapon_1" else "weapon_1"
        if progress.equipped_slots.get(other_slot) == item_id:
            return False
    # Ring-slot rules: locked slot + no duplicate ring ids.
    if slot in RING_EQUIPMENT_SLOTS:
        if not is_ring_slot_unlocked(progress, slot):
            return False
        for ring_slot in RING_EQUIPMENT_SLOTS:
            if ring_slot != slot and progress.equipped_slots.get(ring_slot) == item_id:
                return False
    return progress.equipment_storage.get(item_id, 0) > 0


def equip_item(progress, slot, item_id, *, player=None):
    if not can_equip(progress, slot, item_id):
        return False
    current_item = progress.equipped_slots.get(slot)
    if current_item == item_id:
        return True
    if current_item is not None:
        progress.add_to_equipment_storage(current_item)
    progress.remove_from_equipment_storage(item_id)
    progress.equipped_slots[slot] = item_id
    # On-equip hooks.
    if item_id == "serpent_charm" and player is not None:
        status_effects.remove_status(player, status_effects.POISONED)
    return True


def unequip_slot(progress, slot):
    item_id = progress.equipped_slots.get(slot)
    if item_id is None:
        return False
    progress.add_to_equipment_storage(item_id)
    progress.equipped_slots[slot] = None
    return True


def force_equip_item(progress, slot, item_id):
    """Test-room equip: bypass ownership / equipment_storage checks.

    Validates slot existence, that the item is equippable, that the slot
    appears in the item's ``equipment_slots`` list, and the dual-weapon
    rule.  Does not require a positive ``equipment_storage`` count and
    does not mutate storage; the slot is simply overwritten.  Intended
    for use only inside the bespoke test-room pause menu where the
    surrounding flow snapshots and restores all loadout state.
    """
    if slot not in progress.equipped_slots:
        return False
    item_data = ITEM_DATABASE.get(item_id)
    if item_data is None or not item_data.get("is_equippable"):
        return False
    if slot not in item_data.get("equipment_slots", []):
        return False
    if slot in WEAPON_EQUIPMENT_SLOTS:
        other_slot = "weapon_2" if slot == "weapon_1" else "weapon_1"
        if progress.equipped_slots.get(other_slot) == item_id:
            return False
    progress.equipped_slots[slot] = item_id
    return True


def force_unequip_slot(progress, slot):
    """Test-room unequip: clear slot without touching equipment_storage."""
    if slot not in progress.equipped_slots:
        return False
    progress.equipped_slots[slot] = None
    return True