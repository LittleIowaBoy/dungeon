"""Telegraphed-attack damage application for enemies.

Every enemy advertises ``active_hitboxes()`` (a list of ``pygame.Rect``)
during its ``STRIKE`` state.  This module walks the enemy group each
tick and applies the enemy's ``attack_damage`` to the player and any
ally that overlaps a hitbox, honouring per-strike single-hit semantics
via ``Enemy.try_register_hit``.

Pulsator rings and launcher projectiles live in their own sprite groups
and are processed by :func:`apply_enemy_projectiles` and
:func:`apply_pulsator_rings` (called from the same place).
"""
import stat_runes


def apply_enemy_attacks(enemy_group, player, ally_group, now_ticks):
    """Apply telegraphed enemy strikes to the player + allies.

    Returns the list of ``(enemy, victim, amount)`` events for
    observability/testing.  Stat-rune reflect on player damage is
    preserved (matches the legacy contact-damage behaviour).
    """
    events = []
    for enemy in list(enemy_group):
        if not enemy.alive() or getattr(enemy, "attacks_disabled", False):
            continue
        hitboxes = enemy.active_hitboxes()
        if not hitboxes:
            continue
        damage = int(getattr(enemy, "attack_damage", 0))
        if damage <= 0:
            continue

        # Player.
        if player is not None and not getattr(player, "is_invincible", False):
            if any(player.rect.colliderect(h) for h in hitboxes):
                if enemy.try_register_hit(player, now_ticks):
                    pre_hp = player.current_hp
                    player.take_damage(damage)
                    taken = pre_hp - player.current_hp
                    reflect = stat_runes.compute_reflect(player, taken)
                    if reflect > 0:
                        enemy.take_damage(reflect)
                    events.append((enemy, player, damage))

        # Allies.
        if ally_group is not None:
            for ally in list(ally_group):
                if not getattr(ally, "alive", lambda: True)():
                    continue
                if not any(ally.rect.colliderect(h) for h in hitboxes):
                    continue
                if not enemy.try_register_hit(ally, now_ticks):
                    continue
                if hasattr(ally, "take_damage"):
                    ally.take_damage(damage)
                events.append((enemy, ally, damage))

    return events


def apply_pulsator_rings(ring_group, player, ally_group):
    """Apply expanding-ring damage; once per ring per target."""
    from enemies import PULSATOR_RING_DAMAGE  # local import to avoid cycles

    events = []
    for ring in list(ring_group):
        targets = []
        if player is not None and not getattr(player, "is_invincible", False):
            targets.append(player)
        if ally_group is not None:
            targets.extend(ally for ally in ally_group)
        struck = ring.hit_targets(targets)
        for target in struck:
            if hasattr(target, "take_damage"):
                pre_hp = getattr(target, "current_hp", None)
                target.take_damage(PULSATOR_RING_DAMAGE)
                if target is player and pre_hp is not None:
                    taken = pre_hp - target.current_hp
                    reflect = stat_runes.compute_reflect(player, taken)
                    if reflect > 0 and ring._source is not None:
                        ring._source.take_damage(reflect)
            events.append((ring, target, PULSATOR_RING_DAMAGE))
    return events


def apply_launcher_projectiles(projectile_group, player, ally_group, wall_rects):
    """Step launcher projectiles; damage player/allies and despawn on walls.

    Projectiles never damage other enemies (per the design spec).
    """
    events = []
    for proj in list(projectile_group):
        if not proj.alive():
            continue
        if proj.collide_walls(wall_rects):
            continue
        damage = int(getattr(proj, "damage", 0))
        if damage <= 0:
            continue
        if player is not None and not getattr(player, "is_invincible", False):
            if proj.rect.colliderect(player.rect):
                pre_hp = player.current_hp
                player.take_damage(damage)
                taken = pre_hp - player.current_hp
                reflect = stat_runes.compute_reflect(player, taken)
                events.append((proj, player, damage))
                proj.kill()
                if reflect > 0:
                    # Projectiles have no source enemy reference here; reflect
                    # is dropped (matches behaviour: nothing to reflect onto
                    # once the projectile is gone).
                    pass
                continue
        if ally_group is not None:
            for ally in list(ally_group):
                if proj.rect.colliderect(ally.rect):
                    if hasattr(ally, "take_damage"):
                        ally.take_damage(damage)
                    events.append((proj, ally, damage))
                    proj.kill()
                    break
    return events
