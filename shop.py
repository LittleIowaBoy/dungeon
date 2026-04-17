"""Shop system template.

The item list starts empty — add ShopItem entries to SHOP_ITEMS
when you are ready to populate the shop.
"""
from dataclasses import dataclass


@dataclass
class ShopItem:
    id: str
    name: str
    description: str
    cost: int
    category: str = "general"
    icon_color: tuple = (200, 200, 200)


# Add shop items here in the future.  Example:
# ShopItem("health_ring", "Health Ring", "+25 max HP", 50, "equipment", (30, 200, 60))
SHOP_ITEMS: list[ShopItem] = []


class Shop:
    """Manages the purchasable item catalogue and transactions."""

    def __init__(self):
        self.items = list(SHOP_ITEMS)  # copy so runtime additions don't leak

    def can_afford(self, item_id, player_progress) -> bool:
        item = self._find(item_id)
        if item is None:
            return False
        return player_progress.coins >= item.cost

    def buy(self, item_id, player_progress) -> bool:
        """Attempt to buy an item.  Returns True on success."""
        item = self._find(item_id)
        if item is None or player_progress.coins < item.cost:
            return False
        player_progress.coins -= item.cost
        player_progress.inventory[item_id] = (
            player_progress.inventory.get(item_id, 0) + 1
        )
        return True

    def _find(self, item_id) -> ShopItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None
