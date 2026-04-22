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


_CHEST_BONUS_ITEMS_BY_TIER = {
    "standard": 0,
    "branch_bonus": 1,
    "finale_bonus": 2,
}


class Chest(pygame.sprite.Sprite):
    SIZE = 24

    def __init__(self, x, y, looted=False, reward_tier="standard"):
        super().__init__()
        self.looted = looted
        self.reward_tier = reward_tier
        self._set_image()
        self.rect = self.image.get_rect(center=(x, y))
        # Pre-generate contents (only used if not looted)
        # Each entry is either ("coin",) or ("loot", item_id)
        self.contents = []
        if not looted:
            bonus_items = _CHEST_BONUS_ITEMS_BY_TIER.get(reward_tier, 0)
            count = random.randint(CHEST_MIN_ITEMS, CHEST_MAX_ITEMS) + bonus_items
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

    def mark_looted(self):
        self.looted = True
        self.contents.clear()
        self._set_image()

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
        contents = list(self.contents)
        self.mark_looted()
        # Spawn items around the chest
        for i, entry in enumerate(contents):
            offset_x = (i - len(contents) // 2) * 20
            cx = self.rect.centerx + offset_x
            cy = self.rect.centery - 24
            if entry[0] == "coin":
                item = Coin(cx, cy)
            else:
                item = LootDrop(cx, cy, entry[1])
            items_group.add(item)
        return True
