"""Timer-based effect-state queries for Player runtime state."""

import stat_runes
from settings import SPEED_BOOST_MULTIPLIER


def is_speed_boosted(player, now_ticks):
    return now_ticks < player.speed_boost_until


def is_attack_boosted(player, now_ticks):
    return now_ticks < player.attack_boost_until


def effective_speed_multiplier(player, now_ticks):
    if is_speed_boosted(player, now_ticks):
        base = SPEED_BOOST_MULTIPLIER
    else:
        base = player.speed_multiplier
    return stat_runes.modify_speed_multiplier(player, base)