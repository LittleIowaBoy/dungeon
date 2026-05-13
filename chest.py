"""Chests that hold random items, with persistent looted state."""
import random
import pygame
from sprites import make_rect_surface
from settings import (
    COLOR_CHEST, COLOR_CHEST_LOOTED, COLOR_CHEST_GAMBLE,
    CHEST_MIN_ITEMS, CHEST_MAX_ITEMS, CHEST_INTERACT_DIST,
    CHEST_GAMBLE_WIN_CHANCE,
)
from item_catalog import CHEST_CONTENT_ENTRIES, CHEST_CONTENT_WEIGHTS
from items import Coin, LootDrop


# Ordered progression used by the gamble mechanic to elevate a chest's tier.
_TIER_PROGRESSION = {
    "standard":     "branch_bonus",
    "branch_bonus": "finale_bonus",
    "finale_bonus": "finale_bonus",  # already maximum
}

_CHEST_BONUS_ITEMS_BY_TIER = {
    "standard": 0,
    "branch_bonus": 1,
    "finale_bonus": 2,
}

# Biome-themed challenge-route bonus loot. The bonus item id (if any) is
# guaranteed-spawned alongside the standard rolled chest contents whenever the
# player commits to the trap-gauntlet challenge route. Each kind maps to a
# bespoke biome-flavored item from the catalog (see item_catalog.py
# `biome_reward` category) so the trophy reads clearly in the inventory.
_CHEST_BONUS_LOOT_BY_REWARD_KIND = {
    "chest_upgrade": None,
    "stat_shard": "stat_shard",
    "tempo_rune": "tempo_rune",
    "mobility_consumable": "mobility_charge",
}


class Chest(pygame.sprite.Sprite):
    SIZE = 24

    def __init__(self, x, y, looted=False, reward_tier="standard", reward_kind="chest_upgrade"):
        super().__init__()
        self.looted = looted
        self.reward_tier = reward_tier
        self.reward_kind = reward_kind
        self.gamble_pending = False
        self._set_image()
        self.rect = self.image.get_rect(center=(x, y))
        # Pre-generate contents (only used if not looted)
        # Each entry is either ("coin",) or ("loot", item_id)
        self.contents = []
        if not looted:
            self.contents = self._roll_contents()

    # ── visuals ─────────────────────────────────────────
    def _set_image(self):
        if self.looted:
            color = COLOR_CHEST_LOOTED
        elif self.gamble_pending:
            color = COLOR_CHEST_GAMBLE
        else:
            color = COLOR_CHEST
        self.image = make_rect_surface(self.SIZE, self.SIZE, color)

    # ── gamble ──────────────────────────────────────────
    def try_gamble(self, player_rect) -> bool:
        """Enter gamble-pending state if the player is within interact range.

        Returns True if the state was entered; False if the chest is already
        looted, already pending, or the player is too far away.
        """
        if self.looted or self.gamble_pending:
            return False
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        if (dx * dx + dy * dy) ** 0.5 > CHEST_INTERACT_DIST:
            return False
        self.gamble_pending = True
        self._set_image()
        return True

    def cancel_gamble(self):
        """Abort a pending gamble without any side-effects."""
        if not self.gamble_pending:
            return
        self.gamble_pending = False
        self._set_image()

    def confirm_gamble(self, rng) -> str:
        """Resolve the pending gamble.  Returns 'win', 'lose', or 'idle'.

        Win (55 % by default): elevates reward tier and rerolls contents.
        Lose: forfeits the chest (marks it looted without yielding items).
        """
        if not self.gamble_pending:
            return "idle"
        self.gamble_pending = False
        if rng.random() < CHEST_GAMBLE_WIN_CHANCE:
            self.try_elevate_tier()
            self._set_image()
            return "win"
        self.mark_looted()
        return "lose"

    def try_elevate_tier(self) -> bool:
        """Bump the reward tier one step up the _TIER_PROGRESSION ladder.

        Rerolls contents immediately.  Returns False if already at maximum.
        """
        next_tier = _TIER_PROGRESSION.get(self.reward_tier, self.reward_tier)
        if next_tier == self.reward_tier:
            return False
        self.reward_tier = next_tier
        if not self.looted:
            self.contents = self._roll_contents()
        return True

    def mark_looted(self):
        self.looted = True
        self.contents.clear()
        self._set_image()

    def restore_for_reclaim(self):
        self.looted = False
        self.contents = []
        self._set_image()

    def set_reward_tier(self, reward_tier):
        if self.looted or reward_tier == self.reward_tier:
            return
        self.reward_tier = reward_tier
        self.contents = self._roll_contents()

    def set_reward_kind(self, reward_kind):
        if self.looted or reward_kind == self.reward_kind:
            return
        self.reward_kind = reward_kind
        self.contents = self._roll_contents()

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

    def _roll_contents(self):
        contents = []
        bonus_items = _CHEST_BONUS_ITEMS_BY_TIER.get(self.reward_tier, 0)
        count = random.randint(CHEST_MIN_ITEMS, CHEST_MAX_ITEMS) + bonus_items
        for _ in range(count):
            entry = random.choices(
                CHEST_CONTENT_ENTRIES,
                weights=CHEST_CONTENT_WEIGHTS,
                k=1,
            )[0]
            if entry[0] == "coin":
                contents.append(("coin",))
            else:
                contents.append(("loot", entry[1]))
        bonus_loot_id = _CHEST_BONUS_LOOT_BY_REWARD_KIND.get(self.reward_kind)
        if bonus_loot_id:
            contents.append(("loot", bonus_loot_id))
        return contents
