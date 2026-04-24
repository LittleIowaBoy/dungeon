"""Weapons: Sword (arc), Spear (line), Axe (circle) with AttackHitbox sprites."""
import pygame
from settings import (
    TILE_SIZE, PLAYER_SIZE, ATTACK_DURATION_MS,
    SWORD_DAMAGE, SWORD_RANGE, SWORD_COOLDOWN,
    SPEAR_DAMAGE, SPEAR_RANGE, SPEAR_WIDTH, SPEAR_COOLDOWN,
    AXE_DAMAGE, AXE_RANGE, AXE_COOLDOWN,
    HAMMER_DAMAGE, HAMMER_COOLDOWN,
    COLOR_SWORD_HIT, COLOR_SPEAR_HIT, COLOR_AXE_HIT, COLOR_HAMMER_HIT,
    COLOR_ATTACK_GLOW,
)

_SQ2 = 0.7071067811865476  # 1/sqrt(2) — used for 45° arc segments


# ── AttackHitbox sprite ─────────────────────────────────
class AttackHitbox(pygame.sprite.Sprite):
    """Temporary sprite that checks collisions with enemies."""

    def __init__(self, rect, damage, duration_ms, color,
                 weapon_id=None, damage_type=None):
        super().__init__()
        self.image = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        self.image.fill(color)
        self.rect = rect
        self.damage = damage
        self.weapon_id = weapon_id
        self.damage_type = damage_type
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
    weapon_id = None
    damage_type = None
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

    def _build_hitbox(self, rect, color):
        return AttackHitbox(
            rect,
            self.damage,
            ATTACK_DURATION_MS,
            color,
            weapon_id=self.weapon_id,
            damage_type=self.damage_type,
        )


# ── Sword ───────────────────────────────────────────────
class Sword(Weapon):
    name = "Sword"
    weapon_id = "sword"
    damage_type = "slash"
    damage = SWORD_DAMAGE
    cooldown_ms = SWORD_COOLDOWN

    def _make_hitbox(self, cx, cy, dx, dy):
        depth = int(SWORD_RANGE * TILE_SIZE)
        size = max(depth, PLAYER_SIZE + 8)
        offset = PLAYER_SIZE // 2 + size // 2 + 2
        # 180° arc: five hitbox segments fanned at -90°, -45°, 0°, +45°, +90°
        # relative to the facing direction.  Each returns as a list so the
        # pipeline can treat them like multi-segment spear hits.
        directions = [
            ( dy,           -dx),            # -90°
            ( _SQ2*(dx+dy),  _SQ2*(dy-dx)), # -45°
            ( dx,            dy),            #   0° (centre)
            ( _SQ2*(dx-dy),  _SQ2*(dx+dy)), # +45°
            (-dy,            dx),            # +90°
        ]
        hitboxes = []
        for ndx, ndy in directions:
            rect = pygame.Rect(0, 0, size, size)
            rect.center = (cx + int(ndx * offset), cy + int(ndy * offset))
            hitboxes.append(self._build_hitbox(rect, COLOR_SWORD_HIT))
        return hitboxes


# ── Spear ───────────────────────────────────────────────
class Spear(Weapon):
    name = "Spear"
    weapon_id = "spear"
    damage_type = "pierce"
    damage = SPEAR_DAMAGE
    cooldown_ms = SPEAR_COOLDOWN

    def _make_hitbox(self, cx, cy, dx, dy):
        length = int(SPEAR_RANGE * TILE_SIZE * 1.5)
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
                    self._build_hitbox(rect, COLOR_SPEAR_HIT)
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
            return self._build_hitbox(rect, COLOR_SPEAR_HIT)


# ── Axe ─────────────────────────────────────────────────
class Axe(Weapon):
    name = "Axe"
    weapon_id = "axe"
    damage_type = "slash"
    damage = AXE_DAMAGE
    cooldown_ms = AXE_COOLDOWN

    def _make_hitbox(self, cx, cy, _dx, _dy):
        r = int(AXE_RANGE * TILE_SIZE)
        size = r * 2
        rect = pygame.Rect(0, 0, size, size)
        rect.center = (cx, cy)
        return self._build_hitbox(rect, COLOR_AXE_HIT)


class Hammer(Weapon):
    name = "Hammer"
    weapon_id = "hammer"
    damage_type = "blunt"
    damage = HAMMER_DAMAGE
    cooldown_ms = HAMMER_COOLDOWN

    def _make_hitbox(self, cx, cy, dx, dy):
        # Small tight square — one tile — placed directly in front.
        size = TILE_SIZE
        offset = PLAYER_SIZE // 2 + size // 2 + 2
        rect = pygame.Rect(0, 0, size, size)
        rect.center = (cx + int(dx * offset), cy + int(dy * offset))
        return self._build_hitbox(rect, COLOR_HAMMER_HIT)


WEAPON_CLASS_BY_ID = {
    "sword": Sword,
    "spear": Spear,
    "axe": Axe,
    "hammer": Hammer,
}


def create_weapon(weapon_id):
    weapon_cls = WEAPON_CLASS_BY_ID.get(weapon_id)
    if weapon_cls is None:
        return None
    return weapon_cls()
