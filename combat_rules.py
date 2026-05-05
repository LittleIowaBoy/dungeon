"""Combat-specific runtime rules for Player state."""

import armor_rules
import damage_feedback
import dodge_rules
import identity_runes
import stat_runes
from settings import INVINCIBILITY_MS


def reset_runtime_combat(player, max_hp):
    base_max = stat_runes.modify_max_hp(player, max_hp)
    base_max = armor_rules.apply_max_hp_bonus(player, base_max)
    player.max_hp = base_max
    player.current_hp = base_max
    player._invincible_until = 0


def is_invincible(player, now_ticks):
    if now_ticks < player._invincible_until:
        return True
    if dodge_rules.is_dodging(player, now_ticks) and stat_runes.dodge_grants_iframes(player):
        return True
    return False


def is_alive(player):
    return player.current_hp > 0


def take_damage(player, amount, now_ticks, damage_type=None):
    if is_invincible(player, now_ticks):
        return

    # Glass Soul converts incoming damage into i-frames instead of HP loss.
    absorbed_iframe, iframe_until = identity_runes.glass_soul_intercept_damage(
        player, amount, now_ticks
    )
    if absorbed_iframe:
        player._invincible_until = iframe_until
        return

    amount = stat_runes.modify_incoming_damage(player, amount)
    amount = armor_rules.apply_incoming_damage_multiplier(player, amount, damage_type)
    if amount <= 0:
        player._invincible_until = now_ticks + INVINCIBILITY_MS
        return

    pre_total = player.armor_hp + player.current_hp
    if player.armor_hp > 0:
        absorbed = min(amount, player.armor_hp)
        player.armor_hp -= absorbed
        amount -= absorbed

    player.current_hp = max(0, player.current_hp - amount)
    player._invincible_until = now_ticks + INVINCIBILITY_MS
    stat_runes.on_player_damage_taken(player, amount)
    total_taken = pre_total - (player.armor_hp + player.current_hp)
    if total_taken > 0:
        damage_feedback.report_damage(player, total_taken, damage_type=damage_type)