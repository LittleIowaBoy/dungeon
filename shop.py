"""Shop system — populated from the item database.

Items are filtered from ITEM_DATABASE where can_purchase is True.
Purchase limits are enforced via max_owned per item.
"""
from dataclasses import dataclass
from item_catalog import ITEM_DATABASE, tier_index
import armor_rules
from settings import (
    COMPASS_USES,
    BIOME_TROPHY_IDS,
    BIOME_TROPHY_EXCHANGE_RATIO,
    BIOME_TROPHY_KEYSTONE_ID,
    KEYSTONE_MAX_OWNED,
)


@dataclass
class ShopItem:
    id: str
    name: str
    description: str
    cost: int
    max_owned: int
    category: str = "general"
    icon_color: tuple = (200, 200, 200)


# Build shop catalogue from item database, sorted by rarity tier then name.
SHOP_ITEMS: list[ShopItem] = [
    ShopItem(
        id=item_id,
        name=data["name"],
        description=data["description"],
        cost=data["cost"],
        max_owned=data["max_owned"],
        category=data["category"],
        icon_color=data["icon_color"],
    )
    for item_id, data in ITEM_DATABASE.items()
    if data["can_purchase"]
]
SHOP_ITEMS.sort(key=lambda item: (tier_index(item.id), item.name))


class Shop:
    """Manages the purchasable item catalogue and transactions."""

    def __init__(self):
        self.items = list(SHOP_ITEMS)

    def can_afford(self, item_id, player_progress) -> bool:
        item = self._find(item_id)
        if item is None:
            return False
        return player_progress.coins >= item.cost

    def is_maxed(self, item_id, player_progress) -> bool:
        """True if the player already owns the max quantity of this item."""
        item = self._find(item_id)
        if item is None:
            return True
        item_data = ITEM_DATABASE[item_id]

        if item_data.get("category") == "weapon_upgrade":
            upgrade_id = item_data.get("upgrade_weapon_id")
            if upgrade_id is not None:
                owned = player_progress.weapon_upgrade_tier(upgrade_id)
                return owned >= item.max_owned
            # Legacy weapon-plus (no upgrade_weapon_id): use inventory count.
            owned = player_progress.inventory.get(item_id, 0)
            return owned >= item.max_owned

        if item_data.get("storage_bucket") == "equipment":
            owned = player_progress.total_owned(item_id)
        else:
            owned = player_progress.inventory.get(item_id, 0)

        # Armor: allow re-purchase to restore HP (not blocked by max_owned)
        if item_id == "armor" and owned >= 1:
            return False
        return owned >= item.max_owned

    def buy(self, item_id, player_progress) -> bool:
        """Attempt to buy an item.  Returns True on success."""
        item = self._find(item_id)
        if item is None or player_progress.coins < item.cost:
            return False

        item_data = ITEM_DATABASE[item_id]
        if item_data.get("storage_bucket") == "equipment":
            owned = player_progress.total_owned(item_id)
        else:
            owned = player_progress.inventory.get(item_id, 0)

        if item_data.get("category") == "weapon_upgrade":
            upgrade_id = item_data.get("upgrade_weapon_id")
            if upgrade_id is not None:
                if player_progress.weapon_upgrade_tier(upgrade_id) >= item.max_owned:
                    return False
                player_progress.coins -= item.cost
                player_progress.set_weapon_upgrade(
                    upgrade_id,
                    item_data.get("upgrade_tier", 1),
                )
                return True
            # Legacy weapon-plus: fall through to inventory purchase logic.

        # Armor special case: re-buying restores armor HP, doesn't add count
        if item_id == "armor" and owned >= 1:
            player_progress.coins -= item.cost
            armor_rules.refill_armor_hp(player_progress)
            return True

        # Compass special case: re-buying restores uses
        if item_id == "compass" and owned >= 1:
            player_progress.coins -= item.cost
            player_progress.compass_uses = COMPASS_USES
            return True

        # Enforce max_owned
        if owned >= item.max_owned:
            return False

        player_progress.coins -= item.cost
        if item_data.get("storage_bucket") == "equipment":
            player_progress.add_to_equipment_storage(item_id)
            if item_id == "armor" and player_progress.equipped_slots.get("chest") is None:
                player_progress.equip_item("chest", item_id)
        else:
            player_progress.inventory[item_id] = owned + 1

        # Initialize armor HP on first purchase
        if item_id == "armor":
            armor_rules.refill_armor_hp(player_progress)

        # Initialize compass uses on first purchase
        if item_id == "compass":
            player_progress.compass_uses = COMPASS_USES

        return True

    def _find(self, item_id) -> ShopItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    # ── biome trophy exchange ───────────────────────────
    # Biome challenge-route trophies (`stat_shard`, `tempo_rune`,
    # `mobility_charge`) cannot be purchased like regular shop items
    # (`can_purchase=False` in `item_catalog.py`).  The post-run shop instead
    # offers a one-way exchange: spend `BIOME_TROPHY_EXCHANGE_RATIO` of any
    # surplus trophy to receive 1 of a different biome trophy.
    def can_exchange_trophy(self, from_id, to_id, player_progress) -> bool:
        if from_id == to_id:
            return False
        if from_id not in BIOME_TROPHY_IDS or to_id not in BIOME_TROPHY_IDS:
            return False
        owned_from = player_progress.inventory.get(from_id, 0)
        if owned_from < BIOME_TROPHY_EXCHANGE_RATIO:
            return False
        max_owned_to = ITEM_DATABASE[to_id].get("max_owned", 0)
        if max_owned_to and player_progress.inventory.get(to_id, 0) >= max_owned_to:
            return False
        return True

    def exchange_trophy(self, from_id, to_id, player_progress) -> bool:
        """Spend `BIOME_TROPHY_EXCHANGE_RATIO` of `from_id` for 1 of `to_id`.

        Returns True on success.  Both ids must be biome trophies and must
        differ.  The destination trophy's `max_owned` cap is respected.
        """
        if not self.can_exchange_trophy(from_id, to_id, player_progress):
            return False
        inventory = player_progress.inventory
        inventory[from_id] -= BIOME_TROPHY_EXCHANGE_RATIO
        if inventory[from_id] <= 0:
            del inventory[from_id]
        inventory[to_id] = inventory.get(to_id, 0) + 1
        return True

    def best_trophy_source_for(self, to_id, player_progress) -> str | None:
        """Pick the biome trophy with the largest exchangeable surplus.

        Returns the id of a biome trophy other than `to_id` that the player
        owns at least `BIOME_TROPHY_EXCHANGE_RATIO` of, preferring the one
        with the largest count (ties broken by the order in
        `BIOME_TROPHY_IDS`).  Returns ``None`` if no source is exchangeable.
        """
        best_id = None
        best_count = 0
        for trophy_id in BIOME_TROPHY_IDS:
            if trophy_id == to_id:
                continue
            count = player_progress.inventory.get(trophy_id, 0)
            if count >= BIOME_TROPHY_EXCHANGE_RATIO and count > best_count:
                best_id = trophy_id
                best_count = count
        return best_id

    # ── prismatic keystone craft ────────────────────────
    # Long-arc collectible: requires 1 of each biome trophy to craft a single
    # `prismatic_keystone`.  Crafted keystones are stored on the persistent
    # `progress.meta_keystones` counter (NOT the per-run inventory) so they
    # survive death/abandon and grant a starting-coin bonus on every run.
    # Capped at `KEYSTONE_MAX_OWNED`.  Pure rules — UI in
    # `menu.py:ShopScreen` triggers via K_4.
    def can_craft_keystone(self, player_progress) -> bool:
        for trophy_id in BIOME_TROPHY_IDS:
            if player_progress.inventory.get(trophy_id, 0) < 1:
                return False
        if player_progress.meta_keystones >= KEYSTONE_MAX_OWNED:
            return False
        return True

    def craft_keystone(self, player_progress) -> bool:
        """Spend 1 of each biome trophy for 1 permanent meta-keystone."""
        if not self.can_craft_keystone(player_progress):
            return False
        inventory = player_progress.inventory
        for trophy_id in BIOME_TROPHY_IDS:
            inventory[trophy_id] -= 1
            if inventory[trophy_id] <= 0:
                del inventory[trophy_id]
        player_progress.meta_keystones += 1
        return True
