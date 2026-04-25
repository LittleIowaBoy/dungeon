"""Enemy-vs-enemy collision damage.

Off by default (multiplier 0.0).  The Pacifist identity rune flips it
on by writing into ``player.rune_state["enemy_vs_enemy_multiplier"]``.

Each enemy carries ``collide_damage_cooldown_until`` so it cannot be
struck twice in the same frame chain.
"""

import pygame

COLLISION_COOLDOWN_MS = 500


def reset_collision_state(enemy):
    enemy.collide_damage_cooldown_until = 0


def enemy_vs_enemy_multiplier(player):
    state = getattr(player, "rune_state", None) or {}
    try:
        return float(state.get("enemy_vs_enemy_multiplier", 0.0))
    except (TypeError, ValueError):
        return 0.0


def apply_enemy_collisions(enemy_group, multiplier, now_ticks):
    """Damage each pair of overlapping enemies once per cooldown.

    Damage = ``other.damage * multiplier`` (rounded down to int).  Both
    enemies enter cooldown after a successful hit.  Returns the list of
    (attacker, victim, amount) tuples for testing/observability.
    """
    if multiplier <= 0:
        return []

    enemies = list(enemy_group)
    events = []
    for i, attacker in enumerate(enemies):
        if not attacker.alive() or _on_cooldown(attacker, now_ticks):
            continue
        if getattr(attacker, "is_frozen", False):
            continue
        for victim in enemies[i + 1:]:
            if not victim.alive() or _on_cooldown(victim, now_ticks):
                continue
            if getattr(victim, "is_frozen", False):
                continue
            if not attacker.rect.colliderect(victim.rect):
                continue
            amount_to_victim = int(getattr(attacker, "damage", 0) * multiplier)
            amount_to_attacker = int(getattr(victim, "damage", 0) * multiplier)
            if amount_to_victim > 0:
                victim.take_damage(amount_to_victim)
            if amount_to_attacker > 0:
                attacker.take_damage(amount_to_attacker)
            attacker.collide_damage_cooldown_until = now_ticks + COLLISION_COOLDOWN_MS
            victim.collide_damage_cooldown_until = now_ticks + COLLISION_COOLDOWN_MS
            events.append((attacker, victim, amount_to_victim))
            break  # attacker exhausted this frame
    return events


def _on_cooldown(enemy, now_ticks):
    return now_ticks < getattr(enemy, "collide_damage_cooldown_until", 0)
