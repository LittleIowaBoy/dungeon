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
    GOLEM_HP, GOLEM_SPEED, GOLEM_COLOR, GOLEM_SIZE,
    GOLEM_MELEE_TRIGGER, GOLEM_THROW_RANGE, GOLEM_SLAM_RADIUS,
    GOLEM_SLAM_DAMAGE, GOLEM_SLAM_WINDUP_MS, GOLEM_SLAM_STRIKE_MS,
    GOLEM_SLAM_COOLDOWN_MS, GOLEM_THROW_WINDUP_MS, GOLEM_THROW_STRIKE_MS,
    GOLEM_THROW_COOLDOWN_MS, GOLEM_BOULDER_SPEED, GOLEM_BOULDER_RANGE,
    GOLEM_BOULDER_DAMAGE, GOLEM_BOULDER_SIZE,
    GOLEM_ENRAGE_TRIGGER_MIN, GOLEM_ENRAGE_TRIGGER_MAX, GOLEM_ENRAGE_DAMAGE,
    GOLEM_ENRAGE_WINDUP_MS, GOLEM_ENRAGE_STRIKE_MS, GOLEM_ENRAGE_COOLDOWN_MS,
    GOLEM_ENRAGE_DASH_SPEED,
    GOLEM_SHARD_HP, GOLEM_SHARD_SPEED, GOLEM_SHARD_COLOR, GOLEM_SHARD_SIZE,
    GOLEM_SHARD_ATTACK_TRIGGER, GOLEM_SHARD_ATTACK_SIZE,
    GOLEM_SHARD_ATTACK_OFFSET, GOLEM_SHARD_ATTACK_DAMAGE,
    GOLEM_SHARD_ATTACK_WINDUP_MS, GOLEM_SHARD_ATTACK_STRIKE_MS,
    GOLEM_SHARD_ATTACK_COOLDOWN_MS,
    DROP_CHANCE,
    COLOR_WATER_SPIRIT,
    WATER_SPIRIT_HP,
    WATER_SPIRIT_ATTACK_WINDUP_MS,
    WATER_SPIRIT_ATTACK_STRIKE_MS,
    WATER_SPIRIT_ATTACK_COOLDOWN_MS,
    WATER_SPIRIT_ATTACK_TRIGGER,
    WATER_SPIRIT_PROJECTILE_SPEED,
    WATER_SPIRIT_PROJECTILE_RANGE,
    WATER_SPIRIT_PROJECTILE_DAMAGE,
    WATER_SPIRIT_PROJECTILE_SIZE,
    WATER_SPIRIT_ANCHOR_INTERVAL_MS,
    WATER_SPIRIT_ANCHOR_DURATION_MS,
    WATER_SPIRIT_ANCHOR_HP,
    COLOR_WATER_SPIRIT_ANCHORED,
    ICE_CRYSTAL_HP, COLOR_ICE_CRYSTAL, COLOR_ICE_CRYSTAL_PULSE,
    ICE_CRYSTAL_SIZE,
    ICE_CRYSTAL_PULSE_RADIUS, ICE_CRYSTAL_PULSE_INTERVAL_MS,
    ICE_CRYSTAL_PULSE_WINDUP_MS, ICE_CRYSTAL_PULSE_STRIKE_MS,
    ICE_CRYSTAL_PULSE_COOLDOWN_MS, ICE_CRYSTAL_FREEZE_DURATION_MS,
    TIDE_LORD_HP, TIDE_LORD_SPEED, COLOR_TIDE_LORD, TIDE_LORD_SIZE,
    TIDE_LORD_CRASH_RANGE, TIDE_LORD_CRASH_RADIUS, TIDE_LORD_CRASH_DAMAGE,
    TIDE_LORD_CRASH_WINDUP_MS, TIDE_LORD_CRASH_STRIKE_MS, TIDE_LORD_CRASH_COOLDOWN_MS,
    TIDE_LORD_SURGE_RANGE, TIDE_LORD_SURGE_WINDUP_MS, TIDE_LORD_SURGE_STRIKE_MS,
    TIDE_LORD_SURGE_COOLDOWN_MS, TIDE_LORD_SURGE_SPREAD_DEG,
    TIDE_LORD_SURGE_SHOTS_P1, TIDE_LORD_SURGE_SHOTS_P2,
    TIDE_LORD_PROJECTILE_SPEED, TIDE_LORD_PROJECTILE_RANGE,
    TIDE_LORD_PROJECTILE_DAMAGE, TIDE_LORD_PROJECTILE_SIZE,
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
    attack_damage_type = "blunt"  # F2: base default; subclasses override per archetype

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

    def roll_drop(self, progress=None):
        """Return an Item instance (or None) at this enemy's position."""
        import armor_rules
        drop_chance = armor_rules.apply_magic_find(DROP_CHANCE, progress)
        if random.random() > drop_chance:
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
    attack_damage_type = "slash"

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
    attack_damage_type = "pierce"

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
    attack_damage_type = "slash"

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
    attack_damage_type = "lightning"

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
    damage_type = "pierce"

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
    attack_damage_type = "pierce"

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
    attack_damage_type = "blunt"

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


# ── Golem mini-boss + GolemShard minion (Earth biome finale) ─

# Golem attack identifiers — selected per-attack in :meth:`Golem._can_begin_attack`
# based on player distance + phase, then committed in
# :meth:`_on_telegraph_start` so the strike geometry matches the picked move.
_GOLEM_ATTACK_NONE   = ""
_GOLEM_ATTACK_SLAM   = "slam"
_GOLEM_ATTACK_THROW  = "throw"
_GOLEM_ATTACK_ENRAGE = "enrage"


class GolemBoulderProjectile(pygame.sprite.Sprite):
    """Heavy boulder hurled by :class:`Golem`'s ``throw`` attack.

    Mirrors :class:`LauncherProjectile`: linear motion, despawns on wall
    contact or after travelling :data:`GOLEM_BOULDER_RANGE` pixels.
    Damage is delivered by :func:`enemy_attack_rules.apply_launcher_projectiles`.
    """

    SIZE = GOLEM_BOULDER_SIZE
    damage = GOLEM_BOULDER_DAMAGE
    damage_type = "blunt"

    def __init__(self, x, y, vx, vy):
        super().__init__()
        self.image = make_rect_surface(self.SIZE, self.SIZE, GOLEM_COLOR)
        self.rect = self.image.get_rect(center=(int(x), int(y)))
        self._vx = float(vx)
        self._vy = float(vy)
        self._distance_traveled = 0.0

    def update(self, *_args, **_kwargs):
        self.rect.x += self._vx
        self.rect.y += self._vy
        self._distance_traveled += math.hypot(self._vx, self._vy)
        if self._distance_traveled >= GOLEM_BOULDER_RANGE:
            self.kill()

    def collide_walls(self, wall_rects):
        for wall in wall_rects:
            if self.rect.colliderect(wall):
                self.kill()
                return True
        return False


class Golem(Enemy):
    """High-HP Earth-biome mini-boss with three telegraphed attacks.

    Attack selection is distance-gated:

    * Player within :data:`GOLEM_MELEE_TRIGGER` → ``slam`` (AOE circle).
    * Player within :data:`GOLEM_THROW_RANGE`  → ``throw`` (boulder
      projectile aimed at the player's position at telegraph start).
    * Player in mid-range AND ``phase_2`` is True → ``enrage`` charge
      (brief dash with a swept hitbox).

    Phase 2 is set externally by :class:`BossController` when the
    Golem's HP crosses 50%.  The Golem itself never reads HP — it only
    consults the flag, keeping the controller fully in charge of when
    the new move unlocks.
    """

    hp = GOLEM_HP
    speed = GOLEM_SPEED
    damage = 0
    color = GOLEM_COLOR

    # Per-attack timing varies; the values here are placeholders and get
    # overwritten in ``_on_telegraph_start`` before the state machine
    # reads them.  Keeping defaults non-zero ensures the base class never
    # divides by zero or skips a transition if telegraph_start fails.
    attack_damage     = 0
    attack_windup_ms  = GOLEM_SLAM_WINDUP_MS
    attack_strike_ms  = GOLEM_SLAM_STRIKE_MS
    attack_cooldown_ms = GOLEM_SLAM_COOLDOWN_MS
    attack_damage_type = "blunt"

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        # Override the base rect/image with the larger boss sprite.
        self.image = make_rect_surface(GOLEM_SIZE, GOLEM_SIZE, self.color)
        self._base_image = self.image
        self.rect = self.image.get_rect(center=(x, y))
        self.phase_2 = False
        self._pending_attack = _GOLEM_ATTACK_NONE
        self._committed_attack = _GOLEM_ATTACK_NONE
        self._throw_dir = (1.0, 0.0)
        self._enrage_dir = (1.0, 0.0)
        self._enrage_dash_until = 0
        self.emitted_projectiles: list[GolemBoulderProjectile] = []

    # ── movement ────────────────────────────────────────
    def update_movement(self, player_rect, wall_rects):
        # During an enrage strike, charge in the locked direction.
        now = pygame.time.get_ticks()
        if self._committed_attack == _GOLEM_ATTACK_ENRAGE and now < self._enrage_dash_until:
            ex, ey = self._enrage_dir
            speed = GOLEM_ENRAGE_DASH_SPEED
            self._move_axis(ex * speed, 0, wall_rects)
            self._move_axis(0, ey * speed, wall_rects)
            return
        if self.is_attacking_blocking_movement():
            return
        if player_rect is None:
            return
        # Slow trudge toward the player.
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        nx, ny = dx / dist, dy / dist
        self._move_axis(nx * self.speed, 0, wall_rects)
        self._move_axis(0, ny * self.speed, wall_rects)

    # ── attack selection ────────────────────────────────
    def _player_distance(self, player_rect):
        if player_rect is None:
            return float("inf")
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return math.hypot(dx, dy)

    def _can_begin_attack(self, player_rect):
        dist = self._player_distance(player_rect)
        if dist == float("inf"):
            return False
        if dist <= GOLEM_MELEE_TRIGGER:
            self._pending_attack = _GOLEM_ATTACK_SLAM
            return True
        if (
            self.phase_2
            and GOLEM_ENRAGE_TRIGGER_MIN <= dist <= GOLEM_ENRAGE_TRIGGER_MAX
        ):
            self._pending_attack = _GOLEM_ATTACK_ENRAGE
            return True
        if dist <= GOLEM_THROW_RANGE:
            self._pending_attack = _GOLEM_ATTACK_THROW
            return True
        return False

    def _on_telegraph_start(self, player_rect, _now_ticks):
        kind = self._pending_attack
        self._committed_attack = kind
        if kind == _GOLEM_ATTACK_SLAM:
            self.attack_windup_ms   = GOLEM_SLAM_WINDUP_MS
            self.attack_strike_ms   = GOLEM_SLAM_STRIKE_MS
            self.attack_cooldown_ms = GOLEM_SLAM_COOLDOWN_MS
        elif kind == _GOLEM_ATTACK_THROW:
            self.attack_windup_ms   = GOLEM_THROW_WINDUP_MS
            self.attack_strike_ms   = GOLEM_THROW_STRIKE_MS
            self.attack_cooldown_ms = GOLEM_THROW_COOLDOWN_MS
            if player_rect is not None:
                dx = player_rect.centerx - self.rect.centerx
                dy = player_rect.centery - self.rect.centery
                d = math.hypot(dx, dy) or 1.0
                self._throw_dir = (dx / d, dy / d)
        elif kind == _GOLEM_ATTACK_ENRAGE:
            self.attack_windup_ms   = GOLEM_ENRAGE_WINDUP_MS
            self.attack_strike_ms   = GOLEM_ENRAGE_STRIKE_MS
            self.attack_cooldown_ms = GOLEM_ENRAGE_COOLDOWN_MS
            if player_rect is not None:
                dx = player_rect.centerx - self.rect.centerx
                dy = player_rect.centery - self.rect.centery
                d = math.hypot(dx, dy) or 1.0
                self._enrage_dir = (dx / d, dy / d)
        # The base state machine snapshots the new attack_state_until
        # value after this hook returns by reading attack_windup_ms; but
        # by the time we land here the timer has already been computed
        # using the previous values.  Patch it for the freshly-picked
        # attack so the picked windup actually applies.
        self._attack_state_until = _now_ticks + max(1, self.attack_windup_ms)

    def _on_strike_start(self, player_rect, now_ticks):
        # Re-snap the strike duration to the picked move.
        self._attack_state_until = now_ticks + max(1, self.attack_strike_ms)
        if self._committed_attack == _GOLEM_ATTACK_THROW:
            fx, fy = self._throw_dir
            speed = GOLEM_BOULDER_SPEED
            proj = GolemBoulderProjectile(
                self.rect.centerx, self.rect.centery,
                fx * speed, fy * speed,
            )
            self.emitted_projectiles.append(proj)
        elif self._committed_attack == _GOLEM_ATTACK_ENRAGE:
            self._enrage_dash_until = now_ticks + max(1, self.attack_strike_ms)

    def _on_strike_end(self, _now_ticks):
        # Re-snap the cooldown for the committed move.
        self._attack_state_until = _now_ticks + max(0, self.attack_cooldown_ms)
        self._committed_attack = _GOLEM_ATTACK_NONE
        self._pending_attack = _GOLEM_ATTACK_NONE

    def _hitbox_geometry(self):
        # Slam is the only attack that delivers damage via the standard
        # active_hitboxes path; throw uses a projectile (handled by the
        # launcher-projectile pipeline) and enrage delivers damage via a
        # dash-swept body collider tracked separately on strike.
        if self._committed_attack == _GOLEM_ATTACK_SLAM:
            self.attack_damage = GOLEM_SLAM_DAMAGE
            size = GOLEM_SLAM_RADIUS * 2
            rect = pygame.Rect(0, 0, size, size)
            rect.center = self.rect.center
            return (rect,)
        if self._committed_attack == _GOLEM_ATTACK_ENRAGE:
            self.attack_damage = GOLEM_ENRAGE_DAMAGE
            # The enrage hitbox is the Golem's body itself — a moving
            # collider during the dash.  Returning the body rect lets
            # the standard apply_enemy_attacks pipeline handle damage.
            return (self.rect.copy(),)
        return ()

    def consume_emitted_projectiles(self):
        out = self.emitted_projectiles
        self.emitted_projectiles = []
        return out


class GolemShard(Enemy):
    """Small fast melee minion summoned in waves by the Golem encounter.

    Functionally a stripped-down :class:`ChaserEnemy`: always chases the
    nearest target (no chase-state gating), strikes a small forward
    rect, low HP/damage so 4-6 simultaneous shards stay readable.
    """

    hp = GOLEM_SHARD_HP
    speed = GOLEM_SHARD_SPEED
    damage = GOLEM_SHARD_ATTACK_DAMAGE
    color = GOLEM_SHARD_COLOR

    attack_damage = GOLEM_SHARD_ATTACK_DAMAGE
    attack_windup_ms = GOLEM_SHARD_ATTACK_WINDUP_MS
    attack_strike_ms = GOLEM_SHARD_ATTACK_STRIKE_MS
    attack_cooldown_ms = GOLEM_SHARD_ATTACK_COOLDOWN_MS
    attack_damage_type = "slash"

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self.image = make_rect_surface(GOLEM_SHARD_SIZE, GOLEM_SHARD_SIZE, self.color)
        self._base_image = self.image
        self.rect = self.image.get_rect(center=(x, y))
        self._facing = (1, 0)
        self._strike_facing = (1, 0)

    def update_movement(self, player_rect, wall_rects):
        if self.is_attacking_blocking_movement():
            return
        if player_rect is None:
            return
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        nx, ny = dx / dist, dy / dist
        if abs(nx) >= abs(ny):
            self._facing = (1 if nx >= 0 else -1, 0)
        else:
            self._facing = (0, 1 if ny >= 0 else -1)
        self._move_axis(nx * self.speed, 0, wall_rects)
        self._move_axis(0, ny * self.speed, wall_rects)

    def _can_begin_attack(self, player_rect):
        if player_rect is None:
            return False
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return (dx * dx + dy * dy) <= (
            GOLEM_SHARD_ATTACK_TRIGGER * GOLEM_SHARD_ATTACK_TRIGGER
        )

    def _on_telegraph_start(self, _player_rect, _now_ticks):
        self._strike_facing = self._facing

    def _hitbox_geometry(self):
        fx, fy = self._strike_facing
        size = GOLEM_SHARD_ATTACK_SIZE
        offset = GOLEM_SHARD_ATTACK_OFFSET + size // 2
        cx = self.rect.centerx + fx * offset
        cy = self.rect.centery + fy * offset
        rect = pygame.Rect(0, 0, size, size)
        rect.center = (cx, cy)
        return (rect,)


# ── WaterSpiritEnemy ────────────────────────────────────
class WaterSpiritProjectile(pygame.sprite.Sprite):
    """Slow orb fired by a WaterSpiritEnemy toward the player.

    Behaves identically to LauncherProjectile but uses the spirit's colour
    and range settings.  Damage is delivered by the launcher-projectile
    pipeline in enemy_attack_rules.
    """

    SIZE = WATER_SPIRIT_PROJECTILE_SIZE
    damage = WATER_SPIRIT_PROJECTILE_DAMAGE
    damage_type = "poison"

    def __init__(self, x, y, vx, vy):
        super().__init__()
        self.image = make_rect_surface(self.SIZE, self.SIZE, COLOR_WATER_SPIRIT)
        self.rect = self.image.get_rect(center=(int(x), int(y)))
        self._vx = float(vx)
        self._vy = float(vy)
        self._distance_traveled = 0.0

    def update(self, *_args, **_kwargs):
        self.rect.x += self._vx
        self.rect.y += self._vy
        self._distance_traveled += math.hypot(self._vx, self._vy)
        if self._distance_traveled >= WATER_SPIRIT_PROJECTILE_RANGE:
            self.kill()

    def collide_walls(self, wall_rects):
        for wall in wall_rects:
            if self.rect.colliderect(wall):
                self.kill()
                return True
        return False


class WaterSpiritEnemy(Enemy):
    """Stationary water-spirit guardian placed at pool centres or summoned in waves.

    By default (``immortal=True``) the spirit ignores all incoming damage and
    cannot be killed; this is used for pool guardians in water_spirit_room.
    Wave-spawned spirits in the Tide Lord arena are created with
    ``immortal=False`` so they contribute to the clear_enemies objective.

    The spirit never moves; it fires a WaterSpiritProjectile toward the player
    whenever they are within WATER_SPIRIT_ATTACK_TRIGGER range.  Room-placed
    spirits are excluded from ENEMY_CLASSES (never randomly spawned).
    """

    hp = WATER_SPIRIT_HP
    speed = 0
    damage = 0
    color = COLOR_WATER_SPIRIT
    immortal = True   # class-level default; wave-spawned copies set immortal=False

    attack_damage = 0   # damage delivered by projectile, not hitbox
    attack_windup_ms = WATER_SPIRIT_ATTACK_WINDUP_MS
    attack_strike_ms = WATER_SPIRIT_ATTACK_STRIKE_MS
    attack_cooldown_ms = WATER_SPIRIT_ATTACK_COOLDOWN_MS
    attack_damage_type = "poison"

    def __init__(self, x, y, *, is_frozen=False, immortal=True):
        super().__init__(x, y, is_frozen=is_frozen)
        self.immortal = immortal
        self._fire_dir = (1.0, 0.0)
        self.emitted_projectiles: list[WaterSpiritProjectile] = []
        # Anchor cycle: pool spirits (immortal=True at birth) periodically
        # become vulnerable for WATER_SPIRIT_ANCHOR_DURATION_MS so the player
        # has a timing window to deal damage.  Wave-spawned mortal spirits
        # (_can_anchor=False) are already permanently mortal and skip this.
        self._can_anchor = bool(immortal)
        self._next_anchor_at: int = 0   # 0 = not initialised yet
        self._anchor_ends_at: int = 0

    def take_damage(self, amount):
        """Invulnerable when immortal=True; mortal wave-spirits use normal damage."""
        if self.immortal:
            return
        super().take_damage(amount)

    def update_movement(self, _player_rect, _wall_rects):
        """Spirits are stationary — no movement logic."""

    def _can_begin_attack(self, player_rect):
        if player_rect is None:
            return False
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return (dx * dx + dy * dy) <= (WATER_SPIRIT_ATTACK_TRIGGER * WATER_SPIRIT_ATTACK_TRIGGER)

    def _on_telegraph_start(self, player_rect, _now_ticks):
        if player_rect is None:
            return
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy) or 1.0
        self._fire_dir = (dx / dist, dy / dist)

    def _on_strike_start(self, _player_rect, _now_ticks):
        fx, fy = self._fire_dir
        speed = WATER_SPIRIT_PROJECTILE_SPEED
        proj = WaterSpiritProjectile(
            self.rect.centerx, self.rect.centery, fx * speed, fy * speed,
        )
        self.emitted_projectiles.append(proj)

    def consume_emitted_projectiles(self):
        out = self.emitted_projectiles
        self.emitted_projectiles = []
        return out

    def update_anchor_cycle(self, now_ticks):
        """Advance the immortal ↔ vulnerable anchor cycle.

        Called once per frame by the runtime for every WaterSpiritEnemy.
        Wave-spawned spirits (``_can_anchor=False``) are permanently mortal
        and skip this method immediately.

        States:
        - **Immortal (idle)** — spirit is invulnerable.  At ``_next_anchor_at``
          it switches to the anchor (vulnerable) state, gains
          ``WATER_SPIRIT_ANCHOR_HP`` HP, and its tint changes to
          ``COLOR_WATER_SPIRIT_ANCHORED``.
        - **Anchor (vulnerable)** — spirit is mortal and can be burst down.
          At ``_anchor_ends_at`` it returns to immortal, HP is restored to 1,
          and the next anchor window is scheduled.
        """
        if not self._can_anchor:
            return
        # Deferred initialisation: set the first window on the first real tick.
        if self._next_anchor_at == 0:
            self._next_anchor_at = now_ticks + WATER_SPIRIT_ANCHOR_INTERVAL_MS
            return
        if self.immortal:
            # Check whether it is time to open the vulnerability window.
            if now_ticks >= self._next_anchor_at:
                self.immortal = False
                self.current_hp = WATER_SPIRIT_ANCHOR_HP
                self._anchor_ends_at = now_ticks + WATER_SPIRIT_ANCHOR_DURATION_MS
                self.image = make_rect_surface(ENEMY_SIZE, ENEMY_SIZE, COLOR_WATER_SPIRIT_ANCHORED)
        else:
            # In anchor window: check for expiry.
            if self._anchor_ends_at > 0 and now_ticks >= self._anchor_ends_at:
                self.immortal = True
                self.current_hp = self.hp  # restore to WATER_SPIRIT_HP (= 1)
                self._anchor_ends_at = 0
                self._next_anchor_at = now_ticks + WATER_SPIRIT_ANCHOR_INTERVAL_MS
                self.image = self._base_image


# ── Ice Crystal (ice_crystal_room) ────────────────────────────────────────
class IceCrystalEnemy(Enemy):
    """Stationary ice-crystal pillar placed in the Ice Crystal Room.

    The crystal never moves and is immortal (cannot be destroyed by normal
    attacks).  Every :data:`ICE_CRYSTAL_PULSE_INTERVAL_MS` it telegraphs
    a freeze blast — the attack-state machine drives the windup / strike /
    cooldown cycle.

    Unlike :class:`WaterSpiritEnemy`, this enemy emits *freeze pulses*
    rather than projectiles.  The strike event is recorded via
    :attr:`_freeze_pulse_pending`; :meth:`consume_freeze_pulses` lets
    the runtime apply :data:`FROZEN` status to nearby targets.
    """

    hp = ICE_CRYSTAL_HP
    speed = 0
    damage = 0
    color = COLOR_ICE_CRYSTAL
    immortal = True

    # Use the attack-state machine for the windup/telegraph animation.
    attack_damage = 0
    attack_windup_ms = ICE_CRYSTAL_PULSE_WINDUP_MS
    attack_strike_ms = ICE_CRYSTAL_PULSE_STRIKE_MS
    attack_cooldown_ms = ICE_CRYSTAL_PULSE_COOLDOWN_MS
    attack_damage_type = "ice"

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self._freeze_pulse_pending = False
        self._next_pulse_at: int = ICE_CRYSTAL_PULSE_INTERVAL_MS  # deferred init

    def take_damage(self, amount):
        """Crystals are immortal room fixtures."""

    def update_movement(self, _player_rect, _wall_rects):
        """Crystals are stationary."""

    def _can_begin_attack(self, player_rect):
        """Always pulse on schedule, regardless of player distance."""
        return True

    def _on_telegraph_start(self, player_rect, now_ticks):
        """Shift to brighter tint during windup so players have a warning."""
        self.image = make_rect_surface(
            ICE_CRYSTAL_SIZE, ICE_CRYSTAL_SIZE, COLOR_ICE_CRYSTAL_PULSE
        )

    def _on_strike_start(self, player_rect, now_ticks):
        """Mark a freeze pulse for the runtime to read and dispatch."""
        self._freeze_pulse_pending = True
        # Revert visual at strike start.
        self.image = self._base_image

    def consume_freeze_pulses(self):
        """Return True (and clear the flag) if a freeze pulse fired this frame."""
        if self._freeze_pulse_pending:
            self._freeze_pulse_pending = False
            return True
        return False

    def update_attack_state(self, player_rect, now_ticks):
        """Gate the first pulse behind the initial interval delay.

        The parent attack-state machine would fire immediately on the
        first frame (because ``_can_begin_attack`` always returns True).
        Instead, we defer the first attack until ``_next_pulse_at`` so
        crystals don't fire the instant the player enters the room.
        """
        # Deferred init: _next_pulse_at holds an offset until the first tick.
        if self._next_pulse_at > 0 and self._next_pulse_at < 100_000:
            # First real call — promote to absolute timestamp.
            self._next_pulse_at = now_ticks + self._next_pulse_at
        if now_ticks < self._next_pulse_at:
            return
        # Hand off to the parent state machine for the rest of the cycle.
        if self._attack_state == ATTACK_IDLE:
            self._next_pulse_at = 0  # clear; parent machine owns timing now
        super().update_attack_state(player_rect, now_ticks)


# ── Tide Lord mini-boss (water_tide_lord_arena) ────────────────────────────
_TIDE_LORD_ATTACK_NONE  = "none"
_TIDE_LORD_ATTACK_CRASH = "crash"
_TIDE_LORD_ATTACK_SURGE = "surge"


class TideLordProjectile(pygame.sprite.Sprite):
    """Water projectile fired in a fan by :class:`TideLord` during Wave Surge.

    Behaves identically to :class:`LauncherProjectile`: linear motion,
    despawns after travelling :data:`TIDE_LORD_PROJECTILE_RANGE` pixels or on
    wall contact.  Damage is delivered by the launcher-projectile pipeline.
    """

    SIZE = TIDE_LORD_PROJECTILE_SIZE
    damage = TIDE_LORD_PROJECTILE_DAMAGE
    damage_type = "ice"

    def __init__(self, x, y, vx, vy):
        super().__init__()
        self.image = make_rect_surface(self.SIZE, self.SIZE, COLOR_TIDE_LORD)
        self.rect = self.image.get_rect(center=(int(x), int(y)))
        self._vx = float(vx)
        self._vy = float(vy)
        self._distance_traveled = 0.0

    def update(self, *_args, **_kwargs):
        self.rect.x += self._vx
        self.rect.y += self._vy
        self._distance_traveled += math.hypot(self._vx, self._vy)
        if self._distance_traveled >= TIDE_LORD_PROJECTILE_RANGE:
            self.kill()

    def collide_walls(self, wall_rects):
        for wall in wall_rects:
            if self.rect.colliderect(wall):
                self.kill()
                return True
        return False


class TideLord(Enemy):
    """Water-biome mini-boss with two telegraphed attacks.

    * **Tide Crash** (player within :data:`TIDE_LORD_CRASH_RANGE`) — AOE circle
      slam centred on the boss; high damage, moderate windup.
    * **Wave Surge** (player within :data:`TIDE_LORD_SURGE_RANGE`) — fan of
      :data:`TIDE_LORD_SURGE_SHOTS_P1` water projectiles; widens to
      :data:`TIDE_LORD_SURGE_SHOTS_P2` shots when ``phase_2`` is True.

    ``phase_2`` is set externally by the :class:`~objective_entities.BossController`
    when HP drops to 50%.  Wave-spirit adds at 75/50/25 % are also managed by
    the controller (via rpg.py), not here.
    """

    hp = TIDE_LORD_HP
    speed = TIDE_LORD_SPEED
    damage = 0
    color = COLOR_TIDE_LORD

    attack_damage     = 0
    attack_windup_ms  = TIDE_LORD_CRASH_WINDUP_MS
    attack_strike_ms  = TIDE_LORD_CRASH_STRIKE_MS
    attack_cooldown_ms = TIDE_LORD_CRASH_COOLDOWN_MS
    attack_damage_type = "ice"

    def __init__(self, x, y, *, is_frozen=False):
        super().__init__(x, y, is_frozen=is_frozen)
        self.image = make_rect_surface(TIDE_LORD_SIZE, TIDE_LORD_SIZE, self.color)
        self._base_image = self.image
        self.rect = self.image.get_rect(center=(x, y))
        self.phase_2 = False
        self._pending_attack = _TIDE_LORD_ATTACK_NONE
        self._committed_attack = _TIDE_LORD_ATTACK_NONE
        self._surge_dir = (1.0, 0.0)
        self.emitted_projectiles: list[TideLordProjectile] = []

    # ── movement ────────────────────────────────────────
    def update_movement(self, player_rect, wall_rects):
        if self.is_attacking_blocking_movement():
            return
        if player_rect is None:
            return
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        nx, ny = dx / dist, dy / dist
        self._move_axis(nx * self.speed, 0, wall_rects)
        self._move_axis(0, ny * self.speed, wall_rects)

    # ── attack selection ────────────────────────────────
    def _player_dist(self, player_rect):
        if player_rect is None:
            return float("inf")
        dx = player_rect.centerx - self.rect.centerx
        dy = player_rect.centery - self.rect.centery
        return math.hypot(dx, dy)

    def _can_begin_attack(self, player_rect):
        dist = self._player_dist(player_rect)
        if dist == float("inf"):
            return False
        if dist <= TIDE_LORD_CRASH_RANGE:
            self._pending_attack = _TIDE_LORD_ATTACK_CRASH
            return True
        if dist <= TIDE_LORD_SURGE_RANGE:
            self._pending_attack = _TIDE_LORD_ATTACK_SURGE
            return True
        return False

    def _on_telegraph_start(self, player_rect, _now_ticks):
        kind = self._pending_attack
        self._committed_attack = kind
        if kind == _TIDE_LORD_ATTACK_CRASH:
            self.attack_windup_ms   = TIDE_LORD_CRASH_WINDUP_MS
            self.attack_strike_ms   = TIDE_LORD_CRASH_STRIKE_MS
            self.attack_cooldown_ms = TIDE_LORD_CRASH_COOLDOWN_MS
        elif kind == _TIDE_LORD_ATTACK_SURGE:
            self.attack_windup_ms   = TIDE_LORD_SURGE_WINDUP_MS
            self.attack_strike_ms   = TIDE_LORD_SURGE_STRIKE_MS
            self.attack_cooldown_ms = TIDE_LORD_SURGE_COOLDOWN_MS
            if player_rect is not None:
                dx = player_rect.centerx - self.rect.centerx
                dy = player_rect.centery - self.rect.centery
                d = math.hypot(dx, dy) or 1.0
                self._surge_dir = (dx / d, dy / d)
        self._attack_state_until = _now_ticks + max(1, self.attack_windup_ms)

    def _on_strike_start(self, _player_rect, now_ticks):
        self._attack_state_until = now_ticks + max(1, self.attack_strike_ms)
        if self._committed_attack == _TIDE_LORD_ATTACK_SURGE:
            shots = TIDE_LORD_SURGE_SHOTS_P2 if self.phase_2 else TIDE_LORD_SURGE_SHOTS_P1
            spread_rad = math.radians(TIDE_LORD_SURGE_SPREAD_DEG)
            fx, fy = self._surge_dir
            base_angle = math.atan2(fy, fx)
            half = (shots - 1) / 2.0
            for i in range(shots):
                angle = base_angle + spread_rad * (i - half)
                vx = math.cos(angle) * TIDE_LORD_PROJECTILE_SPEED
                vy = math.sin(angle) * TIDE_LORD_PROJECTILE_SPEED
                proj = TideLordProjectile(
                    self.rect.centerx, self.rect.centery, vx, vy
                )
                self.emitted_projectiles.append(proj)

    def _on_strike_end(self, _now_ticks):
        self._attack_state_until = _now_ticks + max(0, self.attack_cooldown_ms)
        self._committed_attack = _TIDE_LORD_ATTACK_NONE
        self._pending_attack   = _TIDE_LORD_ATTACK_NONE

    def _hitbox_geometry(self):
        if self._committed_attack == _TIDE_LORD_ATTACK_CRASH:
            self.attack_damage = TIDE_LORD_CRASH_DAMAGE
            size = TIDE_LORD_CRASH_RADIUS * 2
            rect = pygame.Rect(0, 0, size, size)
            rect.center = self.rect.center
            return (rect,)
        return ()

    def consume_emitted_projectiles(self):
        out = self.emitted_projectiles
        self.emitted_projectiles = []
        return out


ENEMY_CLASSES = [
    PatrolEnemy,
    RandomEnemy,
    ChaserEnemy,
    PulsatorEnemy,
    LauncherEnemy,
]
# SentryEnemy is intentionally excluded — it is spawned only by stealth-room
# objective configs, not by the random-palette pool.
# Golem, GolemShard, TideLord are likewise excluded; they are spawned
# exclusively by their respective boss-room builders and wave triggers.
# WaterSpiritEnemy is likewise excluded; it is placed explicitly by
# _polish_water_spirit_room() at pool centres, never by the random palette.
