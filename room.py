"""Room: tile grid, terrain, walls/doors, enemy/chest spawn configs."""
import random
import pygame
from objective_metadata import (
    DEFAULT_ALTAR_VARIANT,
    DEFAULT_RELIC_VARIANT,
    get_altar_variant,
    get_relic_variant,
    pluralize_label,
)
from settings import (
    TILE_SIZE, ROOM_COLS, ROOM_ROWS, DOOR_WIDTH,
    COLOR_FLOOR, COLOR_WALL, COLOR_MUD, COLOR_ICE, COLOR_WATER,
    COLOR_DOOR, COLOR_PORTAL,
    ENEMY_MIN_PER_ROOM, ENEMY_MAX_PER_ROOM,
    CHEST_SPAWN_CHANCE,
    TERRAIN_PATCH_MIN, TERRAIN_PATCH_MAX,
    TERRAIN_PATCH_SIZE_MIN, TERRAIN_PATCH_SIZE_MAX,
)
from enemies import ENEMY_CLASSES

# tile type constants
FLOOR = "floor"
WALL  = "wall"
MUD   = "mud"
ICE   = "ice"
WATER = "water"
DOOR  = "door"
PORTAL = "portal"

TERRAIN_COLORS = {
    FLOOR:  COLOR_FLOOR,
    WALL:   COLOR_WALL,
    MUD:    COLOR_MUD,
    ICE:    COLOR_ICE,
    WATER:  COLOR_WATER,
    DOOR:   COLOR_DOOR,
    PORTAL: COLOR_PORTAL,
}

# terrain types that can be randomly placed (default pool)
_TERRAIN_POOL = [MUD, ICE, WATER]

_DEFAULT_PRESSURE_PLATE_OFFSETS = ((-5, -3), (5, -3), (0, 4), (0, -4))
_DEFAULT_ALARM_BEACON_OFFSETS = ((-4, -2), (4, -2), (0, 4), (0, -4))
_DEFAULT_ESCORT_SPAWN_OFFSET = (-6, 0)


class Room:
    """A single dungeon room stored as a ROOM_COLS×ROOM_ROWS tile grid."""

    def __init__(self, doors, is_exit=False, terrain_type=None,
                 enemy_count_range=None, enemy_type_weights=None,
                 room_plan=None):
        """
        Parameters
        ----------
        doors : dict  {direction_str: bool}
            Which side has a door.
        is_exit : bool
            Whether to place an exit portal in this room.
        terrain_type : str or None
            If given, only this terrain is used for patches (e.g. "mud").
            If None, patches are chosen randomly from the default pool.
        enemy_count_range : tuple(int, int) or None
            (min, max) enemies to spawn.  Falls back to settings defaults.
        enemy_type_weights : list[int] or None
            Weights for [PatrolEnemy, RandomEnemy, ChaserEnemy].
        """
        self.doors = dict(doors)  # copy
        self.is_exit = is_exit
        self._terrain_type = terrain_type
        self._enemy_count_range = enemy_count_range
        self._enemy_type_weights = enemy_type_weights
        self.room_plan = room_plan
        if self.room_plan is not None:
            if self.room_plan.terrain_type is not None:
                self._terrain_type = self.room_plan.terrain_type
            if self.room_plan.enemy_count_range is not None:
                self._enemy_count_range = self.room_plan.enemy_count_range
            if self.room_plan.enemy_type_weights:
                self._enemy_type_weights = self.room_plan.enemy_type_weights

        self._portal_cells = []
        self._portal_active = True
        self.objective_status = "inactive"
        self.objective_started_at = None
        self._reinforcement_spawned = False
        self._holdout_wave_index = 0
        self._holdout_progress_ms = 0
        self._holdout_last_tick = None
        self._resource_race_failed = False
        self._ritual_reaction_ids = set()
        self.objective_entity_configs = []

        # build grid
        self.grid = [[FLOOR] * ROOM_COLS for _ in range(ROOM_ROWS)]
        self._place_walls()
        self._place_doors()
        self._place_terrain()
        if is_exit:
            self._place_portal()
            if self.room_plan and self.room_plan.objective_rule not in {"immediate", "avoid_alarm_zones"}:
                self._set_portal_active(False)

        # spawn configs (created once, enemies re-instantiated on each visit)
        self.enemy_configs = self._gen_enemy_configs()
        self._build_objective_configs()

        # chest
        self.chest_pos = None  # (px, py) or None
        self.chest_looted = False
        chest_spawn_chance = CHEST_SPAWN_CHANCE
        if self.room_plan and self.room_plan.chest_spawn_chance is not None:
            chest_spawn_chance = self.room_plan.chest_spawn_chance
        if self.room_plan and self.room_plan.guaranteed_chest:
            self.chest_pos = self._random_floor_pos(margin=3)
        elif random.random() < chest_spawn_chance:
            self.chest_pos = self._random_floor_pos(margin=3)

    # ── grid helpers ────────────────────────────────────
    def tile_at(self, col, row):
        if 0 <= col < ROOM_COLS and 0 <= row < ROOM_ROWS:
            return self.grid[row][col]
        return WALL

    def terrain_at_pixel(self, px, py):
        """Return the terrain string at a pixel coordinate."""
        col = int(px) // TILE_SIZE
        row = int(py) // TILE_SIZE
        t = self.tile_at(col, row)
        if t in (FLOOR, MUD, ICE, WATER, DOOR, PORTAL):
            return t if t in (MUD, ICE, WATER) else "floor"
        return "floor"

    def get_wall_rects(self):
        """Return a list of pygame.Rects for all WALL tiles."""
        walls = []
        for r in range(ROOM_ROWS):
            for c in range(ROOM_COLS):
                if self.grid[r][c] == WALL:
                    walls.append(pygame.Rect(c * TILE_SIZE, r * TILE_SIZE,
                                             TILE_SIZE, TILE_SIZE))
        return walls

    # ── door centre positions (pixel) ───────────────────
    def door_pixel_pos(self, direction):
        """Return (px, py) at the door opening for *direction*."""
        mid_col = ROOM_COLS // 2
        mid_row = ROOM_ROWS // 2
        if direction == "top":
            return mid_col * TILE_SIZE + TILE_SIZE // 2, TILE_SIZE // 2
        if direction == "bottom":
            return (mid_col * TILE_SIZE + TILE_SIZE // 2,
                    (ROOM_ROWS - 1) * TILE_SIZE + TILE_SIZE // 2)
        if direction == "left":
            return TILE_SIZE // 2, mid_row * TILE_SIZE + TILE_SIZE // 2
        if direction == "right":
            return ((ROOM_COLS - 1) * TILE_SIZE + TILE_SIZE // 2,
                    mid_row * TILE_SIZE + TILE_SIZE // 2)

    # ── private builders ────────────────────────────────
    def _place_walls(self):
        for c in range(ROOM_COLS):
            self.grid[0][c] = WALL
            self.grid[ROOM_ROWS - 1][c] = WALL
        for r in range(ROOM_ROWS):
            self.grid[r][0] = WALL
            self.grid[r][ROOM_COLS - 1] = WALL

    def _place_doors(self):
        mid_col = ROOM_COLS // 2
        mid_row = ROOM_ROWS // 2
        half = DOOR_WIDTH // 2
        if self.doors.get("top"):
            for dc in range(-half, half + 1):
                self.grid[0][mid_col + dc] = DOOR
        if self.doors.get("bottom"):
            for dc in range(-half, half + 1):
                self.grid[ROOM_ROWS - 1][mid_col + dc] = DOOR
        if self.doors.get("left"):
            for dr in range(-half, half + 1):
                self.grid[mid_row + dr][0] = DOOR
        if self.doors.get("right"):
            for dr in range(-half, half + 1):
                self.grid[mid_row + dr][ROOM_COLS - 1] = DOOR

    def _place_terrain(self):
        if self.room_plan and self.room_plan.terrain_patch_count_range:
            count_lo, count_hi = self.room_plan.terrain_patch_count_range
        else:
            count_lo, count_hi = TERRAIN_PATCH_MIN, TERRAIN_PATCH_MAX
        if self.room_plan and self.room_plan.terrain_patch_size_range:
            size_lo, size_hi = self.room_plan.terrain_patch_size_range
        else:
            size_lo, size_hi = TERRAIN_PATCH_SIZE_MIN, TERRAIN_PATCH_SIZE_MAX

        count = random.randint(count_lo, count_hi)
        for _ in range(count):
            if self._terrain_type:
                kind = self._terrain_type
            else:
                kind = random.choice(_TERRAIN_POOL)
            w = random.randint(size_lo, size_hi)
            h = random.randint(size_lo, size_hi)
            sc = random.randint(2, ROOM_COLS - 2 - w)
            sr = random.randint(2, ROOM_ROWS - 2 - h)
            for r in range(sr, min(sr + h, ROOM_ROWS - 1)):
                for c in range(sc, min(sc + w, ROOM_COLS - 1)):
                    if self.grid[r][c] == FLOOR:
                        self.grid[r][c] = kind

        if self.room_plan and self.room_plan.clear_center:
            self._clear_center_arena()

    def _place_portal(self):
        cx, cy = ROOM_COLS // 2, ROOM_ROWS // 2
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                r, c = cy + dr, cx + dc
                if 0 < r < ROOM_ROWS - 1 and 0 < c < ROOM_COLS - 1:
                    self.grid[r][c] = PORTAL
                    self._portal_cells.append((r, c))

    def _clear_center_arena(self):
        cx, cy = ROOM_COLS // 2, ROOM_ROWS // 2
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                r, c = cy + dr, cx + dc
                if 0 < r < ROOM_ROWS - 1 and 0 < c < ROOM_COLS - 1:
                    if self.grid[r][c] not in {DOOR, PORTAL}:
                        self.grid[r][c] = FLOOR

    def _set_portal_active(self, active):
        self._portal_active = active
        tile = PORTAL if active else FLOOR
        for r, c in self._portal_cells:
            self.grid[r][c] = tile

    def on_enter(self, now_ticks):
        if not self.is_exit or self.room_plan is None:
            return

        if self.objective_status == "completed":
            self._set_portal_active(True)
            return

        self.objective_status = "active"
        if (
            self.room_plan.objective_rule in {"holdout_timer", "claim_relic_before_lockdown"}
            and self.objective_started_at is None
        ):
            self.objective_started_at = now_ticks
            if self.room_plan.objective_rule == "holdout_timer":
                self._holdout_last_tick = now_ticks
        elif self.room_plan.objective_rule == "loot_then_timer" and self.chest_looted:
            if self.objective_started_at is None:
                self.objective_started_at = now_ticks
            self._set_portal_active(True)

    def notify_chest_opened(self, now_ticks):
        if self.room_plan is None:
            return
        self.chest_looted = True
        if self.room_plan.objective_rule == "loot_then_timer":
            if self.objective_started_at is None:
                self.objective_started_at = now_ticks
            self.objective_status = "escape"
            self._set_portal_active(True)
        elif self.room_plan.objective_rule == "claim_relic_before_lockdown":
            if self.objective_started_at is None:
                self.objective_started_at = now_ticks
            self.objective_status = "completed"
            self._set_portal_active(True)

    def allows_chest_open(self, now_ticks):
        if self.room_plan is None:
            return True
        if self.room_plan.chest_locked_until_complete and self.objective_status != "completed":
            return False
        if self.room_plan.objective_rule != "claim_relic_before_lockdown":
            return True
        if self.chest_looted or self._resource_race_failed:
            return True
        return not self._resource_race_deadline_elapsed(now_ticks)

    def update_objective(self, now_ticks, enemy_group):
        if not self.is_exit or self.room_plan is None:
            return None

        rule = self.room_plan.objective_rule
        if rule == "immediate":
            self.objective_status = "completed"
            self._set_portal_active(True)
            return None

        if rule == "holdout_timer":
            if self.objective_started_at is None:
                self.objective_started_at = now_ticks
                self._holdout_last_tick = now_ticks

            holdout_zone = self._holdout_zone_config()
            if holdout_zone is not None:
                if self._holdout_last_tick is None:
                    self._holdout_last_tick = now_ticks
                delta_ms = max(0, now_ticks - self._holdout_last_tick)
                self._holdout_last_tick = now_ticks
                if holdout_zone.get("occupied"):
                    self._holdout_progress_ms += delta_ms
                elapsed_ms = self._holdout_progress_ms
            else:
                elapsed_ms = now_ticks - self.objective_started_at

            duration = self.room_plan.objective_duration_ms or 0
            if elapsed_ms >= duration:
                self.objective_status = "completed"
                self._set_portal_active(True)
            else:
                self.objective_status = "active"
                self._set_portal_active(False)
                holdout_update = self._maybe_spawn_holdout_wave(elapsed_ms)
                if holdout_update is not None:
                    return holdout_update
            return None

        if rule == "charge_plates":
            if self.remaining_puzzle_plates() == 0:
                self.objective_status = "completed"
                self._set_portal_active(True)
            else:
                self.objective_status = "active"
                self._set_portal_active(False)
            return None

        if rule in {"escort_to_exit", "escort_bomb_to_exit"}:
            escort = self._escort_config()
            if escort is None:
                self.objective_status = "completed"
                self._set_portal_active(True)
            elif escort.get("reached_exit"):
                self.objective_status = "completed"
                self._set_portal_active(True)
            elif escort.get("destroyed"):
                if len(enemy_group) == 0:
                    self.objective_status = "completed"
                    self._set_portal_active(True)
                else:
                    self.objective_status = (
                        "carrier_down" if rule == "escort_bomb_to_exit" else "escort_down"
                    )
                    self._set_portal_active(False)
            else:
                self.objective_status = "active"
                self._set_portal_active(False)
            return None

        if rule == "avoid_alarm_zones":
            if not self._has_triggered_alarm_beacon():
                self.objective_status = "active"
                self._set_portal_active(True)
                return None

            self.objective_status = "alarm"
            self._set_portal_active(False)
            if not self._reinforcement_spawned:
                reinforcements = self._spawn_reinforcement_wave()
                self._reinforcement_spawned = True
                self.enemy_configs.extend(reinforcements)
                return {"kind": "spawn_reinforcements", "enemy_configs": reinforcements}
            if len(enemy_group) == 0:
                self.objective_status = "completed"
                self._set_portal_active(True)
            return None

        if rule == "claim_relic_before_lockdown":
            if self.objective_started_at is None:
                self.objective_started_at = now_ticks

            if not self.chest_looted and not self._resource_race_failed:
                if self._resource_race_deadline_elapsed(now_ticks):
                    self._resource_race_failed = True
                    self.chest_looted = True
                    self.objective_status = "lost_race"
                    self._set_portal_active(False)
                    return {"kind": "forfeit_chest"}

                self.objective_status = "active"
                self._set_portal_active(False)
                return None

            if self._resource_race_failed:
                if len(enemy_group) == 0:
                    self.objective_status = "completed"
                    self._set_portal_active(True)
                else:
                    self.objective_status = "lost_race"
                    self._set_portal_active(False)
                return None

            self.objective_status = "completed"
            self._set_portal_active(True)
            return None

        if rule == "clear_enemies":
            if len(enemy_group) == 0:
                self.objective_status = "completed"
                self.enemy_configs = []
                self._set_portal_active(True)
            else:
                self.objective_status = "active"
                self._set_portal_active(False)
            return None

        if rule == "destroy_altars":
            remaining_altars = self.remaining_objective_entities()
            if remaining_altars == 0:
                self.objective_status = "completed"
                self._set_portal_active(True)
                payoff_update = self._complete_ritual_payoff()
                if payoff_update is not None:
                    return payoff_update
            else:
                ritual_update = self._maybe_trigger_ritual_reaction()
                self.objective_status = "active"
                self._set_portal_active(False)
                if ritual_update is not None:
                    return ritual_update
            return None

        if rule == "loot_then_timer":
            if not self.chest_looted:
                self.objective_status = "active"
                self._set_portal_active(False)
                return

            if self.objective_started_at is None:
                self.objective_started_at = now_ticks
            duration = self.room_plan.objective_duration_ms or 0
            if duration and now_ticks - self.objective_started_at > duration:
                self.objective_status = "overtime"
                if not self._reinforcement_spawned:
                    reinforcements = self._spawn_reinforcement_wave()
                    self._reinforcement_spawned = True
                    self.enemy_configs.extend(reinforcements)
                    self._set_portal_active(True)
                    return {"kind": "spawn_reinforcements", "enemy_configs": reinforcements}
            else:
                self.objective_status = "escape"
            self._set_portal_active(True)
        return None

    def objective_target_info(self, origin_px=None):
        if not self.is_exit or self.room_plan is None:
            return None

        rule = self.room_plan.objective_rule
        if rule == "destroy_altars":
            if self._ritual_payoff_available():
                return self._ritual_payoff_label(), self.chest_pos

            active_altars = [
                config for config in self.objective_entity_configs if not config["destroyed"]
            ]
            if active_altars:
                target_pool = [config for config in active_altars if not config.get("invulnerable")]
                if not target_pool:
                    target_pool = active_altars
                target = self._nearest_target(origin_px, [config["pos"] for config in target_pool])
                return self._altar_label(), target
            return "Exit", self._portal_center_pixel()

        if rule == "holdout_timer":
            holdout_zone = self._holdout_zone_config()
            if holdout_zone is not None and self.objective_status != "completed":
                return holdout_zone.get("label", "Holdout"), holdout_zone["pos"]
            return "Exit", self._portal_center_pixel()

        if rule == "charge_plates":
            active_plates = [
                config for config in self.objective_entity_configs if not config["activated"]
            ]
            if active_plates:
                target = self._nearest_target(origin_px, [config["pos"] for config in active_plates])
                return self._plate_label(), target
            return "Exit", self._portal_center_pixel()

        if rule in {"escort_to_exit", "escort_bomb_to_exit"}:
            escort = self._escort_config()
            if escort and not escort.get("destroyed") and not escort.get("reached_exit"):
                return escort.get("label", "Escort"), escort["pos"]
            if self.objective_status == "completed":
                return "Exit", self._portal_center_pixel()
            return None

        if rule == "avoid_alarm_zones":
            return "Exit", self._portal_center_pixel()

        if rule == "claim_relic_before_lockdown":
            if not self.chest_looted and not self._resource_race_failed:
                return self._relic_label(), self.chest_pos
            if self._resource_race_failed:
                return None
            return "Exit", self._portal_center_pixel()

        if rule == "loot_then_timer":
            if not self.chest_looted:
                return self._relic_label(), self.chest_pos
            return "Exit", self._portal_center_pixel()

        return None

    def minimap_objective_marker(self):
        target_info = self.objective_target_info()
        if target_info is None:
            return None

        label, _target_pos = target_info
        rule = self.room_plan.objective_rule if self.room_plan else None
        if rule == "destroy_altars" and label != "Exit" and not self._ritual_payoff_available():
            return ("altar", label)
        if rule == "holdout_timer" and label != "Exit":
            return ("holdout", label)
        if rule in {"claim_relic_before_lockdown", "loot_then_timer"} and label != "Exit":
            return ("relic", label)
        if rule == "charge_plates" and label != "Exit":
            return ("puzzle", label)
        if rule in {"escort_to_exit", "escort_bomb_to_exit"} and label != "Exit":
            return ("escort", label)

        lower = label.lower()
        if lower in {"altar", "totem", "obelisk", "idol"}:
            return ("altar", label)
        if lower in {"holdout", "circle"}:
            return ("holdout", label)
        if lower in {"relic", "cache", "reliquary", "sarcophagus"}:
            return ("relic", label)
        if lower in {"seal", "plate", "plates"}:
            return ("puzzle", label)
        if lower in {"escort", "carrier"}:
            return ("escort", label)
        return ("exit", label)

    def objective_hud_state(self, now_ticks):
        if self.room_plan is None:
            return {"visible": False, "label": ""}

        rule = self.room_plan.objective_rule
        if rule == "holdout_timer" and self.is_exit and self.objective_status != "completed":
            started_at = self.objective_started_at or now_ticks
            elapsed_ms = self._holdout_progress_ms if self._holdout_zone_config() is not None else now_ticks - started_at
            remaining_ms = max(
                0,
                (self.room_plan.objective_duration_ms or 0) - elapsed_ms,
            )
            total_waves = len(self._holdout_wave_thresholds())
            wave_suffix = f" | Wave {self._holdout_wave_index}/{total_waves}" if total_waves else ""
            zone = self._holdout_zone_config()
            zone_suffix = ""
            if zone is not None and not zone.get("occupied"):
                zone_suffix = " | Return to circle"
            return {
                "visible": True,
                "label": f"Objective: Hold out {remaining_ms / 1000:.1f}s{wave_suffix}{zone_suffix}",
            }

        if rule == "charge_plates" and self.is_exit and self.objective_status != "completed":
            total = len(self.objective_entity_configs)
            activated = total - self.remaining_puzzle_plates()
            label = pluralize_label(self._plate_label()).lower()
            return {
                "visible": True,
                "label": f"Objective: Charge {label} {activated}/{total}",
            }

        if rule in {"escort_to_exit", "escort_bomb_to_exit"} and self.is_exit:
            escort = self._escort_config()
            if escort is None:
                return {"visible": False, "label": ""}
            escort_label = escort.get("label", "Carrier" if rule == "escort_bomb_to_exit" else "Escort")
            if escort.get("destroyed") and self.objective_status != "completed":
                return {"visible": True, "label": f"Objective: {escort_label} down, clear the room"}
            if escort.get("reached_exit") or self.objective_status == "completed":
                return {"visible": False, "label": ""}
            hp_label = f"HP {escort['current_hp']}/{escort['max_hp']}"
            if rule == "escort_bomb_to_exit" and escort.get("waiting_for_clearance"):
                return {"visible": True, "label": f"Objective: Clear a safe lane {hp_label}"}
            if rule == "escort_bomb_to_exit":
                return {"visible": True, "label": f"Objective: Guide {escort_label} {hp_label}"}
            return {"visible": True, "label": f"Objective: Protect {escort_label} {hp_label}"}

        if rule == "avoid_alarm_zones" and self.is_exit:
            if self._has_triggered_alarm_beacon() and self.objective_status != "completed":
                return {"visible": True, "label": "Objective: Alarm raised, clear the room"}
            return {"visible": True, "label": "Objective: Slip through unseen"}

        if rule == "claim_relic_before_lockdown" and self.is_exit:
            relic_label = self._relic_label().lower()
            if not self.chest_looted and not self._resource_race_failed:
                started_at = self.objective_started_at or now_ticks
                remaining_ms = max(
                    0,
                    (self.room_plan.objective_duration_ms or 0) - (now_ticks - started_at),
                )
                return {
                    "visible": True,
                    "label": f"Objective: Secure the {relic_label} {remaining_ms / 1000:.1f}s",
                }
            if self._resource_race_failed:
                return {"visible": True, "label": "Objective: Relic lost, clear the room"}
            return {"visible": True, "label": f"Objective: Escape with the {relic_label}"}

        if rule == "clear_enemies" and self.is_exit and self.objective_status != "completed":
            return {"visible": True, "label": "Objective: Break the ritual"}

        if rule == "destroy_altars" and self.is_exit and self._ritual_payoff_available():
            return {
                "visible": True,
                "label": f"Objective: Claim revealed {self._ritual_payoff_label().lower()}",
            }

        if rule == "destroy_altars" and self.is_exit and self.objective_status != "completed":
            label = pluralize_label(self._altar_label())
            pulse_suffix = " | Pulse active" if self._has_active_pulse(now_ticks) else ""
            summon_count = sum(
                1
                for config in self.objective_entity_configs
                if not config["destroyed"] and config.get("role") == "summon"
            )
            shielded_count = sum(
                1
                for config in self.objective_entity_configs
                if not config["destroyed"] and config.get("invulnerable")
            )
            summon_suffix = ""
            if summon_count:
                suffix = "s" if summon_count != 1 else ""
                summon_suffix = f" | {summon_count} summoner{suffix}"
            shield_suffix = ""
            if shielded_count:
                shield_suffix = f" | Break wards {shielded_count} shielded"
            return {
                "visible": True,
                "label": f"Objective: Destroy {self.remaining_objective_entities()} {label}{pulse_suffix}{summon_suffix}{shield_suffix}",
            }

        if rule == "loot_then_timer" and self.is_exit:
            relic_label = self._relic_label().lower()
            if not self.chest_looted:
                return {"visible": True, "label": f"Objective: Secure the {relic_label}"}
            if self.objective_started_at is not None and self.room_plan.objective_duration_ms:
                remaining_ms = max(
                    0,
                    self.room_plan.objective_duration_ms - (now_ticks - self.objective_started_at),
                )
                if remaining_ms > 0:
                    return {
                        "visible": True,
                        "label": f"Objective: Escape {remaining_ms / 1000:.1f}s",
                    }
            if self.objective_status == "overtime":
                return {"visible": True, "label": "Objective: Escape under pressure"}
            return {"visible": True, "label": f"Objective: Escape with the {relic_label}"}

        if self.is_exit and rule == "immediate" and self.room_plan.room_id != "standard_combat":
            return {"visible": True, "label": f"Objective: {self.room_plan.display_name}"}

        return {"visible": False, "label": ""}

    def _spawn_reinforcement_wave(self):
        return self._gen_enemy_configs_for_range((2, 2))

    def _maybe_spawn_holdout_wave(self, elapsed_ms):
        thresholds = self._holdout_wave_thresholds()
        if self._holdout_wave_index >= len(thresholds):
            return None
        if elapsed_ms < thresholds[self._holdout_wave_index]:
            return None

        wave_sizes = self._holdout_wave_sizes()
        wave_size = wave_sizes[self._holdout_wave_index]
        enemy_configs = self._gen_enemy_configs_for_range((wave_size, wave_size))
        self.enemy_configs.extend(enemy_configs)
        self._holdout_wave_index += 1
        return {
            "kind": "spawn_enemies",
            "source": "holdout_timer",
            "enemy_configs": enemy_configs,
        }

    def _holdout_wave_thresholds(self):
        duration = self.room_plan.objective_duration_ms if self.room_plan else None
        if not duration:
            return ()
        wave_sizes = self._holdout_wave_sizes()
        if not wave_sizes:
            return ()
        segment_count = len(wave_sizes) + 1
        return tuple((duration * (index + 1)) // segment_count for index in range(len(wave_sizes)))

    def _resource_race_deadline_elapsed(self, now_ticks):
        duration = self.room_plan.objective_duration_ms if self.room_plan else None
        if self.objective_started_at is None or not duration:
            return False
        return now_ticks - self.objective_started_at >= duration

    def escort_allows_advance(self, enemy_group):
        if self.room_plan is None:
            return True
        if self.room_plan.objective_rule != "escort_bomb_to_exit":
            return True
        escort = self._escort_config()
        if escort is None or escort.get("destroyed") or escort.get("reached_exit"):
            return False
        return len(enemy_group) == 0

    def portal_center_pixel(self):
        return self._portal_center_pixel()

    def _has_triggered_alarm_beacon(self):
        return any(config.get("triggered") for config in self.objective_entity_configs)

    def _escort_config(self):
        for config in self.objective_entity_configs:
            if config.get("kind") == "escort_npc":
                return config
        return None

    def _holdout_zone_config(self):
        for config in self.objective_entity_configs:
            if config.get("kind") == "holdout_zone":
                return config
        return None

    def remaining_objective_entities(self):
        return sum(1 for config in self.objective_entity_configs if not config["destroyed"])

    def remaining_puzzle_plates(self):
        return sum(1 for config in self.objective_entity_configs if not config.get("activated"))

    def _build_objective_configs(self):
        if self.room_plan is None:
            return
        if self.room_plan.objective_rule == "destroy_altars":
            variant_id = self.room_plan.objective_variant or DEFAULT_ALTAR_VARIANT
            variant = get_altar_variant(variant_id)
            role_script = self.room_plan.ritual_role_script or ()
            self.objective_entity_configs = [
                {
                    "kind": "altar",
                    "variant_id": variant_id,
                    "label": variant["label"],
                    "role": self._ritual_role_for_index(index, role_script),
                    "pos": pos,
                    "max_hp": self._altar_max_hp_for_role(variant, self._ritual_role_for_index(index, role_script)),
                    "current_hp": self._altar_max_hp_for_role(variant, self._ritual_role_for_index(index, role_script)),
                    "pulse_radius": self._altar_pulse_radius_for_role(variant, self._ritual_role_for_index(index, role_script)),
                    "pulse_damage": self._altar_pulse_damage_for_role(variant, self._ritual_role_for_index(index, role_script)),
                    "pulse_cycle_ms": variant["pulse_cycle_ms"],
                    "pulse_active_ms": self._altar_pulse_active_ms_for_role(variant, self._ritual_role_for_index(index, role_script)),
                    "pulse_offset_ms": index * variant["pulse_stagger_ms"],
                    "reinforcement_count": self.room_plan.ritual_reinforcement_count,
                    "reaction_id": index,
                    "invulnerable": False,
                    "destroyed": False,
                }
                for index, pos in enumerate(self._altar_positions(self.room_plan.objective_entity_count or 3))
            ]
            self._refresh_ritual_links()
        elif self.room_plan.objective_rule == "holdout_timer" and self.room_plan.holdout_zone_radius > 0:
            self.objective_entity_configs = [
                {
                    "kind": "holdout_zone",
                    "label": "Holdout",
                    "pos": self._portal_center_pixel(),
                    "radius": self.room_plan.holdout_zone_radius,
                    "occupied": False,
                }
            ]
        elif self.room_plan.objective_rule == "charge_plates":
            plate_positions = self._objective_positions(
                self.room_plan.objective_layout_offsets,
                _DEFAULT_PRESSURE_PLATE_OFFSETS,
                self.room_plan.objective_entity_count or 3,
            )
            self.objective_entity_configs = [
                {
                    "kind": "pressure_plate",
                    "label": self._plate_label(),
                    "pos": pos,
                    "trigger_padding": self.room_plan.objective_trigger_padding or 10,
                    "activated": False,
                }
                for pos in plate_positions
            ]
        elif self.room_plan.objective_rule in {"escort_to_exit", "escort_bomb_to_exit"}:
            requires_safe_path = self.room_plan.objective_rule == "escort_bomb_to_exit"
            default_label = "Carrier" if requires_safe_path else "Escort"
            max_hp = self.room_plan.objective_max_hp or (26 if requires_safe_path else 22)
            speed = self.room_plan.objective_move_speed or (1.0 if requires_safe_path else 1.2)
            guide_radius = self.room_plan.objective_guide_radius or 92
            exit_radius = self.room_plan.objective_exit_radius or 24
            damage_cooldown_ms = self.room_plan.objective_damage_cooldown_ms or 500
            self.objective_entity_configs = [
                {
                    "kind": "escort_npc",
                    "label": self.room_plan.objective_label or default_label,
                    "pos": self._spawn_position_from_offset(
                        self.room_plan.objective_spawn_offset,
                        _DEFAULT_ESCORT_SPAWN_OFFSET,
                    ),
                    "max_hp": max_hp,
                    "current_hp": max_hp,
                    "speed": speed,
                    "guide_radius": guide_radius,
                    "exit_radius": exit_radius,
                    "reached_exit": False,
                    "destroyed": False,
                    "requires_safe_path": requires_safe_path,
                    "waiting_for_clearance": False,
                    "damage_cooldown_ms": damage_cooldown_ms,
                    "damage_cooldown_until": 0,
                }
            ]
        elif self.room_plan.objective_rule == "avoid_alarm_zones":
            beacon_positions = self._objective_positions(
                self.room_plan.objective_layout_offsets,
                _DEFAULT_ALARM_BEACON_OFFSETS,
                self.room_plan.objective_entity_count or 3,
            )
            self.objective_entity_configs = [
                {
                    "kind": "alarm_beacon",
                    "label": self.room_plan.objective_label or "Alarm",
                    "pos": pos,
                    "radius": self.room_plan.objective_radius or 34,
                    "triggered": False,
                }
                for pos in beacon_positions
            ]

    def _altar_positions(self, count=3):
        cx, cy = ROOM_COLS // 2, ROOM_ROWS // 2
        offsets = ((-2, 0), (2, 0), (0, 2), (0, -2), (-4, 2), (4, 2))
        positions = []
        for dc, dr in offsets[: max(1, min(count, len(offsets)))]:
            col = cx + dc
            row = cy + dr
            positions.append(
                (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)
            )
        return tuple(positions)

    def _objective_positions(self, scripted_offsets, default_offsets, count):
        if scripted_offsets:
            offsets = scripted_offsets[:count] if count else scripted_offsets
        else:
            offsets = default_offsets[: max(1, min(count, len(default_offsets)))]
        positions = []
        for offset in offsets:
            positions.append(self._offset_to_pixel(offset))
        return tuple(positions)

    def _spawn_position_from_offset(self, scripted_offset, default_offset):
        offset = scripted_offset or default_offset
        col = max(1, min(ROOM_COLS - 2, ROOM_COLS // 2 + offset[0]))
        row = max(1, min(ROOM_ROWS - 2, ROOM_ROWS // 2 + offset[1]))
        if self.grid[row][col] != WALL:
            return (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)
        return self._random_floor_pos(margin=4)

    @staticmethod
    def _offset_to_pixel(offset):
        col = ROOM_COLS // 2 + offset[0]
        row = ROOM_ROWS // 2 + offset[1]
        return (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)

    def _holdout_wave_sizes(self):
        if self.room_plan is None or self.room_plan.objective_rule != "holdout_timer":
            return ()
        return self.room_plan.scripted_wave_sizes or (1, 2)

    def _maybe_trigger_ritual_reaction(self):
        if self.room_plan is None or self.room_plan.objective_rule != "destroy_altars":
            return None

        enemy_configs = []
        for config in self.objective_entity_configs:
            if not config.get("destroyed"):
                continue

            reaction_id = config.get("reaction_id")
            if reaction_id in self._ritual_reaction_ids:
                continue
            self._ritual_reaction_ids.add(reaction_id)

            role = config.get("role")
            if role == "summon":
                count = max(0, config.get("reinforcement_count", 0))
                if count:
                    enemy_configs.extend(self._gen_enemy_configs_for_range((count, count)))
            elif role == "ward":
                self._empower_remaining_altars()

        self._refresh_ritual_links()

        if not enemy_configs:
            return None

        self.enemy_configs.extend(enemy_configs)
        return {
            "kind": "spawn_enemies",
            "source": "ritual_reaction",
            "enemy_configs": enemy_configs,
        }

    def _empower_remaining_altars(self):
        for config in self.objective_entity_configs:
            if config.get("kind") != "altar" or config.get("destroyed"):
                continue
            config["pulse_radius"] += 8
            config["pulse_damage"] += 1

    def _refresh_ritual_links(self):
        link_mode = self.room_plan.ritual_link_mode if self.room_plan else ""
        live_wards = any(
            config.get("kind") == "altar"
            and not config.get("destroyed")
            and config.get("role") == "ward"
            for config in self.objective_entity_configs
        )
        for config in self.objective_entity_configs:
            if config.get("kind") != "altar" or config.get("destroyed"):
                continue
            if link_mode == "ward_shields_others" and live_wards and config.get("role") != "ward":
                config["invulnerable"] = True
            else:
                config["invulnerable"] = False

    def _complete_ritual_payoff(self):
        if self.room_plan is None or self.room_plan.ritual_payoff_kind != "reveal_reliquary":
            return None
        if self.chest_pos is not None:
            return None

        self.chest_pos = self._random_floor_pos(margin=3)
        self.chest_looted = False
        return {
            "kind": "spawn_reward_chest",
            "position": self.chest_pos,
            "reward_tier": self.room_plan.reward_tier,
        }

    def _ritual_payoff_available(self):
        return (
            self.room_plan is not None
            and self.room_plan.objective_rule == "destroy_altars"
            and self.objective_status == "completed"
            and self.room_plan.ritual_payoff_kind == "reveal_reliquary"
            and self.chest_pos is not None
            and not self.chest_looted
        )

    @staticmethod
    def _ritual_role_for_index(index, role_script):
        if not role_script:
            return "pulse"
        return role_script[index % len(role_script)]

    @staticmethod
    def _altar_max_hp_for_role(variant, role):
        if role == "ward":
            return variant["max_hp"] + 4
        if role == "summon":
            return max(1, variant["max_hp"] - 2)
        return variant["max_hp"]

    @staticmethod
    def _altar_pulse_radius_for_role(variant, role):
        if role == "pulse":
            return variant["pulse_radius"] + 10
        return variant["pulse_radius"]

    @staticmethod
    def _altar_pulse_damage_for_role(variant, role):
        if role == "pulse":
            return variant["pulse_damage"] + 1
        return variant["pulse_damage"]

    @staticmethod
    def _altar_pulse_active_ms_for_role(variant, role):
        if role == "ward":
            return min(variant["pulse_cycle_ms"], variant["pulse_active_ms"] + variant["pulse_stagger_ms"])
        return variant["pulse_active_ms"]

    def _portal_center_pixel(self):
        if not self._portal_cells:
            return (
                ROOM_COLS // 2 * TILE_SIZE + TILE_SIZE // 2,
                ROOM_ROWS // 2 * TILE_SIZE + TILE_SIZE // 2,
            )

        avg_row = sum(row for row, _col in self._portal_cells) / len(self._portal_cells)
        avg_col = sum(col for _row, col in self._portal_cells) / len(self._portal_cells)
        return (
            int(avg_col * TILE_SIZE + TILE_SIZE // 2),
            int(avg_row * TILE_SIZE + TILE_SIZE // 2),
        )

    @staticmethod
    def _nearest_target(origin_px, targets):
        if origin_px is None or not targets:
            return targets[0] if targets else None
        return min(
            targets,
            key=lambda target: (target[0] - origin_px[0]) ** 2 + (target[1] - origin_px[1]) ** 2,
        )

    def _has_active_pulse(self, now_ticks):
        return any(
            not config["destroyed"] and self._pulse_active(config, now_ticks)
            for config in self.objective_entity_configs
        )

    @staticmethod
    def _pulse_active(config, now_ticks):
        cycle_ms = config.get("pulse_cycle_ms")
        active_ms = config.get("pulse_active_ms")
        if not cycle_ms or not active_ms:
            return False
        elapsed = max(0, now_ticks + config.get("pulse_offset_ms", 0))
        return elapsed % cycle_ms < active_ms

    def _altar_label(self):
        if self.objective_entity_configs:
            return self.objective_entity_configs[0].get("label", "Altar")
        variant_id = self.room_plan.objective_variant if self.room_plan else DEFAULT_ALTAR_VARIANT
        return get_altar_variant(variant_id or DEFAULT_ALTAR_VARIANT)["label"]

    def _ritual_payoff_label(self):
        if self.room_plan and self.room_plan.ritual_payoff_label:
            return self.room_plan.ritual_payoff_label
        return "Reliquary"

    def _plate_label(self):
        if self.objective_entity_configs:
            return self.objective_entity_configs[0].get("label", "Seal")
        if self.room_plan and self.room_plan.objective_label:
            return self.room_plan.objective_label
        return "Seal"

    def _relic_label(self):
        variant_id = self.room_plan.objective_variant if self.room_plan else DEFAULT_RELIC_VARIANT
        return get_relic_variant(variant_id or DEFAULT_RELIC_VARIANT)["label"]

    def _random_floor_pos(self, margin=3):
        """Return a (px, py) on a FLOOR tile at least *margin* tiles from edges."""
        for _ in range(200):
            c = random.randint(margin, ROOM_COLS - 1 - margin)
            r = random.randint(margin, ROOM_ROWS - 1 - margin)
            if self.grid[r][c] == FLOOR:
                return (c * TILE_SIZE + TILE_SIZE // 2,
                        r * TILE_SIZE + TILE_SIZE // 2)
        # fallback: center
        return (ROOM_COLS // 2 * TILE_SIZE + TILE_SIZE // 2,
                ROOM_ROWS // 2 * TILE_SIZE + TILE_SIZE // 2)

    def _gen_enemy_configs(self):
        return self._gen_enemy_configs_for_range(self._enemy_count_range)

    def _gen_enemy_configs_for_range(self, enemy_count_range):
        if enemy_count_range:
            lo, hi = enemy_count_range
        else:
            lo, hi = ENEMY_MIN_PER_ROOM, ENEMY_MAX_PER_ROOM
        count = random.randint(lo, hi)
        configs = []
        for _ in range(count):
            if self._enemy_type_weights:
                cls = random.choices(
                    ENEMY_CLASSES, weights=self._enemy_type_weights, k=1
                )[0]
            else:
                cls = random.choice(ENEMY_CLASSES)
            pos = self._random_floor_pos(margin=4)
            configs.append((cls, pos))
        return configs
