"""Friendly NPCs that fight alongside the player.

Currently supplies :class:`SkeletonAlly` for the Necromancer identity rune.
Allies share the broad shape of :class:`enemies.Enemy` (sprite + ``rect`` +
``current_hp``/``max_hp`` + ``take_damage``) but live in a separate sprite
group so they do not interfere with enemy-vs-enemy collisions or player hit
detection.
"""

import math
import random

import pygame

import status_effects
from sprites import make_rect_surface


ALLY_SIZE = 24

# ── SkeletonAlly tuning ────────────────────────────────
SKELETON_HP = 18
SKELETON_DAMAGE = 6
SKELETON_SPEED = 1.4
SKELETON_ATTACK_COOLDOWN_MS = 600
SKELETON_LIFETIME_MS = 15_000          # despawn after 15s if alive
SKELETON_FOLLOW_RADIUS = 64            # idle distance from player when no enemies
SKELETON_COLOR = (220, 220, 200)       # bone-white


class SkeletonAlly(pygame.sprite.Sprite):
    """A summoned skeleton that chases the nearest enemy and melee-hits it."""

    def __init__(self, x, y, spawn_ticks=0):
        super().__init__()
        self.image = make_rect_surface(ALLY_SIZE, ALLY_SIZE, SKELETON_COLOR)
        self.rect = self.image.get_rect(center=(x, y))
        self.max_hp = SKELETON_HP
        self.current_hp = SKELETON_HP
        self.damage = SKELETON_DAMAGE
        self.speed = SKELETON_SPEED
        self._spawn_ticks = int(spawn_ticks)
        self._next_attack_ready_at = 0
        status_effects.reset_statuses(self)

    # ── lifecycle ──────────────────────────────────────
    def expired(self, now_ticks):
        return now_ticks - self._spawn_ticks >= SKELETON_LIFETIME_MS

    def take_damage(self, amount):
        self.current_hp -= amount
        if self.current_hp <= 0:
            self.kill()

    # ── targeting ──────────────────────────────────────
    def pick_target(self, enemy_group):
        nearest = None
        best_dist_sq = None
        cx, cy = self.rect.center
        for enemy in enemy_group:
            ex, ey = enemy.rect.center
            d_sq = (ex - cx) * (ex - cx) + (ey - cy) * (ey - cy)
            if best_dist_sq is None or d_sq < best_dist_sq:
                best_dist_sq = d_sq
                nearest = enemy
        return nearest

    # ── movement ───────────────────────────────────────
    def update_movement(self, target_rect, wall_rects):
        """Step toward *target_rect*. If None, hold position."""
        if target_rect is None:
            return
        dx = target_rect.centerx - self.rect.centerx
        dy = target_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        move_dx = (dx / dist) * self.speed
        move_dy = (dy / dist) * self.speed
        self._move_axis(move_dx, 0, wall_rects)
        self._move_axis(0, move_dy, wall_rects)

    def _move_axis(self, dx, dy, wall_rects):
        self.rect.x += dx
        self.rect.y += dy
        for wall in wall_rects:
            if self.rect.colliderect(wall):
                if dx > 0:
                    self.rect.right = wall.left
                elif dx < 0:
                    self.rect.left = wall.right
                if dy > 0:
                    self.rect.bottom = wall.top
                elif dy < 0:
                    self.rect.top = wall.bottom

    # ── attack ─────────────────────────────────────────
    def try_attack(self, enemy, now_ticks):
        """Deal damage to *enemy* if cooldown ready and they touch.

        Returns True if a hit landed.
        """
        if now_ticks < self._next_attack_ready_at:
            return False
        if not self.rect.colliderect(enemy.rect):
            return False
        enemy.take_damage(self.damage)
        self._next_attack_ready_at = now_ticks + SKELETON_ATTACK_COOLDOWN_MS
        return True


def spawn_skeleton_near(player, ally_group, now_ticks, jitter=12):
    """Spawn a SkeletonAlly within a small jitter of the player's position."""
    cx, cy = player.rect.center
    ox = random.randint(-jitter, jitter)
    oy = random.randint(-jitter, jitter)
    ally = SkeletonAlly(cx + ox, cy + oy, spawn_ticks=now_ticks)
    ally_group.add(ally)
    return ally


def update_allies(ally_group, enemy_group, player, wall_rects, now_ticks):
    """Per-frame ally tick: target nearest enemy (or follow player), then attack on contact.

    Despawns expired allies.
    """
    for ally in list(ally_group):
        if ally.expired(now_ticks):
            ally.kill()
            continue
        target = ally.pick_target(enemy_group)
        if target is None:
            # idle: drift toward player but stop within follow radius
            dx = player.rect.centerx - ally.rect.centerx
            dy = player.rect.centery - ally.rect.centery
            dist = math.hypot(dx, dy)
            if dist > SKELETON_FOLLOW_RADIUS:
                ally.update_movement(player.rect, wall_rects)
            continue
        ally.update_movement(target.rect, wall_rects)
        # melee swing if touching
        ally.try_attack(target, now_ticks)
