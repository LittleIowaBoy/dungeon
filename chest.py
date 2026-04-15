"""Chests that hold random items, with persistent looted state."""
import random
import pygame
from sprites import make_rect_surface
from settings import (
    COLOR_CHEST, COLOR_CHEST_LOOTED,
    CHEST_MIN_ITEMS, CHEST_MAX_ITEMS, CHEST_INTERACT_DIST,
    DROP_WEIGHTS,
)
from items import ITEM_CLASSES


class Chest(pygame.sprite.Sprite):
    SIZE = 24

    def __init__(self, x, y, looted=False):
        super().__init__()
        self.looted = looted
        self._set_image()
        self.rect = self.image.get_rect(center=(x, y))
        # Pre-generate contents (only used if not looted)
        self.contents = []
        if not looted:
            count = random.randint(CHEST_MIN_ITEMS, CHEST_MAX_ITEMS)
            for _ in range(count):
                cls = random.choices(ITEM_CLASSES, weights=DROP_WEIGHTS, k=1)[0]
                self.contents.append(cls)

    # ── visuals ─────────────────────────────────────────
    def _set_image(self):
        color = COLOR_CHEST_LOOTED if self.looted else COLOR_CHEST
        self.image = make_rect_surface(self.SIZE, self.SIZE, color)

    # ── interaction ─────────────────────────────────────
    def try_open(self, player_rect, items_group):
        """If the player is close enough and the chest is unopened, spawn items.

        Returns True if the chest was opened this call.
        """
        if self.looted:
            return False
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > CHEST_INTERACT_DIST:
            return False
        self.looted = True
        self._set_image()
        # Spawn items around the chest
        for i, cls in enumerate(self.contents):
            offset_x = (i - len(self.contents) // 2) * 20
            item = cls(self.rect.centerx + offset_x, self.rect.centery - 24)
            items_group.add(item)
        self.contents.clear()
        return True
