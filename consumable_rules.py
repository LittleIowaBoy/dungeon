"""Consumable selection and inventory-use rules for Player runtime state."""

from settings import (
    HEAL_SMALL,
    HEAL_MEDIUM,
    HEAL_LARGE,
    SPEED_BOOST_DURATION_MS,
    ATTACK_BOOST_DURATION_MS,
)


POTION_SIZES = ("small", "medium", "large")
DEFAULT_POTION_SIZE = POTION_SIZES[0]
POTION_ITEM_IDS = {
    "small": "health_potion_small",
    "medium": "health_potion_medium",
    "large": "health_potion_large",
}
POTION_HEAL = {
    "small": HEAL_SMALL,
    "medium": HEAL_MEDIUM,
    "large": HEAL_LARGE,
}


def reset_runtime_consumables(player):
    player.speed_boost_until = 0
    player.attack_boost_until = 0
    player.selected_potion_size = DEFAULT_POTION_SIZE


def cycle_potion(player):
    idx = POTION_SIZES.index(player.selected_potion_size)
    player.selected_potion_size = POTION_SIZES[(idx + 1) % len(POTION_SIZES)]
    return player.selected_potion_size


def use_selected_potion(player):
    if player.progress is None:
        return False
    import behavior_runes  # local import to avoid circular dep
    import identity_runes  # local import to avoid circular dep
    import pygame
    if behavior_runes.blocks_health_pickup(player):
        return False
    item_id = POTION_ITEM_IDS[player.selected_potion_size]
    if not consume_inventory_item(player.progress, item_id):
        return False
    heal = POTION_HEAL[player.selected_potion_size]
    # Glass Soul: heals convert into a temporary attack-speed boost.
    iframe = identity_runes.glass_soul_intercept_heal(
        player, heal, pygame.time.get_ticks()
    )
    if iframe > 0:
        player.attack_boost_until = max(
            getattr(player, "attack_boost_until", 0), iframe
        )
        return True
    player.current_hp = min(player.current_hp + heal, player.max_hp)
    return True


def use_speed_boost(player, now_ticks):
    if player.progress is None:
        return False
    if not consume_inventory_item(player.progress, "speed_boost"):
        return False
    player.speed_boost_until = now_ticks + SPEED_BOOST_DURATION_MS
    return True


def use_attack_boost(player, now_ticks):
    if player.progress is None:
        return False
    if not consume_inventory_item(player.progress, "attack_boost"):
        return False
    player.attack_boost_until = now_ticks + ATTACK_BOOST_DURATION_MS
    return True


def consume_inventory_item(progress, item_id):
    inventory = progress.inventory
    if inventory.get(item_id, 0) <= 0:
        return False
    inventory[item_id] -= 1
    if inventory[item_id] <= 0:
        del inventory[item_id]
    return True