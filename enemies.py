"""Enemies: PatrolEnemy, RandomEnemy, ChaserEnemy."""
import math
import random
import pygame
import damage_feedback
import enemy_collision_rules
import status_effects
from sprites import make_rect_surface
from settings import (
    TILE_SIZE,
    PATROL_HP, PATROL_SPEED, PATROL_DAMAGE, COLOR_PATROL,
    RANDOM_HP, RANDOM_SPEED, RANDOM_DAMAGE, COLOR_RANDOM,
    CHASER_HP, CHASER_SPEED, CHASER_DAMAGE, COLOR_CHASER,
    CHASE_RADIUS, CHASE_LOST_RADIUS,
    DROP_CHANCE,
)
from item_catalog import ENEMY_LOOT_IDS, ENEMY_LOOT_WEIGHTS
from items import LootDrop, Coin

ENEMY_SIZE = 26


class Enemy(pygame.sprite.Sprite):
    """Abstract base enemy."""

    hp = 10
    speed = 1.0
    damage = 5
    color = COLOR_PATROL

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__()
        self.image = make_rect_surface(ENEMY_SIZE, ENEMY_SIZE, self.color)
        self.rect = self.image.get_rect(center=(x, y))
        self.max_hp = self.hp
        self.current_hp = self.hp
        self.is_frozen = bool(is_frozen)
        status_effects.reset_statuses(self)
        enemy_collision_rules.reset_collision_state(self)

    # ── to be overridden ────────────────────────────────
    def update_movement(self, player_rect, wall_rects):
        """Move according to AI pattern."""

    # ── damage / death ──────────────────────────────────
    def take_damage(self, amount):
        previous_hp = self.current_hp
        self.current_hp -= amount
        damage_dealt = previous_hp - max(self.current_hp, 0)
        if damage_dealt > 0:
            damage_feedback.report_damage(self, damage_dealt)
        if self.current_hp <= 0:
            self.kill()

    def roll_drop(self):
        """Return an Item instance (or None) at this enemy's position."""
        if random.random() > DROP_CHANCE:
            return None
        # 50% chance of a coin (instant pickup), 50% chance of inventory loot
        if random.random() < 0.5:
            return Coin(self.rect.centerx, self.rect.centery)
        # Pick from the inventory loot table
        if not ENEMY_LOOT_IDS:
            return None
        item_id = random.choices(ENEMY_LOOT_IDS, weights=ENEMY_LOOT_WEIGHTS, k=1)[0]
        return LootDrop(self.rect.centerx, self.rect.centery, item_id)

    # ── collision helper ────────────────────────────────
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


# ── PatrolEnemy ─────────────────────────────────────────
class PatrolEnemy(Enemy):
    hp = PATROL_HP
    speed = PATROL_SPEED
    damage = PATROL_DAMAGE
    color = COLOR_PATROL

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        # pick a random patrol axis and extent
        self._axis = random.choice(("h", "v"))
        extent = random.randint(4, 8) * TILE_SIZE
        if self._axis == "h":
            self._min = x - extent // 2
            self._max = x + extent // 2
            self._dir = 1
        else:
            self._min = y - extent // 2
            self._max = y + extent // 2
            self._dir = 1

    def update_movement(self, _player_rect, wall_rects):
        if self._axis == "h":
            dx = self.speed * self._dir
            self._move_axis(dx, 0, wall_rects)
            if self.rect.centerx >= self._max or self.rect.centerx <= self._min:
                self._dir *= -1
        else:
            dy = self.speed * self._dir
            self._move_axis(0, dy, wall_rects)
            if self.rect.centery >= self._max or self.rect.centery <= self._min:
                self._dir *= -1


# ── RandomEnemy ─────────────────────────────────────────
class RandomEnemy(Enemy):
    hp = RANDOM_HP
    speed = RANDOM_SPEED
    damage = RANDOM_DAMAGE
    color = COLOR_RANDOM

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self._pick_direction()

    def _pick_direction(self):
        angle = random.uniform(0, 2 * math.pi)
        self._dx = math.cos(angle)
        self._dy = math.sin(angle)
        self._timer = random.randint(30, 120)  # frames

    def update_movement(self, _player_rect, wall_rects):
        self._timer -= 1
        if self._timer <= 0:
            self._pick_direction()
        dx = self._dx * self.speed
        dy = self._dy * self.speed
        old_x, old_y = self.rect.x, self.rect.y
        self._move_axis(dx, 0, wall_rects)
        self._move_axis(0, dy, wall_rects)
        # if stuck on a wall, pick a new direction
        if self.rect.x == old_x and self.rect.y == old_y:
            self._pick_direction()


# ── ChaserEnemy ─────────────────────────────────────────
class ChaserEnemy(Enemy):
    hp = CHASER_HP
    speed = CHASER_SPEED
    damage = CHASER_DAMAGE
    color = COLOR_CHASER

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self._chasing = False

    def update_movement(self, player_rect, wall_rects):
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)

        if self._chasing:
            if dist > CHASE_LOST_RADIUS:
                self._chasing = False
                return
        else:
            if dist < CHASE_RADIUS:
                self._chasing = True
            else:
                return

        if dist == 0:
            return
        move_dx = (dx / dist) * self.speed
        move_dy = (dy / dist) * self.speed
        self._move_axis(move_dx, 0, wall_rects)
        self._move_axis(0, move_dy, wall_rects)


ENEMY_CLASSES = [PatrolEnemy, RandomEnemy, ChaserEnemy]
