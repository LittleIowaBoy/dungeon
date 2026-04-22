"""Timer-based effect-state queries for Player runtime state."""

from settings import SPEED_BOOST_MULTIPLIER


def is_speed_boosted(player, now_ticks):
    return now_ticks < player.speed_boost_until


def is_attack_boosted(player, now_ticks):
    return now_ticks < player.attack_boost_until


def effective_speed_multiplier(player, now_ticks):
    if is_speed_boosted(player, now_ticks):
        return SPEED_BOOST_MULTIPLIER
    return player.speed_multiplier