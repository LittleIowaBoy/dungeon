"""Combat-specific runtime rules for Player state."""

from settings import INVINCIBILITY_MS


def reset_runtime_combat(player, max_hp):
    player.max_hp = max_hp
    player.current_hp = max_hp
    player._invincible_until = 0


def is_invincible(player, now_ticks):
    return now_ticks < player._invincible_until


def is_alive(player):
    return player.current_hp > 0


def take_damage(player, amount, now_ticks):
    if is_invincible(player, now_ticks):
        return

    if player.armor_hp > 0:
        absorbed = min(amount, player.armor_hp)
        player.armor_hp -= absorbed
        amount -= absorbed

    player.current_hp = max(0, player.current_hp - amount)
    player._invincible_until = now_ticks + INVINCIBILITY_MS