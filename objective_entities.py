"""Objective-specific room entities such as altar anchors."""

import math

import pygame

import damage_feedback
from objective_metadata import get_altar_variant
from sprites import make_rect_surface


_PLATE_COLOR = (90, 205, 230)
_PLATE_ACTIVE_COLOR = (245, 225, 120)
_PLATE_PRIMED_COLOR = (170, 200, 255)
_PLATE_TARGET_COLOR = (255, 245, 170)
_PLATE_PENALTY_RESET_COLOR = (255, 120, 110)
_PLATE_PENALTY_STALL_COLOR = (255, 175, 90)
_PLATE_STABILIZER_COLOR = (180, 140, 230)
_PLATE_STABILIZER_DAMAGED_COLOR = (140, 90, 200)
_PLATE_STABILIZER_BURST_COLOR = (235, 210, 255)
_ALARM_IDLE_COLOR = (120, 230, 190)
_ALARM_TRIGGERED_COLOR = (255, 110, 90)
_HOLDOUT_IDLE_COLOR = (245, 210, 120)
_HOLDOUT_ACTIVE_COLOR = (255, 245, 180)
_HOLDOUT_STABILIZER_COLOR = (120, 220, 255)
_HOLDOUT_STABILIZER_USED_COLOR = (110, 130, 160)
_HOLDOUT_STABILIZER_BURST_COLOR = (190, 255, 255)
_ALTAR_SHIELDED_COLOR = (120, 180, 255)
# Role glyph colors for ritual altars. Bright = active/vulnerable role,
# dim = shielded by another altar (e.g. role_chain or ward_shields_others).
_ALTAR_ROLE_COLORS = {
    "summon": ((255, 130, 110), (140, 80, 70)),
    "pulse":  ((255, 220, 110), (150, 130, 70)),
    "ward":   ((140, 200, 255), (80, 110, 150)),
}
_ALTAR_ROLE_DEFAULT_COLORS = ((230, 230, 230), (130, 130, 130))
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
_TRAP_SAFE_SPOT_COLOR = (90, 200, 130, 140)   # muted green, semi-transparent
_RUNE_ALTAR_BASE_COLOR = (90, 110, 170)
_RUNE_ALTAR_GLYPH_COLOR = (220, 195, 255)
_RUNE_ALTAR_HALO_COLOR = (200, 170, 255, 80)
_RUNE_ALTAR_CONSUMED_COLOR = (110, 110, 130)


def _player_in_safe_spot(player, safe_spots):
    """Return True if the player's centre is inside any of the given safe spot rects."""
    cx, cy = player.rect.center
    for rect_tuple in safe_spots:
        x, y, w, h = rect_tuple
        if x <= cx <= x + w and y <= cy <= y + h:
            return True
    return False


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
        # Re-sync pulse stats from config so live ritual mutations
        # (e.g. _empower_remaining_altars) take effect on the sprite.
        self.pulse_radius = self._config.get("pulse_radius", self.pulse_radius)
        self.pulse_damage = self._config.get("pulse_damage", self.pulse_damage)
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
        if self._config.get("destroyed"):
            return
        if self.pulse_active:
            pygame.draw.circle(
                surface,
                self._variant["pulse_color"],
                self.rect.center,
                self.pulse_radius,
                2,
            )
        glyph_color = self.role_glyph_color()
        if glyph_color is not None:
            self._draw_role_glyph(surface, glyph_color)

    def role_glyph_color(self):
        """Return the role-glyph color for this altar, or ``None`` when the
        altar has no ``role`` (e.g. ritual rooms with no role script).

        Bright color when the altar is currently strikable (vulnerable);
        dim color when shielded by ``invulnerable`` or a closed pulse window.
        """
        role = self._config.get("role")
        if not role:
            return None
        bright, dim = _ALTAR_ROLE_COLORS.get(role, _ALTAR_ROLE_DEFAULT_COLORS)
        if self._config.get("invulnerable"):
            return dim
        if self._config.get("window_gated") and not self._config.get(
            "window_vulnerable", self.pulse_active
        ):
            return dim
        return bright

    def _draw_role_glyph(self, surface, color):
        """Render a small downward-pointing triangle above the altar."""
        cx, cy = self.rect.center
        top_y = self.rect.top - 6
        glyph_w = 8
        glyph_h = 6
        points = (
            (cx - glyph_w, top_y - glyph_h),
            (cx + glyph_w, top_y - glyph_h),
            (cx, top_y),
        )
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, (20, 20, 24), points, 1)

    def take_damage(self, amount):
        if self._config.get("destroyed"):
            return False
        if self._config.get("invulnerable"):
            self._config["wrong_struck_pending"] = True
            return False
        if self._config.get("window_gated") and not self._config.get("window_vulnerable", self.pulse_active):
            self._config["wrong_struck_pending"] = True
            return False

        previous_hp = self.current_hp
        self.current_hp = max(0, self.current_hp - amount)
        self._config["current_hp"] = self.current_hp
        damage_dealt = previous_hp - self.current_hp
        if damage_dealt > 0:
            damage_feedback.report_damage(self, damage_dealt)

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

    def apply_player_pressure(self, player):
        """Punish camping on solved plates by emitting periodic damage pulses.

        Disabled unless the puzzle controller has both ``camp_pulse_damage``
        and ``camp_pulse_interval_ms`` configured. Pulses begin only after
        the configured grace period since the plate was activated.
        """
        if not self._config.get("activated"):
            return False
        controller = self._config.get("controller")
        if controller is None:
            return False
        damage = int(controller.get("camp_pulse_damage", 0))
        interval = int(controller.get("camp_pulse_interval_ms", 0))
        if damage <= 0 or interval <= 0:
            return False
        now_ticks = controller.get("now_ticks")
        if now_ticks is None:
            return False
        activated_at = self._config.get("activated_at")
        if activated_at is None:
            return False
        grace = int(controller.get("camp_pulse_grace_ms", 0))
        if now_ticks - activated_at < grace:
            return False
        last_pulse_at = self._config.get("last_camp_pulse_at")
        if last_pulse_at is not None and now_ticks - last_pulse_at < interval:
            return False
        radius = int(controller.get("camp_pulse_radius", 0))
        if radius <= 0:
            radius = self.SIZE // 2 + max(0, int(self._config.get("trigger_padding", 0)))
            if radius <= 0:
                radius = self.SIZE
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        if dx * dx + dy * dy > radius * radius:
            return False

        player.take_damage(damage)
        self._config["last_camp_pulse_at"] = now_ticks
        controller["last_penalty_at"] = now_ticks
        controller["last_penalty_reason"] = "camp"
        return True

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

        return self._config.get("plate_id", self._config.get("order_index", 0)) == self._expected_plate_id(controller)

    def _sync_ordered_variant(self, controller):
        expected_plate_id = self._expected_plate_id(controller)
        current_tick = controller.get("now_ticks")
        if self._config.get("plate_id", self._config.get("order_index", 0)) != expected_plate_id:
            for config in controller.get("configs", ()): 
                config["activated"] = False
                config["primed"] = False
                config["activated_at"] = None
                config["last_camp_pulse_at"] = None
            controller["progress_index"] = 0
            controller["reaction_pending"] = True
            controller["reaction_reason"] = "reset"
            controller["last_reset_label"] = self._config.get("telegraph_text", "")
            if current_tick is not None:
                controller["last_progress_at"] = current_tick
            return True

        self._config["activated"] = True
        if current_tick is not None:
            self._config["activated_at"] = current_tick
        controller["progress_index"] = controller.get("progress_index", 0) + 1
        controller["last_reset_label"] = ""
        if current_tick is not None:
            controller["last_progress_at"] = current_tick
        return True

    @staticmethod
    def _expected_plate_id(controller):
        sequence = tuple(controller.get("target_sequence") or range(len(controller.get("configs", ()))))
        progress_index = controller.get("progress_index", 0)
        if progress_index < 0 or progress_index >= len(sequence):
            return None
        return sequence[progress_index]

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
                    if current_tick is not None:
                        config["activated_at"] = current_tick
            self._config["activated"] = True
            if current_tick is not None:
                self._config["activated_at"] = current_tick
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


class PuzzleStabilizer(pygame.sprite.Sprite):
    """Optional puzzle shortcut. Destroying it skips the next-expected plate.

    Config keys:
        pos:               pixel center
        max_hp/current_hp: durability the player must spend to claim the skip
        controller:        shared puzzle controller dict (see ``Room._build_puzzle_plate_configs``)
        trigger_padding:   reserved for future overlap-based interactions
        destroyed:         flipped to True once the stabilizer is shattered
        consumed:          flipped to True once the skip has been applied
    """

    SIZE = 18

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.max_hp = config.get("max_hp", 1)
        self.current_hp = config.get("current_hp", self.max_hp)
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        controller = self._config.get("controller")
        if controller is not None:
            controller["now_ticks"] = now_ticks
        if self._config.get("destroyed"):
            self.kill()
            return
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def take_damage(self, amount):
        if self._config.get("destroyed"):
            return False
        previous_hp = self.current_hp
        self.current_hp = max(0, self.current_hp - amount)
        self._config["current_hp"] = self.current_hp
        damage_dealt = previous_hp - self.current_hp
        if damage_dealt > 0:
            damage_feedback.report_damage(self, damage_dealt)
        if self.current_hp <= 0:
            self._config["destroyed"] = True
            self._apply_skip()
            self.kill()
            return True
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)
        return False

    def draw_overlay(self, surface):
        if self._config.get("destroyed"):
            return
        radius = self.SIZE // 2 + 4
        color = _PLATE_STABILIZER_DAMAGED_COLOR if self.current_hp < self.max_hp else _PLATE_STABILIZER_COLOR
        pygame.draw.circle(surface, color, self.rect.center, radius, 2)

    def _apply_skip(self):
        controller = self._config.get("controller")
        if controller is None:
            return
        if controller.get("variant") == "paired_runes":
            if not self._apply_paired_skip(controller):
                return
        else:
            if not self._apply_ordered_skip(controller):
                return
        controller["last_skip_label"] = self._config.get("label", "Stabilizer")
        controller["last_skip_at"] = controller.get("now_ticks")
        # Cancel any pending stall reaction so the skip does not also
        # immediately spawn reinforcements after the strike.
        controller["reaction_pending"] = False
        controller["reaction_reason"] = ""
        self._config["consumed"] = True

    def _apply_ordered_skip(self, controller):
        configs = controller.get("configs", ())
        sequence = controller.get("target_sequence") or tuple(range(len(configs)))
        progress_index = controller.get("progress_index", 0)
        if progress_index < 0 or progress_index >= len(sequence):
            return False
        expected_plate_id = sequence[progress_index]
        for plate_config in configs:
            plate_id = plate_config.get("plate_id", plate_config.get("order_index", 0))
            if plate_id == expected_plate_id and not plate_config.get("activated"):
                plate_config["activated"] = True
                plate_config["primed"] = False
                break
        controller["progress_index"] = progress_index + 1
        controller["last_progress_at"] = controller.get("now_ticks")
        return True

    def _apply_paired_skip(self, controller):
        configs = controller.get("configs", ())
        # Skip the first pair that still has any un-activated plate. Prefer the
        # pair the player has already half-primed so the shortcut fits the
        # player's intent; otherwise walk pair_labels in their authored order.
        pending_label = controller.get("pending_pair_label")
        candidate_labels = []
        if pending_label:
            candidate_labels.append(pending_label)
        for label in controller.get("pair_labels", ()):
            if label not in candidate_labels:
                candidate_labels.append(label)
        for label in candidate_labels:
            pair_configs = [
                config
                for config in configs
                if config.get("kind") == "pressure_plate" and config.get("pair_label") == label
            ]
            if not pair_configs or all(config.get("activated") for config in pair_configs):
                continue
            for config in pair_configs:
                config["activated"] = True
                config["primed"] = False
                if controller.get("now_ticks") is not None:
                    config["activated_at"] = controller["now_ticks"]
            controller["pending_pair_label"] = None
            controller["last_reset_label"] = ""
            controller["last_progress_at"] = controller.get("now_ticks")
            return True
        return False

    def _build_image(self):
        size = self.SIZE
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        color = _PLATE_STABILIZER_DAMAGED_COLOR if self.current_hp < self.max_hp else _PLATE_STABILIZER_COLOR
        # Hexagon silhouette so stabilizers read distinctly from plates and crystals.
        points = [
            (size // 2, 0),
            (size - 1, size // 4),
            (size - 1, size * 3 // 4),
            (size // 2, size - 1),
            (0, size * 3 // 4),
            (0, size // 4),
        ]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, _PLATE_STABILIZER_BURST_COLOR, points, 1)
        return surface


class AlarmBeacon(pygame.sprite.Sprite):
    """Visible alarm ward that trips if the player enters its radius."""

    SIZE = 20

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._patrol_route = self._build_patrol_route()
        self._patrol_cycle_ms = max(1, int(config.get("patrol_cycle_ms", 1800)))
        self._sync_patrol_state(0)
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        self._sync_patrol_state(now_ticks)
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self._config["pos"])

    def sync_player_overlap(self, player):
        if self._config.get("triggered"):
            return False

        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        radius = self._config.get("radius", 36)
        if dx * dx + dy * dy > radius * radius:
            return False
        if not self._player_inside_vision_cone(dx, dy):
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
        vision_angle = self._config.get("vision_angle_deg", 360)
        if vision_angle >= 360:
            pygame.draw.circle(
                surface,
                color,
                self.rect.center,
                self._config.get("radius", 36),
                2,
            )
            return

        points = self._vision_outline_points()
        if len(points) >= 3:
            pygame.draw.polygon(surface, color, points, 2)

    def _build_image(self):
        color = _ALARM_TRIGGERED_COLOR if self._config.get("triggered") else _ALARM_IDLE_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)

    def _build_patrol_route(self):
        points = tuple(self._config.get("patrol_points") or ())
        if len(points) < 2:
            return (tuple(self._config.get("pos", (0, 0))),)

        route = list(points)
        route.extend(reversed(points[:-1]))
        return tuple(route)

    def _sync_patrol_state(self, now_ticks):
        if len(self._patrol_route) < 2:
            self._config.setdefault("facing", (0.0, 1.0))
            return

        segment_count = len(self._patrol_route) - 1
        cycle_progress = ((now_ticks % self._patrol_cycle_ms) / self._patrol_cycle_ms) * segment_count
        segment_index = min(segment_count - 1, int(cycle_progress))
        segment_progress = cycle_progress - segment_index
        start = self._patrol_route[segment_index]
        end = self._patrol_route[segment_index + 1]

        px = round(start[0] + (end[0] - start[0]) * segment_progress)
        py = round(start[1] + (end[1] - start[1]) * segment_progress)
        self._config["pos"] = (px, py)
        self._config["facing"] = self._normalized_vector(
            end[0] - start[0],
            end[1] - start[1],
            default=self._config.get("facing", (0.0, 1.0)),
        )

    def _player_inside_vision_cone(self, dx, dy):
        vision_angle = float(self._config.get("vision_angle_deg", 360))
        if vision_angle >= 360:
            return True

        distance = math.hypot(dx, dy)
        if distance <= 0:
            return True

        facing_x, facing_y = self._normalized_vector(*self._config.get("facing", (0.0, 1.0)))
        facing_dot = (dx * facing_x + dy * facing_y) / distance
        min_dot = math.cos(math.radians(vision_angle / 2))
        return facing_dot >= min_dot

    def _vision_outline_points(self):
        radius = self._config.get("radius", 36)
        vision_angle = float(self._config.get("vision_angle_deg", 360))
        center_x, center_y = self.rect.center
        facing_x, facing_y = self._normalized_vector(*self._config.get("facing", (0.0, 1.0)))
        facing_angle = math.atan2(facing_y, facing_x)
        half_angle = math.radians(vision_angle / 2)
        arc_points = 6
        points = [(center_x, center_y)]

        for step in range(arc_points + 1):
            angle = facing_angle - half_angle + ((2 * half_angle) * step / arc_points)
            points.append(
                (
                    round(center_x + math.cos(angle) * radius),
                    round(center_y + math.sin(angle) * radius),
                )
            )
        return points

    @staticmethod
    def _normalized_vector(dx, dy, default=(0.0, 1.0)):
        magnitude = math.hypot(dx, dy)
        if magnitude <= 0:
            return default
        return dx / magnitude, dy / magnitude


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
        config_pos = self._config.get("pos")
        center = (
            (int(config_pos[0]), int(config_pos[1]))
            if config_pos is not None
            else self.rect.center
        )
        self.rect = self.image.get_rect(center=center)

    def sync_player_overlap(self, player):
        config_pos = self._config.get("pos")
        if config_pos is not None and (
            self.rect.centerx != int(config_pos[0])
            or self.rect.centery != int(config_pos[1])
        ):
            self.rect = self.image.get_rect(center=(int(config_pos[0]), int(config_pos[1])))
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

        zone_config = self._config.get("zone_config")
        migration_delay_ms = int(self._config.get("migration_delay_ms", 0) or 0)
        if zone_config is not None and migration_delay_ms > 0 and int(zone_config.get("migrate_ms") or 0) > 0:
            now_ticks = controller.get("now_ticks") or 0
            zone_config["migration_baseline_ms"] = (
                int(zone_config.get("migration_baseline_ms", 0)) + migration_delay_ms
            )
            zone_config["migration_anchor_until"] = int(now_ticks) + migration_delay_ms

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
        self._config["selected"] = self._selected(now_ticks)
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def sync_player_overlap(self, player):
        import pygame
        now_ticks = pygame.time.get_ticks()
        padding = self._config.get("trigger_padding", 18)
        if not player.rect.colliderect(self.rect.inflate(padding, padding)):
            return False

        controller = self._config.get("controller") or {}
        lane_index = self._config.get("lane_index", 0)
        is_challenge = lane_index == controller.get("challenge_lane")

        if is_challenge:
            if controller.get("challenge_route_selected"):
                return False
            controller["safe_lane"] = lane_index
            controller["challenge_route_selected"] = True
        else:
            cooldown_until = controller.setdefault("lane_suppress_cooldown_until", {})
            if now_ticks < cooldown_until.get(lane_index, 0):
                return False
            suppress_until = controller.setdefault("lane_suppress_until", {})
            suppress_duration_ms = controller.get("suppress_duration_ms", 2500)
            suppress_cooldown_ms = controller.get("suppress_cooldown_ms", 8000)
            suppress_until[lane_index] = now_ticks + suppress_duration_ms
            cooldown_until[lane_index] = now_ticks + suppress_cooldown_ms
            controller["safe_lane"] = lane_index
            controller["challenge_route_selected"] = False

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

    def _selected(self, now_ticks=None):
        import pygame
        controller = self._config.get("controller") or {}
        lane_index = self._config.get("lane_index")
        if controller.get("challenge_route_selected") and controller.get("challenge_lane") == lane_index:
            return True
        if now_ticks is None:
            now_ticks = pygame.time.get_ticks()
        return now_ticks < controller.get("lane_suppress_until", {}).get(lane_index, 0)

    def _build_image(self):
        color = _TRAP_SWITCH_SELECTED_COLOR if self._selected() else _TRAP_SWITCH_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)


class TrapSweeper(pygame.sprite.Sprite):
    """Moving trap hazard that patrols a lane until that lane is marked safe."""

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._last_now_ticks = 0
        self._travel_float = None  # float accumulator to avoid sub-pixel stalling
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
        if _player_in_safe_spot(player, self._config.get("safe_spots", ())):
            return False

        player.take_damage(self._config.get("damage", 8), damage_type="trap")
        self._config["damage_cooldown_until"] = (
            self._last_now_ticks + self._config.get("damage_cooldown_ms", 350)
        )
        controller = self._config.get("controller") or {}
        if (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == self._config.get("lane_index")
        ):
            controller["trap_challenge_hits"] = controller.get("trap_challenge_hits", 0) + 1
        knockback_px = controller.get("sweeper_knockback_px", 0)
        if knockback_px > 0:
            orientation = self._config.get("orientation", "horizontal")
            sx, sy = self.rect.center
            px, py = player.rect.center
            if orientation == "horizontal":
                push = knockback_px if px >= sx else -knockback_px
                player.rect.x += push
            else:
                push = knockback_px if py >= sy else -knockback_px
                player.rect.y += push
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
        if controller.get("surge_active", False):
            return True
        lane_index = self._config.get("lane_index")
        if (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == lane_index
        ):
            return True
        suppress_until = controller.get("lane_suppress_until", {})
        return self._last_now_ticks >= suppress_until.get(lane_index, 0)

    def _build_image(self):
        lane_thickness = self._config.get("lane_thickness", 20)
        if self._config.get("orientation") == "horizontal":
            size = (36, lane_thickness)
        else:
            size = (lane_thickness, 36)
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
        orientation = self._config.get("orientation")

        # Use a float accumulator so sub-pixel speeds (<1 px/frame) don't stall
        # the sweeper at the boundary when the challenge lane slows the boulder.
        if self._travel_float is None:
            self._travel_float = float(
                self.rect.centerx if orientation == "horizontal" else self.rect.centery
            )

        self._travel_float += direction * speed
        if self._travel_float <= travel_min or self._travel_float >= travel_max:
            direction *= -1
            self._travel_float = max(float(travel_min), min(float(travel_max), self._travel_float))

        if orientation == "horizontal":
            self.rect.center = (int(self._travel_float), self.rect.centery)
        else:
            self.rect.center = (self.rect.centerx, int(self._travel_float))

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
        if _player_in_safe_spot(player, self._config.get("safe_spots", ())):
            return False

        player.take_damage(self._config.get("damage", 7), damage_type="trap")
        self._config["damage_cooldown_until"] = (
            self._last_now_ticks + self._config.get("damage_cooldown_ms", 300)
        )
        controller = self._config.get("controller") or {}
        if (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == self._config.get("lane_index")
        ):
            controller["trap_challenge_hits"] = controller.get("trap_challenge_hits", 0) + 1
        chilled_ms = int(controller.get("vent_chilled_duration_ms", 0))
        if chilled_ms > 0:
            import status_effects as _se
            _se.apply_status(player, _se.CHILLED, self._last_now_ticks,
                             duration_ms=chilled_ms)
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        color = _TRAP_VENT_ACTIVE_COLOR if self._config.get("active") else _TRAP_VENT_IDLE_COLOR
        pygame.draw.rect(surface, color, self._lane_rect(), 2 if self._config.get("active") else 1)

    def _active(self, now_ticks):
        controller = self._config.get("controller") or {}
        if controller.get("surge_active", False):
            return True
        lane_index = self._config.get("lane_index")
        challenge_selected = (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == lane_index
        )
        if not challenge_selected:
            suppress_until = controller.get("lane_suppress_until", {})
            if now_ticks < suppress_until.get(lane_index, 0):
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
        if _player_in_safe_spot(player, self._config.get("safe_spots", ())):
            return False

        player.take_damage(self._config.get("damage", 9), damage_type="trap")
        self._config["damage_cooldown_until"] = (
            self._last_now_ticks + self._config.get("damage_cooldown_ms", 350)
        )
        controller = self._config.get("controller") or {}
        if (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == self._config.get("lane_index")
        ):
            controller["trap_challenge_hits"] = controller.get("trap_challenge_hits", 0) + 1
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        color = _TRAP_CRUSHER_ACTIVE_COLOR if self._config.get("active") else _TRAP_CRUSHER_IDLE_COLOR
        pygame.draw.rect(surface, color, self._active_rect(), 0 if self._config.get("active") else 1)

    def _active(self, now_ticks):
        controller = self._config.get("controller") or {}
        if controller.get("surge_active", False):
            return True
        lane_index = self._config.get("lane_index")
        challenge_selected = (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == lane_index
        )
        if not challenge_selected:
            suppress_until = controller.get("lane_suppress_until", {})
            if now_ticks < suppress_until.get(lane_index, 0):
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


class TrapSafeSpot(pygame.sprite.Sprite):
    """Visual marker for a safe spot inside a trap lane.

    Safe spots are logical zones where hazard damage is suppressed even when
    the hazard is active.  This sprite draws a subtle coloured overlay so the
    player can identify them.
    """

    def __init__(self, config):
        super().__init__()
        self._config = config
        x, y, w, h = config["rect"]
        self.image = make_rect_surface(w, h, _TRAP_SAFE_SPOT_COLOR)
        self.rect = self.image.get_rect(topleft=(x, y))

    def update(self, now_ticks):
        del now_ticks

    def draw_overlay(self, surface):
        x, y, w, h = self._config["rect"]
        pygame.draw.rect(surface, _TRAP_SAFE_SPOT_COLOR, pygame.Rect(x, y, w, h))
        pygame.draw.rect(surface, (120, 240, 160), pygame.Rect(x, y, w, h), 1)


_TRAP_SPIKE_ACTIVE_COLOR = (220, 60, 60, 200)
_TRAP_SPIKE_IDLE_COLOR = (80, 80, 80, 120)
_TRAP_SPIKE_WARN_COLOR = (220, 160, 40, 160)


class TrapSpikePanel(pygame.sprite.Sprite):
    """Floor panel hazard that pulses active/inactive on a fixed cycle.

    When active the panel deals damage to any player standing on it.  The
    panel respects the same surge-override and lane-suppress logic as the
    other trap hazards.
    """

    SIZE = 20

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._last_now_ticks = 0
        self.image = self._build_image(False)
        x, y = config.get("pos", (0, 0))
        self.rect = self.image.get_rect(center=(x, y))

    def update(self, now_ticks):
        self._last_now_ticks = now_ticks
        active = self._active(now_ticks)
        self._config["active"] = active
        self.image = self._build_image(active)

    def apply_player_pressure(self, player):
        if not self._config.get("active"):
            return False
        if self._last_now_ticks < self._config.get("damage_cooldown_until", 0):
            return False
        panel_rect = self._panel_rect()
        if not panel_rect.colliderect(player.rect):
            return False
        player.take_damage(self._config.get("damage", 6), damage_type="trap")
        self._config["damage_cooldown_until"] = (
            self._last_now_ticks + self._config.get("damage_cooldown_ms", 400)
        )
        controller = self._config.get("controller") or {}
        if (
            controller.get("challenge_route_selected")
            and controller.get("challenge_lane") == self._config.get("lane_index")
        ):
            controller["trap_challenge_hits"] = controller.get("trap_challenge_hits", 0) + 1
        return True

    def take_damage(self, amount):
        del amount
        return False

    def draw_overlay(self, surface):
        active = self._config.get("active", False)
        warn = self._warn(self._last_now_ticks)
        if active:
            color = _TRAP_SPIKE_ACTIVE_COLOR
        elif warn:
            color = _TRAP_SPIKE_WARN_COLOR
        else:
            color = _TRAP_SPIKE_IDLE_COLOR
        pygame.draw.rect(surface, color, self._panel_rect())
        pygame.draw.rect(surface, (200, 200, 200), self._panel_rect(), 1)

    def _active(self, now_ticks):
        controller = self._config.get("controller") or {}
        if controller.get("surge_active", False):
            return True
        lane_index = self._config.get("lane_index")
        suppress_until = controller.get("lane_suppress_until", {})
        if now_ticks < suppress_until.get(lane_index, 0):
            return False
        cycle_ms = self._config.get("cycle_ms", 1400)
        active_ms = self._config.get("active_ms", 600)
        phase = (now_ticks + self._config.get("phase_offset_ms", 0)) % cycle_ms
        return phase < active_ms

    def _warn(self, now_ticks):
        """True during the 300 ms window before the panel fires."""
        controller = self._config.get("controller") or {}
        if controller.get("surge_active", False):
            return False
        lane_index = self._config.get("lane_index")
        suppress_until = controller.get("lane_suppress_until", {})
        if now_ticks < suppress_until.get(lane_index, 0):
            return False
        cycle_ms = self._config.get("cycle_ms", 1400)
        active_ms = self._config.get("active_ms", 600)
        warn_ms = self._config.get("warn_ms", 300)
        phase = (now_ticks + self._config.get("phase_offset_ms", 0)) % cycle_ms
        return cycle_ms - warn_ms <= phase < cycle_ms or phase < active_ms

    def _panel_rect(self):
        x, y = self._config.get("pos", (0, 0))
        s = self.SIZE
        return pygame.Rect(x - s // 2, y - s // 2, s, s)

    def _build_image(self, active):
        color = _TRAP_SPIKE_ACTIVE_COLOR if active else _TRAP_SPIKE_IDLE_COLOR
        return make_rect_surface(self.SIZE, self.SIZE, color)


class RuneAltar(pygame.sprite.Sprite):
    """Static altar that offers the player a choice of three runes.

    The altar tracks ``consumed`` on its config dict so that re-entering the
    room after a pick does not respawn the choice.  Detection of the player's
    interaction with the altar (overlap + room-level pending offer) is
    handled by :class:`room.Room`, not by this sprite.
    """

    SIZE = 32
    INTERACTION_RADIUS = 36

    def __init__(self, config):
        super().__init__()
        self._config = config
        consumed = bool(config.get("consumed"))
        color = _RUNE_ALTAR_CONSUMED_COLOR if consumed else _RUNE_ALTAR_BASE_COLOR
        self.image = make_rect_surface(self.SIZE, self.SIZE, color)
        self.rect = self.image.get_rect(center=config["pos"])
        self._pulse_phase_ms = 0

    @property
    def consumed(self):
        return bool(self._config.get("consumed"))

    @property
    def offered_rune_ids(self):
        return tuple(self._config.get("offered_rune_ids", ()))

    def update(self, now_ticks):
        self._pulse_phase_ms = now_ticks

    def draw_overlay(self, surface):
        if self.consumed:
            return
        # halo pulse
        period = 1400
        phase = (self._pulse_phase_ms % period) / period
        radius = self.INTERACTION_RADIUS + int(6 * (0.5 + 0.5 * math.sin(phase * math.tau)))
        halo_size = radius * 2
        halo = pygame.Surface((halo_size, halo_size), pygame.SRCALPHA)
        pygame.draw.circle(halo, _RUNE_ALTAR_HALO_COLOR, (radius, radius), radius)
        halo_rect = halo.get_rect(center=self.rect.center)
        surface.blit(halo, halo_rect)
        # central glyph
        cx, cy = self.rect.center
        pygame.draw.circle(surface, _RUNE_ALTAR_GLYPH_COLOR, (cx, cy), 5)


class EscortNPC(pygame.sprite.Sprite):
    """Friendly objective actor that moves through the room and can be attacked by enemies."""

    SIZE = 24
    """Visual marker for a safe spot inside a trap lane.

    Safe spots are logical zones where hazard damage is suppressed even when
    the hazard is active.  This sprite draws a subtle coloured overlay so the
    player can identify them.
    """

    def __init__(self, config):
        super().__init__()
        self._config = config
        x, y, w, h = config["rect"]
        self.image = make_rect_surface(w, h, _TRAP_SAFE_SPOT_COLOR)
        self.rect = self.image.get_rect(topleft=(x, y))

    def update(self, now_ticks):
        del now_ticks

    def draw_overlay(self, surface):
        x, y, w, h = self._config["rect"]
        pygame.draw.rect(surface, _TRAP_SAFE_SPOT_COLOR, pygame.Rect(x, y, w, h))
        pygame.draw.rect(surface, (120, 240, 160), pygame.Rect(x, y, w, h), 1)


class EscortNPC(pygame.sprite.Sprite):
    """Friendly objective actor that moves through the room and can be attacked by enemies."""

    SIZE = 24

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])
        # False until the first update_behavior tick.  on_enter may update
        # config["pos"] after the sprite is constructed; snapping here ensures
        # the NPC appears at the correct near-player position on first frame.
        self._positioned = False

    @property
    def current_hp(self):
        return int(self._config.get("current_hp", 0))

    @property
    def max_hp(self):
        return int(self._config.get("max_hp", 0))

    def update(self, now_ticks):
        del now_ticks
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def update_behavior(self, *, player, wall_rects, portal_pos, allow_advance):
        if self._config.get("destroyed") or self._config.get("reached_exit"):
            return False

        # Snap to config["pos"] on the very first tick.  _position_escort_for_entry
        # runs during room.on_enter(), which is called after _load_room_sprites
        # created this sprite.  Without this snap the NPC starts at its
        # pre-repositioned default offset rather than next to the player.
        if not self._positioned:
            self._positioned = True
            self.rect.center = self._config["pos"]

        waiting_for_clearance = self._config.get("requires_safe_path") and not allow_advance
        self._config["waiting_for_clearance"] = bool(waiting_for_clearance)
        if waiting_for_clearance:
            return False

        from settings import ESCORT_FOLLOW_DISTANCE_PX

        player_center = player.rect.center

        # ── Track player movement direction ──────────────────────────────────
        # Each frame we record the player's position so we can derive their
        # movement vector.  The NPC then targets a point BEHIND the player in
        # that direction, making it visually trail rather than run alongside.
        last_player_center = self._config.get("_last_player_center")
        self._config["_last_player_center"] = player_center

        if last_player_center is not None:
            move_dx = player_center[0] - last_player_center[0]
            move_dy = player_center[1] - last_player_center[1]
            mag_sq = move_dx * move_dx + move_dy * move_dy
            if mag_sq > 0.0625:   # player moved at least 0.25 px this frame
                mag = mag_sq ** 0.5
                self._config["_last_player_dir"] = (move_dx / mag, move_dy / mag)

        # Default direction: player facing downward so NPC starts above them
        # on first-frame contact before any movement is recorded.
        player_dir = self._config.get("_last_player_dir", (0.0, 1.0))
        follow_dist = self._config.get("follow_distance", ESCORT_FOLLOW_DISTANCE_PX)

        # Trail point: a spot behind the player in their direction of motion.
        trail_x = player_center[0] - player_dir[0] * follow_dist
        trail_y = player_center[1] - player_dir[1] * follow_dist

        # Use the config's goal_pos as the escort's walk target if one has
        # been set (e.g. by _position_escort_for_entry).  Fall back to
        # portal_pos only when no explicit target was placed.
        goal_pos = self._config.get("goal_pos") or portal_pos

        # ── Choose target ─────────────────────────────────────────────────────
        # Switch from trailing to goal-seeking only once the *player* is
        # themselves within guide_radius of the goal.  This ensures the NPC
        # doesn't break away from the player prematurely.
        guide_radius = self._config.get("guide_radius", 96)
        px, py = player_center
        pdx = goal_pos[0] - px
        pdy = goal_pos[1] - py
        player_near_goal = pdx * pdx + pdy * pdy <= guide_radius * guide_radius

        if player_near_goal and allow_advance:
            target_pos = goal_pos
        else:
            target_pos = (trail_x, trail_y)

        # Dead-zone: skip movement when already within 2 px of the trail point
        # to avoid jitter when the player is stationary.
        tdx = self.rect.centerx - target_pos[0]
        tdy = self.rect.centery - target_pos[1]
        if tdx * tdx + tdy * tdy > 4:
            self._move_toward(target_pos, wall_rects)

        self._config["pos"] = self.rect.center

        exit_radius = self._config.get("exit_radius", 24)
        ex = goal_pos[0] - self.rect.centerx
        ey = goal_pos[1] - self.rect.centery
        if ex * ex + ey * ey <= exit_radius * exit_radius:
            self.rect.center = goal_pos
            self._config["pos"] = goal_pos
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

            previous_hp = self._config["current_hp"]
            current_hp = max(0, previous_hp - enemy.damage)
            self._config["current_hp"] = current_hp
            damage_dealt = previous_hp - current_hp
            if damage_dealt > 0:
                damage_feedback.report_damage(self, damage_dealt)
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


_HEARTSTONE_FILL = (200, 30, 40)
_HEARTSTONE_OUTLINE = (110, 10, 20)


class Heartstone(pygame.sprite.Sprite):
    """Carryable heart-shaped relic for the Heartstone Claim room."""

    SIZE = 16

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        del now_ticks
        # Sync visual position to logical config (the room/rpg loop sets pos
        # to the player's center while carried, or to the drop spot otherwise).
        self.rect.center = self._config["pos"]

    @classmethod
    def _build_image(cls):
        size = cls.SIZE
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        # Two lobes + bottom triangle to form a heart silhouette.
        lobe_radius = size // 4
        left_center = (size // 4, size // 3)
        right_center = (size - size // 4, size // 3)
        pygame.draw.circle(surface, _HEARTSTONE_FILL, left_center, lobe_radius)
        pygame.draw.circle(surface, _HEARTSTONE_FILL, right_center, lobe_radius)
        triangle = [
            (1, size // 3),
            (size - 1, size // 3),
            (size // 2, size - 1),
        ]
        pygame.draw.polygon(surface, _HEARTSTONE_FILL, triangle)
        # Outline overlay
        pygame.draw.circle(surface, _HEARTSTONE_OUTLINE, left_center, lobe_radius, 1)
        pygame.draw.circle(surface, _HEARTSTONE_OUTLINE, right_center, lobe_radius, 1)
        pygame.draw.polygon(surface, _HEARTSTONE_OUTLINE, triangle, 1)
        return surface


# ── Phase 2.A biome-room entities ───────────────────────
_VEIN_CRYSTAL_COLORS = {
    "damage": (240, 120, 200),  # rose quartz — attack boost
    "speed":  (160, 240, 200),  # mint geode  — move speed boost
    "armor":  (200, 200, 240),  # pale amethyst — incoming damage reduction
}
_VEIN_CRYSTAL_OUTLINE = (40, 30, 60)
_TREMOR_TELEGRAPH_COLOR = (220, 160, 60, 110)
_TREMOR_STRIKE_COLOR = (240, 90, 50, 170)


class VeinCrystal(pygame.sprite.Sprite):
    """Destructible crystal that grants a room-scoped buff when broken.

    Config keys:
        pos:            pixel center
        max_hp:         hit points
        buff_stat:      "damage" | "speed" | "armor"
        buff_magnitude: additive multiplier (0.20 = +20%)
        destroyed:      bool, set on destruction
        buff_applied:   bool, set after Room.update_objective grants the buff
    """

    SIZE = 18

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.max_hp = config.get("max_hp", 1)
        self.current_hp = config.get("current_hp", self.max_hp)
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        del now_ticks
        if self._config.get("destroyed"):
            self.kill()
            return
        # Re-render in case damage feedback flashes a recolor someday.
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def take_damage(self, amount):
        if self._config.get("destroyed"):
            return False
        previous_hp = self.current_hp
        self.current_hp = max(0, self.current_hp - amount)
        self._config["current_hp"] = self.current_hp
        damage_dealt = previous_hp - self.current_hp
        if damage_dealt > 0:
            damage_feedback.report_damage(self, damage_dealt)
        if self.current_hp <= 0:
            self._config["destroyed"] = True
            self.kill()
            return True
        return False

    def _build_image(self):
        size = self.SIZE
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        color = _VEIN_CRYSTAL_COLORS.get(
            self._config.get("buff_stat"), (220, 220, 240)
        )
        # Diamond silhouette so crystals are visually distinct from chests.
        points = [
            (size // 2, 1),
            (size - 1, size // 2),
            (size // 2, size - 1),
            (1, size // 2),
        ]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, _VEIN_CRYSTAL_OUTLINE, points, 1)
        return surface


class TremorEmitter(pygame.sprite.Sprite):
    """Invisible objective entity that periodically stuns the player.

    The stun is suppressed when the player stands on a HEARTH safe-spot
    tile.  The emitter has no rect for collision; it draws a soft
    overlay circle covering the whole room while telegraphing/striking.

    Config keys:
        pos:            pixel center (used only as anchor for overlay)
        cycle_ms:       full cycle length (telegraph + strike + cooldown)
        telegraph_ms:   windup window
        strike_ms:      damage window
        stun_duration_ms: status duration applied on strike
        offset_ms:      phase offset
    """

    SIZE = 1

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.cycle_ms = config.get("cycle_ms", 4000)
        self.telegraph_ms = config.get("telegraph_ms", 1500)
        self.strike_ms = config.get("strike_ms", 500)
        self.stun_duration_ms = config.get("stun_duration_ms", 1000)
        self.offset_ms = config.get("offset_ms", 0)
        # Tracks the strike-phase cycle index already applied so a single
        # strike window can't stun the player every frame.
        self._last_strike_cycle = -1
        self.telegraphing = False
        self.striking = False
        self._now_ticks = 0
        # Invisible 1×1 surface — drawing happens via draw_overlay().
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        phase = (now_ticks + self.offset_ms) % self.cycle_ms
        self.telegraphing = phase < self.telegraph_ms
        self.striking = (
            self.telegraph_ms <= phase < self.telegraph_ms + self.strike_ms
        )
        # Latch the timestamp so apply_player_pressure (called immediately
        # afterwards by rpg.py) doesn't have to query pygame's clock — and
        # so unit tests can drive the entity by calling update(strike_now)
        # directly without a live pygame timer.
        self._now_ticks = now_ticks

    def apply_player_pressure(self, player):
        if not self.striking:
            return False
        # Suppress when the player is standing on a HEARTH safe-spot tile.
        room = self._config.get("room")
        if room is not None:
            from room import HEARTH, TILE_SIZE
            col = player.rect.centerx // TILE_SIZE
            row = player.rect.centery // TILE_SIZE
            if room.tile_at(col, row) == HEARTH:
                return False
        # Idempotent within a single strike window.
        now_ticks = self._now_ticks
        cycle_index = (now_ticks + self.offset_ms) // self.cycle_ms
        if cycle_index == self._last_strike_cycle:
            return False
        self._last_strike_cycle = cycle_index
        import status_effects
        status_effects.apply_status(
            player, status_effects.STUNNED, now_ticks,
            duration_ms=self.stun_duration_ms,
        )
        return True

    def draw_overlay(self, surface):
        if not (self.telegraphing or self.striking):
            return
        color = _TREMOR_STRIKE_COLOR if self.striking else _TREMOR_TELEGRAPH_COLOR
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill(color)
        surface.blit(overlay, (0, 0))


# ── Phase 2.A.3 biome-room entities ─────────────────────
_SPORE_MUSHROOM_CAP_COLOR = (170, 90, 200)
_SPORE_MUSHROOM_STEM_COLOR = (235, 220, 200)
_SPORE_MUSHROOM_OUTLINE = (40, 20, 50)
_SPORE_MUSHROOM_PULSE_COLOR = (140, 220, 130, 90)
_COLLAPSE_TELEGRAPH_COLOR = (220, 130, 60, 140)
_COLLAPSE_BORDER_COLOR = (50, 30, 20)
_MINING_CART_BODY_COLOR = (140, 90, 50)
_MINING_CART_TRIM_COLOR = (60, 40, 25)


class SporeMushroom(pygame.sprite.Sprite):
    """Destructible spore-emitter that periodically poisons the player.

    Pulse cycle is identical in shape to ``AltarAnchor`` but the payload is
    a :data:`status_effects.POISONED` application instead of HP damage.
    Destroying the mushroom (HP→0) silences its pulses for the rest of
    the room.

    Config keys:
        pos:                pixel center
        max_hp:             hit points (default 3)
        pulse_cycle_ms:     full cycle length (default 3000)
        pulse_active_ms:    pulse window length (default 700)
        pulse_offset_ms:    phase offset for variety
        pulse_radius:       poison ring radius in px (default 80)
        poison_duration_ms: status duration on hit (default 5000)
        destroyed:          bool, set on destruction
    """

    SIZE = 22

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.max_hp = config.get("max_hp", 3)
        self.current_hp = config.get("current_hp", self.max_hp)
        self.pulse_cycle_ms = config.get("pulse_cycle_ms", 3000)
        self.pulse_active_ms = config.get("pulse_active_ms", 700)
        self.pulse_offset_ms = config.get("pulse_offset_ms", 0)
        self.pulse_radius = config.get("pulse_radius", 80)
        self.poison_duration_ms = config.get("poison_duration_ms", 5000)
        self.pulse_active = False
        self._last_pulse_cycle = -1
        self._now_ticks = 0
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        if self._config.get("destroyed"):
            self.pulse_active = False
            self.kill()
            return
        elapsed = max(0, now_ticks + self.pulse_offset_ms)
        self.pulse_active = elapsed % self.pulse_cycle_ms < self.pulse_active_ms
        self._now_ticks = now_ticks

    def apply_player_pressure(self, player):
        if not self.pulse_active or self._config.get("destroyed"):
            return False
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        if dx * dx + dy * dy > self.pulse_radius * self.pulse_radius:
            return False
        # Idempotent within one pulse window.
        now_ticks = self._now_ticks
        cycle_index = (now_ticks + self.pulse_offset_ms) // self.pulse_cycle_ms
        if cycle_index == self._last_pulse_cycle:
            return False
        self._last_pulse_cycle = cycle_index
        import status_effects
        status_effects.apply_status(
            player, status_effects.POISONED, now_ticks,
            duration_ms=self.poison_duration_ms,
        )
        return True

    def take_damage(self, amount):
        if self._config.get("destroyed"):
            return False
        previous_hp = self.current_hp
        self.current_hp = max(0, self.current_hp - amount)
        self._config["current_hp"] = self.current_hp
        damage_dealt = previous_hp - self.current_hp
        if damage_dealt > 0:
            damage_feedback.report_damage(self, damage_dealt)
        if self.current_hp <= 0:
            self._config["destroyed"] = True
            self.kill()
            return True
        return False

    def draw_overlay(self, surface):
        if not self.pulse_active or self._config.get("destroyed"):
            return
        ring = pygame.Surface(
            (self.pulse_radius * 2, self.pulse_radius * 2), pygame.SRCALPHA
        )
        pygame.draw.circle(
            ring, _SPORE_MUSHROOM_PULSE_COLOR,
            (self.pulse_radius, self.pulse_radius),
            self.pulse_radius,
        )
        surface.blit(
            ring,
            (self.rect.centerx - self.pulse_radius,
             self.rect.centery - self.pulse_radius),
        )

    def _build_image(self):
        size = self.SIZE
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        # Stem.
        stem_rect = pygame.Rect(size // 2 - 2, size // 2, 4, size // 2 - 1)
        surface.fill(_SPORE_MUSHROOM_STEM_COLOR, stem_rect)
        # Cap (semicircle).
        pygame.draw.circle(
            surface, _SPORE_MUSHROOM_CAP_COLOR,
            (size // 2, size // 2),
            size // 2 - 1,
            draw_top_left=True, draw_top_right=True,
        )
        pygame.draw.circle(
            surface, _SPORE_MUSHROOM_OUTLINE,
            (size // 2, size // 2),
            size // 2 - 1, 1,
            draw_top_left=True, draw_top_right=True,
        )
        return surface


class CollapseEmitter(pygame.sprite.Sprite):
    """Cycle-driven floor-tile collapser for the Cave-In room.

    Each cycle: pick a random FLOOR cell during the telegraph window, paint
    a warning marker, then convert it to ``PIT_TILE`` at the strike instant.
    Stops once ``max_collapses`` cells have been converted so the room
    doesn't end up as a wall-to-wall pit field.

    Config keys:
        pos:            anchor pixel (room centre, used for sprite rect only)
        cycle_ms:       full cycle length (default 5000)
        telegraph_ms:   windup window during which the warning is shown
        max_collapses:  cap on total tiles converted (default 4)
        offset_ms:      phase offset
        room:           live Room reference (required for grid mutation)
    """

    SIZE = 1

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.cycle_ms = config.get("cycle_ms", 5000)
        self.telegraph_ms = config.get("telegraph_ms", 1500)
        self.max_collapses = config.get("max_collapses", 4)
        self.offset_ms = config.get("offset_ms", 0)
        self.collapses_done = config.get("collapses_done", 0)
        self.telegraphing = False
        self._pending_cell = None  # (col, row) or None
        self._last_strike_cycle = -1
        self._now_ticks = 0
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        self._now_ticks = now_ticks
        if self.collapses_done >= self.max_collapses:
            self.telegraphing = False
            self._pending_cell = None
            return
        phase = (now_ticks + self.offset_ms) % self.cycle_ms
        in_telegraph = phase < self.telegraph_ms
        cycle_index = (now_ticks + self.offset_ms) // self.cycle_ms

        if in_telegraph:
            if self._pending_cell is None or cycle_index != self._last_strike_cycle - 1:
                # Pick a fresh victim cell at the start of each telegraph.
                if cycle_index != self._last_strike_cycle:
                    self._pending_cell = self._pick_target_cell()
            self.telegraphing = self._pending_cell is not None
        else:
            # Strike the moment we leave the telegraph window.
            if cycle_index != self._last_strike_cycle and self._pending_cell is not None:
                self._collapse_cell(self._pending_cell)
                self._last_strike_cycle = cycle_index
                self._pending_cell = None
            self.telegraphing = False

    def _pick_target_cell(self):
        room = self._config.get("room")
        if room is None:
            return None
        from room import FLOOR, ROOM_COLS, ROOM_ROWS
        candidates = [
            (c, r)
            for r in range(2, ROOM_ROWS - 2)
            for c in range(2, ROOM_COLS - 2)
            if room.grid[r][c] == FLOOR
        ]
        if not candidates:
            return None
        import random as _random
        return _random.choice(candidates)

    def _collapse_cell(self, cell):
        room = self._config.get("room")
        if room is None:
            return
        from room import FLOOR, PIT_TILE
        col, row = cell
        if room.grid[row][col] != FLOOR:
            return
        room.grid[row][col] = PIT_TILE
        self.collapses_done += 1
        self._config["collapses_done"] = self.collapses_done

    def draw_overlay(self, surface):
        if not self.telegraphing or self._pending_cell is None:
            return
        from room import TILE_SIZE
        col, row = self._pending_cell
        rect = pygame.Rect(col * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        marker = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        marker.fill(_COLLAPSE_TELEGRAPH_COLOR)
        pygame.draw.rect(marker, _COLLAPSE_BORDER_COLOR, marker.get_rect(), 2)
        surface.blit(marker, rect.topleft)


class MiningCart(pygame.sprite.Sprite):
    """Auto-rolling cart that travels along a CART_RAIL row.

    Wraps around the room horizontally; on contact with the player applies
    damage + horizontal knockback (rate-limited via ``damage_cooldown_ms``).

    Config keys:
        pos:                  initial pixel center
        speed:                px per frame (positive = right, negative = left)
        damage:               HP damage on hit (default 8)
        knockback_px:         horizontal displacement applied on hit
        damage_cooldown_ms:   minimum gap between successive hits
    """

    SIZE = 24

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.speed = config.get("speed", 2.4)
        self.damage = config.get("damage", 8)
        self.knockback_px = config.get("knockback_px", 24)
        self.damage_cooldown_ms = config.get("damage_cooldown_ms", 600)
        self._last_hit_at = -10**9
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        del now_ticks
        from room import ROOM_COLS, TILE_SIZE
        room_width = ROOM_COLS * TILE_SIZE
        self.rect.x += self.speed
        # Wrap when the entire sprite has cleared either side.
        if self.rect.left > room_width:
            self.rect.right = 0
        elif self.rect.right < 0:
            self.rect.left = room_width

    def apply_player_pressure(self, player):
        if not self.rect.colliderect(player.rect):
            return False
        import pygame as _pg
        now_ticks = _pg.time.get_ticks()
        if now_ticks - self._last_hit_at < self.damage_cooldown_ms:
            return False
        self._last_hit_at = now_ticks
        player.take_damage(self.damage)
        # Knock the player back along the cart's travel direction.
        kx = self.knockback_px if self.speed >= 0 else -self.knockback_px
        player.rect.x += kx
        return True

    def _build_image(self):
        size = self.SIZE
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        body_rect = pygame.Rect(2, size // 3, size - 4, size // 2)
        surface.fill(_MINING_CART_BODY_COLOR, body_rect)
        pygame.draw.rect(surface, _MINING_CART_TRIM_COLOR, body_rect, 1)
        # Wheels.
        wheel_y = body_rect.bottom
        pygame.draw.circle(surface, _MINING_CART_TRIM_COLOR, (5, wheel_y), 3)
        pygame.draw.circle(surface, _MINING_CART_TRIM_COLOR, (size - 5, wheel_y), 3)
        return surface


# ── Phase 2.A.4 biome-room entities ─────────────────────
_BURROW_MOUND_COLOR = (110, 75, 50)
_BURROW_MOUND_OUTLINE = (50, 30, 20)
_BURROW_TELEGRAPH_COLOR = (240, 180, 60, 130)


class BurrowSpawner(pygame.sprite.Sprite):
    """Periodically telegraphs then spawns an enemy at its position.

    The actual ``enemy_group.add`` happens in :meth:`Room.update_objective`
    (via a ``spawn_enemies`` update), which polls each spawner's
    ``config["pending_spawn"]`` flag.  The spawner sets that flag the
    moment it transitions from telegraph → strike, then clears it after
    the room has consumed it.

    Config keys:
        pos:            pixel center (used as spawn point)
        cycle_ms:       full cycle length (default 4500)
        telegraph_ms:   windup window (mound visible, no spawn yet)
        max_spawns:     cap on total enemies spawned (default 4)
        offset_ms:      phase offset
        enemy_cls:      ``ChaserEnemy`` (or any constructor accepting (x, y))
        spawns_done:    int counter, persisted on the config
        pending_spawn:  bool flag the room reads & resets each tick
    """

    SIZE = 24

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.cycle_ms = config.get("cycle_ms", 4500)
        self.telegraph_ms = config.get("telegraph_ms", 1500)
        self.max_spawns = config.get("max_spawns", 4)
        self.offset_ms = config.get("offset_ms", 0)
        self.spawns_done = config.get("spawns_done", 0)
        self.telegraphing = False
        self._last_strike_cycle = -1
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def update(self, now_ticks):
        if self.spawns_done >= self.max_spawns:
            self.telegraphing = False
            return
        phase = (now_ticks + self.offset_ms) % self.cycle_ms
        cycle_index = (now_ticks + self.offset_ms) // self.cycle_ms
        in_telegraph = phase < self.telegraph_ms
        self.telegraphing = in_telegraph
        if not in_telegraph and cycle_index != self._last_strike_cycle:
            # Transition to strike: arm a spawn for the room to harvest.
            self._last_strike_cycle = cycle_index
            self._config["pending_spawn"] = True
            self.spawns_done += 1
            self._config["spawns_done"] = self.spawns_done

    def _build_image(self):
        size = self.SIZE
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        # Earth mound: half-circle with a dirt rim.
        pygame.draw.circle(
            surface, _BURROW_MOUND_COLOR,
            (size // 2, size // 2),
            size // 2 - 1,
        )
        pygame.draw.circle(
            surface, _BURROW_MOUND_OUTLINE,
            (size // 2, size // 2),
            size // 2 - 1, 1,
        )
        return surface

    def draw_overlay(self, surface):
        if not self.telegraphing:
            return
        radius = self.SIZE // 2 + 4
        ring = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            ring, _BURROW_TELEGRAPH_COLOR,
            (radius, radius), radius,
        )
        surface.blit(
            ring,
            (self.rect.centerx - radius, self.rect.centery - radius),
        )


# ── Phase 2.A.5 biome-room entities ─────────────────────
_BOULDER_COLOR = (115, 95, 75)
_BOULDER_OUTLINE = (55, 40, 25)
_BOULDER_TELEGRAPH_COLOR = (240, 140, 60, 130)
_SHRINE_GLYPH_COLOR = (220, 200, 130)
_SHRINE_GLYPH_OUTLINE = (120, 95, 50)
_SHRINE_AURA_COLOR = (240, 220, 140, 90)


class Boulder(pygame.sprite.Sprite):
    """Vertical single-trip boulder hazard.

    A boulder spawns just outside one wall (top or bottom) at a fixed
    column, then rolls in a straight line at a constant speed until it
    leaves the opposite wall, at which point it removes itself from its
    sprite group.  There is no telegraph and no recycling — boulders are
    transient projectiles fired by :class:`BoulderRunSpawner`.

    Config keys:
        lane_x:               pixel center x of the column the boulder rolls along
        direction:            +1 (rolls down from top wall) or -1 (rolls up from bottom)
        speed:                px per frame travelled along the lane (>0)
        damage:               HP damage dealt on contact
        knockback_px:         vertical displacement applied on hit
        damage_cooldown_ms:   minimum gap between successive hits on the same player
    """

    SIZE = 32

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.lane_x = config["lane_x"]
        self.direction = 1 if config.get("direction", 1) >= 0 else -1
        # Speed always stored as a positive magnitude; direction lives on
        # ``self.direction`` so movement = speed * direction.
        self.speed = abs(config.get("speed", 5))
        self.damage = config.get("damage", 10)
        self.knockback_px = config.get("knockback_px", 32)
        self.damage_cooldown_ms = config.get("damage_cooldown_ms", 700)
        self._last_hit_at = -10 ** 9
        self.image = self._build_image()
        # Spawn just outside the source wall so the boulder enters the
        # play area on its first update.
        from room import ROOM_ROWS, TILE_SIZE
        room_height = ROOM_ROWS * TILE_SIZE
        if self.direction > 0:
            spawn_y = -self.SIZE  # source = top wall
        else:
            spawn_y = room_height + self.SIZE  # source = bottom wall
        self.rect = self.image.get_rect(center=(self.lane_x, spawn_y))

    def _is_offscreen(self):
        from room import ROOM_ROWS, TILE_SIZE
        room_height = ROOM_ROWS * TILE_SIZE
        if self.direction > 0:
            return self.rect.top > room_height
        return self.rect.bottom < 0

    def update(self, now_ticks):  # noqa: ARG002  — uniform sprite signature
        self.rect.y += int(round(self.speed * self.direction))
        if self._is_offscreen():
            self.kill()

    def apply_player_pressure(self, player):
        if not self.rect.colliderect(player.rect):
            return False
        import pygame as _pg
        now_ticks = _pg.time.get_ticks()
        if now_ticks - self._last_hit_at < self.damage_cooldown_ms:
            return False
        self._last_hit_at = now_ticks
        player.take_damage(self.damage)
        ky = self.knockback_px if self.direction > 0 else -self.knockback_px
        player.rect.y += ky
        return True

    def _build_image(self):
        size = self.SIZE
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(
            surface, _BOULDER_COLOR,
            (size // 2, size // 2), size // 2 - 1,
        )
        pygame.draw.circle(
            surface, _BOULDER_OUTLINE,
            (size // 2, size // 2), size // 2 - 1, 2,
        )
        pygame.draw.circle(surface, _BOULDER_OUTLINE, (size // 3, size // 3), 2)
        pygame.draw.circle(surface, _BOULDER_OUTLINE, (2 * size // 3, 2 * size // 3), 2)
        return surface


class BoulderRunSpawner(pygame.sprite.Sprite):
    """Invisible per-room spawner that fires :class:`Boulder` projectiles.

    Owns a single source wall (``"top"`` or ``"bottom"``) chosen at room
    build time.  Each frame, advances an internal timer; when the next
    spawn time is reached, instantiates a :class:`Boulder` at a random
    valid column with a random speed and adds it to the spawner's sprite
    group, then schedules the next spawn at a random interval.

    Config keys:
        source_wall:    "top" or "bottom"
        door_columns:   iterable of int columns to exclude (boulders never
                        spawn on a door tile so traversal lanes stay clear)
        speed_range:    (min, max) px/frame for boulder speed
        interval_range: (min_ms, max_ms) cadence between successive spawns

    Attributes:
        objective_group:  set externally (by ``dungeon.py`` after construction)
                          to the sprite group new boulders are added to
        spawned:          int counter of how many boulders this spawner fired
    """

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.source_wall = config.get("source_wall", "top")
        self.door_columns = set(config.get("door_columns") or ())
        from settings import (
            BOULDER_BASE_SPEED_RANGE, BOULDER_SPAWN_INTERVAL_RANGE_MS,
            BOULDER_DAMAGE,
        )
        self.speed_range = config.get("speed_range", BOULDER_BASE_SPEED_RANGE)
        self.interval_range = config.get(
            "interval_range", BOULDER_SPAWN_INTERVAL_RANGE_MS,
        )
        self.damage = config.get("damage", BOULDER_DAMAGE)
        # Invisible spawner — give it a 1x1 transparent image so pygame
        # group draw passes are no-ops.
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(-1000, -1000))
        # Set externally by dungeon.py after construction so the spawner
        # can directly add new boulders to the live objective group.
        self.objective_group = None
        self.spawned = 0
        # Per-instance RNG so tests can seed deterministically.
        self._rng = config.get("rng") or random
        # First spawn fires after the first interval — gives the player a
        # beat to enter the room before boulders start flying.
        self._next_spawn_at_ms = None

    def _valid_columns(self):
        """Return the list of spawn columns (interior cols minus doors)."""
        from room import ROOM_COLS
        return [
            c for c in range(2, ROOM_COLS - 2)
            if c not in self.door_columns
        ]

    def _schedule_next_spawn(self, now_ticks):
        lo, hi = self.interval_range
        self._next_spawn_at_ms = now_ticks + self._rng.randint(int(lo), int(hi))

    def update(self, now_ticks):
        if self._next_spawn_at_ms is None:
            self._schedule_next_spawn(now_ticks)
            return
        if now_ticks < self._next_spawn_at_ms:
            return
        self._spawn_boulder(now_ticks)
        self._schedule_next_spawn(now_ticks)

    def _spawn_boulder(self, now_ticks):  # noqa: ARG002
        from room import TILE_SIZE
        cols = self._valid_columns()
        if not cols:
            return
        col = self._rng.choice(cols)
        lane_x = col * TILE_SIZE + TILE_SIZE // 2
        lo, hi = self.speed_range
        speed = self._rng.uniform(float(lo), float(hi))
        direction = 1 if self.source_wall == "top" else -1
        boulder = Boulder({
            "lane_x": lane_x,
            "direction": direction,
            "speed": speed,
            "damage": self.damage,
        })
        self.spawned += 1
        if self.objective_group is not None:
            self.objective_group.add(boulder)
        # Stash the most recent boulder on the config so tests / tools can
        # inspect spawner output without poking at the live group.
        self._config["last_spawned"] = boulder

    def draw_overlay(self, surface):  # noqa: ARG002 — invisible
        return


class ShrineGlyph(pygame.sprite.Sprite):
    """Centerpiece shrine that weakens enemies while the player stands on it.

    The glyph itself is decorative — the active "weaken" effect is applied
    by :meth:`apply_room_pressure` which rpg.py invokes each tick with the
    current ``enemy_group`` and player.  When the player's tile is one of
    the shrine's GLYPH_TILE positions, every enemy receives a short SLOWED
    refresh; the entity's own ``active`` flag drives a pulsing aura.

    Config keys:
        pos:           pixel center
        glyph_tiles:   set of (col, row) tile coords that count as "on shrine"
        slow_ms:       SLOWED status duration applied to enemies (default 600)
    """

    SIZE = 24

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.glyph_tiles = set(config.get("glyph_tiles", ()))
        self.slow_ms = config.get("slow_ms", 600)
        self.active = False
        self.image = self._build_image()
        self.rect = self.image.get_rect(center=config["pos"])

    def _player_on_shrine(self, player):
        from room import TILE_SIZE
        col = player.rect.centerx // TILE_SIZE
        row = player.rect.centery // TILE_SIZE
        return (col, row) in self.glyph_tiles

    def apply_room_pressure(self, player, enemy_group):
        on_shrine = self._player_on_shrine(player)
        self.active = on_shrine
        if not on_shrine:
            return False
        import pygame as _pg
        import status_effects
        now_ticks = _pg.time.get_ticks()
        for enemy in enemy_group:
            status_effects.apply_status(
                enemy, status_effects.SLOWED, now_ticks,
                duration_ms=self.slow_ms,
            )
        return True

    def _build_image(self):
        size = self.SIZE
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        # Carved stone disk with a glyph cross.
        pygame.draw.circle(
            surface, _SHRINE_GLYPH_COLOR,
            (size // 2, size // 2), size // 2 - 1,
        )
        pygame.draw.circle(
            surface, _SHRINE_GLYPH_OUTLINE,
            (size // 2, size // 2), size // 2 - 1, 2,
        )
        pygame.draw.line(
            surface, _SHRINE_GLYPH_OUTLINE,
            (size // 2, 4), (size // 2, size - 4), 2,
        )
        pygame.draw.line(
            surface, _SHRINE_GLYPH_OUTLINE,
            (4, size // 2), (size - 4, size // 2), 2,
        )
        return surface

    def draw_overlay(self, surface):
        if not self.active:
            return
        radius = self.SIZE // 2 + 8
        aura = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            aura, _SHRINE_AURA_COLOR,
            (radius, radius), radius,
        )
        surface.blit(
            aura,
            (self.rect.centerx - radius, self.rect.centery - radius),
        )


# ── Phase 0c: biome-agnostic boss orchestration ─────────


class BossEvents:
    """Per-tick event bundle returned by :meth:`BossController.update`.

    Attributes:
        new_waves:        wave thresholds (HP fractions in (0, 1)) that
                          fired this tick. Empty tuple if none fired.
        phase_advanced:   True the single tick the boss crosses its
                          phase-2 HP threshold.
        defeated:         True the single tick the boss is detected dead
                          (HP<=0 or sprite no longer ``alive()``).
    """

    __slots__ = ("new_waves", "phase_advanced", "defeated")

    def __init__(self, new_waves=(), phase_advanced=False, defeated=False):
        self.new_waves = tuple(new_waves)
        self.phase_advanced = bool(phase_advanced)
        self.defeated = bool(defeated)


class BossController:
    """Pure orchestrator for a mini-boss encounter.

    The controller tracks a boss reference (any sprite with
    ``current_hp`` / ``max_hp`` and the standard ``alive()`` method) and
    converts HP transitions into one-shot events:

    * **wave thresholds** — list of HP fractions (descending). Each
      threshold fires the first tick the boss's HP ratio drops to or
      below it. Useful for spawning add waves.
    * **phase threshold** — single HP fraction (default 0.5) that fires
      a one-shot phase-2 transition. Use for unlocking new attacks.
    * **defeated** — fires the single tick the boss is detected dead.

    The controller is intentionally biome-agnostic: it owns NO behaviour,
    only state. The caller (room logic) reads the returned
    :class:`BossEvents` and decides what to do — spawn enemies, unseal
    portals, drop loot, etc.
    """

    def __init__(
        self,
        boss,
        *,
        name="",
        wave_thresholds=(0.75, 0.5, 0.25),
        phase_threshold=0.5,
    ):
        self.boss = boss
        self.name = str(name)
        # Sort high→low so we always fire in damage order.
        self.wave_thresholds = tuple(
            sorted((float(t) for t in wave_thresholds), reverse=True)
        )
        self.phase_threshold = float(phase_threshold)
        self.fired_waves: set = set()
        self.current_phase = 1
        self.defeated = False

    @property
    def hp_ratio(self) -> float:
        max_hp = max(1, int(getattr(self.boss, "max_hp", 1)))
        cur = max(0, int(getattr(self.boss, "current_hp", 0)))
        return cur / max_hp

    def update(self) -> BossEvents:
        ratio = self.hp_ratio
        new_waves = []
        for thr in self.wave_thresholds:
            if thr in self.fired_waves:
                continue
            if ratio <= thr:
                self.fired_waves.add(thr)
                new_waves.append(thr)

        phase_advanced = False
        if self.current_phase < 2 and ratio <= self.phase_threshold:
            self.current_phase = 2
            phase_advanced = True

        defeated_now = False
        if not self.defeated:
            alive_fn = getattr(self.boss, "alive", None)
            is_alive = alive_fn() if callable(alive_fn) else True
            if ratio <= 0 or not is_alive:
                self.defeated = True
                defeated_now = True

        return BossEvents(
            new_waves=tuple(new_waves),
            phase_advanced=phase_advanced,
            defeated=defeated_now,
        )


# ── Phase A: Ice Avalanche Run cover entity ───────────────────────────────────

class IcePillar(pygame.sprite.Sprite):
    """Shatterable cover object for the Ice Avalanche Run room.

    A frosty rectangular block that occupies one grid cell.  It has
    ``ICE_PILLAR_HP`` hit points and is destroyed on reaching 0.  While
    standing it blocks both the player and boulders (handled by the
    runtime's wall-rect builder — ``get_wall_rects()`` includes the pillar
    rect when the pillar is alive).  On death it leaves a one-frame flash
    then disappears.

    The pillar is registered in the runtime by an ``"ice_pillar"`` config
    entry in ``room.objective_entity_configs``.

    Attributes
    ----------
    alive : bool
        True while the pillar has HP > 0.
    hp : int
        Remaining hit points.
    """

    def __init__(self, x, y):
        from settings import ICE_PILLAR_HP, ICE_PILLAR_SIZE, COLOR_ICE_PILLAR
        super().__init__()
        self._hp = ICE_PILLAR_HP
        self._size = ICE_PILLAR_SIZE
        self._color = COLOR_ICE_PILLAR
        self._shatter_color = (220, 240, 255)
        self._destroyed_at = None
        self.image = make_rect_surface(self._size, self._size, self._color)
        self.rect = self.image.get_rect(center=(int(x), int(y)))

    # ── public API ────────────────────────────────────────────────────────

    @property
    def hp(self):
        return self._hp

    @property
    def alive(self):
        return self._hp > 0

    def take_damage(self, amount):
        """Reduce HP by *amount*.  Returns True if the pillar was destroyed."""
        if self._hp <= 0:
            return False
        self._hp = max(0, self._hp - amount)
        if self._hp == 0:
            self._on_destroy()
            return True
        # Tint darker to show damage.
        ratio = self._hp / ICE_PILLAR_HP if (
            "ICE_PILLAR_HP" in dir()
        ) else self._hp / 30
        from settings import ICE_PILLAR_HP as _MAX
        ratio = self._hp / _MAX
        r, g, b = self._color
        tinted = (max(60, int(r * ratio)), max(60, int(g * ratio)), max(80, int(b * ratio)))
        self.image = make_rect_surface(self._size, self._size, tinted)
        return False

    def _on_destroy(self):
        from settings import ICE_PILLAR_SIZE
        self.image = make_rect_surface(ICE_PILLAR_SIZE, ICE_PILLAR_SIZE, self._shatter_color)

    def update(self, now_ticks=None):
        """Kill the sprite one frame after destruction (flash visible for 1 frame)."""
        if self._hp <= 0:
            if self._destroyed_at is None:
                import pygame as _pg
                self._destroyed_at = _pg.time.get_ticks()
            elif now_ticks is not None and now_ticks - self._destroyed_at > 50:
                self.kill()

    def draw_overlay(self, surface, camera_offset=(0, 0)):
        """Draw HP pip indicators above the pillar when damaged."""
        from settings import ICE_PILLAR_HP as _MAX
        if self._hp <= 0 or self._hp >= _MAX:
            return
        ox, oy = camera_offset
        x = self.rect.centerx - ox - 12
        y = self.rect.top - oy - 6
        pip_w = 5
        for i in range(_MAX // 10):
            color = self._color if i < self._hp // 10 else (50, 50, 80)
            pygame.draw.rect(surface, color, (x + i * (pip_w + 1), y, pip_w, 3))


class SentryBlocker(pygame.sprite.Sprite):
    """Impassable column that blocks sentry line-of-sight in stealth rooms.

    Unlike IcePillar, SentryBlocker is indestructible.  It exists solely to
    create cover the player can hide behind to avoid the sentry's vision cone.
    It is registered in the dungeon via a ``"sentry_blocker"`` config entry and
    spawned into ``dungeon.objective_group``.

    Attributes
    ----------
    alive : bool
        Always True — blockers are never destroyed.
    """

    def __init__(self, x, y):
        from settings import SENTRY_BLOCKER_SIZE, COLOR_SENTRY_BLOCKER
        super().__init__()
        self._size = SENTRY_BLOCKER_SIZE
        self._color = COLOR_SENTRY_BLOCKER
        self.image = make_rect_surface(self._size, self._size, self._color)
        self.rect = self.image.get_rect(center=(int(x), int(y)))

    @property
    def alive(self):
        return True

    def take_damage(self, amount):
        return False

    def update(self, now_ticks=None):
        pass


# ── Pact Shrine ──────────────────────────────────────────────────────────────
_PACT_SHRINE_COLOR = (160, 40, 80)           # deep crimson
_PACT_SHRINE_CONSUMED_COLOR = (70, 50, 60)   # spent / ash grey


class PactShrine(pygame.sprite.Sprite):
    """An interactive shrine that lets the player choose and commit a Pact.

    Visual: a 26×26 crimson square drawn in the objective layer.  Turns
    grey once the pact has been consumed.  Registered via a
    ``"pact_shrine"`` config entry and tracked in ``dungeon.objective_group``.
    """

    SIZE = 26

    def __init__(self, x, y, consumed=False):
        super().__init__()
        self.consumed = consumed
        self._render()
        self.rect = self.image.get_rect(center=(int(x), int(y)))

    def _render(self):
        color = _PACT_SHRINE_CONSUMED_COLOR if self.consumed else _PACT_SHRINE_COLOR
        self.image = make_rect_surface(self.SIZE, self.SIZE, color)

    def mark_consumed(self):
        if not self.consumed:
            self.consumed = True
            self._render()

    def update(self, now_ticks=None):
        pass
