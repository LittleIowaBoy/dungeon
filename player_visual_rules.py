"""Runtime visual-state rules for the player sprite."""

import pygame

from settings import COLOR_SPEED_GLOW, FLASH_INTERVAL_MS, PLAYER_SIZE


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