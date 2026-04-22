"""Shop system — populated from the item database.

Items are filtered from ITEM_DATABASE where can_purchase is True.
Purchase limits are enforced via max_owned per item.
"""
from dataclasses import dataclass
from item_catalog import ITEM_DATABASE
from settings import ARMOR_HP, COMPASS_USES


@dataclass
class ShopItem:
    id: str
    name: str
    description: str
    cost: int
    max_owned: int
    category: str = "general"
    icon_color: tuple = (200, 200, 200)


# Build shop catalogue from item database
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

_helmet_index = next(
    (i for i, item in enumerate(SHOP_ITEMS) if item.id == "iron_helmet"),
    None,
)
_armor_index = next(
    (i for i, item in enumerate(SHOP_ITEMS) if item.id == "armor"),
    None,
)
if _helmet_index is not None and _armor_index is not None and _armor_index != _helmet_index + 1:
    armor_item = SHOP_ITEMS.pop(_armor_index)
    if _armor_index < _helmet_index:
        _helmet_index -= 1
    SHOP_ITEMS.insert(_helmet_index + 1, armor_item)


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
            owned = player_progress.weapon_upgrade_tier(
                item_data["upgrade_weapon_id"]
            )
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
            if player_progress.weapon_upgrade_tier(item_data["upgrade_weapon_id"]) >= item.max_owned:
                return False
            player_progress.coins -= item.cost
            player_progress.set_weapon_upgrade(
                item_data["upgrade_weapon_id"],
                item_data.get("upgrade_tier", 1),
            )
            return True

        # Armor special case: re-buying restores armor HP, doesn't add count
        if item_id == "armor" and owned >= 1:
            player_progress.coins -= item.cost
            player_progress.armor_hp = ARMOR_HP
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
            player_progress.armor_hp = ARMOR_HP

        # Initialize compass uses on first purchase
        if item_id == "compass":
            player_progress.compass_uses = COMPASS_USES

        return True

    def _find(self, item_id) -> ShopItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None
