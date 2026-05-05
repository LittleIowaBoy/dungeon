"""Consumable selection and inventory-use rules for Player runtime state."""

from settings import (
    HEAL_SMALL,
    HEAL_MEDIUM,
    HEAL_LARGE,
    SPEED_BOOST_DURATION_MS,
    ATTACK_BOOST_DURATION_MS,
    STAT_SHARD_MAX_HP_BONUS,
    TEMPO_RUNE_DURATION_MS,
    MOBILITY_CHARGE_DURATION_MS,
    SPARK_CHARGE_DURATION_MS,
    SPARK_CHARGE_COOLDOWN_MULT,
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
    player.spark_until = 0
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


# ── Biome challenge-route reward activations ────────────
# These trophies are earned only by committing to a trap-gauntlet challenge
# route (see chest._CHEST_BONUS_LOOT_BY_REWARD_KIND). Each spends one inventory
# token to apply a distinctive effect that reuses existing runtime fields:
#   stat_shard       → permanent +max_hp bump (also tops up current_hp).
#   tempo_rune       → extended attack-boost window (longer than attack_boost).
#   mobility_charge  → short, sharp speed-boost burst (shorter than speed_boost).
def use_stat_shard(player):
    if player.progress is None:
        return False
    if not consume_inventory_item(player.progress, "stat_shard"):
        return False
    player.max_hp += STAT_SHARD_MAX_HP_BONUS
    player.current_hp = min(player.current_hp + STAT_SHARD_MAX_HP_BONUS, player.max_hp)
    import damage_feedback  # local import to avoid circular dep
    damage_feedback.report_biome_reward_flash(player, "stat_shard")
    return True


def use_tempo_rune(player, now_ticks):
    if player.progress is None:
        return False
    if not consume_inventory_item(player.progress, "tempo_rune"):
        return False
    player.attack_boost_until = max(
        getattr(player, "attack_boost_until", 0),
        now_ticks + TEMPO_RUNE_DURATION_MS,
    )
    import damage_feedback  # local import to avoid circular dep
    damage_feedback.report_biome_reward_flash(player, "tempo_rune", now_ticks)
    return True


def use_mobility_charge(player, now_ticks):
    if player.progress is None:
        return False
    if not consume_inventory_item(player.progress, "mobility_charge"):
        return False
    player.speed_boost_until = max(
        getattr(player, "speed_boost_until", 0),
        now_ticks + MOBILITY_CHARGE_DURATION_MS,
    )
    import damage_feedback  # local import to avoid circular dep
    damage_feedback.report_biome_reward_flash(player, "mobility_charge", now_ticks)
    return True


def use_spark_charge(player, now_ticks):
    if player.progress is None:
        return False
    if not consume_inventory_item(player.progress, "spark_charge"):
        return False
    player.spark_until = max(
        getattr(player, "spark_until", 0),
        now_ticks + SPARK_CHARGE_DURATION_MS,
    )
    # Retroactively shorten any in-flight dodge cooldown
    cooldown_until = getattr(player, "dodge_cooldown_until", 0)
    if cooldown_until > now_ticks:
        remaining = cooldown_until - now_ticks
        player.dodge_cooldown_until = now_ticks + int(remaining * SPARK_CHARGE_COOLDOWN_MULT)
    return True


def consume_inventory_item(progress, item_id):
    inventory = progress.inventory
    if inventory.get(item_id, 0) <= 0:
        return False
    inventory[item_id] -= 1
    if inventory[item_id] <= 0:
        del inventory[item_id]
    return True