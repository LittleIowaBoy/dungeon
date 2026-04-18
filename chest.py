"""Chests that hold random items, with persistent looted state."""
import random
import pygame
from sprites import make_rect_surface
from settings import (
    COLOR_CHEST, COLOR_CHEST_LOOTED,
    CHEST_MIN_ITEMS, CHEST_MAX_ITEMS, CHEST_INTERACT_DIST,
    CHEST_LOOT_WEIGHT_POTION_SMALL, CHEST_LOOT_WEIGHT_POTION_MEDIUM,
    CHEST_LOOT_WEIGHT_POTION_LARGE, CHEST_LOOT_WEIGHT_SPEED_BOOST,
    CHEST_LOOT_WEIGHT_ATTACK_BOOST,
)
from items import Coin, LootDrop, ITEM_DATABASE


# Build chest loot table from database (items that can_loot) with chest weights
_CHEST_LOOT_WEIGHTS = {
    "health_potion_small": CHEST_LOOT_WEIGHT_POTION_SMALL,
    "health_potion_medium": CHEST_LOOT_WEIGHT_POTION_MEDIUM,
    "health_potion_large": CHEST_LOOT_WEIGHT_POTION_LARGE,
    "speed_boost": CHEST_LOOT_WEIGHT_SPEED_BOOST,
    "attack_boost": CHEST_LOOT_WEIGHT_ATTACK_BOOST,
}
_CHEST_LOOT_IDS = [k for k in _CHEST_LOOT_WEIGHTS if k in ITEM_DATABASE]
_CHEST_LOOT_W = [_CHEST_LOOT_WEIGHTS[k] for k in _CHEST_LOOT_IDS]


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
                # 40% coin, 60% inventory loot
                if random.random() < 0.4:
                    self.contents.append(("coin",))
                else:
                    item_id = random.choices(_CHEST_LOOT_IDS,
                                             weights=_CHEST_LOOT_W, k=1)[0]
                    self.contents.append(("loot", item_id))

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
