"""Enemies: PatrolEnemy, RandomEnemy, ChaserEnemy, PulsatorEnemy,
LauncherEnemy (with projectile), SentryEnemy.

All enemies share a telegraphed-attack state machine implemented on the
``Enemy`` base class.  A helper module ``enemy_attack_rules`` walks the
group every tick and converts each enemy's ``active_hitboxes()`` into
damage applied to the player / allies.  Enemy contact damage no longer
exists; every hit is delivered through this telegraphed pathway.
"""
import math
import random
import pygame
import damage_feedback
import enemy_collision_rules
import movement_rules
import player_visual_rules
import status_effects
from sprites import make_rect_surface
from settings import (
    TILE_SIZE,
    PATROL_HP, PATROL_SPEED, PATROL_DAMAGE, COLOR_PATROL,
    PATROL_ATTACK_TRIGGER, PATROL_ATTACK_RADIUS, PATROL_ATTACK_DAMAGE,
    PATROL_ATTACK_WINDUP_MS, PATROL_ATTACK_STRIKE_MS, PATROL_ATTACK_COOLDOWN_MS,
    RANDOM_HP, RANDOM_SPEED, RANDOM_DAMAGE, COLOR_RANDOM,
    RANDOM_ATTACK_TRIGGER, RANDOM_ATTACK_RANGE, RANDOM_ATTACK_WIDTH,
    RANDOM_ATTACK_DAMAGE, RANDOM_ATTACK_WINDUP_MS, RANDOM_ATTACK_STRIKE_MS,
    RANDOM_ATTACK_COOLDOWN_MS,
    CHASER_HP, CHASER_SPEED, CHASER_DAMAGE, COLOR_CHASER,
    CHASE_RADIUS, CHASE_LOST_RADIUS,
    CHASER_ATTACK_TRIGGER, CHASER_ATTACK_SIZE, CHASER_ATTACK_OFFSET,
    CHASER_ATTACK_DAMAGE, CHASER_ATTACK_WINDUP_MS, CHASER_ATTACK_STRIKE_MS,
    CHASER_ATTACK_COOLDOWN_MS,
    COLOR_PULSATOR, PULSATOR_HP, PULSATOR_SPEED,
    PULSATOR_ANCHOR_RADIUS_TILES, PULSATOR_ANCHOR_WAIT_MS, PULSATOR_WINDUP_MS,
    PULSATOR_RING_SPEED, PULSATOR_RING_THICKNESS, PULSATOR_RING_MAX_RADIUS,
    PULSATOR_RING_DAMAGE, PULSATOR_COOLDOWN_MS,
    COLOR_LAUNCHER, LAUNCHER_HP, LAUNCHER_SPEED, LAUNCHER_RETREAT_SPEED,
    LAUNCHER_RANGE, LAUNCHER_ATTACK_WINDUP_MS, LAUNCHER_ATTACK_STRIKE_MS,
    LAUNCHER_ATTACK_COOLDOWN_MS, LAUNCHER_RETREAT_MS,
    LAUNCHER_PROJECTILE_SPEED, LAUNCHER_PROJECTILE_RANGE,
    LAUNCHER_PROJECTILE_DAMAGE, LAUNCHER_PROJECTILE_SIZE,
    COLOR_SENTRY, SENTRY_HP, SENTRY_PATROL_SPEED, SENTRY_CHASE_SPEED,
    SENTRY_SIGHT_RADIUS, SENTRY_DETONATE_RADIUS, SENTRY_EXPLOSION_RADIUS,
    SENTRY_EXPLOSION_DAMAGE, SENTRY_ALERT_FLASH_MS, SENTRY_ARM_MS,
    DROP_CHANCE,
)
from item_catalog import ENEMY_LOOT_IDS, ENEMY_LOOT_WEIGHTS
from items import LootDrop, Coin

ENEMY_SIZE = 26


# ── Attack-state constants ─────────────────────────────
ATTACK_IDLE      = "idle"
ATTACK_TELEGRAPH = "telegraph"
ATTACK_STRIKE    = "strike"
ATTACK_COOLDOWN  = "cooldown"


class Enemy(pygame.sprite.Sprite):
    """Abstract base enemy with a telegraphed-attack state machine.

    Subclasses opt in to attacks by overriding
    :meth:`_can_begin_attack` / :meth:`_on_telegraph_start` /
    :meth:`active_hitboxes` and setting their ``attack_*_ms`` /
    ``attack_damage`` class attributes.  Subclasses that never attack
    leave the defaults (which return no hitbox and never transition out
    of IDLE).
    """

    hp = 10
    speed = 1.0
    damage = 5                    # legacy stat (kept for tests/UI)
    color = COLOR_PATROL

    # Attack tuning — defaults to a no-op attack.
    attack_damage = 0
    attack_windup_ms = 0
    attack_strike_ms = 0
    attack_cooldown_ms = 0

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__()
        self.image = make_rect_surface(ENEMY_SIZE, ENEMY_SIZE, self.color)
        self._base_image = self.image
        self.rect = self.image.get_rect(center=(x, y))
        self.max_hp = self.hp
        self.current_hp = self.hp
        self.is_frozen = bool(is_frozen)
        # Independent toggle: when True, the enemy never initiates a new
        # attack and ``apply_enemy_attacks`` skips it.  Defaults to track
        # ``is_frozen`` so existing frozen showcase enemies stay passive.
        self.attacks_disabled = bool(is_frozen)
        status_effects.reset_statuses(self)
        enemy_collision_rules.reset_collision_state(self)

        # Attack state machine.
        self._attack_state = ATTACK_IDLE
        self._attack_state_until = 0
        self._telegraph_active = False
        self._struck_ids = set()

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
        if random.random() < 0.5:
            return Coin(self.rect.centerx, self.rect.centery)
        if not ENEMY_LOOT_IDS:
            return None
        item_id = random.choices(ENEMY_LOOT_IDS, weights=ENEMY_LOOT_WEIGHTS, k=1)[0]
        return LootDrop(self.rect.centerx, self.rect.centery, item_id)

    # ── collision helper ────────────────────────────────
    def _move_axis(self, dx, dy, wall_rects):
        """Move this enemy by (dx, dy), returning the set of blocked axes."""
        _mx, _my, blocked = movement_rules.move_axis_with_walls(
            self.rect, dx, dy, wall_rects
        )
        return blocked

    # ── attack state machine ────────────────────────────
    def update_attack_state(self, player_rect, now_ticks):
        """Advance the attack state machine and update visuals."""
        state = self._attack_state
        if state == ATTACK_TELEGRAPH and now_ticks >= self._attack_state_until:
            self._attack_state = ATTACK_STRIKE
            self._attack_state_until = now_ticks + max(1, self.attack_strike_ms)
            self._telegraph_active = False
            self._struck_ids = set()
            self._on_strike_start(player_rect, now_ticks)
        elif state == ATTACK_STRIKE and now_ticks >= self._attack_state_until:
            self._attack_state = ATTACK_COOLDOWN
            self._attack_state_until = now_ticks + max(0, self.attack_cooldown_ms)
            self._on_strike_end(now_ticks)
        elif state == ATTACK_COOLDOWN and now_ticks >= self._attack_state_until:
            self._attack_state = ATTACK_IDLE

        if (
            self._attack_state == ATTACK_IDLE
            and not self.attacks_disabled
            and self._can_begin_attack(player_rect)
        ):
            self._attack_state = ATTACK_TELEGRAPH
            self._attack_state_until = now_ticks + max(1, self.attack_windup_ms)
            self._telegraph_active = True
            self._on_telegraph_start(player_rect, now_ticks)

        player_visual_rules.apply_enemy_telegraph_tint(self, now_ticks)

    def is_attacking_blocking_movement(self):
        """When True, the runtime should skip ``update_movement`` this tick."""
        return self._attack_state in (ATTACK_TELEGRAPH, ATTACK_STRIKE)

    def _hitbox_geometry(self):
        """Return attack hitbox rects ignoring state.

        Subclasses override this with the pure geometry of their swing.
        :meth:`active_hitboxes` and :meth:`telegraph_hitboxes` then filter
        by the current attack state so callers (damage rules, debug
        renderer) see the right rects at the right time.
        """
        return ()

    def active_hitboxes(self):
        """Return current attack hitboxes (only during STRIKE)."""
        if self._attack_state != ATTACK_STRIKE:
            return ()
        return self._hitbox_geometry()

    def telegraph_hitboxes(self):
        """Return preview hitboxes during TELEGRAPH (debug visualisation)."""
        if self._attack_state != ATTACK_TELEGRAPH:
            return ()
        return self._hitbox_geometry()

    def try_register_hit(self, target, _now_ticks):
        """Return True if *target* has not yet been struck this swing."""
        key = id(target)
        if key in self._struck_ids:
            return False
        self._struck_ids.add(key)
        return True

    # Subclass hooks (default no-op).
    def _can_begin_attack(self, player_rect):
        return False

    def _on_telegraph_start(self, player_rect, now_ticks):
        pass

    def _on_strike_start(self, player_rect, now_ticks):
        pass

    def _on_strike_end(self, now_ticks):
        pass


# ── PatrolEnemy ─────────────────────────────────────────
class PatrolEnemy(Enemy):
    hp = PATROL_HP
    speed = PATROL_SPEED
    damage = PATROL_DAMAGE
    color = COLOR_PATROL

    attack_damage = PATROL_ATTACK_DAMAGE
    attack_windup_ms = PATROL_ATTACK_WINDUP_MS
    attack_strike_ms = PATROL_ATTACK_STRIKE_MS
    attack_cooldown_ms = PATROL_ATTACK_COOLDOWN_MS

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
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
        if self.is_attacking_blocking_movement():
            return
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

    def _can_begin_attack(self, player_rect):
        if player_rect is None:
            return False
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return (dx * dx + dy * dy) <= (PATROL_ATTACK_TRIGGER * PATROL_ATTACK_TRIGGER)

    def _hitbox_geometry(self):
        size = int(PATROL_ATTACK_RADIUS * 2)
        rect = pygame.Rect(0, 0, size, size)
        rect.center = self.rect.center
        return (rect,)


# ── RandomEnemy ─────────────────────────────────────────
class RandomEnemy(Enemy):
    hp = RANDOM_HP
    speed = RANDOM_SPEED
    damage = RANDOM_DAMAGE
    color = COLOR_RANDOM

    attack_damage = RANDOM_ATTACK_DAMAGE
    attack_windup_ms = RANDOM_ATTACK_WINDUP_MS
    attack_strike_ms = RANDOM_ATTACK_STRIKE_MS
    attack_cooldown_ms = RANDOM_ATTACK_COOLDOWN_MS

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self._pick_direction()
        self._no_progress_streak = 0
        self._strike_facing = (1, 0)

    def _pick_direction(self, blocked_axes=None):
        # Bias new direction away from any blocked axis to avoid wall-hugging.
        for _ in range(8):
            angle = random.uniform(0, 2 * math.pi)
            dx = math.cos(angle)
            dy = math.sin(angle)
            if blocked_axes:
                if "x" in blocked_axes and dx * self._dx > 0:
                    continue
                if "y" in blocked_axes and dy * self._dy > 0:
                    continue
            self._dx = dx
            self._dy = dy
            break
        else:
            self._dx = math.cos(angle)
            self._dy = math.sin(angle)
        self._timer = random.randint(30, 120)

    # Initial values set before _pick_direction can read them.
    _dx = 1.0
    _dy = 0.0

    def update_movement(self, _player_rect, wall_rects):
        if self.is_attacking_blocking_movement():
            return
        self._timer -= 1
        if self._timer <= 0:
            self._pick_direction()
        dx = self._dx * self.speed
        dy = self._dy * self.speed
        old_x, old_y = self.rect.x, self.rect.y
        blocked = set()
        blocked |= self._move_axis(dx, 0, wall_rects)
        blocked |= self._move_axis(0, dy, wall_rects)
        moved = (self.rect.x != old_x) or (self.rect.y != old_y)
        if not moved:
            self._no_progress_streak += 1
        else:
            self._no_progress_streak = 0
        if blocked or self._no_progress_streak >= 2:
            self._pick_direction(blocked_axes=blocked or {"x", "y"})
            self._no_progress_streak = 0

    def _can_begin_attack(self, player_rect):
        if player_rect is None:
            return False
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return (dx * dx + dy * dy) <= (RANDOM_ATTACK_TRIGGER * RANDOM_ATTACK_TRIGGER)

    def _on_telegraph_start(self, player_rect, now_ticks):
        if player_rect is None:
            return
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        if abs(dx) >= abs(dy):
            self._strike_facing = (1 if dx >= 0 else -1, 0)
        else:
            self._strike_facing = (0, 1 if dy >= 0 else -1)

    def _hitbox_geometry(self):
        fx, fy = self._strike_facing
        cx, cy = self.rect.center
        if fx != 0:
            width = int(RANDOM_ATTACK_RANGE)
            height = RANDOM_ATTACK_WIDTH
            rect = pygame.Rect(0, 0, width, height)
            if fx > 0:
                rect.midleft = (cx, cy)
            else:
                rect.midright = (cx, cy)
        else:
            width = RANDOM_ATTACK_WIDTH
            height = int(RANDOM_ATTACK_RANGE)
            rect = pygame.Rect(0, 0, width, height)
            if fy > 0:
                rect.midtop = (cx, cy)
            else:
                rect.midbottom = (cx, cy)
        return (rect,)


# ── ChaserEnemy ─────────────────────────────────────────
class ChaserEnemy(Enemy):
    hp = CHASER_HP
    speed = CHASER_SPEED
    damage = CHASER_DAMAGE
    color = COLOR_CHASER

    attack_damage = CHASER_ATTACK_DAMAGE
    attack_windup_ms = CHASER_ATTACK_WINDUP_MS
    attack_strike_ms = CHASER_ATTACK_STRIKE_MS
    attack_cooldown_ms = CHASER_ATTACK_COOLDOWN_MS

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self._chasing = False
        self._facing = (1, 0)
        self._strike_facing = (1, 0)

    def update_movement(self, player_rect, wall_rects):
        if self.is_attacking_blocking_movement():
            return
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
        nx = dx / dist
        ny = dy / dist
        if abs(nx) >= abs(ny):
            self._facing = (1 if nx >= 0 else -1, 0)
        else:
            self._facing = (0, 1 if ny >= 0 else -1)
        move_dx = nx * self.speed
        move_dy = ny * self.speed
        self._move_axis(move_dx, 0, wall_rects)
        self._move_axis(0, move_dy, wall_rects)

    def _can_begin_attack(self, player_rect):
        if player_rect is None:
            return False
        # Range-only check; the chase-state gate was removed so a chaser
        # whose movement is suppressed (test-room frozen showcase) can still
        # attack when the player walks into melee range.
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return (dx * dx + dy * dy) <= (CHASER_ATTACK_TRIGGER * CHASER_ATTACK_TRIGGER)

    def _on_telegraph_start(self, player_rect, now_ticks):
        self._strike_facing = self._facing

    def _hitbox_geometry(self):
        fx, fy = self._strike_facing
        size = CHASER_ATTACK_SIZE
        offset = CHASER_ATTACK_OFFSET + size // 2
        cx = self.rect.centerx + fx * offset
        cy = self.rect.centery + fy * offset
        rect = pygame.Rect(0, 0, size, size)
        rect.center = (cx, cy)
        return (rect,)


# ── PulsatorEnemy ───────────────────────────────────────
class PulsatorRing(pygame.sprite.Sprite):
    """Expanding annular damage ring emitted by a PulsatorEnemy."""

    def __init__(self, center, *, source=None):
        super().__init__()
        self.center = (int(center[0]), int(center[1]))
        self._source = source
        self.radius = 4.0
        self._struck_ids = set()
        self._alive = True
        self._build_image()

    def _build_image(self):
        diameter = max(2, int(self.radius * 2 + 4))
        surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        alpha = max(20, 200 - int(self.radius * 200 / max(1, PULSATOR_RING_MAX_RADIUS)))
        color = (*COLOR_PULSATOR, alpha)
        pygame.draw.circle(
            surf, color, (diameter // 2, diameter // 2),
            int(self.radius), max(2, PULSATOR_RING_THICKNESS // 4),
        )
        self.image = surf
        self.rect = surf.get_rect(center=self.center)

    def update(self, *_args, **_kwargs):
        if not self._alive:
            return
        self.radius += PULSATOR_RING_SPEED
        if self.radius >= PULSATOR_RING_MAX_RADIUS:
            self._alive = False
            self.kill()
            return
        self._build_image()

    def hit_targets(self, targets):
        """Return a list of *targets* whose centre falls inside the ring band."""
        inner = max(0, self.radius - PULSATOR_RING_THICKNESS / 2)
        outer = self.radius + PULSATOR_RING_THICKNESS / 2
        cx, cy = self.center
        out = []
        for target in targets:
            if id(target) in self._struck_ids:
                continue
            tx = target.rect.centerx
            ty = target.rect.centery
            d = math.hypot(tx - cx, ty - cy)
            if inner <= d <= outer:
                self._struck_ids.add(id(target))
                out.append(target)
        return out


class PulsatorEnemy(Enemy):
    hp = PULSATOR_HP
    speed = PULSATOR_SPEED
    damage = 0
    color = COLOR_PULSATOR

    attack_damage = PULSATOR_RING_DAMAGE
    attack_windup_ms = PULSATOR_WINDUP_MS
    attack_strike_ms = 60                  # ring "born" frame
    attack_cooldown_ms = PULSATOR_COOLDOWN_MS

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self._anchor_points = self._build_anchor_points(x, y)
        self._target_index = 0
        self._wait_until = 0
        self.emitted_rings: list[PulsatorRing] = []

    def _build_anchor_points(self, x, y):
        radius_px = PULSATOR_ANCHOR_RADIUS_TILES * TILE_SIZE
        shape = random.choice(("line", "L", "triangle"))
        if shape == "line":
            offsets = ((0, 0), (radius_px, 0), (-radius_px, 0))
        elif shape == "L":
            offsets = ((0, 0), (radius_px, 0), (radius_px, radius_px))
        else:
            offsets = ((0, 0), (radius_px, 0), (0, radius_px))
        return [(x + dx, y + dy) for (dx, dy) in offsets]

    def update_movement(self, _player_rect, wall_rects):
        if self.is_attacking_blocking_movement():
            return
        target = self._anchor_points[self._target_index]
        dx = target[0] - self.rect.centerx
        dy = target[1] - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist <= self.speed:
            # Snap into anchor and wait briefly before the next pulse.
            self.rect.center = target
        else:
            nx = dx / dist
            ny = dy / dist
            self._move_axis(nx * self.speed, 0, wall_rects)
            self._move_axis(0, ny * self.speed, wall_rects)

    def _can_begin_attack(self, _player_rect):
        if self._attack_state != ATTACK_IDLE:
            return False
        target = self._anchor_points[self._target_index]
        dx = target[0] - self.rect.centerx
        dy = target[1] - self.rect.centery
        return (dx * dx + dy * dy) <= (TILE_SIZE // 2) ** 2

    def _on_strike_start(self, _player_rect, _now_ticks):
        ring = PulsatorRing(self.rect.center, source=self)
        self.emitted_rings.append(ring)

    def _on_strike_end(self, _now_ticks):
        # Advance to the next anchor after each pulse.
        self._target_index = (self._target_index + 1) % len(self._anchor_points)

    def consume_emitted_rings(self):
        rings = self.emitted_rings
        self.emitted_rings = []
        return rings


# ── LauncherEnemy ──────────────────────────────────────
class LauncherProjectile(pygame.sprite.Sprite):
    """Slow-moving projectile fired by a LauncherEnemy.

    Damages player + allies on overlap; ignores other enemies entirely.
    Despawns on wall collision or after ``LAUNCHER_PROJECTILE_RANGE``.
    """

    SIZE = LAUNCHER_PROJECTILE_SIZE
    damage = LAUNCHER_PROJECTILE_DAMAGE

    def __init__(self, x, y, vx, vy):
        super().__init__()
        self.image = make_rect_surface(self.SIZE, self.SIZE, COLOR_LAUNCHER)
        self.rect = self.image.get_rect(center=(int(x), int(y)))
        self._vx = float(vx)
        self._vy = float(vy)
        self._distance_traveled = 0.0

    def update(self, *_args, **_kwargs):
        # Manual integration; collision handled by enemy_attack_rules.
        self.rect.x += self._vx
        self.rect.y += self._vy
        self._distance_traveled += math.hypot(self._vx, self._vy)
        if self._distance_traveled >= LAUNCHER_PROJECTILE_RANGE:
            self.kill()

    def collide_walls(self, wall_rects):
        for wall in wall_rects:
            if self.rect.colliderect(wall):
                self.kill()
                return True
        return False


class LauncherEnemy(Enemy):
    hp = LAUNCHER_HP
    speed = LAUNCHER_SPEED
    damage = 0
    color = COLOR_LAUNCHER

    attack_damage = 0                       # damage delivered by projectile
    attack_windup_ms = LAUNCHER_ATTACK_WINDUP_MS
    attack_strike_ms = LAUNCHER_ATTACK_STRIKE_MS
    attack_cooldown_ms = LAUNCHER_ATTACK_COOLDOWN_MS

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self._retreat_until = 0
        self._fire_dir = (1.0, 0.0)
        self.emitted_projectiles: list[LauncherProjectile] = []

    def _can_begin_attack(self, player_rect):
        if player_rect is None:
            return False
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return (dx * dx + dy * dy) <= (LAUNCHER_RANGE * LAUNCHER_RANGE)

    def _on_telegraph_start(self, player_rect, _now_ticks):
        if player_rect is None:
            return
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy) or 1.0
        self._fire_dir = (dx / dist, dy / dist)

    def _on_strike_start(self, player_rect, _now_ticks):
        fx, fy = self._fire_dir
        speed = LAUNCHER_PROJECTILE_SPEED
        proj = LauncherProjectile(
            self.rect.centerx, self.rect.centery, fx * speed, fy * speed,
        )
        self.emitted_projectiles.append(proj)

    def _on_strike_end(self, now_ticks):
        self._retreat_until = now_ticks + LAUNCHER_RETREAT_MS

    def update_movement(self, player_rect, wall_rects):
        if self.is_attacking_blocking_movement():
            return
        now = pygame.time.get_ticks()
        if now < self._retreat_until and player_rect is not None:
            dx = self.rect.centerx - player_rect.centerx
            dy = self.rect.centery - player_rect.centery
            dist = math.hypot(dx, dy) or 1.0
            speed = LAUNCHER_RETREAT_SPEED
            self._move_axis((dx / dist) * speed, 0, wall_rects)
            self._move_axis(0, (dy / dist) * speed, wall_rects)

    def consume_emitted_projectiles(self):
        out = self.emitted_projectiles
        self.emitted_projectiles = []
        return out


# ── SentryEnemy ────────────────────────────────────────
SENTRY_PATROL = "patrol"
SENTRY_ALERT  = "alert"
SENTRY_CHASE  = "chase"
SENTRY_ARM    = "arm"
SENTRY_EXPLODE = "explode"


class SentryEnemy(Enemy):
    """Stealth-room patroller that explodes on close contact."""

    hp = SENTRY_HP
    speed = SENTRY_PATROL_SPEED
    damage = 0
    color = COLOR_SENTRY

    attack_damage = SENTRY_EXPLOSION_DAMAGE
    attack_windup_ms = SENTRY_ARM_MS
    attack_strike_ms = 80
    attack_cooldown_ms = 0

    def __init__(self, x, y, *, is_frozen=False, patrol_points=None, alarm_config=None):
        super().__init__(x, y, is_frozen=is_frozen)
        pts = list(patrol_points) if patrol_points else [(x, y)]
        if not pts:
            pts = [(x, y)]
        self._patrol_points = pts
        self._patrol_index = 0
        self._sentry_state = SENTRY_PATROL
        self._alert_until = 0
        self._alarm_config = alarm_config
        self.exploded = False

    def update_movement(self, player_rect, wall_rects):
        if self.is_attacking_blocking_movement():
            return
        now = pygame.time.get_ticks()
        if self._sentry_state == SENTRY_PATROL:
            self._patrol_step(wall_rects)
            if player_rect is not None and self._player_in_sight(player_rect):
                self._enter_alert(now)
        elif self._sentry_state == SENTRY_ALERT:
            if now >= self._alert_until:
                self._sentry_state = SENTRY_CHASE
        elif self._sentry_state == SENTRY_CHASE:
            self._chase_step(player_rect, wall_rects)
        # ARM and EXPLODE are driven by the attack state machine; movement is
        # halted via is_attacking_blocking_movement().

    def _patrol_step(self, wall_rects):
        if not self._patrol_points:
            return
        target = self._patrol_points[self._patrol_index]
        dx = target[0] - self.rect.centerx
        dy = target[1] - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist <= SENTRY_PATROL_SPEED:
            self.rect.center = target
            self._patrol_index = (self._patrol_index + 1) % len(self._patrol_points)
            return
        nx = dx / dist
        ny = dy / dist
        self._move_axis(nx * SENTRY_PATROL_SPEED, 0, wall_rects)
        self._move_axis(0, ny * SENTRY_PATROL_SPEED, wall_rects)

    def _chase_step(self, player_rect, wall_rects):
        if player_rect is None:
            return
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        nx = dx / dist
        ny = dy / dist
        self._move_axis(nx * SENTRY_CHASE_SPEED, 0, wall_rects)
        self._move_axis(0, ny * SENTRY_CHASE_SPEED, wall_rects)

    def _player_in_sight(self, player_rect):
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return (dx * dx + dy * dy) <= (SENTRY_SIGHT_RADIUS * SENTRY_SIGHT_RADIUS)

    def _enter_alert(self, now_ticks):
        self._sentry_state = SENTRY_ALERT
        self._alert_until = now_ticks + SENTRY_ALERT_FLASH_MS
        self._telegraph_active = True
        if self._alarm_config is not None:
            self._alarm_config["triggered"] = True

    def _can_begin_attack(self, player_rect):
        if self._sentry_state != SENTRY_CHASE or player_rect is None:
            return False
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return (dx * dx + dy * dy) <= (SENTRY_DETONATE_RADIUS * SENTRY_DETONATE_RADIUS)

    def _on_telegraph_start(self, _player_rect, _now_ticks):
        self._sentry_state = SENTRY_ARM

    def _on_strike_start(self, _player_rect, _now_ticks):
        self._sentry_state = SENTRY_EXPLODE
        self.exploded = True

    def _on_strike_end(self, _now_ticks):
        # Sentry dies after detonation.
        self.kill()

    def _hitbox_geometry(self):
        size = SENTRY_EXPLOSION_RADIUS * 2
        rect = pygame.Rect(0, 0, size, size)
        rect.center = self.rect.center
        return (rect,)


ENEMY_CLASSES = [
    PatrolEnemy,
    RandomEnemy,
    ChaserEnemy,
    PulsatorEnemy,
    LauncherEnemy,
]
# SentryEnemy is intentionally excluded — it is spawned only by stealth-room
# objective configs, not by the random-palette pool.
