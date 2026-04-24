"""Attack-specific runtime rules for Player state."""

import pygame

import behavior_runes
import stat_runes
import status_effects
from settings import ATTACK_BOOST_MULTIPLIER, WEAPON_PLUS_MULTIPLIER


def attack(player):
    weapon = player.weapon
    if weapon is None:
        return None

    now_ticks = pygame.time.get_ticks()
    if status_effects.is_silenced(player, now_ticks):
        return None

    base_cd = getattr(weapon, "cooldown_ms", 0)
    if base_cd > 0:
        effective_cd = stat_runes.modify_weapon_cooldown(player, base_cd)
        effective_cd = int(effective_cd * behavior_runes.shockwave_cooldown_multiplier(player))
        if now_ticks - getattr(weapon, "_last_attack", 0) < effective_cd:
            return None

    result = weapon.attack(
        player.rect.centerx,
        player.rect.centery,
        player.facing_dx,
        player.facing_dy,
    )
    if result is None:
        return None

    multiplier = 1.0
    if player.is_attack_boosted:
        multiplier *= ATTACK_BOOST_MULTIPLIER

    upgrade_tier = player.weapon_upgrade_tier(player.current_weapon_id)
    if upgrade_tier > 0:
        multiplier *= WEAPON_PLUS_MULTIPLIER ** upgrade_tier

    multiplier *= behavior_runes.shockwave_damage_multiplier(player)
    multiplier *= behavior_runes.consume_static_charge(player)

    # Boomerang: outbound deals 0, but queue a return-trip with full damage.
    if behavior_runes.has_boomerang(player):
        hitboxes = result if isinstance(result, list) else [result]
        for hb in hitboxes:
            base_damage = int(hb.damage * multiplier)
            behavior_runes.queue_boomerang_return(
                player, hb.rect.center, base_damage, now_ticks,
            )
    multiplier *= behavior_runes.boomerang_outbound_multiplier(player)

    _apply_attack_result_modifiers(
        result, multiplier, player.is_attack_boosted,
        duration_multiplier=behavior_runes.shockwave_duration_multiplier(player),
    )
    return result


def _apply_attack_result_modifiers(result, multiplier, use_glow, *, duration_multiplier=1.0):
    hitboxes = result if isinstance(result, list) else [result]
    for hitbox in hitboxes:
        hitbox.damage = int(hitbox.damage * multiplier)
        if use_glow:
            hitbox.set_glow()
        if duration_multiplier != 1.0 and hasattr(hitbox, "_duration"):
            hitbox._duration = int(hitbox._duration * duration_multiplier)