"""Chests that hold random items, with persistent looted state."""
import random
import pygame
from sprites import make_rect_surface
from settings import (
    COLOR_CHEST, COLOR_CHEST_LOOTED,
    CHEST_MIN_ITEMS, CHEST_MAX_ITEMS, CHEST_INTERACT_DIST,
)
from item_catalog import CHEST_CONTENT_ENTRIES, CHEST_CONTENT_WEIGHTS
from items import Coin, LootDrop


class Chest(pygame.sprite.Sprite):
    SIZE = 24

    def __init__(self, x, y, looted=False):
        super().__init__()
        self.looted = looted
        self._set_image()
        self.rect = self.image.get_rect(center=(x, y))
        # Pre-generate contents (only used if not looted)
        # Each entry is either ("coin",) or ("loot", item_id)
        self.contents = []
        if not looted:
            count = random.randint(CHEST_MIN_ITEMS, CHEST_MAX_ITEMS)
            for _ in range(count):
                entry = random.choices(
                    CHEST_CONTENT_ENTRIES,
                    weights=CHEST_CONTENT_WEIGHTS,
                    k=1,
                )[0]
                if entry[0] == "coin":
                    self.contents.append(("coin",))
                else:
                    self.contents.append(("loot", entry[1]))

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
        for i, entry in enumerate(self.contents):
            offset_x = (i - len(self.contents) // 2) * 20
            cx = self.rect.centerx + offset_x
            cy = self.rect.centery - 24
            if entry[0] == "coin":
                item = Coin(cx, cy)
            else:
                item = LootDrop(cx, cy, entry[1])
            items_group.add(item)
        self.contents.clear()
        return True
