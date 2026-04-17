"""Player: 8-dir movement, ice momentum, health, inventory, weapon slot."""
import math
import pygame
from sprites import make_rect_surface
from settings import (
    PLAYER_BASE_SPEED, PLAYER_MAX_HP, PLAYER_SIZE,
    INVINCIBILITY_MS, FLASH_INTERVAL_MS,
    TILE_SIZE, ROOM_COLS, ROOM_ROWS,
    ICE_FRICTION, TERRAIN_SPEED,
    COLOR_PLAYER,
)
from weapons import Sword, Spear, Axe


class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = make_rect_surface(PLAYER_SIZE, PLAYER_SIZE, COLOR_PLAYER)
        self._base_image = self.image.copy()
        self.rect = self.image.get_rect(center=(x, y))

        # stats
        self.max_hp = PLAYER_MAX_HP
        self.current_hp = PLAYER_MAX_HP
        self.speed_multiplier = 1.0
        self.coins = 0

        # movement
        self.facing_dx = 0.0
        self.facing_dy = 1.0  # face down initially
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self._on_ice = False

        # weapons
        self.weapons = [Sword(), Spear(), Axe()]
        self.current_weapon_index = 0

        # invincibility
        self._invincible_until = 0
        self._visible = True

    # ── properties ──────────────────────────────────────
    @property
    def weapon(self):
        return self.weapons[self.current_weapon_index]

    @property
    def is_invincible(self):
        return pygame.time.get_ticks() < self._invincible_until

    @property
    def alive(self):
        return self.current_hp > 0

    # ── damage ──────────────────────────────────────────
    def take_damage(self, amount):
        if self.is_invincible:
            return
        self.current_hp = max(0, self.current_hp - amount)
        self._invincible_until = pygame.time.get_ticks() + INVINCIBILITY_MS

    # ── weapon switching ────────────────────────────────
    def switch_weapon(self, index):
        if 0 <= index < len(self.weapons):
            self.current_weapon_index = index

    def attack(self):
        return self.weapon.attack(
            self.rect.centerx, self.rect.centery,
            self.facing_dx, self.facing_dy,
        )

    # ── movement / update ───────────────────────────────
    def update(self, wall_rects, terrain_at):
        """Called every frame. *wall_rects* is a list of pygame.Rect for
        collidable walls. *terrain_at(cx, cy)* returns the terrain string
        at a pixel position.
        """
        keys = pygame.key.get_pressed()

        # build raw direction from input
        raw_dx, raw_dy = 0.0, 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            raw_dx -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            raw_dx += 1.0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            raw_dy -= 1.0
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            raw_dy += 1.0

        # normalize so diagonal == cardinal speed
        mag = math.hypot(raw_dx, raw_dy)
        if mag > 0:
            raw_dx /= mag
            raw_dy /= mag
            self.facing_dx = raw_dx
            self.facing_dy = raw_dy

        # terrain at current center
        terrain = terrain_at(self.rect.centerx, self.rect.centery)
        self._on_ice = terrain == "ice"

        # compute effective speed
        speed = PLAYER_BASE_SPEED * self.speed_multiplier
        terrain_mult = TERRAIN_SPEED.get(terrain, 1.0)

        if self._on_ice:
            # ice momentum: input adds to velocity, friction decays
            self.velocity_x += raw_dx * speed * 0.15
            self.velocity_y += raw_dy * speed * 0.15
            self.velocity_x *= ICE_FRICTION
            self.velocity_y *= ICE_FRICTION
        else:
            self.velocity_x = raw_dx * speed * terrain_mult
            self.velocity_y = raw_dy * speed * terrain_mult

        # move and collide (axis-separated)
        self._move_axis(self.velocity_x, 0, wall_rects)
        self._move_axis(0, self.velocity_y, wall_rects)

        # invincibility flash
        if self.is_invincible:
            now = pygame.time.get_ticks()
            self._visible = ((now // FLASH_INTERVAL_MS) % 2 == 0)
            if self._visible:
                self.image = self._base_image
            else:
                self.image = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE),
                                            pygame.SRCALPHA)
        else:
            self._visible = True
            self.image = self._base_image

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

    # ── reset on room transition ────────────────────────
    def place(self, x, y):
        """Teleport to (x, y) and zero ice velocity."""
        self.rect.center = (x, y)
        self.velocity_x = 0.0
        self.velocity_y = 0.0

    # ── reset for new dungeon run ───────────────────────
    def reset_for_dungeon(self, progress):
        """Reset in-dungeon stats for a fresh dungeon entry.

        Persistent coins are synced from *progress*.  In-dungeon boosts
        (speed, HP) are reset to base values from progress.
        """
        self.max_hp = progress.max_hp
        self.current_hp = self.max_hp
        self.speed_multiplier = 1.0
        self.coins = progress.coins
        self._invincible_until = 0
        self._visible = True
        self.velocity_x = 0.0
        self.velocity_y = 0.0
