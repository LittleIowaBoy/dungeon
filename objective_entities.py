"""Objective-specific room entities such as altar anchors."""

import pygame

from objective_metadata import get_altar_variant
from sprites import make_rect_surface


_PLATE_COLOR = (90, 205, 230)
_PLATE_ACTIVE_COLOR = (245, 225, 120)
_ALARM_IDLE_COLOR = (120, 230, 190)
_ALARM_TRIGGERED_COLOR = (255, 110, 90)
_HOLDOUT_IDLE_COLOR = (245, 210, 120)
_HOLDOUT_ACTIVE_COLOR = (255, 245, 180)
_ALTAR_SHIELDED_COLOR = (120, 180, 255)
_ESCORT_COLOR = (245, 220, 140)
_ESCORT_DAMAGED_COLOR = (205, 130, 120)
_CARRIER_COLOR = (250, 170, 80)
_CARRIER_WAITING_COLOR = (255, 215, 120)


class AltarAnchor(pygame.sprite.Sprite):
    """Damageable ritual anchor that persists through room revisits."""

    SIZE = 26

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._variant = get_altar_variant(config.get("variant_id"))
        self.max_hp = config["max_hp"]
        self.current_hp = config["current_hp"]
        self.pulse_radius = config.get("pulse_radius", self._variant["pulse_radius"])
        self.pulse_damage = config.get("pulse_damage", self._variant["pulse_damage"])
        self.pulse_cycle_ms = config.get("pulse_cycle_ms", self._variant["pulse_cycle_ms"])
        self.pulse_active_ms = config.get("pulse_active_ms", self._variant["pulse_active_ms"])
        self.pulse_offset_ms = config.get("pulse_offset_ms", 0)
        self.pulse_active = False
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        if self._config.get("destroyed"):
            self.pulse_active = False
            return
        elapsed = max(0, now_ticks + self.pulse_offset_ms)
        self.pulse_active = elapsed % self.pulse_cycle_ms < self.pulse_active_ms
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def apply_player_pressure(self, player):
        if not self.pulse_active or self._config.get("destroyed"):
            return False

        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        if dx * dx + dy * dy > self.pulse_radius * self.pulse_radius:
            return False

        player.take_damage(self.pulse_damage)
        return True

    def draw_overlay(self, surface):
        if not self.pulse_active or self._config.get("destroyed"):
            return
        pygame.draw.circle(
            surface,
            self._variant["pulse_color"],
            self.rect.center,
            self.pulse_radius,
            2,
        )

    def take_damage(self, amount):
        if self._config.get("destroyed"):
            return False
        if self._config.get("invulnerable"):
            return False

        self.current_hp = max(0, self.current_hp - amount)
        self._config["current_hp"] = self.current_hp

        if self.current_hp <= 0:
            self._config["destroyed"] = True
            self.kill()
            return True

        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)
        return False

    def _build_image(self):
        if self._config.get("invulnerable") and not self.pulse_active:
            color = _ALTAR_SHIELDED_COLOR
        elif self.pulse_active:
            color = self._variant["pulse_color"]
        elif self.current_hp >= self.max_hp:
            color = self._variant["base_color"]
        else:
            color = self._variant["damaged_color"]
        return make_rect_surface(self.SIZE, self.SIZE, color)


class PressurePlate(pygame.sprite.Sprite):
    """Objective plate that permanently activates once the player stands on it."""

    SIZE = 22

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        del now_ticks
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def sync_player_overlap(self, player):
        if self._config.get("activated"):
            return False
        padding = self._config.get("trigger_padding", 10)
        if not player.rect.colliderect(self.rect.inflate(padding, padding)):
            return False

        self._config["activated"] = True
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        if not self._config.get("activated"):
            return
        pygame.draw.circle(surface, _PLATE_ACTIVE_COLOR, self.rect.center, self.SIZE // 2 + 3, 1)

    def _build_image(self):
        color = _PLATE_ACTIVE_COLOR if self._config.get("activated") else _PLATE_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)


class AlarmBeacon(pygame.sprite.Sprite):
    """Visible alarm ward that trips if the player enters its radius."""

    SIZE = 20

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        del now_ticks
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def sync_player_overlap(self, player):
        if self._config.get("triggered"):
            return False

        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        radius = self._config.get("radius", 36)
        if dx * dx + dy * dy > radius * radius:
            return False

        self._config["triggered"] = True
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        color = _ALARM_TRIGGERED_COLOR if self._config.get("triggered") else _ALARM_IDLE_COLOR
        pygame.draw.circle(
            surface,
            color,
            self.rect.center,
            self._config.get("radius", 36),
            2,
        )

    def _build_image(self):
        color = _ALARM_TRIGGERED_COLOR if self._config.get("triggered") else _ALARM_IDLE_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)


class HoldoutZone(pygame.sprite.Sprite):
    """Objective zone that tracks whether the player is holding contested ground."""

    SIZE = 18

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        del now_ticks
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def sync_player_overlap(self, player):
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        radius = self._config.get("radius", 96)
        occupied = dx * dx + dy * dy <= radius * radius
        changed = occupied != self._config.get("occupied", False)
        self._config["occupied"] = occupied
        if changed:
            self.image = self._build_image()
            self.rect = self.image.get_rect(center=self.rect.center)
        return changed

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        color = _HOLDOUT_ACTIVE_COLOR if self._config.get("occupied") else _HOLDOUT_IDLE_COLOR
        pygame.draw.circle(surface, color, self.rect.center, self._config.get("radius", 96), 2)

    def _build_image(self):
        color = _HOLDOUT_ACTIVE_COLOR if self._config.get("occupied") else _HOLDOUT_IDLE_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)


class EscortNPC(pygame.sprite.Sprite):
    """Friendly objective actor that moves through the room and can be attacked by enemies."""

    SIZE = 24

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        del now_ticks
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def update_behavior(self, *, player, wall_rects, portal_pos, allow_advance):
        if self._config.get("destroyed") or self._config.get("reached_exit"):
            return False

        waiting_for_clearance = self._config.get("requires_safe_path") and not allow_advance
        self._config["waiting_for_clearance"] = bool(waiting_for_clearance)
        if waiting_for_clearance:
            return False

        guide_radius = self._config.get("guide_radius", 96)
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        player_distance_sq = dx * dx + dy * dy
        if player_distance_sq > guide_radius * guide_radius:
            target_pos = player.rect.center
        else:
            target_pos = portal_pos

        self._move_toward(target_pos, wall_rects)
        self._config["pos"] = self.rect.center

        exit_radius = self._config.get("exit_radius", 24)
        ex = portal_pos[0] - self.rect.centerx
        ey = portal_pos[1] - self.rect.centery
        if ex * ex + ey * ey <= exit_radius * exit_radius:
            self.rect.center = portal_pos
            self._config["pos"] = portal_pos
            self._config["reached_exit"] = True
            return True
        return False

    def apply_enemy_contact(self, enemy_group, now_ticks):
        if self._config.get("destroyed") or self._config.get("reached_exit"):
            return False
        if now_ticks < self._config.get("damage_cooldown_until", 0):
            return False

        for enemy in enemy_group:
            if not self.rect.colliderect(enemy.rect.inflate(6, 6)):
                continue

            current_hp = max(0, self._config["current_hp"] - enemy.damage)
            self._config["current_hp"] = current_hp
            cooldown_ms = self._config.get("damage_cooldown_ms", 500)
            self._config["damage_cooldown_until"] = now_ticks + cooldown_ms

            if current_hp <= 0:
                self._config["destroyed"] = True
                self.kill()
                return True

            self.image = self._build_image()
            self.rect = self.image.get_rect(center=self.rect.center)
            return True
        return False

    def enemy_target_rect(self):
        if self._config.get("destroyed") or self._config.get("reached_exit"):
            return None
        return self.rect

    def take_damage(self, amount):
        del amount
        return False

    def _build_image(self):
        if self._config.get("destroyed"):
            color = _ESCORT_DAMAGED_COLOR
        elif self._config.get("requires_safe_path") and self._config.get("waiting_for_clearance"):
            color = _CARRIER_WAITING_COLOR
        elif self._config.get("requires_safe_path"):
            color = _CARRIER_COLOR
        elif self._config.get("current_hp") < self._config.get("max_hp"):
            color = _ESCORT_DAMAGED_COLOR
        else:
            color = _ESCORT_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)

    def _move_toward(self, target_pos, wall_rects):
        tx, ty = target_pos
        dx = tx - self.rect.centerx
        dy = ty - self.rect.centery
        distance = (dx * dx + dy * dy) ** 0.5
        if distance == 0:
            return

        speed = self._config.get("speed", 1.1)
        move_dx = (dx / distance) * speed
        move_dy = (dy / distance) * speed
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