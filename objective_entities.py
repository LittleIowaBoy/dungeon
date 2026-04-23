"""Objective-specific room entities such as altar anchors."""

import pygame

from objective_metadata import get_altar_variant
from sprites import make_rect_surface


_PLATE_COLOR = (90, 205, 230)
_PLATE_ACTIVE_COLOR = (245, 225, 120)
_PLATE_PRIMED_COLOR = (170, 200, 255)
_PLATE_TARGET_COLOR = (255, 245, 170)
_PLATE_PENALTY_RESET_COLOR = (255, 120, 110)
_PLATE_PENALTY_STALL_COLOR = (255, 175, 90)
_ALARM_IDLE_COLOR = (120, 230, 190)
_ALARM_TRIGGERED_COLOR = (255, 110, 90)
_HOLDOUT_IDLE_COLOR = (245, 210, 120)
_HOLDOUT_ACTIVE_COLOR = (255, 245, 180)
_HOLDOUT_STABILIZER_COLOR = (120, 220, 255)
_HOLDOUT_STABILIZER_USED_COLOR = (110, 130, 160)
_HOLDOUT_STABILIZER_BURST_COLOR = (190, 255, 255)
_ALTAR_SHIELDED_COLOR = (120, 180, 255)
_ESCORT_COLOR = (245, 220, 140)
_ESCORT_DAMAGED_COLOR = (205, 130, 120)
_ESCORT_GOAL_COLOR = (255, 245, 170)
_CARRIER_COLOR = (250, 170, 80)
_CARRIER_WAITING_COLOR = (255, 215, 120)
_TRAP_SWEEPER_ACTIVE_COLOR = (255, 120, 80)
_TRAP_SWEEPER_IDLE_COLOR = (120, 140, 170, 150)
_TRAP_SWITCH_COLOR = (120, 170, 255)
_TRAP_SWITCH_SELECTED_COLOR = (255, 235, 120)
_TRAP_CRUSHER_ACTIVE_COLOR = (255, 150, 110)
_TRAP_CRUSHER_IDLE_COLOR = (120, 120, 120)
_TRAP_VENT_ACTIVE_COLOR = (120, 220, 255)
_TRAP_VENT_IDLE_COLOR = (90, 120, 160)


def _overlay_font(size=12):
    if not pygame.font.get_init():
        return None

    cache = getattr(_overlay_font, "_cache", None)
    if cache is None:
        cache = {}
        _overlay_font._cache = cache

    if size not in cache:
        cache[size] = pygame.font.SysFont("consolas", size)
    return cache[size]


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
            if self._config.get("window_gated"):
                self._config["window_vulnerable"] = False
            return
        elapsed = max(0, now_ticks + self.pulse_offset_ms)
        self.pulse_active = elapsed % self.pulse_cycle_ms < self.pulse_active_ms
        if self._config.get("window_gated"):
            self._config["window_vulnerable"] = self.pulse_active
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
        if self._config.get("window_gated") and not self._config.get("window_vulnerable", self.pulse_active):
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
        if (self._config.get("invulnerable") or (self._config.get("window_gated") and not self.pulse_active)) and not self.pulse_active:
            color = _ALTAR_SHIELDED_COLOR
        elif self.pulse_active:
            color = self._variant["pulse_color"]
        elif self.current_hp >= self.max_hp:
            color = self._variant["base_color"]
        else:
            color = self._variant["damaged_color"]
        return make_rect_surface(self.SIZE, self.SIZE, color)


class PressurePlate(pygame.sprite.Sprite):
    """Objective plate that supports ordered and paired puzzle rule variants."""

    SIZE = 22

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        controller = self._config.get("controller")
        if controller is not None:
            controller["now_ticks"] = now_ticks
        del now_ticks
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def sync_player_overlap(self, player):
        if self._config.get("activated") or self._config.get("primed"):
            return False
        padding = self._config.get("trigger_padding", 10)
        if not player.rect.colliderect(self.rect.inflate(padding, padding)):
            return False

        controller = self._config.get("controller")
        if controller is None:
            self._config["activated"] = True
        elif controller.get("variant") == "paired_runes":
            if not self._sync_paired_variant(controller):
                return False
        else:
            if not self._sync_ordered_variant(controller):
                return False

        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        flash_state = self._penalty_flash_state()
        if flash_state is not None:
            color, radius = flash_state
            pygame.draw.circle(surface, color, self.rect.center, radius, 2)

        color = None
        if self._config.get("activated"):
            color = _PLATE_ACTIVE_COLOR
        elif self._config.get("primed"):
            color = _PLATE_PRIMED_COLOR
        elif self._is_current_target():
            color = _PLATE_TARGET_COLOR

        if color is not None:
            pygame.draw.circle(surface, color, self.rect.center, self.SIZE // 2 + 3, 1)

    def _penalty_flash_state(self):
        controller = self._config.get("controller")
        if controller is None:
            return None

        now_ticks = controller.get("now_ticks")
        last_penalty_at = controller.get("last_penalty_at")
        if now_ticks is None or last_penalty_at is None:
            return None

        flash_ms = max(1, int(controller.get("penalty_flash_ms", 700)))
        age_ms = max(0, now_ticks - last_penalty_at)
        if age_ms > flash_ms:
            return None

        progress = age_ms / flash_ms
        reason = controller.get("last_penalty_reason", "reset")
        color = _PLATE_PENALTY_STALL_COLOR if reason == "stall" else _PLATE_PENALTY_RESET_COLOR
        radius = self.SIZE // 2 + 6 + int(10 * progress)
        return color, radius

    def _build_image(self):
        if self._config.get("activated"):
            color = _PLATE_ACTIVE_COLOR
        elif self._config.get("primed"):
            color = _PLATE_PRIMED_COLOR
        elif self._is_current_target():
            color = _PLATE_TARGET_COLOR
        else:
            color = _PLATE_COLOR

        surface = make_rect_surface(self.SIZE, self.SIZE, color)
        text = self._config.get("telegraph_text", "")
        font = _overlay_font()
        if text and font is not None:
            glyph = font.render(str(text), True, (20, 20, 20))
            surface.blit(glyph, glyph.get_rect(center=(self.SIZE // 2, self.SIZE // 2)))
        return surface

    def _is_current_target(self):
        controller = self._config.get("controller")
        if controller is None or self._config.get("activated"):
            return False

        if controller.get("variant") == "paired_runes":
            pending = controller.get("pending_pair_label")
            return bool(
                pending
                and self._config.get("pair_label") == pending
                and not self._config.get("primed")
            )

        return self._config.get("order_index", 0) == controller.get("progress_index", 0)

    def _sync_ordered_variant(self, controller):
        expected_index = controller.get("progress_index", 0)
        current_tick = controller.get("now_ticks")
        if self._config.get("order_index", 0) != expected_index:
            for config in controller.get("configs", ()): 
                config["activated"] = False
                config["primed"] = False
            controller["progress_index"] = 0
            controller["reaction_pending"] = True
            controller["reaction_reason"] = "reset"
            controller["last_reset_label"] = self._config.get("telegraph_text", "")
            if current_tick is not None:
                controller["last_progress_at"] = current_tick
            return True

        self._config["activated"] = True
        controller["progress_index"] = expected_index + 1
        controller["last_reset_label"] = ""
        if current_tick is not None:
            controller["last_progress_at"] = current_tick
        return True

    def _sync_paired_variant(self, controller):
        pair_label = self._config.get("pair_label", self._config.get("telegraph_text", "?"))
        pending_label = controller.get("pending_pair_label")
        configs = controller.get("configs", ())
        current_tick = controller.get("now_ticks")

        if pending_label is None:
            self._prime_pair_label(controller, pair_label, self._config)
            if current_tick is not None:
                controller["last_progress_at"] = current_tick
            return True

        if pair_label == pending_label:
            for config in configs:
                if config.get("pair_label") == pair_label and (config.get("primed") or config is self._config):
                    config["primed"] = False
                    config["activated"] = True
            self._config["activated"] = True
            controller["pending_pair_label"] = None
            controller["last_reset_label"] = ""
            if current_tick is not None:
                controller["last_progress_at"] = current_tick
            return True

        self._prime_pair_label(controller, pair_label, self._config)
        controller["last_reset_label"] = pair_label
        controller["reaction_pending"] = True
        controller["reaction_reason"] = "reset"
        if current_tick is not None:
            controller["last_progress_at"] = current_tick
        return True

    @staticmethod
    def _prime_pair_label(controller, pair_label, active_config):
        for config in controller.get("configs", ()): 
            config["primed"] = False
        active_config["primed"] = True
        controller["pending_pair_label"] = pair_label


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


class HoldoutStabilizer(pygame.sprite.Sprite):
    """Optional holdout side action that delays future reinforcement waves once activated."""

    SIZE = 18

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        controller = self._config.get("controller")
        if controller is not None:
            controller["now_ticks"] = now_ticks
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def sync_player_overlap(self, player):
        if self._config.get("used"):
            return False

        padding = self._config.get("trigger_padding", 18)
        if not player.rect.colliderect(self.rect.inflate(padding, padding)):
            return False

        controller = self._config.get("controller") or {}
        controller["wave_delay_ms"] = controller.get("wave_delay_ms", 0) + self._config.get("relief_delay_ms", 0)
        controller["last_relief_at"] = controller.get("now_ticks")
        controller["last_relief_label"] = self._config.get("label", "Stabilizer")
        self._config["used"] = True
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        radius = self.SIZE // 2 + 4
        if self._config.get("used"):
            radius += 1
        color = _HOLDOUT_STABILIZER_USED_COLOR if self._config.get("used") else _HOLDOUT_STABILIZER_COLOR
        pygame.draw.circle(surface, color, self.rect.center, radius, 2)

        burst_radius = self._activation_flash_state()
        if burst_radius is not None:
            pygame.draw.circle(surface, _HOLDOUT_STABILIZER_BURST_COLOR, self.rect.center, burst_radius, 2)

    def _activation_flash_state(self):
        controller = self._config.get("controller")
        if controller is None:
            return None
        now_ticks = controller.get("now_ticks")
        last_relief_at = controller.get("last_relief_at")
        if now_ticks is None or last_relief_at is None:
            return None
        if not self._config.get("used"):
            return None
        flash_ms = max(1, int(controller.get("relief_flash_ms", 900)))
        age_ms = max(0, now_ticks - last_relief_at)
        if age_ms > flash_ms:
            return None
        progress = age_ms / flash_ms
        return self.SIZE // 2 + 6 + int(10 * progress)

    def _build_image(self):
        color = _HOLDOUT_STABILIZER_USED_COLOR if self._config.get("used") else _HOLDOUT_STABILIZER_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)


class TrapLaneSwitch(pygame.sprite.Sprite):
    """Selector pad that changes which trap lane is currently safe."""

    SIZE = 18

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        del now_ticks
        self._config["selected"] = self._selected()
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def sync_player_overlap(self, player):
        padding = self._config.get("trigger_padding", 18)
        if not player.rect.colliderect(self.rect.inflate(padding, padding)):
            return False

        controller = self._config.get("controller") or {}
        lane_index = self._config.get("lane_index", 0)
        if controller.get("safe_lane") == lane_index:
            return False

        controller["safe_lane"] = lane_index
        controller["challenge_route_selected"] = lane_index == controller.get("challenge_lane")
        self._config["selected"] = True
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        color = _TRAP_SWITCH_SELECTED_COLOR if self._selected() else _TRAP_SWITCH_COLOR
        pygame.draw.circle(surface, color, self.rect.center, self.SIZE // 2 + 4, 1)

    def _selected(self):
        controller = self._config.get("controller") or {}
        return controller.get("safe_lane") == self._config.get("lane_index")

    def _build_image(self):
        color = _TRAP_SWITCH_SELECTED_COLOR if self._selected() else _TRAP_SWITCH_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)


class TrapSweeper(pygame.sprite.Sprite):
    """Moving trap hazard that patrols a lane until that lane is marked safe."""

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._last_now_ticks = 0
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        self._last_now_ticks = now_ticks
        self._config["active"] = self._active()
        if self._config["active"]:
            self._advance()
            self._config["pos"] = self.rect.center
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def apply_player_pressure(self, player):
        if not self._active():
            return False
        if self._last_now_ticks < self._config.get("damage_cooldown_until", 0):
            return False
        if not self.rect.colliderect(player.rect.inflate(6, 6)):
            return False

        player.take_damage(self._config.get("damage", 8))
        self._config["damage_cooldown_until"] = (
            self._last_now_ticks + self._config.get("damage_cooldown_ms", 350)
        )
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        color = (
            _TRAP_SWEEPER_ACTIVE_COLOR if self._active() else _TRAP_SWEEPER_IDLE_COLOR
        )
        lane_thickness = self._config.get("lane_thickness", 20)
        if self._config.get("orientation") == "horizontal":
            rect = pygame.Rect(
                self._config["travel_min"],
                self.rect.centery - lane_thickness // 2,
                self._config["travel_max"] - self._config["travel_min"],
                lane_thickness,
            )
        else:
            rect = pygame.Rect(
                self.rect.centerx - lane_thickness // 2,
                self._config["travel_min"],
                lane_thickness,
                self._config["travel_max"] - self._config["travel_min"],
            )
        pygame.draw.rect(surface, color, rect, 1)

    def _active(self):
        controller = self._config.get("controller") or {}
        lane_index = self._config.get("lane_index")
        if controller.get("safe_lane") != lane_index:
            return True
        return (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == lane_index
        )

    def _build_image(self):
        if self._config.get("orientation") == "horizontal":
            size = (36, 14)
        else:
            size = (14, 36)
        color = (
            _TRAP_SWEEPER_ACTIVE_COLOR if self._active() else _TRAP_SWEEPER_IDLE_COLOR
        )
        return make_rect_surface(size[0], size[1], color)

    def _advance(self):
        direction = self._config.get("direction", 1)
        speed = self._config.get("speed", 2.4)
        controller = self._config.get("controller") or {}
        if (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == self._config.get("lane_index")
        ):
            speed = self._config.get("challenge_speed", max(1.2, speed * 0.6))
        travel_min = self._config["travel_min"]
        travel_max = self._config["travel_max"]

        center_x, center_y = self.rect.center
        if self._config.get("orientation") == "horizontal":
            center_x += direction * speed
            if center_x <= travel_min or center_x >= travel_max:
                direction *= -1
                center_x = max(travel_min, min(travel_max, center_x))
            self.rect.center = (int(center_x), center_y)
        else:
            center_y += direction * speed
            if center_y <= travel_min or center_y >= travel_max:
                direction *= -1
                center_y = max(travel_min, min(travel_max, center_y))
            self.rect.center = (center_x, int(center_y))

        self._config["direction"] = direction


class TrapVentLane(pygame.sprite.Sprite):
    """Pulsing lane hazard that stays partially live on the optional challenge route."""

    SIZE = 16

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._last_now_ticks = 0
        self.image = self._build_image(False)
        self.rect = self.image.get_rect(center=config["emitter_pos"])

    def update(self, now_ticks):
        self._last_now_ticks = now_ticks
        self._config["active"] = self._active(now_ticks)
        self.image = self._build_image(self._config["active"])
        self.rect = self.image.get_rect(center=self.rect.center)

    def apply_player_pressure(self, player):
        if not self._config.get("active"):
            return False
        if self._last_now_ticks < self._config.get("damage_cooldown_until", 0):
            return False
        if not self._lane_rect().colliderect(player.rect):
            return False

        player.take_damage(self._config.get("damage", 7))
        self._config["damage_cooldown_until"] = (
            self._last_now_ticks + self._config.get("damage_cooldown_ms", 300)
        )
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        color = _TRAP_VENT_ACTIVE_COLOR if self._config.get("active") else _TRAP_VENT_IDLE_COLOR
        pygame.draw.rect(surface, color, self._lane_rect(), 2 if self._config.get("active") else 1)

    def _active(self, now_ticks):
        controller = self._config.get("controller") or {}
        lane_index = self._config.get("lane_index")
        selected = controller.get("safe_lane") == lane_index
        challenge_selected = (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == lane_index
        )
        if selected and not challenge_selected:
            return False

        cycle_ms = self._config.get("cycle_ms", 1100)
        active_ms = self._config.get("active_ms", 650)
        if challenge_selected:
            cycle_ms = self._config.get("challenge_cycle_ms", max(500, cycle_ms - 250))
            active_ms = self._config.get("challenge_active_ms", max(200, active_ms - 200))

        phase = (now_ticks + self._config.get("phase_offset_ms", 0)) % cycle_ms
        return phase < active_ms

    def _build_image(self, active):
        color = _TRAP_VENT_ACTIVE_COLOR if active else _TRAP_VENT_IDLE_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)

    def _lane_rect(self):
        lane_thickness = self._config.get("lane_thickness", 18)
        if self._config.get("orientation") == "horizontal":
            return pygame.Rect(
                self._config["travel_min"],
                self._config["center"] - lane_thickness // 2,
                self._config["travel_max"] - self._config["travel_min"],
                lane_thickness,
            )
        return pygame.Rect(
            self._config["center"] - lane_thickness // 2,
            self._config["travel_min"],
            lane_thickness,
            self._config["travel_max"] - self._config["travel_min"],
        )


class TrapCrusher(pygame.sprite.Sprite):
    """Timed crusher hazard used in corridor-style trap rooms."""

    SIZE = 18

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._last_now_ticks = 0
        self.image = self._build_image(False)
        self.rect = self.image.get_rect(center=config["emitter_pos"])

    def update(self, now_ticks):
        self._last_now_ticks = now_ticks
        self._config["active"] = self._active(now_ticks)
        self.image = self._build_image(self._config["active"])
        self.rect = self.image.get_rect(center=self.rect.center)

    def apply_player_pressure(self, player):
        if not self._config.get("active"):
            return False
        if self._last_now_ticks < self._config.get("damage_cooldown_until", 0):
            return False
        if not self._active_rect().colliderect(player.rect):
            return False

        player.take_damage(self._config.get("damage", 9))
        self._config["damage_cooldown_until"] = (
            self._last_now_ticks + self._config.get("damage_cooldown_ms", 350)
        )
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        color = _TRAP_CRUSHER_ACTIVE_COLOR if self._config.get("active") else _TRAP_CRUSHER_IDLE_COLOR
        pygame.draw.rect(surface, color, self._active_rect(), 0 if self._config.get("active") else 1)

    def _active(self, now_ticks):
        controller = self._config.get("controller") or {}
        lane_index = self._config.get("lane_index")
        selected = controller.get("safe_lane") == lane_index
        challenge_selected = (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == lane_index
        )
        if selected and not challenge_selected:
            return False

        cycle_ms = self._config.get("cycle_ms", 1200)
        active_ms = self._config.get("active_ms", 700)
        if challenge_selected:
            cycle_ms = self._config.get("challenge_cycle_ms", max(500, cycle_ms - 250))
            active_ms = self._config.get("challenge_active_ms", max(180, active_ms - 200))

        phase = (now_ticks + self._config.get("phase_offset_ms", 0)) % cycle_ms
        return phase < active_ms

    def _build_image(self, active):
        color = _TRAP_CRUSHER_ACTIVE_COLOR if active else _TRAP_CRUSHER_IDLE_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)

    def _active_rect(self):
        return pygame.Rect(*self._config["zone_rect"])


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

    def draw_overlay(self, surface):
        if self._config.get("destroyed") or self._config.get("reached_exit"):
            return

        goal_pos = self._config.get("goal_pos")
        if not goal_pos:
            return

        if self._config.get("requires_safe_path") and self._config.get("waiting_for_clearance"):
            color = _CARRIER_WAITING_COLOR
        elif self._config.get("requires_safe_path"):
            color = _CARRIER_COLOR
        else:
            color = _ESCORT_GOAL_COLOR

        goal_radius = max(14, int(self._config.get("goal_radius", 24)) + 8)
        pygame.draw.line(surface, color, self.rect.center, goal_pos, 2)
        pygame.draw.circle(surface, color, goal_pos, goal_radius, 2)
        pygame.draw.circle(surface, color, goal_pos, max(5, goal_radius // 3), 1)

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