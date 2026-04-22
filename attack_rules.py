"""Attack-specific runtime rules for Player state."""

from settings import ATTACK_BOOST_MULTIPLIER, WEAPON_PLUS_MULTIPLIER


def attack(player):
    weapon = player.weapon
    if weapon is None:
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

    _apply_attack_result_modifiers(result, multiplier, player.is_attack_boosted)
    return result


def _apply_attack_result_modifiers(result, multiplier, use_glow):
    hitboxes = result if isinstance(result, list) else [result]
    for hitbox in hitboxes:
        hitbox.damage = int(hitbox.damage * multiplier)
        if use_glow:
            hitbox.set_glow()