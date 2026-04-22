"""Runtime collectible sprites and inventory loot pickups."""
import pygame
from sprites import make_rect_surface
from item_catalog import ITEM_DATABASE
from settings import (
    COLOR_HEALTH_POTION, COLOR_COIN, COLOR_SPEED_BOOST,
    HEAL_AMOUNT, SPEED_BOOST_AMOUNT, SPEED_CAP,
)


class Item(pygame.sprite.Sprite):
    """Base class for all ground items."""

    color = COLOR_COIN
    size = 16

    def __init__(self, x, y):
        super().__init__()
        self.image = make_rect_surface(self.size, self.size, self.color)
        self.rect = self.image.get_rect(center=(x, y))

    def collect(self, player):
        """Override in subclasses to apply the pickup effect."""


class HealthPotion(Item):
    color = COLOR_HEALTH_POTION
    size = 16

    def collect(self, player):
        player.current_hp = min(player.current_hp + HEAL_AMOUNT, player.max_hp)


class Coin(Item):
    color = COLOR_COIN
    size = 12

    def collect(self, player):
        player.coins += 1


class SpeedBoost(Item):
    color = COLOR_SPEED_BOOST
    size = 16

    def collect(self, player):
        player.speed_multiplier = min(
            player.speed_multiplier + SPEED_BOOST_AMOUNT, SPEED_CAP
        )


# Lookup used by drop / chest generation (legacy instant pickups)
ITEM_CLASSES = [Coin, HealthPotion, SpeedBoost]


class LootDrop(Item):
    """A ground item that adds to the player's inventory on pickup."""

    size = 14

    def __init__(self, x, y, item_id):
        self.item_id = item_id
        data = ITEM_DATABASE[item_id]
        self.color = data["icon_color"]
        self.max_owned = data["max_owned"]
        super().__init__(x, y)

    def collect(self, player):
        """Add to inventory if not at max.  Returns silently if full."""
        inv = player.progress.inventory
        current = inv.get(self.item_id, 0)
        if current >= self.max_owned:
            return  # inventory full for this item — leave on ground
        inv[self.item_id] = current + 1
