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
    DIR_OFFSETS, OPPOSITE_DIR,
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
_DEFAULT_ESCORT_PLAYER_OFFSETS = ((1, 0), (0, 1), (0, -1), (-1, 0))
_DEFAULT_HOLDOUT_RELIEF_OFFSETS = ((-6, 0), (6, 0), (0, -6), (0, 6))
_DEFAULT_TRAP_LANE_OFFSETS = {
    2: (-3, 3),
    3: (-4, 0, 4),
    4: (-5, -2, 2, 5),
}
_REWARD_TIER_UPGRADES = {
    "standard": "branch_bonus",
    "branch_bonus": "finale_bonus",
    "finale_bonus": "finale_bonus",
}
_DEFAULT_HOLDOUT_RELIEF_COUNT = 1
_DEFAULT_HOLDOUT_RELIEF_DELAY_MS = 1500
_HOLDOUT_RELIEF_HUD_MS = 1600
_DEFAULT_PUZZLE_REINFORCEMENT_COUNT = 1
_PUZZLE_PENALTY_HUD_MS = 1600
_PUZZLE_PENALTY_FLASH_MS = 700
_PUZZLE_STALL_DURATION_MS = 2500
_STEALTH_SEARCH_WINDOW_MS = 2200


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
        self._resource_race_wave_index = 0
        self._resource_race_claimed_once = False
        self._resource_race_reclaim_started_at = None
        self._stealth_search_started_at = None
        self._stealth_lockdown_started = False
        self._timed_extraction_wave_index = 0
        self._ritual_reaction_ids = set()
        self.objective_entity_configs = []
        self._chest_reward_tier = room_plan.reward_tier if room_plan is not None else "standard"

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
        if self.room_plan and self.room_plan.room_id == "trap_gauntlet":
            self._carve_trap_gauntlet_lanes()

        # chest
        self.chest_pos = None  # (px, py) or None
        self.chest_looted = False
        chest_spawn_chance = CHEST_SPAWN_CHANCE
        if self.room_plan and self.room_plan.chest_spawn_chance is not None:
            chest_spawn_chance = self.room_plan.chest_spawn_chance
        if self.room_plan and self.room_plan.room_id == "trap_gauntlet":
            should_spawn_chest = bool(
                (self.room_plan and self.room_plan.guaranteed_chest)
                or random.random() < chest_spawn_chance
            )
            if should_spawn_chest:
                self.chest_pos = self._trap_reward_position()
        elif self.room_plan and self.room_plan.guaranteed_chest:
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

    def on_enter(self, now_ticks, *, entry_direction=None, player_position=None, room_test=False):
        if not self.is_exit or self.room_plan is None:
            return

        if self.objective_status == "completed":
            self._set_portal_active(True)
            return

        if self.objective_status == "inactive":
            self._position_escort_for_entry(
                entry_direction=entry_direction,
                player_position=player_position,
                room_test=room_test,
            )

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
            self._resource_race_claimed_once = True
            self._resource_race_reclaim_started_at = None
            self.objective_status = "escape"
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
        if self._resource_race_claimed_once:
            return True
        return not self._resource_race_deadline_elapsed(now_ticks)

    def update_objective(self, now_ticks, enemy_group):
        if self.room_plan is None:
            return None

        if self.room_plan.room_id == "trap_gauntlet":
            controller = self._trap_controller()
            if (
                controller is not None
                and controller.get("challenge_route_selected")
                and not controller.get("challenge_reward_applied")
                and not self.chest_looted
            ):
                controller["challenge_reward_applied"] = True
                self._chest_reward_tier = _REWARD_TIER_UPGRADES.get(
                    self._chest_reward_tier,
                    self._chest_reward_tier,
                )
                return {
                    "kind": "upgrade_reward_chest",
                    "reward_tier": self._chest_reward_tier,
                }
            return None

        if not self.is_exit:
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
                puzzle_update = self._maybe_trigger_puzzle_reaction(now_ticks)
                if puzzle_update is not None:
                    return puzzle_update
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
                self._stealth_search_started_at = None
                self.objective_status = "active"
                self._set_portal_active(True)
                return None

            search_window_ms = self._stealth_search_window_ms()
            triggered_count = self._alarm_trigger_count()
            if search_window_ms > 0 and not self._stealth_lockdown_started:
                if self._stealth_search_started_at is None:
                    self._stealth_search_started_at = now_ticks
                if triggered_count < 2 and now_ticks - self._stealth_search_started_at < search_window_ms:
                    self.objective_status = "search"
                    self._set_portal_active(True)
                    return None
                self._stealth_lockdown_started = True

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
                if (not self._resource_race_claimed_once) and self._resource_race_deadline_elapsed(now_ticks):
                    self._resource_race_failed = True
                    self.chest_looted = True
                    self.objective_status = "lost_race"
                    self._set_portal_active(False)
                    return {"kind": "forfeit_chest"}

                self.objective_status = "active"
                self._set_portal_active(False)
                if not self._resource_race_claimed_once:
                    claim_update = self._maybe_spawn_resource_race_wave(now_ticks)
                    if claim_update is not None:
                        return claim_update
                return None

            if self._resource_race_failed:
                if len(enemy_group) == 0:
                    self.objective_status = "completed"
                    self._set_portal_active(True)
                else:
                    self.objective_status = "lost_race"
                    self._set_portal_active(False)
                return None

            claim_update = self._maybe_restore_resource_race_chest(now_ticks, enemy_group)
            if claim_update is not None:
                return claim_update

            if len(enemy_group) == 0:
                self.objective_status = "completed"
            else:
                self.objective_status = "escape"
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
            elapsed_ms = max(0, now_ticks - self.objective_started_at)
            duration = self.room_plan.objective_duration_ms or 0
            if duration and elapsed_ms > duration:
                self.objective_status = "overtime"
                if not self._reinforcement_spawned:
                    reinforcements = self._spawn_reinforcement_wave()
                    self._reinforcement_spawned = True
                    self.enemy_configs.extend(reinforcements)
                    self._set_portal_active(True)
                    return {"kind": "spawn_reinforcements", "enemy_configs": reinforcements}
            else:
                extraction_update = self._maybe_spawn_timed_extraction_wave(elapsed_ms)
                self.objective_status = "collapse" if self._timed_extraction_wave_index else "escape"
                self._set_portal_active(True)
                if extraction_update is not None:
                    return extraction_update
            self._set_portal_active(True)
        return None

    def objective_target_info(self, origin_px=None):
        if (
            self.room_plan is not None
            and self.room_plan.room_id == "trap_gauntlet"
            and self.chest_pos is not None
            and not self.chest_looted
        ):
            return "Cache", self.chest_pos

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
                target_pool = [
                    config
                    for config in active_altars
                    if not config.get("invulnerable") and config.get("window_vulnerable", True)
                ]
                if not target_pool:
                    target_pool = [config for config in active_altars if not config.get("invulnerable")]
                if not target_pool:
                    target_pool = active_altars
                target = self._nearest_target(origin_px, [config["pos"] for config in target_pool])
                return self._altar_label(), target
            return "Exit", self._portal_center_pixel()

        if rule == "holdout_timer":
            holdout_targets = self._holdout_target_configs()
            if holdout_targets and self.objective_status != "completed":
                target_pos = self._nearest_target(origin_px, [config["pos"] for config in holdout_targets])
                target_config = next(config for config in holdout_targets if config["pos"] == target_pos)
                return target_config.get("label", "Holdout"), target_pos
            return "Exit", self._portal_center_pixel()

        if rule == "charge_plates":
            active_plates = self._puzzle_target_configs()
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
        if self.room_plan.room_id == "trap_gauntlet":
            route_prefix = "Challenge lane" if self._trap_challenge_route_selected() else "Safe lane"
            route_label = self._trap_safe_lane_label()
            reward_label = self._trap_reward_status_label()
            return {
                "visible": True,
                "label": f"Objective: {route_prefix} {route_label} | {reward_label}",
            }

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
            relief_suffix = self._holdout_relief_hud_suffix(now_ticks)
            return {
                "visible": True,
                "label": f"Objective: Hold out {remaining_ms / 1000:.1f}s{wave_suffix}{zone_suffix}{relief_suffix}",
            }

        if rule == "charge_plates" and self.is_exit and self.objective_status != "completed":
            controller = self._puzzle_controller() or {}
            variant = self._puzzle_variant()
            pressure_suffix = self._puzzle_pressure_suffix(now_ticks)
            if variant == "paired_runes":
                total_pairs = len(controller.get("pair_labels", ())) or 1
                completed_pairs = self._completed_puzzle_pairs()
                pending_pair = controller.get("pending_pair_label")
                suffix = f" | Match {pending_pair}" if pending_pair else ""
                label = pluralize_label(self._plate_label()).lower()
                return {
                    "visible": True,
                    "label": f"Objective: Match {label} {completed_pairs}/{total_pairs}{suffix}{pressure_suffix}",
                }

            total = len(self.objective_entity_configs)
            activated = total - self.remaining_puzzle_plates()
            label = pluralize_label(self._plate_label()).lower()
            next_target = min(total, controller.get("progress_index", 0) + 1)
            reset_suffix = ""
            if controller.get("last_reset_label"):
                reset_suffix = f" | Reset on {controller['last_reset_label']}"
            return {
                "visible": True,
                "label": f"Objective: Charge {label} {activated}/{total} | Next {next_target}{reset_suffix}{pressure_suffix}",
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
            if self.objective_status == "search":
                remaining_ms = self._stealth_search_remaining_ms(now_ticks)
                return {
                    "visible": True,
                    "label": f"Objective: Search phase {remaining_ms / 1000:.1f}s | Avoid more alarms",
                }
            if self._has_triggered_alarm_beacon() and self.objective_status != "completed":
                return {"visible": True, "label": "Objective: Alarm raised, clear the room"}
            return {"visible": True, "label": "Objective: Slip through unseen"}

        if rule == "claim_relic_before_lockdown" and self.is_exit:
            relic_label = self._relic_label().lower()
            if not self.chest_looted and not self._resource_race_failed:
                if self._resource_race_claimed_once:
                    return {"visible": True, "label": f"Objective: Reclaim the {relic_label}"}
                started_at = self.objective_started_at or now_ticks
                remaining_ms = max(
                    0,
                    (self.room_plan.objective_duration_ms or 0) - (now_ticks - started_at),
                )
                pressure_suffix = ""
                total_waves = len(self._resource_race_wave_thresholds())
                if total_waves:
                    pressure_suffix = f" | Claim pressure {self._resource_race_wave_index}/{total_waves}"
                return {
                    "visible": True,
                    "label": f"Objective: Secure the {relic_label} {remaining_ms / 1000:.1f}s{pressure_suffix}",
                }
            if self._resource_race_failed:
                return {"visible": True, "label": "Objective: Relic lost, clear the room"}
            reclaim_suffix = ""
            reclaim_remaining_ms = self._resource_race_reclaim_remaining_ms(now_ticks)
            if reclaim_remaining_ms is not None:
                reclaim_suffix = f" | Rival reclaim {reclaim_remaining_ms / 1000:.1f}s"
            return {"visible": True, "label": f"Objective: Escape with the {relic_label}{reclaim_suffix}"}

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
            window_suffix = ""
            if self._ritual_uses_pulse_damage_windows():
                open_windows = self._ritual_open_damage_windows(now_ticks)
                if open_windows:
                    window_suffix = f" | Strike on pulse {open_windows} open"
                else:
                    window_suffix = " | Wait for pulse"
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
                "label": f"Objective: Destroy {self.remaining_objective_entities()} {label}{pulse_suffix}{window_suffix}{summon_suffix}{shield_suffix}",
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
                    pressure_suffix = ""
                    total_waves = len(self._timed_extraction_wave_thresholds())
                    if total_waves:
                        pressure_suffix = f" | Pursuit {self._timed_extraction_wave_index}/{total_waves}"
                    if self.objective_status == "collapse":
                        pressure_suffix += " | Route closing"
                    return {
                        "visible": True,
                        "label": f"Objective: Escape {remaining_ms / 1000:.1f}s{pressure_suffix}",
                    }
            if self.objective_status == "overtime":
                return {"visible": True, "label": "Objective: Escape under pressure"}
            return {"visible": True, "label": f"Objective: Escape with the {relic_label}"}

        if self.is_exit and rule == "immediate" and self.room_plan.room_id != "standard_combat":
            return {"visible": True, "label": f"Objective: {self.room_plan.display_name}"}

        return {"visible": False, "label": ""}

    def playtest_identifier_state(self, now_ticks):
        if self.room_plan is None:
            return {"visible": False, "title": "", "detail": ""}

        return {
            "visible": True,
            "title": f"Room: {self.room_plan.display_name}",
            "detail": self._playtest_identifier_detail(now_ticks),
        }

    def _playtest_identifier_detail(self, now_ticks):
        rule = self.room_plan.objective_rule
        if rule == "holdout_timer":
            if self._holdout_zone_config() is not None:
                if self._unused_holdout_relief_configs():
                    return "Solve: Stay inside the holdout circle until the timer ends. Optional stabilizers delay reinforcement waves."
                return "Solve: Stay inside the holdout circle until the timer ends."
            return "Solve: Survive until the holdout timer ends."

        if rule == "charge_plates":
            label = pluralize_label(self._plate_label()).lower()
            if self._puzzle_variant() == "paired_runes":
                return f"Solve: Match two {label} with the same symbol. Changing symbols or waiting too long summons reinforcements."
            return f"Solve: Activate the numbered {label} in order to unlock the exit. Wrong steps or stalling summon reinforcements."

        if rule == "escort_to_exit":
            escort = self._escort_config() or {}
            escort_label = escort.get("label", "Escort")
            if escort.get("destroyed") and self.objective_status != "completed":
                return f"Solve: {escort_label} is down. Clear the room to finish."
            return f"Solve: Protect {escort_label} and guide them to the exit."

        if rule == "escort_bomb_to_exit":
            escort = self._escort_config() or {}
            escort_label = escort.get("label", "Carrier")
            if escort.get("destroyed") and self.objective_status != "completed":
                return f"Solve: {escort_label} is down. Clear the room to finish."
            if escort.get("waiting_for_clearance"):
                return f"Solve: Clear a safe lane so {escort_label} can advance."
            return f"Solve: Guide {escort_label} to the exit and keep them alive."

        if rule == "avoid_alarm_zones":
            if self.objective_status == "search":
                return "Solve: Detection is rising. Reach the exit or avoid any more alarms before lockdown starts."
            if self._has_triggered_alarm_beacon() and self.objective_status != "completed":
                return "Solve: Stealth failed. Clear the room to proceed."
            return "Solve: Avoid the alarm beacons and slip through unseen."

        if rule == "claim_relic_before_lockdown":
            relic_label = self._relic_label().lower()
            if not self.chest_looted and not self._resource_race_failed:
                if self._resource_race_claimed_once:
                    return f"Solve: Rival claimants stole the {relic_label} back. Interrupt them and reclaim it."
                if self._resource_race_wave_index:
                    return f"Solve: Reach the {relic_label} before rival claimants finish locking it down."
                return f"Solve: Reach the {relic_label} before lockdown starts."
            if self._resource_race_failed:
                return "Solve: The relic is lost. Clear the room to proceed."
            if self._resource_race_reclaim_started_at is not None:
                return f"Solve: Carry the {relic_label} to the exit, but clear nearby claimants before they steal it back."
            return f"Solve: Carry the {relic_label} to the exit."

        if rule == "destroy_altars":
            if self._ritual_payoff_available():
                return f"Solve: Claim the revealed {self._ritual_payoff_label().lower()}."
            label = pluralize_label(self._altar_label()).lower()
            shielded_count = sum(
                1
                for config in self.objective_entity_configs
                if not config["destroyed"] and config.get("invulnerable")
            )
            if shielded_count:
                return f"Solve: Break the ward altar first, then destroy the remaining {label}."
            if self._ritual_uses_pulse_damage_windows():
                return f"Solve: Strike the ritual {label} only while their pulse windows are active."
            if self._has_active_pulse(now_ticks):
                return f"Solve: Avoid the pulse and destroy the remaining {label}."
            return f"Solve: Destroy all ritual {label} to break the room."

        if rule == "loot_then_timer":
            relic_label = self._relic_label().lower()
            if not self.chest_looted:
                return f"Solve: Secure the {relic_label}, then prepare to escape."
            if self.objective_status == "collapse":
                return f"Solve: Reach the exit with the {relic_label} while pursuit waves close the route behind you."
            if self.objective_status == "overtime":
                return "Solve: Escape under pressure before reinforcements overwhelm you."
            return f"Solve: Reach the exit with the {relic_label} before time runs out."

        if rule == "clear_enemies":
            if self.room_plan.room_id == "standard_combat":
                return "Solve: Defeat the enemies and continue onward."
            return "Solve: Clear the enemies to complete the room."

        if rule == "immediate":
            if self.room_plan.room_id == "trap_gauntlet":
                variant = (self.room_plan.objective_variant or "sweeper_lanes").lower()
                if variant == "vent_lanes":
                    return "Solve: Step on a lane switch to shut down one vent lane. The challenge lane still pulses but upgrades the chest."
                if variant == "crusher_corridors":
                    return "Solve: Pick a corridor and time the crushers. The challenge corridor stays active but upgrades the chest."
                return "Solve: Step on a lane switch to disable one sweeper lane. The challenge lane stays partially live but upgrades the chest."
            if self.room_plan.room_id == "standard_combat":
                return "Solve: Clear the room and use the portal when it opens."
            return f"Solve: Complete the {self.room_plan.display_name.lower()} objective."

        return "Solve: Complete the room objective to unlock the way forward."

    def _spawn_reinforcement_wave(self):
        return self._gen_enemy_configs_for_range((2, 2))

    @staticmethod
    def _scripted_wave_thresholds(duration, wave_sizes):
        if not duration or not wave_sizes:
            return ()
        segment_count = len(wave_sizes) + 1
        return tuple((duration * (index + 1)) // segment_count for index in range(len(wave_sizes)))

    def _resource_race_wave_thresholds(self):
        duration = self.room_plan.objective_duration_ms if self.room_plan else None
        wave_sizes = self.room_plan.scripted_wave_sizes if self.room_plan else ()
        return self._scripted_wave_thresholds(duration, wave_sizes)

    def _resource_race_reclaim_window_ms(self):
        duration = self.room_plan.objective_duration_ms if self.room_plan else None
        if not duration:
            return 1500
        return max(1200, duration // 3)

    def _resource_race_reclaim_remaining_ms(self, now_ticks):
        if self._resource_race_reclaim_started_at is None:
            return None
        return max(0, self._resource_race_reclaim_window_ms() - (now_ticks - self._resource_race_reclaim_started_at))

    def _maybe_spawn_resource_race_wave(self, now_ticks):
        thresholds = self._resource_race_wave_thresholds()
        if self.objective_started_at is None or self._resource_race_wave_index >= len(thresholds):
            return None
        elapsed_ms = max(0, now_ticks - self.objective_started_at)
        if elapsed_ms < thresholds[self._resource_race_wave_index]:
            return None

        wave_sizes = self.room_plan.scripted_wave_sizes if self.room_plan else ()
        wave_size = wave_sizes[self._resource_race_wave_index]
        enemy_configs = self._gen_enemy_configs_for_range((wave_size, wave_size))
        self.enemy_configs.extend(enemy_configs)
        self._resource_race_wave_index += 1
        return {
            "kind": "spawn_enemies",
            "source": "resource_race",
            "enemy_configs": enemy_configs,
        }

    def _maybe_restore_resource_race_chest(self, now_ticks, enemy_group):
        if len(enemy_group) == 0:
            self._resource_race_reclaim_started_at = None
            return None
        if self._resource_race_reclaim_started_at is None:
            self._resource_race_reclaim_started_at = now_ticks
            return None
        if now_ticks - self._resource_race_reclaim_started_at < self._resource_race_reclaim_window_ms():
            return None

        self.chest_looted = False
        self.objective_status = "active"
        self._resource_race_reclaim_started_at = None
        self._set_portal_active(False)
        return {"kind": "restore_chest"}

    def _maybe_spawn_holdout_wave(self, elapsed_ms):
        thresholds = self._holdout_wave_thresholds()
        if self._holdout_wave_index >= len(thresholds):
            return None
        controller = self._holdout_controller() or {}
        adjusted_threshold = thresholds[self._holdout_wave_index] + controller.get("wave_delay_ms", 0)
        if elapsed_ms < adjusted_threshold:
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

    def _alarm_trigger_count(self):
        return sum(1 for config in self.objective_entity_configs if config.get("triggered"))

    def _stealth_search_window_ms(self):
        if self.room_plan is None or self.room_plan.objective_rule != "avoid_alarm_zones":
            return 0
        return int(self.room_plan.objective_duration_ms or 0)

    def _stealth_search_remaining_ms(self, now_ticks):
        if self._stealth_search_started_at is None:
            return 0
        return max(0, self._stealth_search_window_ms() - (now_ticks - self._stealth_search_started_at))

    def _timed_extraction_wave_thresholds(self):
        if self.room_plan is None or self.room_plan.objective_rule != "loot_then_timer":
            return ()
        return self._scripted_wave_thresholds(
            self.room_plan.objective_duration_ms,
            self.room_plan.scripted_wave_sizes,
        )

    def _maybe_spawn_timed_extraction_wave(self, elapsed_ms):
        thresholds = self._timed_extraction_wave_thresholds()
        if self._timed_extraction_wave_index >= len(thresholds):
            return None
        if elapsed_ms < thresholds[self._timed_extraction_wave_index]:
            return None

        wave_sizes = self.room_plan.scripted_wave_sizes if self.room_plan else ()
        wave_size = wave_sizes[self._timed_extraction_wave_index]
        enemy_configs = self._gen_enemy_configs_for_range((wave_size, wave_size))
        self.enemy_configs.extend(enemy_configs)
        self._timed_extraction_wave_index += 1
        return {
            "kind": "spawn_enemies",
            "source": "timed_extraction",
            "enemy_configs": enemy_configs,
        }

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

    def _holdout_controller(self):
        for config in self.objective_entity_configs:
            if config.get("kind") in {"holdout_zone", "holdout_stabilizer"}:
                controller = config.get("controller")
                if controller is not None:
                    return controller
        return None

    def _unused_holdout_relief_configs(self):
        return [
            config
            for config in self.objective_entity_configs
            if config.get("kind") == "holdout_stabilizer" and not config.get("used")
        ]

    def _holdout_target_configs(self):
        holdout_zone = self._holdout_zone_config()
        if holdout_zone is None:
            return []
        if holdout_zone.get("occupied"):
            relief_configs = self._unused_holdout_relief_configs()
            if relief_configs:
                return relief_configs
        return [holdout_zone]

    def _holdout_relief_hud_suffix(self, now_ticks):
        controller = self._holdout_controller() or {}
        last_relief_at = controller.get("last_relief_at")
        if last_relief_at is not None and now_ticks - last_relief_at <= _HOLDOUT_RELIEF_HUD_MS:
            return " | Pressure eased"

        unused_relief = self._unused_holdout_relief_configs()
        if not unused_relief:
            return ""
        if len(unused_relief) == 1:
            return " | Stabilizer ready"
        return f" | Stabilizers {len(unused_relief)}"

    def _trap_controller(self):
        for config in self.objective_entity_configs:
            controller = config.get("controller")
            if controller is not None:
                return controller
        return None

    def _trap_safe_lane_label(self):
        controller = self._trap_controller()
        if controller is None:
            return "Center"
        labels = controller.get("lane_labels", ())
        safe_lane = controller.get("safe_lane", 0)
        if 0 <= safe_lane < len(labels):
            return labels[safe_lane]
        return f"Lane {safe_lane + 1}"

    def chest_reward_tier(self):
        return self._chest_reward_tier

    def _trap_challenge_route_selected(self):
        controller = self._trap_controller()
        return bool(controller and controller.get("challenge_route_selected"))

    def _trap_reward_status_label(self):
        controller = self._trap_controller()
        if controller is None:
            return "Claim the cache"
        if self.chest_looted:
            return "Route secured"
        if controller.get("challenge_reward_applied"):
            return "Reward upgraded"
        return f"Bonus route {controller.get('challenge_lane_label', 'armed')}"

    def _puzzle_controller(self):
        for config in self.objective_entity_configs:
            controller = config.get("controller")
            if controller is not None:
                return controller
        return None

    def _puzzle_variant(self):
        controller = self._puzzle_controller()
        if controller is not None:
            return controller.get("variant", "ordered_plates")
        if self.room_plan and self.room_plan.objective_variant:
            return self.room_plan.objective_variant
        return "ordered_plates"

    def _puzzle_target_configs(self):
        active_plates = [
            config for config in self.objective_entity_configs if not config.get("activated")
        ]
        if not active_plates:
            return []

        controller = self._puzzle_controller() or {}
        if self._puzzle_variant() == "paired_runes":
            pending_pair = controller.get("pending_pair_label")
            if pending_pair:
                pending_targets = [
                    config
                    for config in active_plates
                    if config.get("pair_label") == pending_pair and not config.get("primed")
                ]
                if pending_targets:
                    return pending_targets
            primed_targets = [config for config in active_plates if config.get("primed")]
            if primed_targets:
                return primed_targets
            return active_plates

        expected_index = controller.get("progress_index", 0)
        ordered_targets = [
            config for config in active_plates if config.get("order_index", 0) == expected_index
        ]
        return ordered_targets or active_plates

    def _completed_puzzle_pairs(self):
        controller = self._puzzle_controller() or {}
        completed_pairs = 0
        for pair_label in controller.get("pair_labels", ()): 
            pair_configs = [
                config
                for config in self.objective_entity_configs
                if config.get("pair_label") == pair_label
            ]
            if pair_configs and all(config.get("activated") for config in pair_configs):
                completed_pairs += 1
        return completed_pairs

    def _puzzle_pressure_suffix(self, now_ticks):
        controller = self._puzzle_controller() or {}
        last_penalty_at = controller.get("last_penalty_at")
        if last_penalty_at is None:
            return ""
        if now_ticks - last_penalty_at > _PUZZLE_PENALTY_HUD_MS:
            return ""
        return " | Pressure spike"

    def _maybe_trigger_puzzle_reaction(self, now_ticks):
        controller = self._puzzle_controller()
        if controller is None:
            return None

        if not controller.get("reaction_pending"):
            if not self._arm_puzzle_stall_reaction(controller, now_ticks):
                return None

        reaction_enemy_count = max(
            1,
            int(controller.get("reaction_enemy_count", _DEFAULT_PUZZLE_REINFORCEMENT_COUNT)),
        )
        enemy_configs = self._gen_enemy_configs_for_range((reaction_enemy_count, reaction_enemy_count))
        self.enemy_configs.extend(enemy_configs)
        controller["reaction_pending"] = False
        controller["last_penalty_at"] = now_ticks
        controller["last_penalty_reason"] = controller.get("reaction_reason", "reset")
        controller["reaction_reason"] = ""
        return {
            "kind": "spawn_reinforcements",
            "source": "puzzle_reaction",
            "enemy_configs": enemy_configs,
        }

    def _arm_puzzle_stall_reaction(self, controller, now_ticks):
        last_progress_at = controller.get("last_progress_at")
        if last_progress_at is None:
            return False

        stall_duration_ms = controller.get("stall_duration_ms", _PUZZLE_STALL_DURATION_MS)
        if now_ticks - last_progress_at < stall_duration_ms:
            return False

        if self._puzzle_variant() == "paired_runes":
            pending_label = controller.get("pending_pair_label")
            if not pending_label:
                return False
            for config in controller.get("configs", ()): 
                config["primed"] = False
            controller["pending_pair_label"] = None
            controller["last_reset_label"] = pending_label
        else:
            progress_index = controller.get("progress_index", 0)
            if progress_index <= 0:
                return False
            next_label = str(min(len(controller.get("configs", ())), progress_index + 1))
            for config in controller.get("configs", ()): 
                config["activated"] = False
                config["primed"] = False
            controller["progress_index"] = 0
            controller["last_reset_label"] = next_label

        controller["last_progress_at"] = now_ticks
        controller["reaction_pending"] = True
        controller["reaction_reason"] = "stall"
        return True

    def remaining_objective_entities(self):
        return sum(1 for config in self.objective_entity_configs if not config["destroyed"])

    def remaining_puzzle_plates(self):
        return sum(1 for config in self.objective_entity_configs if not config.get("activated"))

    def _build_objective_configs(self):
        if self.room_plan is None:
            return
        if self.room_plan.room_id == "trap_gauntlet":
            self.objective_entity_configs = self._build_trap_gauntlet_configs()
        elif self.room_plan.objective_rule == "destroy_altars":
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
                    "window_gated": self.room_plan.ritual_link_mode == "pulse_gates_damage",
                    "window_vulnerable": False,
                    "destroyed": False,
                }
                for index, pos in enumerate(self._altar_positions(self.room_plan.objective_entity_count or 3))
            ]
            if self._ritual_uses_pulse_damage_windows():
                for config in self.objective_entity_configs:
                    config["window_vulnerable"] = self._pulse_active(config, 0)
            self._refresh_ritual_links()
        elif self.room_plan.objective_rule == "holdout_timer" and self.room_plan.holdout_zone_radius > 0:
            self.objective_entity_configs = self._build_holdout_configs()
        elif self.room_plan.objective_rule == "charge_plates":
            self.objective_entity_configs = self._build_puzzle_plate_configs()
        elif self.room_plan.objective_rule in {"escort_to_exit", "escort_bomb_to_exit"}:
            requires_safe_path = self.room_plan.objective_rule == "escort_bomb_to_exit"
            default_label = "Carrier" if requires_safe_path else "Escort"
            max_hp = self.room_plan.objective_max_hp or (30 if requires_safe_path else 26)
            speed = self.room_plan.objective_move_speed or (1.0 if requires_safe_path else 1.2)
            guide_radius = self.room_plan.objective_guide_radius or 92
            exit_radius = self.room_plan.objective_exit_radius or 24
            damage_cooldown_ms = self.room_plan.objective_damage_cooldown_ms or 500
            goal_pos = self._portal_center_pixel()
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
                    "goal_pos": goal_pos,
                    "goal_radius": exit_radius,
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

    def _build_trap_gauntlet_configs(self):
        trap_variant = self.room_plan.objective_variant or "sweeper_lanes"
        lane_count = max(2, min(4, self.room_plan.objective_entity_count or 3))
        if trap_variant == "crusher_corridors":
            lane_count = 2
        orientation = self._trap_orientation()
        lane_offsets = self._trap_lane_offsets(lane_count)
        lane_labels = self._trap_lane_labels(orientation, lane_count)
        switch_bank = self._trap_switch_bank(orientation)
        challenge_lane = lane_count - 1
        controller = {
            "safe_lane": 0 if lane_count == 2 else lane_count // 2,
            "lane_labels": lane_labels,
            "lane_offsets": lane_offsets,
            "orientation": orientation,
            "switch_bank": switch_bank,
            "variant": trap_variant,
            "challenge_lane": challenge_lane,
            "challenge_lane_label": lane_labels[challenge_lane],
            "challenge_route_selected": False,
            "challenge_reward_applied": False,
        }
        configs = []
        for index, offset in enumerate(lane_offsets):
            if trap_variant == "vent_lanes":
                configs.append(
                    self._trap_vent_config(
                        controller,
                        orientation,
                        offset,
                        lane_count,
                        index,
                    )
                )
            elif trap_variant == "crusher_corridors":
                configs.extend(
                    self._trap_crusher_configs(
                        controller,
                        orientation,
                        offset,
                        index,
                    )
                )
            else:
                configs.append(
                    self._trap_sweeper_config(
                        controller,
                        orientation,
                        offset,
                        lane_count,
                        index,
                    )
                )
            configs.append(
                self._trap_switch_config(
                    controller,
                    orientation,
                    offset,
                    lane_labels[index],
                    index,
                    switch_bank,
                )
            )
        return configs

    def _build_puzzle_plate_configs(self):
        variant = self._puzzle_variant()
        plate_count = self.room_plan.objective_entity_count or (4 if variant == "paired_runes" else 3)
        if variant == "paired_runes" and plate_count % 2 == 1:
            plate_count += 1

        plate_positions = self._objective_positions(
            self.room_plan.objective_layout_offsets,
            _DEFAULT_PRESSURE_PLATE_OFFSETS,
            plate_count,
        )
        controller = {
            "variant": variant,
            "progress_index": 0,
            "pending_pair_label": None,
            "last_reset_label": "",
            "reaction_pending": False,
            "reaction_reason": "",
            "last_progress_at": None,
            "last_penalty_at": None,
            "last_penalty_reason": "",
            "stall_duration_ms": max(
                250,
                int(self.room_plan.puzzle_stall_duration_ms or _PUZZLE_STALL_DURATION_MS),
            ),
            "reaction_enemy_count": max(
                1,
                int(self.room_plan.puzzle_reinforcement_count or _DEFAULT_PUZZLE_REINFORCEMENT_COUNT),
            ),
            "penalty_flash_ms": _PUZZLE_PENALTY_FLASH_MS,
        }
        configs = []
        if variant == "paired_runes":
            pair_labels = tuple(chr(ord("A") + index // 2) for index in range(plate_count))
            controller["pair_labels"] = tuple(dict.fromkeys(pair_labels))
            for index, pos in enumerate(plate_positions):
                pair_label = pair_labels[index]
                configs.append(
                    {
                        "kind": "pressure_plate",
                        "label": self._plate_label(),
                        "pos": pos,
                        "trigger_padding": self.room_plan.objective_trigger_padding or 10,
                        "activated": False,
                        "primed": False,
                        "controller": controller,
                        "pair_label": pair_label,
                        "telegraph_text": pair_label,
                    }
                )
        else:
            for index, pos in enumerate(plate_positions):
                configs.append(
                    {
                        "kind": "pressure_plate",
                        "label": self._plate_label(),
                        "pos": pos,
                        "trigger_padding": self.room_plan.objective_trigger_padding or 10,
                        "activated": False,
                        "primed": False,
                        "controller": controller,
                        "order_index": index,
                        "telegraph_text": str(index + 1),
                    }
                )
        controller["configs"] = configs
        return configs

    def _trap_sweeper_config(self, controller, orientation, offset, lane_count, lane_index):
        travel_min = 4 * TILE_SIZE + TILE_SIZE // 2
        if orientation == "horizontal":
            travel_max = (ROOM_COLS - 5) * TILE_SIZE + TILE_SIZE // 2
            center = self._offset_to_pixel((0, offset))
            start_x = self._trap_travel_start(travel_min, travel_max, lane_count, lane_index)
            position = (start_x, center[1])
        else:
            travel_max = (ROOM_ROWS - 5) * TILE_SIZE + TILE_SIZE // 2
            center = self._offset_to_pixel((offset, 0))
            start_y = self._trap_travel_start(travel_min, travel_max, lane_count, lane_index)
            position = (center[0], start_y)

        return {
            "kind": "trap_sweeper",
            "lane_index": lane_index,
            "controller": controller,
            "orientation": orientation,
            "pos": position,
            "travel_min": travel_min,
            "travel_max": travel_max,
            "direction": 1 if lane_index % 2 == 0 else -1,
            "speed": 2.6,
            "challenge_speed": 1.5,
            "damage": 8,
            "damage_cooldown_ms": 350,
            "damage_cooldown_until": 0,
            "lane_thickness": 22,
            "active": lane_index != controller["safe_lane"],
        }

    def _trap_vent_config(self, controller, orientation, offset, lane_count, lane_index):
        travel_min = 4 * TILE_SIZE + TILE_SIZE // 2
        if orientation == "horizontal":
            travel_max = (ROOM_COLS - 5) * TILE_SIZE + TILE_SIZE // 2
            center = self._offset_to_pixel((0, offset))[1]
            emitter_col = 3 if controller["switch_bank"] == "left" else ROOM_COLS - 4
            emitter_pos = (emitter_col * TILE_SIZE + TILE_SIZE // 2, center)
        else:
            travel_max = (ROOM_ROWS - 5) * TILE_SIZE + TILE_SIZE // 2
            center = self._offset_to_pixel((offset, 0))[0]
            emitter_row = 3 if controller["switch_bank"] == "top" else ROOM_ROWS - 4
            emitter_pos = (center, emitter_row * TILE_SIZE + TILE_SIZE // 2)

        return {
            "kind": "trap_vent_lane",
            "lane_index": lane_index,
            "controller": controller,
            "orientation": orientation,
            "center": center,
            "emitter_pos": emitter_pos,
            "travel_min": travel_min,
            "travel_max": travel_max,
            "cycle_ms": 1000,
            "active_ms": 700,
            "challenge_cycle_ms": 800,
            "challenge_active_ms": 260,
            "phase_offset_ms": lane_index * 120,
            "damage": 7,
            "damage_cooldown_ms": 280,
            "damage_cooldown_until": 0,
            "lane_thickness": 20,
            "active": lane_index != controller["safe_lane"],
        }

    def _trap_switch_config(self, controller, orientation, offset, label, lane_index, switch_bank):
        if orientation == "horizontal":
            col = 2 if switch_bank == "left" else ROOM_COLS - 3
            row = ROOM_ROWS // 2 + offset
        else:
            col = ROOM_COLS // 2 + offset
            row = 2 if switch_bank == "top" else ROOM_ROWS - 3

        return {
            "kind": "trap_lane_switch",
            "lane_index": lane_index,
            "label": label,
            "controller": controller,
            "pos": (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2),
            "trigger_padding": self.room_plan.objective_trigger_padding or 18,
            "selected": lane_index == controller["safe_lane"],
        }

    def _trap_crusher_configs(self, controller, orientation, offset, lane_index):
        configs = []
        if orientation == "horizontal":
            lane_center = self._offset_to_pixel((0, offset))[1]
            emitter_y = 2 * TILE_SIZE if offset < 0 else (ROOM_ROWS - 3) * TILE_SIZE
            for phase_index, col in enumerate((ROOM_COLS // 2 - 3, ROOM_COLS // 2 + 3)):
                center_x = col * TILE_SIZE + TILE_SIZE // 2
                configs.append(
                    {
                        "kind": "trap_crusher",
                        "lane_index": lane_index,
                        "controller": controller,
                        "emitter_pos": (center_x, emitter_y),
                        "zone_rect": (center_x - 11, lane_center - TILE_SIZE, 22, TILE_SIZE * 2),
                        "cycle_ms": 1200,
                        "active_ms": 700,
                        "challenge_cycle_ms": 900,
                        "challenge_active_ms": 320,
                        "phase_offset_ms": phase_index * 220 + lane_index * 110,
                        "damage": 9,
                        "damage_cooldown_ms": 350,
                        "damage_cooldown_until": 0,
                        "active": lane_index != controller["safe_lane"],
                    }
                )
        else:
            lane_center = self._offset_to_pixel((offset, 0))[0]
            emitter_x = 2 * TILE_SIZE if offset < 0 else (ROOM_COLS - 3) * TILE_SIZE
            for phase_index, row in enumerate((ROOM_ROWS // 2 - 2, ROOM_ROWS // 2 + 2)):
                center_y = row * TILE_SIZE + TILE_SIZE // 2
                configs.append(
                    {
                        "kind": "trap_crusher",
                        "lane_index": lane_index,
                        "controller": controller,
                        "emitter_pos": (emitter_x, center_y),
                        "zone_rect": (lane_center - TILE_SIZE, center_y - 11, TILE_SIZE * 2, 22),
                        "cycle_ms": 1200,
                        "active_ms": 700,
                        "challenge_cycle_ms": 900,
                        "challenge_active_ms": 320,
                        "phase_offset_ms": phase_index * 220 + lane_index * 110,
                        "damage": 9,
                        "damage_cooldown_ms": 350,
                        "damage_cooldown_until": 0,
                        "active": lane_index != controller["safe_lane"],
                    }
                )
        return configs

    def _carve_trap_gauntlet_lanes(self):
        controller = self._trap_controller()
        if controller is None:
            return

        if controller.get("variant") == "crusher_corridors":
            self._shape_crusher_corridors(controller)
            return

        orientation = controller["orientation"]
        for offset in controller["lane_offsets"]:
            if orientation == "horizontal":
                row = ROOM_ROWS // 2 + offset
                for r in range(max(1, row - 1), min(ROOM_ROWS - 1, row + 2)):
                    for c in range(1, ROOM_COLS - 1):
                        if self.grid[r][c] not in {DOOR, PORTAL, WALL}:
                            self.grid[r][c] = FLOOR

    def _shape_crusher_corridors(self, controller):
        orientation = controller["orientation"]
        lane_offsets = controller["lane_offsets"]

        if orientation == "horizontal":
            for row in (ROOM_ROWS // 2 - 1, ROOM_ROWS // 2):
                for col in range(4, ROOM_COLS - 4):
                    if self.grid[row][col] not in {DOOR, PORTAL}:
                        self.grid[row][col] = WALL
            for offset in lane_offsets:
                lane_row = ROOM_ROWS // 2 + offset
                for row in range(max(1, lane_row - 1), min(ROOM_ROWS - 1, lane_row + 2)):
                    for col in range(1, ROOM_COLS - 1):
                        if self.grid[row][col] not in {DOOR, PORTAL, WALL}:
                            self.grid[row][col] = FLOOR
        else:
            for col in (ROOM_COLS // 2 - 1, ROOM_COLS // 2):
                for row in range(4, ROOM_ROWS - 4):
                    if self.grid[row][col] not in {DOOR, PORTAL}:
                        self.grid[row][col] = WALL
            for offset in lane_offsets:
                lane_col = ROOM_COLS // 2 + offset
                for col in range(max(1, lane_col - 1), min(ROOM_COLS - 1, lane_col + 2)):
                    for row in range(1, ROOM_ROWS - 1):
                        if self.grid[row][col] not in {DOOR, PORTAL, WALL}:
                            self.grid[row][col] = FLOOR
            else:
                col = ROOM_COLS // 2 + offset
                for c in range(max(1, col - 1), min(ROOM_COLS - 1, col + 2)):
                    for r in range(1, ROOM_ROWS - 1):
                        if self.grid[r][c] not in {DOOR, PORTAL, WALL}:
                            self.grid[r][c] = FLOOR

    @staticmethod
    def _trap_travel_start(travel_min, travel_max, lane_count, lane_index):
        if lane_count <= 1:
            return (travel_min + travel_max) // 2
        span = travel_max - travel_min
        return int(travel_min + span * ((lane_index + 1) / (lane_count + 1)))

    def _trap_reward_position(self):
        controller = self._trap_controller()
        if controller is None:
            return self._random_floor_pos(margin=3)

        switch_bank = controller.get("switch_bank", "left")

        if controller.get("orientation") == "horizontal":
            col = ROOM_COLS - 3 if switch_bank == "left" else 2
            row = ROOM_ROWS // 2
        else:
            col = ROOM_COLS // 2
            row = ROOM_ROWS - 3 if switch_bank == "top" else 2
        return (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)

    def _trap_orientation(self):
        if self.doors.get("left") or self.doors.get("right"):
            return "horizontal"
        return "vertical"

    def _trap_switch_bank(self, orientation):
        if orientation == "horizontal":
            if self.doors.get("left"):
                return "left"
            if self.doors.get("right") and not self.doors.get("left"):
                return "right"
            return "left"

        if self.doors.get("top"):
            return "top"
        if self.doors.get("bottom") and not self.doors.get("top"):
            return "bottom"
        return "top"

    @staticmethod
    def _trap_lane_offsets(lane_count):
        if lane_count in _DEFAULT_TRAP_LANE_OFFSETS:
            return _DEFAULT_TRAP_LANE_OFFSETS[lane_count]
        if lane_count <= 1:
            return (0,)
        return tuple(range(-(lane_count - 1), lane_count, 2))

    @staticmethod
    def _trap_lane_labels(orientation, lane_count):
        if orientation == "horizontal":
            if lane_count == 2:
                return ("Top", "Bottom")
            if lane_count == 3:
                return ("Top", "Middle", "Bottom")
            if lane_count == 4:
                return ("North", "Upper", "Lower", "South")
        else:
            if lane_count == 2:
                return ("Left", "Right")
            if lane_count == 3:
                return ("Left", "Center", "Right")
            if lane_count == 4:
                return ("West", "Inner Left", "Inner Right", "East")
        return tuple(f"Lane {index + 1}" for index in range(lane_count))

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

    def _position_escort_for_entry(self, *, entry_direction=None, player_position=None, room_test=False):
        if self.room_plan is None:
            return
        if self.room_plan.objective_rule not in {"escort_to_exit", "escort_bomb_to_exit"}:
            return

        escort = self._escort_config()
        if escort is None or escort.get("destroyed") or escort.get("reached_exit"):
            return

        fallback_pos = escort["pos"]
        if player_position is not None:
            escort["pos"] = self._escort_spawn_near_player(player_position, fallback_pos)
        elif entry_direction is not None:
            escort["pos"] = self._escort_spawn_near_entry_door(entry_direction, fallback_pos)

    def _escort_spawn_near_player(self, player_position, fallback_pos):
        player_col = int(player_position[0]) // TILE_SIZE
        player_row = int(player_position[1]) // TILE_SIZE
        return self._nearest_walkable_position(
            player_col,
            player_row,
            fallback_pos,
            preferred_offsets=_DEFAULT_ESCORT_PLAYER_OFFSETS,
        )

    def _escort_spawn_near_entry_door(self, entry_direction, fallback_pos):
        door_x, door_y = self.door_pixel_pos(entry_direction)
        inward_dx, inward_dy = DIR_OFFSETS[OPPOSITE_DIR[entry_direction]]
        anchor_col = int(door_x) // TILE_SIZE + inward_dx * 2
        anchor_row = int(door_y) // TILE_SIZE + inward_dy * 2
        preferred_offsets = (
            (0, 0),
            (inward_dx, inward_dy),
            (-inward_dy, inward_dx),
            (inward_dy, -inward_dx),
            (inward_dx * 2, inward_dy * 2),
        )
        return self._nearest_walkable_position(
            anchor_col,
            anchor_row,
            fallback_pos,
            preferred_offsets=preferred_offsets,
        )

    def _nearest_walkable_position(self, anchor_col, anchor_row, fallback_pos, *, preferred_offsets=()):
        checked = set()
        for dc, dr in preferred_offsets:
            candidate = (anchor_col + dc, anchor_row + dr)
            if candidate in checked:
                continue
            checked.add(candidate)
            if self._is_walkable_spawn_tile(*candidate):
                return self._tile_center_pixel(*candidate)

        max_radius = max(ROOM_COLS, ROOM_ROWS)
        for radius in range(max_radius):
            candidates = (
                (anchor_col, anchor_row + radius),
                (anchor_col, anchor_row - radius),
                (anchor_col - radius, anchor_row),
                (anchor_col + radius, anchor_row),
            )
            for candidate in candidates:
                if candidate in checked:
                    continue
                checked.add(candidate)
                if self._is_walkable_spawn_tile(*candidate):
                    return self._tile_center_pixel(*candidate)
        return fallback_pos

    def _is_walkable_spawn_tile(self, col, row):
        tile = self.tile_at(col, row)
        return tile not in {WALL, DOOR, PORTAL}

    @staticmethod
    def _tile_center_pixel(col, row):
        return (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)

    @staticmethod
    def _offset_to_pixel(offset):
        col = ROOM_COLS // 2 + offset[0]
        row = ROOM_ROWS // 2 + offset[1]
        return (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)

    def _holdout_wave_sizes(self):
        if self.room_plan is None or self.room_plan.objective_rule != "holdout_timer":
            return ()
        return self.room_plan.scripted_wave_sizes or (1, 2)

    def _build_holdout_configs(self):
        controller = {
            "kind": "holdout",
            "wave_delay_ms": 0,
            "last_relief_at": None,
            "last_relief_label": "",
            "relief_flash_ms": 900,
        }
        configs = [
            {
                "kind": "holdout_zone",
                "label": self.room_plan.objective_label or "Holdout",
                "pos": self._portal_center_pixel(),
                "radius": self.room_plan.holdout_zone_radius,
                "occupied": False,
                "controller": controller,
            }
        ]
        relief_positions = self._objective_positions(
            (),
            _DEFAULT_HOLDOUT_RELIEF_OFFSETS,
            max(0, int(self.room_plan.holdout_relief_count or _DEFAULT_HOLDOUT_RELIEF_COUNT)),
        )
        for pos in relief_positions:
            configs.append(
                {
                    "kind": "holdout_stabilizer",
                    "label": "Stabilizer",
                    "pos": pos,
                    "trigger_padding": 18,
                    "relief_delay_ms": max(
                        250,
                        int(self.room_plan.holdout_relief_delay_ms or _DEFAULT_HOLDOUT_RELIEF_DELAY_MS),
                    ),
                    "used": False,
                    "controller": controller,
                }
            )
        return configs

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

    def _ritual_uses_pulse_damage_windows(self):
        return bool(
            self.room_plan is not None
            and self.room_plan.objective_rule == "destroy_altars"
            and self.room_plan.ritual_link_mode == "pulse_gates_damage"
        )

    def _ritual_open_damage_windows(self, now_ticks):
        if not self._ritual_uses_pulse_damage_windows():
            return 0
        return sum(
            1
            for config in self.objective_entity_configs
            if not config.get("destroyed") and self._pulse_active(config, now_ticks)
        )

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
