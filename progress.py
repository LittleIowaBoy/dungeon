"""Player and dungeon progress tracking.

PlayerProgress is the single source of truth for persistent state.
It is loaded from / saved to the SQLite database via save_system.
"""
import copy

from dungeon_config import DUNGEONS, get_dungeon
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
from settings import (
    BIOME_ATTUNEMENT_MAX_PER_BIOME,
    BIOME_ATTUNEMENT_THRESHOLD,
    BIOME_TROPHY_KEYSTONE_ID,
    KEYSTONE_MAX_OWNED,
    KEYSTONE_TIER_COIN_BONUSES,
    TERRAIN_TROPHY_IDS,
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

        # Permanent meta-progression: prismatic keystones earned by crafting
        # at the shop.  Never wiped on death, abandon, or completion.  Each
        # keystone grants +KEYSTONE_STARTING_COIN_BONUS coins at the start
        # of every dungeon run.  Capped at KEYSTONE_MAX_OWNED.
        self.meta_keystones: int = 0

        # T17 meta-progression: biome attunements.  Per-biome completion
        # counters (`biome_completions[terrain] -> int`) tick monotonically
        # on every dungeon completion (never reset on death/abandon).  Every
        # `BIOME_ATTUNEMENT_THRESHOLD` completions in a single biome grants
        # one attunement (`biome_attunements[terrain] -> int`), capped at
        # `BIOME_ATTUNEMENT_MAX_PER_BIOME`.  Each attunement grants +1 of
        # that biome's trophy at the start of every run in that biome —
        # parallel to the keystone coin bonus pattern.
        self.biome_completions: dict[str, int] = {}
        self.biome_attunements: dict[str, int] = {}

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
        snapshot = self.snapshot_run_state()
        # Apply the meta-keystone starting-coin bonus AFTER snapshotting so
        # the snapshot reflects the pre-bonus baseline.  Abandoning therefore
        # reverts the bonus too, and re-entering grants it again — keystones
        # apply once per `begin_dungeon_run`, never compounding.
        bonus = self.keystone_starting_coin_bonus()
        if bonus:
            self.coins += bonus
        # T17: biome attunements grant +1 of the matching biome's trophy at
        # run start, per attunement of that biome.  Same post-snapshot
        # pattern as the keystone bonus — abandoning reverts the grant.
        terrain = self._terrain_for_dungeon(dungeon_id)
        attunements = self.biome_attunements.get(terrain, 0)
        if terrain is not None and attunements > 0:
            trophy_id = TERRAIN_TROPHY_IDS.get(terrain)
            if trophy_id is not None:
                self.inventory[trophy_id] = (
                    self.inventory.get(trophy_id, 0) + attunements
                )
        return snapshot

    @staticmethod
    def _terrain_for_dungeon(dungeon_id):
        cfg = get_dungeon(dungeon_id)
        if cfg is None:
            return None
        return cfg.get("terrain_type")

    def biome_attunement_starting_trophies(self, dungeon_id) -> int:
        """Number of bonus trophies the next run in *dungeon_id* will grant."""
        terrain = self._terrain_for_dungeon(dungeon_id)
        if terrain is None:
            return 0
        return self.biome_attunements.get(terrain, 0)

    def biome_attunement_progress(self, terrain) -> tuple[int, int]:
        """Return ``(completions_toward_next, threshold)`` for a biome.

        ``completions_toward_next`` ranges from 0 to ``threshold - 1`` and
        represents how many additional completions in that biome are needed
        before the next attunement is granted.  Returns ``(0, threshold)``
        when the biome is at the per-biome attunement cap (no more
        attunements will ever be earned for that biome).
        """
        attunements = self.biome_attunements.get(terrain, 0)
        if attunements >= BIOME_ATTUNEMENT_MAX_PER_BIOME:
            return (0, BIOME_ATTUNEMENT_THRESHOLD)
        completions = self.biome_completions.get(terrain, 0)
        return (completions % BIOME_ATTUNEMENT_THRESHOLD, BIOME_ATTUNEMENT_THRESHOLD)

    def record_biome_completion(self, terrain) -> int:
        """Increment the completion counter for *terrain* and award an
        attunement when the threshold is hit.  Returns the number of
        attunements granted by this call (0 or 1).
        """
        if terrain is None or terrain not in TERRAIN_TROPHY_IDS:
            return 0
        self.biome_completions[terrain] = (
            self.biome_completions.get(terrain, 0) + 1
        )
        # Award one attunement when the running count crosses a threshold
        # multiple AND the biome is below the per-biome cap.
        if self.biome_completions[terrain] % BIOME_ATTUNEMENT_THRESHOLD != 0:
            return 0
        current = self.biome_attunements.get(terrain, 0)
        if current >= BIOME_ATTUNEMENT_MAX_PER_BIOME:
            return 0
        self.biome_attunements[terrain] = current + 1
        return 1

    def keystone_starting_coin_bonus(self) -> int:
        """Per-run starting-coin bonus granted by owned keystones.

        Tiered: each owned keystone adds the next entry from
        `KEYSTONE_TIER_COIN_BONUSES`.  The Nth keystone (1-indexed) is worth
        the Nth tier value, never more than `KEYSTONE_MAX_OWNED` entries.
        """
        owned = min(self.meta_keystones, len(KEYSTONE_TIER_COIN_BONUSES))
        return sum(KEYSTONE_TIER_COIN_BONUSES[:owned])

    def next_keystone_tier_bonus(self) -> int:
        """Coin bonus the *next* crafted keystone would add (0 if at cap)."""
        if self.meta_keystones >= len(KEYSTONE_TIER_COIN_BONUSES):
            return 0
        return KEYSTONE_TIER_COIN_BONUSES[self.meta_keystones]

    def sync_dungeon_run(self, player):
        """Persist the current dungeon-run resources from the live player."""
        self.sync_runtime_state(player)

    def complete_dungeon_from_runtime(self, dungeon_id, player):
        """Mark the dungeon complete and persist run resources."""
        self.sync_dungeon_run(player)
        self.get_dungeon(dungeon_id).complete()
        # Runes are per-dungeon and wipe on completion.
        self.equipped_runes = rune_rules.empty_loadout()
        # T17: tick the per-biome completion counter so attunements can
        # accrue across repeated runs in the same biome.
        self.record_biome_completion(self._terrain_for_dungeon(dungeon_id))
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

        # T11 migration: T10 stored crafted keystones in `inventory` (per-run,
        # wiped on death/abandon).  Move any leaked keystones into the
        # permanent `meta_keystones` counter, capped at KEYSTONE_MAX_OWNED.
        legacy_keystones = self.inventory.pop(BIOME_TROPHY_KEYSTONE_ID, 0)
        if legacy_keystones:
            self.meta_keystones = min(
                KEYSTONE_MAX_OWNED, self.meta_keystones + legacy_keystones
            )

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
