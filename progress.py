"""Player and dungeon progress tracking.

PlayerProgress is the single source of truth for persistent state.
It is loaded from / saved to the SQLite database via save_system.
"""
import copy

from dungeon_config import DUNGEONS
import loadout_rules
import rune_rules
from item_catalog import (
    DEFAULT_EQUIPPED_SLOTS,
    EQUIPMENT_SLOTS,
    ITEM_DATABASE,
    STARTER_WEAPON_IDS,
    UPGRADEABLE_WEAPON_IDS,
    WEAPON_EQUIPMENT_SLOTS,
)


class DungeonProgress:
    """Tracks a single dungeon's run state.

    Each dungeon is now a single generated floor.  There are no level indices —
    a run is either in-progress, completed, or not yet attempted.
    """

    def __init__(self, dungeon_id, is_alive=True, completed=False):
        self.dungeon_id = dungeon_id
        self.is_alive = is_alive
        self.completed = completed

    def complete(self):
        """Mark the dungeon as fully cleared."""
        self.completed = True
        self.is_alive = True

    def reset(self):
        """Reset dungeon to a fresh unstarted state (used on death or restart)."""
        self.is_alive = True
        self.completed = False

    def die(self):
        """Mark the player as dead in this dungeon."""
        self.is_alive = False
        self.completed = False


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

        # Equipment state (persists across runs, lost on death)
        self.armor_hp = 0        # current armor durability
        self.compass_uses = 0    # remaining compass uses

        # Runes (per-dungeon loadout, wiped on completion or death)
        self.equipped_runes: dict[str, list[str]] = rune_rules.empty_loadout()

        # Dungeon difficulty preference: "default", "medium", or "hard".
        # Persisted across sessions.  Drives grid size during dungeon generation.
        self.difficulty_preference: str = "default"

        # create an entry for every defined dungeon
        for d in DUNGEONS:
            self.dungeons[d["id"]] = DungeonProgress(d["id"])

        self.ensure_loadout_state()

    def get_dungeon(self, dungeon_id) -> DungeonProgress:
        if dungeon_id not in self.dungeons:
            self.dungeons[dungeon_id] = DungeonProgress(dungeon_id)
        return self.dungeons[dungeon_id]

    def can_resume(self, dungeon_id) -> bool:
        """Returns False — unfinished runs restart from scratch."""
        return False

    def snapshot_run_state(self):
        """Capture progress that should revert when a level is abandoned."""
        return {
            "coins": self.coins,
            "inventory": copy.deepcopy(self.inventory),
            "armor_hp": self.armor_hp,
            "compass_uses": self.compass_uses,
            "equipped_runes": rune_rules.serialize_loadout(self.equipped_runes),
        }

    def restore_run_state(self, snapshot):
        """Restore progress captured by snapshot_run_state()."""
        self.coins = snapshot["coins"]
        self.inventory = copy.deepcopy(snapshot["inventory"])
        self.armor_hp = snapshot["armor_hp"]
        self.compass_uses = snapshot["compass_uses"]
        self.equipped_runes = rune_rules.normalize_loadout(
            snapshot.get("equipped_runes")
        )

    def sync_runtime_state(self, player):
        """Sync runtime player values back into persistent progress."""
        self.coins = player.coins
        self.armor_hp = player.armor_hp
        self.compass_uses = player.compass_uses
        rune_rules.sync_progress_to_runtime(self, player)

    def begin_dungeon_run(self, dungeon_id):
        """Mark a dungeon run active and capture its pre-level revert point.

        Defensive: clear any equipped runes left over from a prior session
        before snapshotting.  Runes are per-run state and should never
        persist across runs; clearing here cleanses leaked state from
        older saves so subsequent abandon/complete logic operates on a
        clean baseline.
        """
        self.equipped_runes = rune_rules.empty_loadout()
        self.start_dungeon(dungeon_id)
        return self.snapshot_run_state()

    def sync_dungeon_run(self, player):
        """Persist the current dungeon-run resources from the live player."""
        self.sync_runtime_state(player)

    def complete_dungeon_from_runtime(self, dungeon_id, player):
        """Mark the dungeon complete and persist run resources."""
        self.sync_dungeon_run(player)
        self.get_dungeon(dungeon_id).complete()
        # Runes are per-dungeon and wipe on completion.
        self.equipped_runes = rune_rules.empty_loadout()
        return True, None

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
        self.equipped_runes = rune_rules.empty_loadout()
        for weapon_id in self.weapon_upgrades:
            self.weapon_upgrades[weapon_id] = 0
        self.inventory.pop("armor", None)
        self.inventory.pop("compass", None)
        self.equipment_storage.pop("armor", None)
        if self.equipped_slots.get("chest") == "armor":
            self.equipped_slots["chest"] = None
        self.ensure_loadout_state()

    def start_dungeon(self, dungeon_id):
        """Prepare a dungeon for a fresh start (or resume)."""
        dp = self.get_dungeon(dungeon_id)
        dp.is_alive = True
        self.ensure_loadout_state()
