"""Collectible items: HealthPotion, Coin, SpeedBoost."""
import pygame
from sprites import make_rect_surface
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


# Lookup used by drop / chest generation
ITEM_CLASSES = [Coin, HealthPotion, SpeedBoost]
