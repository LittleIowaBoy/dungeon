"""Runtime visual-state rules for the player sprite."""

import pygame

from settings import (
    COLOR_SPEED_GLOW,
    ENEMY_TELEGRAPH_FLASH_INTERVAL_MS,
    FLASH_INTERVAL_MS,
    PLAYER_SIZE,
)


def reset_runtime_visuals(player):
    player._visible = True
    _set_image(player, player._base_image)


def update_runtime_visuals(player, now):
    if now < player._invincible_until:
        player._visible = ((now // FLASH_INTERVAL_MS) % 2 == 0)
        if player._visible:
            _set_image(player, player._base_image)
        else:
            _set_image(
                player,
                pygame.Surface((PLAYER_SIZE, PLAYER_SIZE), pygame.SRCALPHA),
            )
        return

    player._visible = True
    if now < player.speed_boost_until:
        glow = pygame.Surface((PLAYER_SIZE + 4, PLAYER_SIZE + 4), pygame.SRCALPHA)
        glow.fill((*COLOR_SPEED_GLOW, 80))
        glow.blit(player._base_image, (2, 2))
        _set_image(player, glow)
        return

    _set_image(player, player._base_image)


def _set_image(player, image):
    center = player.rect.center
    player.image = image
    player.rect = image.get_rect(center=center)


_TELEGRAPH_OVERLAY_COLOR = (255, 255, 255, 140)


def apply_enemy_telegraph_tint(enemy, now_ticks):
    """Drive the pre-attack flash for an enemy sprite.

    Reads ``enemy._telegraph_active`` (bool) and toggles a bright overlay on
    top of ``enemy._base_image`` at a fixed cadence.  When the telegraph is
    inactive the original image is restored.  Safe to call every frame.
    """
    base = getattr(enemy, "_base_image", None)
    if base is None:
        return
    center = enemy.rect.center
    if getattr(enemy, "_telegraph_active", False):
        on = (int(now_ticks) // ENEMY_TELEGRAPH_FLASH_INTERVAL_MS) % 2 == 0
        if on:
            overlay = base.copy()
            flash = pygame.Surface(base.get_size(), pygame.SRCALPHA)
            flash.fill(_TELEGRAPH_OVERLAY_COLOR)
            overlay.blit(flash, (0, 0))
            enemy.image = overlay
            enemy.rect = overlay.get_rect(center=center)
            return
    if enemy.image is not base:
        enemy.image = base
        enemy.rect = base.get_rect(center=center)