"""Player and dungeon progress tracking.

PlayerProgress is the single source of truth for persistent state.
It is loaded from / saved to the SQLite database via save_system.
"""
import copy

from dungeon_config import DUNGEONS
import loadout_rules
from item_catalog import (
    DEFAULT_EQUIPPED_SLOTS,
    EQUIPMENT_SLOTS,
    ITEM_DATABASE,
    LEGACY_WEAPON_PLUS_IDS,
    STARTER_WEAPON_IDS,
    UPGRADEABLE_WEAPON_IDS,
    WEAPON_EQUIPMENT_SLOTS,
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

    def snapshot_run_state(self):
        """Capture progress that should revert when a level is abandoned."""
        return {
            "coins": self.coins,
            "inventory": copy.deepcopy(self.inventory),
            "armor_hp": self.armor_hp,
            "compass_uses": self.compass_uses,
        }

    def restore_run_state(self, snapshot):
        """Restore progress captured by snapshot_run_state()."""
        self.coins = snapshot["coins"]
        self.inventory = copy.deepcopy(snapshot["inventory"])
        self.armor_hp = snapshot["armor_hp"]
        self.compass_uses = snapshot["compass_uses"]

    def sync_runtime_state(self, player):
        """Sync runtime player values back into persistent progress."""
        self.coins = player.coins
        self.armor_hp = player.armor_hp
        self.compass_uses = player.compass_uses

    def begin_dungeon_run(self, dungeon_id):
        """Mark a dungeon run active and capture its pre-level revert point."""
        self.start_dungeon(dungeon_id)
        return self.snapshot_run_state()

    def sync_dungeon_run(self, player):
        """Persist the current dungeon-run resources from the live player."""
        self.sync_runtime_state(player)

    def advance_dungeon_level_from_runtime(self, dungeon_id, total_levels, player):
        """Advance after a cleared level and capture the next abandon snapshot."""
        self.sync_dungeon_run(player)
        completed = self.advance_in_dungeon(dungeon_id, total_levels)
        if completed:
            return True, None
        return False, self.snapshot_run_state()

    def abandon_dungeon_run(self, snapshot):
        """Restore the pre-level revert point for an abandoned run."""
        self.restore_run_state(snapshot)

    def resolve_dungeon_death(self, dungeon_id, player):
        """Persist the run state, then apply death penalties."""
        self.sync_dungeon_run(player)
        self.die_in_dungeon(dungeon_id)

    def ensure_loadout_state(self):
        loadout_rules.ensure_loadout_state(self)

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
        return loadout_rules.can_equip(self, slot, item_id)

    def equip_item(self, slot, item_id):
        return loadout_rules.equip_item(self, slot, item_id)

    def unequip_slot(self, slot):
        return loadout_rules.unequip_slot(self, slot)

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
