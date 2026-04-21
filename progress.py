"""Player and dungeon progress tracking.

PlayerProgress is the single source of truth for persistent state.
It is loaded from / saved to the SQLite database via save_system.
"""
from dungeon_config import DUNGEONS
from items import (
    DEFAULT_EQUIPPED_SLOTS,
    EQUIPMENT_SLOTS,
    ITEM_DATABASE,
    LEGACY_WEAPON_PLUS_IDS,
    STARTER_WEAPON_IDS,
    UPGRADEABLE_WEAPON_IDS,
)


class DungeonProgress:
    """Tracks a single dungeon's run state."""

    def __init__(self, dungeon_id, current_level=0, is_alive=True, completed=False):
        self.dungeon_id = dungeon_id
        self.current_level = current_level
        self.is_alive = is_alive
        self.completed = completed

    def advance_level(self, total_levels=5):
        """Move to the next level. Returns True if dungeon is now complete."""
        if self.current_level >= total_levels - 1:
            self.completed = True
            return True
        self.current_level += 1
        return False

    def reset(self):
        """Reset dungeon to the beginning (used on death)."""
        self.current_level = 0
        self.is_alive = True
        self.completed = False

    def die(self):
        """Mark the player as dead in this dungeon and reset to level 0."""
        self.is_alive = False
        self.current_level = 0


class PlayerProgress:
    """Aggregates all persistent player state."""

    def __init__(self):
        self.coins = 0
        self.max_hp = 100
        self.speed_cap = 1.5
        self.dungeons: dict[str, DungeonProgress] = {}
        self.inventory: dict[str, int] = {}  # item_id -> quantity
        self.equipment_storage: dict[str, int] = {}
        self.equipped_slots: dict[str, str | None] = dict(DEFAULT_EQUIPPED_SLOTS)
        self.weapon_upgrades: dict[str, int] = {
            weapon_id: 0 for weapon_id in UPGRADEABLE_WEAPON_IDS
        }

        # Equipment state (persists across levels, lost on death)
        self.armor_hp = 0        # current armor durability
        self.compass_uses = 0    # remaining compass uses

        # create an entry for every defined dungeon
        for d in DUNGEONS:
            self.dungeons[d["id"]] = DungeonProgress(d["id"])

        self.ensure_loadout_state()

    def get_dungeon(self, dungeon_id) -> DungeonProgress:
        if dungeon_id not in self.dungeons:
            self.dungeons[dungeon_id] = DungeonProgress(dungeon_id)
        return self.dungeons[dungeon_id]

    def can_resume(self, dungeon_id) -> bool:
        dp = self.get_dungeon(dungeon_id)
        return dp.is_alive and dp.current_level > 0 and not dp.completed

    def ensure_loadout_state(self):
        for slot in EQUIPMENT_SLOTS:
            self.equipped_slots.setdefault(slot, DEFAULT_EQUIPPED_SLOTS.get(slot))
        for weapon_id in UPGRADEABLE_WEAPON_IDS:
            self.weapon_upgrades.setdefault(weapon_id, 0)
        self._ensure_starter_weapons_owned()

    def _ensure_starter_weapons_owned(self):
        for weapon_id in STARTER_WEAPON_IDS:
            if self.total_owned(weapon_id) > 0:
                continue
            default_slot = next(
                (
                    slot_name
                    for slot_name, default_item_id in DEFAULT_EQUIPPED_SLOTS.items()
                    if default_item_id == weapon_id
                ),
                None,
            )
            if default_slot and self.equipped_slots.get(default_slot) is None:
                self.equipped_slots[default_slot] = weapon_id
            else:
                self.add_to_equipment_storage(weapon_id)

    def migrate_legacy_state(self):
        for legacy_item_id, weapon_id in LEGACY_WEAPON_PLUS_IDS.items():
            if self.inventory.pop(legacy_item_id, 0) > 0:
                self.set_weapon_upgrade(weapon_id, 1)

        if self.inventory.pop("armor", 0) > 0 and self.total_owned("armor") == 0:
            if self.equipped_slots.get("chest") is None:
                self.equipped_slots["chest"] = "armor"
            else:
                self.add_to_equipment_storage("armor")

        self.ensure_loadout_state()

    def total_owned(self, item_id):
        equipped = sum(1 for equipped_item in self.equipped_slots.values()
                       if equipped_item == item_id)
        return (
            self.inventory.get(item_id, 0)
            + self.equipment_storage.get(item_id, 0)
            + equipped
        )

    def add_to_equipment_storage(self, item_id, quantity=1):
        if quantity <= 0:
            return
        self.equipment_storage[item_id] = (
            self.equipment_storage.get(item_id, 0) + quantity
        )

    def remove_from_equipment_storage(self, item_id, quantity=1):
        current = self.equipment_storage.get(item_id, 0)
        if quantity <= 0 or current < quantity:
            return False
        remaining = current - quantity
        if remaining > 0:
            self.equipment_storage[item_id] = remaining
        else:
            del self.equipment_storage[item_id]
        return True

    def can_equip(self, slot, item_id):
        if slot not in self.equipped_slots:
            return False
        item_data = ITEM_DATABASE.get(item_id)
        if item_data is None or not item_data.get("is_equippable"):
            return False
        if slot not in item_data.get("equipment_slots", []):
            return False
        if self.equipped_slots.get(slot) == item_id:
            return True
        if slot in ("weapon_1", "weapon_2"):
            other_slot = "weapon_2" if slot == "weapon_1" else "weapon_1"
            if self.equipped_slots.get(other_slot) == item_id:
                return False
        return self.equipment_storage.get(item_id, 0) > 0

    def equip_item(self, slot, item_id):
        if not self.can_equip(slot, item_id):
            return False
        current_item = self.equipped_slots.get(slot)
        if current_item == item_id:
            return True
        if current_item is not None:
            self.add_to_equipment_storage(current_item)
        self.remove_from_equipment_storage(item_id)
        self.equipped_slots[slot] = item_id
        return True

    def unequip_slot(self, slot):
        item_id = self.equipped_slots.get(slot)
        if item_id is None:
            return False
        self.add_to_equipment_storage(item_id)
        self.equipped_slots[slot] = None
        return True

    def weapon_upgrade_tier(self, weapon_id):
        return self.weapon_upgrades.get(weapon_id, 0)

    def set_weapon_upgrade(self, weapon_id, tier):
        if weapon_id not in self.weapon_upgrades:
            self.weapon_upgrades[weapon_id] = 0
        self.weapon_upgrades[weapon_id] = max(self.weapon_upgrades[weapon_id], tier)

    def die_in_dungeon(self, dungeon_id):
        self.get_dungeon(dungeon_id).die()
        # Clear equipment that is lost on death
        self.armor_hp = 0
        self.compass_uses = 0
        for legacy_item_id in LEGACY_WEAPON_PLUS_IDS:
            self.inventory.pop(legacy_item_id, None)
        for weapon_id in self.weapon_upgrades:
            self.weapon_upgrades[weapon_id] = 0
        self.inventory.pop("armor", None)
        self.inventory.pop("compass", None)
        self.equipment_storage.pop("armor", None)
        if self.equipped_slots.get("chest") == "armor":
            self.equipped_slots["chest"] = None
        self.ensure_loadout_state()

    def advance_in_dungeon(self, dungeon_id, total_levels=5):
        return self.get_dungeon(dungeon_id).advance_level(total_levels)

    def start_dungeon(self, dungeon_id):
        """Prepare a dungeon for a fresh start (or resume)."""
        dp = self.get_dungeon(dungeon_id)
        dp.is_alive = True
        self.ensure_loadout_state()
