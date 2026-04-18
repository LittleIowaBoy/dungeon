"""Weapons: Sword (arc), Spear (line), Axe (circle) with AttackHitbox sprites."""
import math
import pygame
from settings import (
    TILE_SIZE, ATTACK_DURATION_MS,
    SWORD_DAMAGE, SWORD_RANGE, SWORD_COOLDOWN, SWORD_ARC_DEG,
    SPEAR_DAMAGE, SPEAR_RANGE, SPEAR_WIDTH, SPEAR_COOLDOWN,
    AXE_DAMAGE, AXE_RANGE, AXE_COOLDOWN,
    COLOR_SWORD_HIT, COLOR_SPEAR_HIT, COLOR_AXE_HIT,
    COLOR_ATTACK_GLOW,
)


# ── helpers ─────────────────────────────────────────────
def _direction_angle(dx, dy):
    """Return angle in degrees (0 = right, 90 = up) from a direction vector."""
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(-dy, dx))  # pygame y-down


# ── AttackHitbox sprite ─────────────────────────────────
class AttackHitbox(pygame.sprite.Sprite):
    """Temporary sprite that checks collisions with enemies."""

    def __init__(self, rect, damage, duration_ms, color):
        super().__init__()
        self.image = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        self.image.fill(color)
        self.rect = rect
        self.damage = damage
        self._spawn_time = pygame.time.get_ticks()
        self._duration = duration_ms
        self._hit_enemies = set()

    def update(self):
        if pygame.time.get_ticks() - self._spawn_time >= self._duration:
            self.kill()

    def try_hit(self, enemy):
        eid = id(enemy)
        if eid in self._hit_enemies:
            return False
        self._hit_enemies.add(eid)
        return True

    def set_glow(self):
        """Re-tint the hitbox image with attack boost red glow."""
        glow = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        glow.fill(COLOR_ATTACK_GLOW)
        self.image = glow


# ── Base Weapon ─────────────────────────────────────────
class Weapon:
    name = "weapon"
    damage = 0
    cooldown_ms = 300

    def __init__(self):
        self._last_attack = 0

    def can_attack(self):
        return pygame.time.get_ticks() - self._last_attack >= self.cooldown_ms

    def attack(self, player_cx, player_cy, facing_dx, facing_dy):
        """Return an AttackHitbox sprite or None if on cooldown."""
        if not self.can_attack():
            return None
        self._last_attack = pygame.time.get_ticks()
        return self._make_hitbox(player_cx, player_cy, facing_dx, facing_dy)

    def _make_hitbox(self, cx, cy, dx, dy):
        raise NotImplementedError


# ── Sword ───────────────────────────────────────────────
class Sword(Weapon):
    name = "Sword"
    damage = SWORD_DAMAGE
    cooldown_ms = SWORD_COOLDOWN

    def _make_hitbox(self, cx, cy, dx, dy):
        r = int(SWORD_RANGE * TILE_SIZE)
        # Build a square hitbox in front of the player
        size = r
        ox = int(dx * r * 0.6)
        oy = int(dy * r * 0.6)
        rect = pygame.Rect(0, 0, size, size)
        rect.center = (cx + ox, cy + oy)
        return AttackHitbox(rect, self.damage, ATTACK_DURATION_MS,
                            COLOR_SWORD_HIT)


# ── Spear ───────────────────────────────────────────────
class Spear(Weapon):
    name = "Spear"
    damage = SPEAR_DAMAGE
    cooldown_ms = SPEAR_COOLDOWN

    def _make_hitbox(self, cx, cy, dx, dy):
        length = int(SPEAR_RANGE * TILE_SIZE)
        width = int(SPEAR_WIDTH * TILE_SIZE)
        is_diagonal = abs(dx) > 0.1 and abs(dy) > 0.1

        if is_diagonal:
            # Place a line of small square segments along the diagonal.
            seg_size = max(width, 12)
            segments = max(int(length / seg_size), 3)
            hitboxes = []
            for i in range(segments):
                t = (i + 1) / segments  # 0..1 along the line
                sx = int(cx + dx * length * t)
                sy = int(cy + dy * length * t)
                rect = pygame.Rect(0, 0, seg_size, seg_size)
                rect.center = (sx, sy)
                hitboxes.append(
                    AttackHitbox(rect, self.damage, ATTACK_DURATION_MS,
                                 COLOR_SPEAR_HIT)
                )
            return hitboxes
        else:
            # Cardinal direction: simple oriented rectangle
            if abs(dx) >= abs(dy):
                w, h = length, width
            else:
                w, h = width, length
            ox = int(dx * length * 0.5)
            oy = int(dy * length * 0.5)
            rect = pygame.Rect(0, 0, w, h)
            rect.center = (cx + ox, cy + oy)
            return AttackHitbox(rect, self.damage, ATTACK_DURATION_MS,
                                COLOR_SPEAR_HIT)


# ── Axe ─────────────────────────────────────────────────
class Axe(Weapon):
    name = "Axe"
    damage = AXE_DAMAGE
    cooldown_ms = AXE_COOLDOWN

    def _make_hitbox(self, cx, cy, _dx, _dy):
        r = int(AXE_RANGE * TILE_SIZE)
        size = r * 2
        rect = pygame.Rect(0, 0, size, size)
        rect.center = (cx, cy)
        return AttackHitbox(rect, self.damage, ATTACK_DURATION_MS,
                            COLOR_AXE_HIT)
