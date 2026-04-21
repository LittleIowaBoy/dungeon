"""Collectible items: ground pickups and inventory loot drops."""
import pygame
from sprites import make_rect_surface
from settings import (
    COLOR_HEALTH_POTION, COLOR_COIN, COLOR_SPEED_BOOST,
    HEAL_AMOUNT, SPEED_BOOST_AMOUNT, SPEED_CAP,
    # new item constants
    HEAL_SMALL, HEAL_MEDIUM, HEAL_LARGE,
    POTION_SMALL_MAX, POTION_MEDIUM_MAX, POTION_LARGE_MAX,
    SPEED_BOOST_MAX, ATTACK_BOOST_MAX, COMPASS_MAX,
    ARMOR_HP, COMPASS_USES,
    PRICE_POTION_SMALL, PRICE_POTION_MEDIUM, PRICE_POTION_LARGE,
    PRICE_SPEED_BOOST, PRICE_ATTACK_BOOST, PRICE_ARMOR,
    PRICE_WEAPON_PLUS, PRICE_COMPASS,
    COLOR_ARMOR, COLOR_COMPASS,
    LOOT_WEIGHT_POTION_SMALL, LOOT_WEIGHT_POTION_MEDIUM,
    LOOT_WEIGHT_POTION_LARGE, LOOT_WEIGHT_SPEED_BOOST,
    LOOT_WEIGHT_ATTACK_BOOST,
)


EQUIPMENT_SLOTS = (
    "weapon_1",
    "weapon_2",
    "helmet",
    "chest",
    "arms",
    "legs",
)
WEAPON_EQUIPMENT_SLOTS = ("weapon_1", "weapon_2")
STARTER_WEAPON_IDS = ("sword", "spear", "axe", "hammer")
UPGRADEABLE_WEAPON_IDS = STARTER_WEAPON_IDS
DEFAULT_EQUIPPED_SLOTS = {
    "weapon_1": "sword",
    "weapon_2": "spear",
    "helmet": None,
    "chest": None,
    "arms": None,
    "legs": None,
}
LEGACY_WEAPON_PLUS_IDS = {
    "sword_plus": "sword",
    "spear_plus": "spear",
    "axe_plus": "axe",
}


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


# ═════════════════════════════════════════════════════════
#  Item Database — centralized registry for all items
# ═════════════════════════════════════════════════════════
ITEM_DATABASE = {
    # ── Health Potions ──────────────────────────────────
    "health_potion_small": {
        "name": "Small Health Potion",
        "description": f"Restores {HEAL_SMALL} HP",
        "cost": PRICE_POTION_SMALL,
        "icon_color": COLOR_HEALTH_POTION,
        "max_owned": POTION_SMALL_MAX,
        "can_purchase": True,
        "can_loot": True,
        "drop_weight": LOOT_WEIGHT_POTION_SMALL,
        "category": "potion",
    },
    "health_potion_medium": {
        "name": "Medium Health Potion",
        "description": f"Restores {HEAL_MEDIUM} HP",
        "cost": PRICE_POTION_MEDIUM,
        "icon_color": (20, 160, 50),
        "max_owned": POTION_MEDIUM_MAX,
        "can_purchase": True,
        "can_loot": True,
        "drop_weight": LOOT_WEIGHT_POTION_MEDIUM,
        "category": "potion",
    },
    "health_potion_large": {
        "name": "Large Health Potion",
        "description": f"Restores {HEAL_LARGE} HP (full heal)",
        "cost": PRICE_POTION_LARGE,
        "icon_color": (10, 120, 40),
        "max_owned": POTION_LARGE_MAX,
        "can_purchase": True,
        "can_loot": True,
        "drop_weight": LOOT_WEIGHT_POTION_LARGE,
        "category": "potion",
    },
    # ── Speed Boost ─────────────────────────────────────
    "speed_boost": {
        "name": "Speed Boost",
        "description": "Doubles movement speed for 20s",
        "cost": PRICE_SPEED_BOOST,
        "icon_color": COLOR_SPEED_BOOST,
        "max_owned": SPEED_BOOST_MAX,
        "can_purchase": True,
        "can_loot": True,
        "drop_weight": LOOT_WEIGHT_SPEED_BOOST,
        "category": "boost",
    },
    # ── Attack Boost ────────────────────────────────────
    "attack_boost": {
        "name": "Attack Boost",
        "description": "Doubles damage for 20s",
        "cost": PRICE_ATTACK_BOOST,
        "icon_color": (255, 80, 80),
        "max_owned": ATTACK_BOOST_MAX,
        "can_purchase": True,
        "can_loot": True,
        "drop_weight": LOOT_WEIGHT_ATTACK_BOOST,
        "category": "boost",
    },
    # ── Armor ───────────────────────────────────────────
    "armor": {
        "name": "Iron Chestplate",
        "description": f"+{ARMOR_HP} armor HP (absorbs damage first)",
        "cost": PRICE_ARMOR,
        "icon_color": COLOR_ARMOR,
        "max_owned": 1,
        "can_purchase": True,
        "can_loot": False,
        "drop_weight": 0,
        "category": "equipment",
    },
    # ── +1 Weapons ──────────────────────────────────────
    "sword_plus": {
        "name": "+1 Sword",
        "description": "1.5x sword damage. Lost on death.",
        "cost": PRICE_WEAPON_PLUS,
        "icon_color": (220, 220, 255),
        "max_owned": 1,
        "can_purchase": True,
        "can_loot": False,
        "drop_weight": 0,
        "category": "equipment",
    },
    "spear_plus": {
        "name": "+1 Spear",
        "description": "1.5x spear damage. Lost on death.",
        "cost": PRICE_WEAPON_PLUS,
        "icon_color": (200, 255, 200),
        "max_owned": 1,
        "can_purchase": True,
        "can_loot": False,
        "drop_weight": 0,
        "category": "equipment",
    },
    "axe_plus": {
        "name": "+1 Axe",
        "description": "1.5x axe damage. Lost on death.",
        "cost": PRICE_WEAPON_PLUS,
        "icon_color": (255, 200, 200),
        "max_owned": 1,
        "can_purchase": True,
        "can_loot": False,
        "drop_weight": 0,
        "category": "equipment",
    },
    # ── Compass ─────────────────────────────────────────
    "compass": {
        "name": "Compass",
        "description": f"Points toward portal ({COMPASS_USES} uses)",
        "cost": PRICE_COMPASS,
        "icon_color": COLOR_COMPASS,
        "max_owned": COMPASS_MAX,
        "can_purchase": True,
        "can_loot": False,
        "drop_weight": 0,
        "category": "tool",
    },
}

ITEM_DATABASE.update({
    "sword": {
        "name": "Sword",
        "description": "Starter weapon. Slash damage.",
        "cost": 0,
        "icon_color": (220, 220, 255),
        "max_owned": 1,
        "can_purchase": False,
        "can_loot": False,
        "drop_weight": 0,
        "category": "weapon",
        "equipment_slots": list(WEAPON_EQUIPMENT_SLOTS),
        "storage_bucket": "equipment",
        "weapon_id": "sword",
        "damage_type": "slash",
        "is_equippable": True,
    },
    "spear": {
        "name": "Spear",
        "description": "Starter weapon. Pierce damage.",
        "cost": 0,
        "icon_color": (200, 255, 200),
        "max_owned": 1,
        "can_purchase": False,
        "can_loot": False,
        "drop_weight": 0,
        "category": "weapon",
        "equipment_slots": list(WEAPON_EQUIPMENT_SLOTS),
        "storage_bucket": "equipment",
        "weapon_id": "spear",
        "damage_type": "pierce",
        "is_equippable": True,
    },
    "axe": {
        "name": "Axe",
        "description": "Starter weapon. Slash damage.",
        "cost": 0,
        "icon_color": (255, 200, 200),
        "max_owned": 1,
        "can_purchase": False,
        "can_loot": False,
        "drop_weight": 0,
        "category": "weapon",
        "equipment_slots": list(WEAPON_EQUIPMENT_SLOTS),
        "storage_bucket": "equipment",
        "weapon_id": "axe",
        "damage_type": "slash",
        "is_equippable": True,
    },
    "hammer": {
        "name": "Hammer",
        "description": "Starter weapon. Blunt damage.",
        "cost": 0,
        "icon_color": (180, 180, 180),
        "max_owned": 1,
        "can_purchase": False,
        "can_loot": False,
        "drop_weight": 0,
        "category": "weapon",
        "equipment_slots": list(WEAPON_EQUIPMENT_SLOTS),
        "storage_bucket": "equipment",
        "weapon_id": "hammer",
        "damage_type": "blunt",
        "is_equippable": True,
    },
    "iron_helmet": {
        "name": "Iron Helmet",
        "description": "Basic head protection for the helmet slot.",
        "cost": 40,
        "icon_color": (145, 155, 170),
        "max_owned": 1,
        "can_purchase": True,
        "can_loot": False,
        "drop_weight": 0,
        "category": "equipment",
        "equipment_slots": ["helmet"],
        "storage_bucket": "equipment",
        "is_equippable": True,
    },
    "iron_bracers": {
        "name": "Iron Bracers",
        "description": "Basic arm guards for the arms slot.",
        "cost": 35,
        "icon_color": (165, 145, 120),
        "max_owned": 1,
        "can_purchase": True,
        "can_loot": False,
        "drop_weight": 0,
        "category": "equipment",
        "equipment_slots": ["arms"],
        "storage_bucket": "equipment",
        "is_equippable": True,
    },
    "traveler_boots": {
        "name": "Traveler Boots",
        "description": "Basic leg gear for the legs slot.",
        "cost": 30,
        "icon_color": (120, 100, 80),
        "max_owned": 1,
        "can_purchase": True,
        "can_loot": False,
        "drop_weight": 0,
        "category": "equipment",
        "equipment_slots": ["legs"],
        "storage_bucket": "equipment",
        "is_equippable": True,
    },
})

ITEM_DATABASE["armor"].update({
    "equipment_slots": ["chest"],
    "storage_bucket": "equipment",
    "is_equippable": True,
})
ITEM_DATABASE["sword_plus"].update({
    "category": "weapon_upgrade",
    "storage_bucket": "upgrade",
    "upgrade_weapon_id": "sword",
    "upgrade_tier": 1,
})
ITEM_DATABASE["spear_plus"].update({
    "category": "weapon_upgrade",
    "storage_bucket": "upgrade",
    "upgrade_weapon_id": "spear",
    "upgrade_tier": 1,
})
ITEM_DATABASE["axe_plus"].update({
    "category": "weapon_upgrade",
    "storage_bucket": "upgrade",
    "upgrade_weapon_id": "axe",
    "upgrade_tier": 1,
})

for item_data in ITEM_DATABASE.values():
    item_data.setdefault("equipment_slots", [])
    item_data.setdefault("storage_bucket", "inventory")
    item_data.setdefault("weapon_id", None)
    item_data.setdefault("damage_type", None)
    item_data.setdefault("upgrade_weapon_id", None)
    item_data.setdefault("upgrade_tier", 0)
    item_data.setdefault("is_equippable", bool(item_data["equipment_slots"]))

# Precomputed loot tables
ENEMY_LOOT_TABLE = [
    (item_id, data["drop_weight"])
    for item_id, data in ITEM_DATABASE.items()
    if data["can_loot"] and data["drop_weight"] > 0
]
ENEMY_LOOT_IDS = [t[0] for t in ENEMY_LOOT_TABLE]
ENEMY_LOOT_WEIGHTS = [t[1] for t in ENEMY_LOOT_TABLE]


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
