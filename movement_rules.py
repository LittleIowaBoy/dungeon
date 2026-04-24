"""Movement and collision rules for Player runtime state."""

import math

import pygame

import dodge_rules
import status_effects
import time_rules
from settings import ICE_FRICTION, PLAYER_BASE_SPEED, TERRAIN_SPEED


def reset_runtime_movement(player):
    player.speed_multiplier = 1.0
    player.velocity_x = 0.0
    player.velocity_y = 0.0
    player._on_ice = False


def teleport(player, x, y):
    player.rect.center = (x, y)
    player.velocity_x = 0.0
    player.velocity_y = 0.0


def update_motion(player, wall_rects, terrain_at, keys):
    raw_dx, raw_dy = _read_input_vector(keys)

    magnitude = math.hypot(raw_dx, raw_dy)
    if magnitude > 0:
        raw_dx /= magnitude
        raw_dy /= magnitude
        player.facing_dx = raw_dx
        player.facing_dy = raw_dy

    terrain = terrain_at(player.rect.centerx, player.rect.centery)
    player._on_ice = terrain == "ice"

    speed = PLAYER_BASE_SPEED * player._effective_speed_multiplier()
    terrain_multiplier = TERRAIN_SPEED.get(terrain, 1.0)

    now_ticks = pygame.time.get_ticks()
    speed *= status_effects.speed_multiplier(player, now_ticks)
    speed *= time_rules.get_time_scale(player)
    if status_effects.is_immobilized(player, now_ticks):
        raw_dx = 0.0
        raw_dy = 0.0

    if player._on_ice:
        player.velocity_x += raw_dx * speed * 0.15
        player.velocity_y += raw_dy * speed * 0.15
        player.velocity_x *= ICE_FRICTION
        player.velocity_y *= ICE_FRICTION
    else:
        player.velocity_x = raw_dx * speed * terrain_multiplier
        player.velocity_y = raw_dy * speed * terrain_multiplier

    # Dodge override — locks velocity into a frozen burst direction.
    dodge_v = dodge_rules.dodge_velocity(player, pygame.time.get_ticks(), speed)
    if dodge_v is not None:
        player.velocity_x, player.velocity_y = dodge_v

    move_axis(player, player.velocity_x, 0, wall_rects)
    move_axis(player, 0, player.velocity_y, wall_rects)


def move_axis(player, dx, dy, wall_rects):
    player.rect.x += dx
    player.rect.y += dy
    for wall in wall_rects:
        if player.rect.colliderect(wall):
            if dx > 0:
                player.rect.right = wall.left
            elif dx < 0:
                player.rect.left = wall.right
            if dy > 0:
                player.rect.bottom = wall.top
            elif dy < 0:
                player.rect.top = wall.bottom


def _read_input_vector(keys):
    raw_dx = 0.0
    raw_dy = 0.0

    if _key_down(keys, pygame.K_LEFT) or _key_down(keys, pygame.K_a):
        raw_dx -= 1.0
    if _key_down(keys, pygame.K_RIGHT) or _key_down(keys, pygame.K_d):
        raw_dx += 1.0
    if _key_down(keys, pygame.K_UP) or _key_down(keys, pygame.K_w):
        raw_dy -= 1.0
    if _key_down(keys, pygame.K_DOWN) or _key_down(keys, pygame.K_s):
        raw_dy += 1.0

    return raw_dx, raw_dy


def _key_down(keys, key):
    if hasattr(keys, "get"):
        return bool(keys.get(key, False))
    return bool(keys[key])