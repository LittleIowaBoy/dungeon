"""Room: tile grid, terrain, walls/doors, enemy/chest spawn configs."""
import random
import pygame
import rune_rules
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
    COLOR_QUICKSAND, COLOR_SPIKE_PATCH, COLOR_PIT_TILE, COLOR_CURRENT,
    COLOR_THIN_ICE, COLOR_HEARTH, COLOR_CART_RAIL, COLOR_GLYPH_TILE,
    COLOR_BLACK, COLOR_WHITE,
    ENEMY_MIN_PER_ROOM, ENEMY_MAX_PER_ROOM,
    ENEMY_DOOR_BUFFER_TILES, ROOM_MAX_DISTINCT_ENEMY_TYPES,
    CHEST_SPAWN_CHANCE,
    TERRAIN_PATCH_MIN, TERRAIN_PATCH_MAX,
    TERRAIN_PATCH_SIZE_MIN, TERRAIN_PATCH_SIZE_MAX,
)
from enemies import (
    ENEMY_CLASSES, ChaserEnemy, PatrolEnemy, RandomEnemy,
    PulsatorEnemy, LauncherEnemy, SentryEnemy,
)

# tile type constants
FLOOR = "floor"
WALL  = "wall"
MUD   = "mud"
ICE   = "ice"
WATER = "water"
DOOR  = "door"
PORTAL = "portal"

# Biome-room hazard tile constants (Phase 1 of biome room expansion).
# These tiles are walkable but trigger effects via terrain_effects.py:
# QUICKSAND   — drowning timer; lethal if player remains in the patch.
# SPIKE_PATCH — small passive tick damage on contact.
# PIT_TILE    — lethal-on-step (collapsed cell from cave-in / thin ice).
# CURRENT     — directional push (vector stored on the tile via Room helper).
# THIN_ICE    — normal floor that progresses to PIT_TILE under prolonged use.
# HEARTH      — safe spot that suppresses room-wide auras for the player.
# CART_RAIL   — cosmetic (mining-cart entities navigate along it).
# GLYPH_TILE  — puzzle tile that records ordered touches.
QUICKSAND  = "quicksand"
SPIKE_PATCH = "spike_patch"
PIT_TILE   = "pit_tile"
CURRENT    = "current"
THIN_ICE   = "thin_ice"
HEARTH     = "hearth"
CART_RAIL  = "cart_rail"
GLYPH_TILE = "glyph_tile"

# Tiles that block player and enemy movement (treated as walls).  Only
# WALL itself qualifies today; biome-room hazard tiles are walkable.
WALKABLE_HAZARD_TILES = (
    QUICKSAND, SPIKE_PATCH, PIT_TILE, CURRENT,
    THIN_ICE, HEARTH, CART_RAIL, GLYPH_TILE,
)

TERRAIN_COLORS = {
    FLOOR:  COLOR_FLOOR,
    WALL:   COLOR_WALL,
    MUD:    COLOR_MUD,
    ICE:    COLOR_ICE,
    WATER:  COLOR_WATER,
    DOOR:   COLOR_DOOR,
    PORTAL: COLOR_PORTAL,
    QUICKSAND:   COLOR_QUICKSAND,
    SPIKE_PATCH: COLOR_SPIKE_PATCH,
    PIT_TILE:    COLOR_PIT_TILE,
    CURRENT:     COLOR_CURRENT,
    THIN_ICE:    COLOR_THIN_ICE,
    HEARTH:      COLOR_HEARTH,
    CART_RAIL:   COLOR_CART_RAIL,
    GLYPH_TILE:  COLOR_GLYPH_TILE,
}

# terrain types that can be randomly placed (default pool)
_TERRAIN_POOL = [MUD, ICE, WATER]

# Biome-room IDs whose terrain patches are replaced with a hazard tile
# instead of the biome's default terrain.  Patch count/size still come from
# the room template; only the tile kind is swapped.
HAZARD_ROOM_TERRAIN = {
    "earth_stalagmite_field": SPIKE_PATCH,
    "earth_quicksand_trap":   QUICKSAND,
    "earth_tremor_chamber":   HEARTH,
}

# Identifier for the bespoke "Tuning Test Room" used by the room-test menu.
# When a room is built from a plan with this room_id, the standard random
# placement is replaced with a hand-tuned layout (see Room._build_tuning_test_room).
TUNING_TEST_ROOM_ID = "tuning_test_room"

_TUNING_LABEL_FONT = None


def _tuning_label_font():
    """Lazy-init shared Pygame font for tuning-test-room labels."""
    global _TUNING_LABEL_FONT
    if _TUNING_LABEL_FONT is None:
        if not pygame.font.get_init():
            try:
                pygame.font.init()
            except pygame.error:
                return None
        try:
            _TUNING_LABEL_FONT = pygame.font.SysFont("consolas", 14, bold=True)
        except pygame.error:
            return None
    return _TUNING_LABEL_FONT

_DEFAULT_PRESSURE_PLATE_OFFSETS = ((-5, -3), (5, -3), (0, 4), (0, -4))
_DEFAULT_ALARM_BEACON_OFFSETS = ((-4, -2), (4, -2), (0, 4), (0, -4))
_DEFAULT_ESCORT_SPAWN_OFFSET = (-6, 0)
_DEFAULT_ESCORT_PLAYER_OFFSETS = ((1, 0), (0, 1), (0, -1), (-1, 0))
_DEFAULT_HOLDOUT_RELIEF_OFFSETS = ((-6, 0), (6, 0), (0, -6), (0, 6))
# ── Trap safe-spot helpers ───────────────────────────────────────────────────
# Player base speed in px/ms (3.0 px/frame × 60 fps = 0.18 px/ms).
_PLAYER_SPEED_PX_PER_MS = 0.18
# Safe-spot size in the travel direction (wide enough for a 28 px player sprite).
_SAFE_SPOT_TRAVEL_SIZE = TILE_SIZE + TILE_SIZE // 2   # 60 px
# Minimum gap between the start of the travel range and the first safe spot.
_SAFE_SPOT_FIRST_OFFSET = TILE_SIZE * 2               # 80 px


def _compute_timed_safe_spots(
    orientation, travel_min, travel_max, lane_center_px, lane_thickness,
    cycle_ms, active_ms,
):
    """Return a list of ``(x, y, w, h)`` safe-spot rects for a timed hazard.

    Safe spots are spaced along the travel axis so that a player moving at
    base speed can reach each spot during a single inactive window.
    """
    inactive_ms = cycle_ms - active_ms
    spacing = int(_PLAYER_SPEED_PX_PER_MS * inactive_ms)   # max reachable distance
    spacing = max(TILE_SIZE * 3, spacing)                   # floor at 3 tiles
    spots = []
    pos = travel_min + _SAFE_SPOT_FIRST_OFFSET
    while pos + _SAFE_SPOT_TRAVEL_SIZE <= travel_max - TILE_SIZE:
        half_thick = lane_thickness // 2
        if orientation == "horizontal":
            # Travel axis is X; safe spot is a band across the lane at this X.
            spots.append((
                pos,
                lane_center_px - half_thick,
                _SAFE_SPOT_TRAVEL_SIZE,
                lane_thickness,
            ))
        else:
            # Travel axis is Y; safe spot is a band across the lane at this Y.
            spots.append((
                lane_center_px - half_thick,
                pos,
                lane_thickness,
                _SAFE_SPOT_TRAVEL_SIZE,
            ))
        pos += spacing
    return spots


def _compute_sweeper_safe_spots(
    orientation, travel_min, travel_max, lane_center_px, lane_thickness,
):
    """Return safe-spot rects for a sweeper lane.

    For sweepers the hazard is always present but moves.  Safe spots are
    short recesses in the travel axis where the player can wait while the
    sweeper passes on the next cycle.
    """
    # At speed 1.5 px/frame × 60 fps the sweeper traverses the whole lane in
    # roughly 4-5 seconds.  Place spots every 4 tiles so the player always has
    # a nearby refuge even with varying lane lengths.
    spacing = TILE_SIZE * 4   # 160 px
    half_thick = lane_thickness // 2
    half_spot = _SAFE_SPOT_TRAVEL_SIZE // 2
    spots = []
    pos = travel_min + _SAFE_SPOT_FIRST_OFFSET
    while pos + _SAFE_SPOT_TRAVEL_SIZE <= travel_max - TILE_SIZE:
        if orientation == "horizontal":
            spots.append((
                pos,
                lane_center_px - half_thick,
                _SAFE_SPOT_TRAVEL_SIZE,
                lane_thickness,
            ))
        else:
            spots.append((
                lane_center_px - half_thick,
                pos,
                lane_thickness,
                _SAFE_SPOT_TRAVEL_SIZE,
            ))
        pos += spacing
    return spots


_DEFAULT_TRAP_LANE_OFFSETS = {
    2: (-3, 3),
    3: (-4, 0, 4),
    4: (-5, -2, 2, 5),
}


def _safe_spot_configs(hazard_config, lane_index):
    """Return ``trap_safe_spot`` display configs for every safe spot in a hazard config."""
    return [
        {
            "kind": "trap_safe_spot",
            "lane_index": lane_index,
            "rect": rect,
        }
        for rect in hazard_config.get("safe_spots", ())
    ]
_GAUNTLET_ENTRY_DEPTH = 2   # columns/rows for the entry lobby at the player-entry side
_GAUNTLET_REWARD_DEPTH = 3  # columns/rows for the reward arena at the far end
_REWARD_TIER_UPGRADES = {
    "standard": "branch_bonus",
    "branch_bonus": "finale_bonus",
    "finale_bonus": "finale_bonus",
}
_TIMED_EXTRACTION_CLEAN_BONUS_COINS = {
    "standard": 10,
    "branch_bonus": 14,
    "finale_bonus": 18,
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
        self.enemies_cleared: bool = False  # persists across re-entries
        if self.room_plan is not None:
            if self.room_plan.terrain_type is not None:
                self._terrain_type = self.room_plan.terrain_type
            if self.room_plan.enemy_count_range is not None:
                self._enemy_count_range = self.room_plan.enemy_count_range
            if self.room_plan.enemy_type_weights:
                self._enemy_type_weights = self.room_plan.enemy_type_weights
            # Hazard-tile rooms override the biome default terrain so the
            # patches placed by ``_place_terrain`` carry the biome-room
            # mechanic (spike tick damage, drowning, etc.).
            hazard_kind = HAZARD_ROOM_TERRAIN.get(self.room_plan.room_id)
            if hazard_kind is not None:
                self._terrain_type = hazard_kind

        self._portal_cells = []
        self._portal_active = True
        self.objective_status = "inactive"
        self.objective_started_at = None
        self._secondary_objective_active = False
        self._reinforcement_spawned = False
        self._holdout_wave_index = 0
        self._holdout_progress_ms = 0
        self._holdout_last_tick = None
        self._resource_race_failed = False
        self._resource_race_wave_index = 0
        self._resource_race_claimed_once = False
        self._resource_race_reclaim_started_at = None
        self._stealth_search_started_at = None
        self._stealth_alarm_started_at = None
        self._stealth_lockdown_started = False
        self._stealth_bonus_cache_armed = False
        self._stealth_bonus_cache_forfeited = False
        self._timed_extraction_wave_index = 0
        self._timed_extraction_route_sealed = False
        self._timed_extraction_bonus_awarded = False
        self._heartstone_config = None  # Set when chest opened in Heartstone Claim rooms.
        self._heartstone_spawn_pending = False
        self._heartstone_delivered = False
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

        # ── Phase 1 biome-room infrastructure ─────────────
        # Initialised here (before _build_objective_configs) so per-room
        # builders can override these defaults — e.g. earth_echo_cavern
        # narrows ``vision_radius`` to enable the fog-of-war camera pass.
        self.vision_radius: int | None = None
        self.current_vectors: dict[tuple[int, int], tuple[float, float]] = {}
        self._room_buffs: list[dict] = []
        self._quicksand_drown_ms: int = 0
        self._hazard_last_tick_ms: int = 0

        # spawn configs (created once, enemies re-instantiated on each visit)
        self.enemy_configs = self._gen_enemy_configs()
        self._build_objective_configs()
        # Test rooms can opt into auto-respawning slain enemies after a delay.
        # When None (default), enemies stay dead for the run as usual.
        self.respawn_enemies_after_ms: int | None = None
        self._enemy_respawn_due_at: dict[int, int] = {}
        if self.room_plan and self.room_plan.room_id == "trap_gauntlet":
            self._carve_trap_gauntlet_lanes()
        # Tuning test room: bespoke layout for gameplay testing.  Replaces
        # the random terrain/enemy placement with hand-tuned sections so each
        # terrain and enemy type can be exercised in isolation.
        self.frozen_enemies = False
        # Test-room knob: when False, every spawned enemy in this room has
        # ``attacks_disabled = True`` so designers can inspect them safely.
        # Toggle at runtime in the tuning test room (see RpgRuntime keymap).
        self.enemy_attacks_enabled = True
        self.tuning_test_labels: list[tuple[str, tuple[int, int]]] = []

        # ── Phase 1 biome-room infrastructure (legacy comment block) ──
        # The fields above were moved up so per-room ``_build_objective_configs``
        # branches (notably ``earth_echo_cavern``'s vision_radius assignment)
        # take effect.  This block is kept as a doc comment for clarity:
        # vision_radius / current_vectors / _room_buffs / _quicksand_drown_ms /
        # _hazard_last_tick_ms.
        if self.room_plan and self.room_plan.room_id == TUNING_TEST_ROOM_ID:
            self._build_tuning_test_room()

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
        elif self.room_plan and self.room_plan.room_id == TUNING_TEST_ROOM_ID:
            self.chest_pos = None
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
        if t in (MUD, ICE, WATER):
            return t
        if t in WALKABLE_HAZARD_TILES:
            return t
        if t in (FLOOR, DOOR, PORTAL):
            return "floor"
        return "floor"

    # ── biome-room helpers (Phase 1) ────────────────────
    def current_vector_at_pixel(self, px, py):
        """Return the (dx, dy) push vector for a CURRENT tile, else None."""
        col = int(px) // TILE_SIZE
        row = int(py) // TILE_SIZE
        if self.tile_at(col, row) != CURRENT:
            return None
        return self.current_vectors.get((col, row))

    def add_room_buff(self, stat, magnitude, expires_at=None):
        """Add a transient room-only buff (e.g., crystal vein pickup).

        ``stat`` is a free-form string (e.g., ``"speed"``, ``"damage"``).
        ``magnitude`` is the modifier (additive 0.20 = +20%).
        ``expires_at`` is a pygame tick timestamp, or None for room-lifetime.
        Buffs do not survive room transitions; ``Dungeon._load_room_sprites``
        clears them via :meth:`reset_room_buffs` on entry.
        """
        self._room_buffs.append({
            "stat": stat,
            "magnitude": float(magnitude),
            "expires_at": expires_at,
        })

    def active_room_buff_total(self, stat, now_ticks):
        """Return summed magnitude of un-expired buffs for *stat*."""
        total = 0.0
        for buff in self._room_buffs:
            if buff["stat"] != stat:
                continue
            exp = buff["expires_at"]
            if exp is not None and now_ticks >= exp:
                continue
            total += buff["magnitude"]
        return total

    def prune_expired_room_buffs(self, now_ticks):
        """Drop buffs whose ``expires_at`` has passed (called each frame)."""
        self._room_buffs = [
            b for b in self._room_buffs
            if b["expires_at"] is None or now_ticks < b["expires_at"]
        ]

    def reset_room_buffs(self):
        """Clear the room-buff registry (called on room entry / quit)."""
        self._room_buffs = []
        self._quicksand_drown_ms = 0
        self._hazard_last_tick_ms = 0

    def get_wall_rects(self):
        """Return a list of pygame.Rects for all WALL tiles.

        When the room is sealed, the closed door tiles are also returned
        so they block player and enemy movement just like walls.
        """
        walls = []
        for r in range(ROOM_ROWS):
            for c in range(ROOM_COLS):
                if self.grid[r][c] == WALL:
                    walls.append(pygame.Rect(c * TILE_SIZE, r * TILE_SIZE,
                                             TILE_SIZE, TILE_SIZE))
        if self.doors_sealed:
            for _direction, rect in self.get_seal_door_rects():
                walls.append(rect)
        return walls

    def get_seal_door_rects(self):
        """Return ``[(direction, pygame.Rect), ...]`` covering each present door.

        Each rect spans the ``DOOR_WIDTH``-tile opening on the room border.
        Empty when the room has no doors; not gated by ``doors_sealed`` so
        callers can render "open door" art post-completion if desired.
        """
        mid_col = ROOM_COLS // 2
        mid_row = ROOM_ROWS // 2
        half = DOOR_WIDTH // 2
        span = (half * 2 + 1) * TILE_SIZE
        rects = []
        if self.doors.get("top"):
            x = (mid_col - half) * TILE_SIZE
            rects.append(("top", pygame.Rect(x, 0, span, TILE_SIZE)))
        if self.doors.get("bottom"):
            x = (mid_col - half) * TILE_SIZE
            rects.append(("bottom",
                          pygame.Rect(x, (ROOM_ROWS - 1) * TILE_SIZE,
                                      span, TILE_SIZE)))
        if self.doors.get("left"):
            y = (mid_row - half) * TILE_SIZE
            rects.append(("left", pygame.Rect(0, y, TILE_SIZE, span)))
        if self.doors.get("right"):
            y = (mid_row - half) * TILE_SIZE
            rects.append(("right",
                          pygame.Rect((ROOM_COLS - 1) * TILE_SIZE, y,
                                      TILE_SIZE, span)))
        return rects

    @property
    def biome_terrain(self):
        """Return the room's biome terrain key ("mud"/"ice"/"water"/None)."""
        return self._terrain_type

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

    def _mark_primary_failed(self, status):
        """Flag the primary objective as unrecoverable and engage the secondary fallback.

        Doors stay sealed (portal off) until ``_check_secondary_objective`` resolves the
        fallback. ``status`` is the rule-specific HUD label key (e.g. ``"escort_down"``,
        ``"alarm"``, ``"lost_race"``).
        """
        self._secondary_objective_active = True
        self.objective_status = status
        self._set_portal_active(False)

    def _check_secondary_objective(self, now_ticks, enemy_group):
        """Resolve the secondary objective when the primary has been failed.

        Default secondary objective: clear the room of enemies. Future per-rule
        overrides can hook here to substitute a more thematic fallback.
        Returns True when the secondary objective just completed.
        """
        if not self._secondary_objective_active:
            return False
        if len(enemy_group) == 0:
            self.objective_status = "completed"
            self._set_portal_active(True)
            return True
        return False

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
            if self._is_heartstone_variant():
                # Heartstone variant: portal stays sealed until the heartstone
                # is delivered; spawn the heartstone at the chest position.
                self._set_portal_active(False)
                if self._heartstone_config is None:
                    drop_pos = self.chest_pos or (0, 0)
                    self._heartstone_config = {
                        "kind": "heartstone",
                        "pos": tuple(drop_pos),
                        "carried": False,
                        "delivered": False,
                    }
                    self._heartstone_spawn_pending = True
            else:
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
                already_completed = self.objective_status == "completed"
                self.objective_status = "completed"
                self._set_portal_active(True)
                if not already_completed and not escort.get("destroyed"):
                    # Mark destroyed so re-entering the room won't respawn the
                    # escort sprite, and tell rpg.py to despawn the live one.
                    escort["destroyed"] = True
                    return {"kind": "despawn_escort"}
            elif escort.get("destroyed"):
                failure_status = (
                    "carrier_down" if rule == "escort_bomb_to_exit" else "escort_down"
                )
                self._mark_primary_failed(failure_status)
                self._check_secondary_objective(now_ticks, enemy_group)
            else:
                self.objective_status = "active"
                self._set_portal_active(False)
            return None

        if rule == "avoid_alarm_zones":
            if not self._has_triggered_alarm_beacon():
                self._stealth_search_started_at = None
                self._stealth_alarm_started_at = None
                self.objective_status = "active"
                self._set_portal_active(True)
                stealth_reward_update = self._maybe_prepare_stealth_bonus_cache()
                if stealth_reward_update is not None:
                    return stealth_reward_update
                return None

            search_window_ms = self._stealth_search_window_ms()
            triggered_count = self._alarm_trigger_count()
            if search_window_ms > 0 and not self._stealth_lockdown_started:
                if self._stealth_search_started_at is None:
                    self._stealth_search_started_at = now_ticks
                if triggered_count < 2 and now_ticks - self._stealth_search_started_at < search_window_ms:
                    self.objective_status = "search"
                    self._set_portal_active(True)
                    stealth_reward_update = self._maybe_forfeit_stealth_bonus_cache()
                    if stealth_reward_update is not None:
                        return stealth_reward_update
                    return None
                self._stealth_lockdown_started = True

            self._mark_primary_failed("alarm")
            portal_should_stay_active = self._stealth_uses_escape_variant()
            if self._stealth_uses_release_variant():
                if self._stealth_alarm_started_at is None:
                    self._stealth_alarm_started_at = now_ticks
                if self._stealth_release_remaining_ms(now_ticks) == 0:
                    self.objective_status = "escape"
                    portal_should_stay_active = True
            self._set_portal_active(portal_should_stay_active)
            stealth_reward_update = self._maybe_forfeit_stealth_bonus_cache()
            if stealth_reward_update is not None:
                return stealth_reward_update
            if not self._reinforcement_spawned:
                reinforcements = self._spawn_reinforcement_wave()
                self._reinforcement_spawned = True
                self.enemy_configs.extend(reinforcements)
                return {"kind": "spawn_reinforcements", "enemy_configs": reinforcements}
            self._check_secondary_objective(now_ticks, enemy_group)
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
                if not self._secondary_objective_active:
                    self._mark_primary_failed("lost_race")
                self._check_secondary_objective(now_ticks, enemy_group)
                return None

            claim_update = self._maybe_restore_resource_race_chest(now_ticks, enemy_group)
            if claim_update is not None:
                return claim_update

            if self._is_heartstone_variant():
                # Emit a one-shot spawn update the first tick after pickup.
                if self._heartstone_spawn_pending and self._heartstone_config is not None:
                    self._heartstone_spawn_pending = False
                    self.objective_status = "escape"
                    self._set_portal_active(False)
                    return {
                        "kind": "spawn_heartstone",
                        "position": self._heartstone_config["pos"],
                    }
                # Completion requires delivery, not just enemy clear.
                if self._heartstone_delivered:
                    self.objective_status = "completed"
                    self._set_portal_active(True)
                else:
                    self.objective_status = "escape"
                    self._set_portal_active(False)
                return None

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
            # Crystal Vein: grant a room-scoped buff for each crystal the
            # player has destroyed since the last poll.  Buffs persist for
            # the room lifetime (cleared on room exit by Dungeon).
            if self.room_plan.room_id == "earth_crystal_vein":
                for cfg in self.objective_entity_configs:
                    if cfg.get("kind") != "vein_crystal":
                        continue
                    if cfg.get("destroyed") and not cfg.get("buff_applied"):
                        self.add_room_buff(
                            cfg["buff_stat"],
                            cfg["buff_magnitude"],
                            expires_at=None,
                        )
                        cfg["buff_applied"] = True
            # Burrower Den: harvest pending spawn flags from each spawner
            # and emit a single ``spawn_enemies`` update so rpg.py can
            # add the new enemies to the live group.
            if self.room_plan.room_id == "earth_burrower_den":
                fresh_configs = []
                for cfg in self.objective_entity_configs:
                    if cfg.get("kind") != "burrow_spawner":
                        continue
                    if cfg.get("pending_spawn"):
                        cfg["pending_spawn"] = False
                        fresh_configs.append((ChaserEnemy, cfg["pos"]))
                if fresh_configs:
                    self.enemy_configs.extend(fresh_configs)
                    return {
                        "kind": "spawn_enemies",
                        "source": "burrower_den",
                        "enemy_configs": fresh_configs,
                    }
            return None

        if rule == "destroy_altars":
            # Defensive: keep ritual link state fresh every frame so a destroyed
            # ward immediately drops shielding on remaining altars even if no
            # new ritual reaction triggers this tick.
            self._refresh_ritual_links()
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
                self._timed_extraction_route_sealed = False
                self.objective_status = "overtime"
                if not self._reinforcement_spawned:
                    reinforcements = self._spawn_reinforcement_wave()
                    self._reinforcement_spawned = True
                    self.enemy_configs.extend(reinforcements)
                    self._set_portal_active(True)
                    return {"kind": "spawn_reinforcements", "enemy_configs": reinforcements}
            else:
                extraction_update = self._maybe_spawn_timed_extraction_wave(elapsed_ms)
                if extraction_update is not None:
                    self.objective_status = "collapse"
                    self._set_portal_active(False)
                    return extraction_update
                if self._timed_extraction_route_sealed and len(enemy_group) > 0:
                    self.objective_status = "collapse"
                    self._set_portal_active(False)
                    return None
                else:
                    self._timed_extraction_route_sealed = False
                    self.objective_status = "escape"
                    self._set_portal_active(True)
                    return None
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
            next_target = self._puzzle_expected_label(controller)
            reset_suffix = ""
            if controller.get("last_reset_label"):
                reset_suffix = f" | Reset on {controller['last_reset_label']}"
            next_suffix = f" | Next {next_target}" if next_target else ""
            return {
                "visible": True,
                "label": f"Objective: Charge {label} {activated}/{total}{next_suffix}{reset_suffix}{pressure_suffix}",
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
                if self._stealth_uses_release_variant():
                    remaining_ms = self._stealth_release_remaining_ms(now_ticks)
                    if remaining_ms > 0:
                        return {
                            "visible": True,
                            "label": f"Objective: Alarm raised {remaining_ms / 1000:.1f}s | Hold out",
                        }
                    return {"visible": True, "label": "Objective: Alarm raised, seals broken | Escape"}
                if self._stealth_uses_escape_variant():
                    return {"visible": True, "label": "Objective: Alarm raised, escape or clear pursuit"}
                return {"visible": True, "label": "Objective: Alarm raised, clear the room"}
            bonus_suffix = " | Bonus cache armed" if self._stealth_bonus_cache_available() else ""
            return {"visible": True, "label": f"Objective: Slip through unseen{bonus_suffix}"}

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
                    if self._timed_extraction_clean_bonus_pending():
                        pressure_suffix += " | Preserve payout"
                    return {
                        "visible": True,
                        "label": f"Objective: Escape {remaining_ms / 1000:.1f}s{pressure_suffix}",
                    }
            if self.objective_status == "overtime":
                return {"visible": True, "label": "Objective: Escape under pressure | Payout reduced"}
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
            if self._puzzle_variant() == "staggered_plates":
                sequence = ", ".join(self._puzzle_sequence_labels())
                return f"Solve: Follow the staggered {label} order {sequence}. Wrong steps or stalling summon reinforcements."
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
                if self._stealth_uses_release_variant():
                    if self._stealth_release_remaining_ms(now_ticks) > 0:
                        return "Solve: Stealth failed. Hold out until the seals release, or clear the room early."
                    return "Solve: Stealth failed. The seals broke. Escape before pursuit corners you, or clear the room."
                if self._stealth_uses_escape_variant():
                    return "Solve: Stealth failed. Break through the pursuit or sprint for the exit while it stays open."
                return "Solve: Stealth failed. Clear the room to proceed."
            if self._stealth_bonus_cache_available():
                return "Solve: Avoid the alarm beacons, claim the bonus cache, and slip through unseen."
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
                if self._timed_extraction_clean_bonus_pending():
                    return f"Solve: Reach the exit with the {relic_label} while pursuit waves close the route behind you and preserve the payout."
                return f"Solve: Reach the exit with the {relic_label} while pursuit waves close the route behind you."
            if self.objective_status == "overtime":
                return "Solve: Escape under pressure before reinforcements overwhelm you. Overtime cuts the extraction payout."
            if self._timed_extraction_clean_bonus_pending():
                return f"Solve: Reach the exit with the {relic_label} before time runs out to preserve the bonus payout."
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
                if variant == "mixed_lanes":
                    return "Solve: Use the entry and checkpoint switches to reroute through mixed trap lanes. The challenge lane keeps every hazard live but upgrades the chest."
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
        self._timed_extraction_route_sealed = True
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

    def _stealth_uses_escape_variant(self):
        return bool(
            self.room_plan is not None
            and self.room_plan.objective_rule == "avoid_alarm_zones"
            and self.room_plan.objective_variant == "escape_on_alarm"
        )

    def _stealth_uses_release_variant(self):
        return bool(
            self.room_plan is not None
            and self.room_plan.objective_rule == "avoid_alarm_zones"
            and self.room_plan.objective_variant == "release_on_alarm"
        )

    def _stealth_release_window_ms(self):
        if self.room_plan is None or self.room_plan.objective_rule != "avoid_alarm_zones":
            return 0
        return max(1000, int(self.room_plan.objective_duration_ms or _STEALTH_SEARCH_WINDOW_MS))

    def _stealth_release_remaining_ms(self, now_ticks):
        if self._stealth_alarm_started_at is None:
            return 0
        return max(0, self._stealth_release_window_ms() - (now_ticks - self._stealth_alarm_started_at))

    def _stealth_bonus_cache_available(self):
        return (
            self.room_plan is not None
            and self.room_plan.objective_rule == "avoid_alarm_zones"
            and self._stealth_bonus_cache_armed
            and self.chest_pos is not None
            and not self.chest_looted
            and not self._stealth_bonus_cache_forfeited
            and not self._has_triggered_alarm_beacon()
        )

    def _maybe_prepare_stealth_bonus_cache(self):
        if self.room_plan is None or self.room_plan.objective_rule != "avoid_alarm_zones":
            return None
        if self.chest_looted or self._stealth_bonus_cache_forfeited:
            return None

        reward_tier = _REWARD_TIER_UPGRADES.get(self._chest_reward_tier, self._chest_reward_tier)
        self._stealth_bonus_cache_armed = True

        if self.chest_pos is None:
            self.chest_pos = self._random_floor_pos(margin=3)
            self.chest_looted = False
            self._chest_reward_tier = reward_tier
            return {
                "kind": "spawn_reward_chest",
                "position": self.chest_pos,
                "reward_tier": reward_tier,
            }

        if reward_tier != self._chest_reward_tier:
            self._chest_reward_tier = reward_tier
            return {"kind": "upgrade_reward_chest", "reward_tier": reward_tier}
        return None

    def _maybe_forfeit_stealth_bonus_cache(self):
        if (
            self.room_plan is None
            or self.room_plan.objective_rule != "avoid_alarm_zones"
            or self._stealth_bonus_cache_forfeited
            or self.chest_looted
            or self.chest_pos is None
            or not self._stealth_bonus_cache_armed
        ):
            return None

        self._stealth_bonus_cache_forfeited = True
        self.chest_looted = True
        return {"kind": "forfeit_chest"}

    def _timed_extraction_clean_bonus_pending(self):
        return (
            self.room_plan is not None
            and self.room_plan.objective_rule == "loot_then_timer"
            and self.chest_looted
            and self.objective_status != "overtime"
            and not self._timed_extraction_bonus_awarded
        )

    def claim_timed_extraction_completion_bonus(self):
        if not self._timed_extraction_clean_bonus_pending():
            return 0
        self._timed_extraction_bonus_awarded = True
        return _TIMED_EXTRACTION_CLEAN_BONUS_COINS.get(self.room_plan.reward_tier, 0)

    def timed_extraction_bonus_state(self):
        """Return the current Mire Cache extraction bonus state for HUD display.

        ``available`` is True while the player can still earn the bonus by
        completing the room cleanly (chest looted, not in overtime, not yet
        awarded). ``amount`` is the coin value the bonus would award now.
        Returns None for non-extraction rooms so the HUD can hide the badge.
        """
        if self.room_plan is None or self.room_plan.objective_rule != "loot_then_timer":
            return None
        amount = _TIMED_EXTRACTION_CLEAN_BONUS_COINS.get(self.room_plan.reward_tier, 0)
        return {
            "available": self._timed_extraction_clean_bonus_pending(),
            "amount": amount,
        }

    def _escort_config(self):
        for config in self.objective_entity_configs:
            if config.get("kind") == "escort_npc":
                return config
        return None

    # ── Heartstone Claim helpers ───────────────────────
    def _is_heartstone_variant(self):
        return (
            self.room_plan is not None
            and self.room_plan.objective_rule == "claim_relic_before_lockdown"
            and (self.room_plan.objective_variant or "") == "heartstone_shard"
        )

    def heartstone_state(self):
        """Return current heartstone state, or None if not active in this room."""
        if not self._is_heartstone_variant() or self._heartstone_config is None:
            return None
        config = self._heartstone_config
        return {
            "pos": config["pos"],
            "carried": config["carried"],
            "delivered": config["delivered"],
        }

    def notify_heartstone_picked_up(self):
        if self._heartstone_config is None:
            return
        self._heartstone_config["carried"] = True

    def notify_heartstone_dropped(self, pos):
        if self._heartstone_config is None:
            return
        self._heartstone_config["carried"] = False
        self._heartstone_config["pos"] = (int(pos[0]), int(pos[1]))

    def notify_heartstone_position(self, pos):
        if self._heartstone_config is None:
            return
        self._heartstone_config["pos"] = (int(pos[0]), int(pos[1]))

    def notify_heartstone_delivered(self):
        if self._heartstone_config is None:
            return
        self._heartstone_config["delivered"] = True
        self._heartstone_config["carried"] = False
        self._heartstone_delivered = True

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

    def _puzzle_target_sequence(self, variant=None, plate_count=0):
        if variant is None:
            variant = self._puzzle_variant()
        if plate_count <= 0:
            plate_count = len(self.objective_entity_configs)
        if variant == "staggered_plates":
            return tuple(range(0, plate_count, 2)) + tuple(range(1, plate_count, 2))
        return tuple(range(plate_count))

    def _puzzle_expected_plate_id(self, controller=None):
        controller = controller or self._puzzle_controller() or {}
        sequence = controller.get("target_sequence") or self._puzzle_target_sequence(
            controller.get("variant", self._puzzle_variant()),
            len(controller.get("configs", ())),
        )
        progress_index = controller.get("progress_index", 0)
        if progress_index < 0 or progress_index >= len(sequence):
            return None
        return sequence[progress_index]

    def _puzzle_expected_label(self, controller=None):
        controller = controller or self._puzzle_controller() or {}
        expected_plate_id = self._puzzle_expected_plate_id(controller)
        if expected_plate_id is None:
            return ""
        for config in controller.get("configs", ()):
            if config.get("plate_id", config.get("order_index", 0)) == expected_plate_id:
                return config.get("telegraph_text", str(expected_plate_id + 1))
        return str(expected_plate_id + 1)

    def _puzzle_sequence_labels(self, controller=None):
        controller = controller or self._puzzle_controller() or {}
        sequence = controller.get("target_sequence") or self._puzzle_target_sequence(
            controller.get("variant", self._puzzle_variant()),
            len(controller.get("configs", ())),
        )
        labels = []
        for plate_id in sequence:
            label = str(plate_id + 1)
            for config in controller.get("configs", ()):
                if config.get("plate_id", config.get("order_index", 0)) == plate_id:
                    label = config.get("telegraph_text", label)
                    break
            labels.append(label)
        return tuple(labels)

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

        expected_plate_id = self._puzzle_expected_plate_id(controller)
        ordered_targets = [
            config
            for config in active_plates
            if config.get("plate_id", config.get("order_index", 0)) == expected_plate_id
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
            next_label = self._puzzle_expected_label(controller)
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
                    "patrol_points": self._stealth_patrol_points(
                        pos,
                        self.room_plan.objective_patrol_offset,
                        shape=self.room_plan.objective_patrol_shape,
                    ),
                    "patrol_cycle_ms": 1800 + index * 250,
                    "vision_angle_deg": 75,
                }
                for index, pos in enumerate(beacon_positions)
            ]
        elif self.room_plan.objective_rule == "rune_altar":
            self.objective_entity_configs = self._build_rune_altar_configs()
        elif self.room_plan.room_id == "earth_crystal_vein":
            self.objective_entity_configs = self._build_crystal_vein_configs()
        elif self.room_plan.room_id == "earth_tremor_chamber":
            self.objective_entity_configs = self._build_tremor_chamber_configs()
        elif self.room_plan.room_id == "earth_mushroom_grove":
            self.objective_entity_configs = self._build_mushroom_grove_configs()
        elif self.room_plan.room_id == "earth_cave_in":
            self.objective_entity_configs = self._build_cave_in_configs()
        elif self.room_plan.room_id == "earth_mining_carts":
            self.objective_entity_configs = self._build_mining_carts_configs()
        elif self.room_plan.room_id == "earth_burrower_den":
            self.objective_entity_configs = self._build_burrower_den_configs()
        elif self.room_plan.room_id == "earth_echo_cavern":
            # Echo Cavern is a fog-of-war room — no entities to spawn,
            # just narrow the camera vision radius.  Set this here so
            # rooms re-built (e.g. on revisit) keep the effect.
            self.vision_radius = 96
        elif self.room_plan.room_id == "earth_boulder_run":
            self.objective_entity_configs = self._build_boulder_run_configs()
        elif self.room_plan.room_id == "earth_shrine_circle":
            self.objective_entity_configs = self._build_shrine_circle_configs()

    def _build_crystal_vein_configs(self):
        """Place 3-4 destructible vein crystals on FLOOR cells.

        Each crystal advertises a single buff (``damage`` / ``speed`` /
        ``armor``) granted via ``Room.add_room_buff`` when destroyed.  See
        :meth:`update_objective` rule branch ``crystal_vein``.
        """
        crystal_count = random.randint(3, 4)
        buff_pool = (
            ("damage", 0.20),
            ("speed",  0.20),
            ("armor",  0.15),
        )
        positions = self._sample_floor_positions(crystal_count)
        return [
            {
                "kind": "vein_crystal",
                "pos": pos,
                "max_hp": 1,
                "current_hp": 1,
                "buff_stat": stat,
                "buff_magnitude": magnitude,
                "destroyed": False,
                "buff_applied": False,
            }
            for pos, (stat, magnitude) in zip(
                positions,
                random.choices(buff_pool, k=crystal_count),
            )
        ]

    def _build_tremor_chamber_configs(self):
        """Single invisible tremor emitter centred in the room."""
        cx = (ROOM_COLS // 2) * TILE_SIZE + TILE_SIZE // 2
        cy = (ROOM_ROWS // 2) * TILE_SIZE + TILE_SIZE // 2
        return [
            {
                "kind": "tremor_emitter",
                "pos": (cx, cy),
                "cycle_ms": 4000,
                "telegraph_ms": 1500,
                "strike_ms": 500,
                "stun_duration_ms": 1000,
                "offset_ms": 0,
                # Live room reference so the emitter can poll HEARTH safe
                # tiles when checking whether to suppress a stun strike.
                "room": self,
            }
        ]

    def _sample_floor_positions(self, count):
        """Pick up to ``count`` random pixel-centres on FLOOR cells."""
        candidates = [
            (c, r)
            for r in range(2, ROOM_ROWS - 2)
            for c in range(2, ROOM_COLS - 2)
            if self.grid[r][c] == FLOOR
        ]
        random.shuffle(candidates)
        chosen = candidates[:count]
        return [
            (c * TILE_SIZE + TILE_SIZE // 2, r * TILE_SIZE + TILE_SIZE // 2)
            for c, r in chosen
        ]

    def _build_mushroom_grove_configs(self):
        """Place 3-4 destructible spore mushrooms with staggered pulse phases."""
        mushroom_count = random.randint(3, 4)
        positions = self._sample_floor_positions(mushroom_count)
        cycle_ms = 3000
        return [
            {
                "kind": "spore_mushroom",
                "pos": pos,
                "max_hp": 3,
                "current_hp": 3,
                "pulse_cycle_ms": cycle_ms,
                "pulse_active_ms": 700,
                "pulse_offset_ms": (cycle_ms // mushroom_count) * index,
                "pulse_radius": 80,
                "poison_duration_ms": 5000,
                "destroyed": False,
            }
            for index, pos in enumerate(positions)
        ]

    def _build_cave_in_configs(self):
        """Single collapse emitter centred in the room."""
        cx = (ROOM_COLS // 2) * TILE_SIZE + TILE_SIZE // 2
        cy = (ROOM_ROWS // 2) * TILE_SIZE + TILE_SIZE // 2
        return [
            {
                "kind": "collapse_emitter",
                "pos": (cx, cy),
                "cycle_ms": 5000,
                "telegraph_ms": 1500,
                "max_collapses": 4,
                "offset_ms": 0,
                "collapses_done": 0,
                # Live room reference: the emitter mutates ``room.grid``
                # directly when a tile collapses to PIT_TILE.
                "room": self,
            }
        ]

    def _build_mining_carts_configs(self):
        """Lay 2-3 horizontal CART_RAIL rows and spawn one cart per row."""
        # Choose 2-3 rail rows spaced across the play area.
        candidate_rows = [3, 6, 9, 12]
        cart_count = random.randint(2, 3)
        random.shuffle(candidate_rows)
        rail_rows = sorted(candidate_rows[:cart_count])

        # Lay the rail tiles (only over FLOOR — preserves walls/doors).
        for row in rail_rows:
            for col in range(1, ROOM_COLS - 1):
                if self.grid[row][col] == FLOOR:
                    self.grid[row][col] = CART_RAIL

        configs = []
        room_width = ROOM_COLS * TILE_SIZE
        for index, row in enumerate(rail_rows):
            cy = row * TILE_SIZE + TILE_SIZE // 2
            # Alternate direction + stagger horizontal offset for variety.
            direction = 1 if index % 2 == 0 else -1
            start_x = (room_width // (cart_count + 1)) * (index + 1)
            configs.append({
                "kind": "mining_cart",
                "pos": (start_x, cy),
                "speed": 2.4 * direction,
                "damage": 8,
                "knockback_px": 24,
                "damage_cooldown_ms": 600,
            })
        return configs

    def _build_burrower_den_configs(self):
        """Place 3-4 burrow spawners on FLOOR cells with staggered phases."""
        spawner_count = random.randint(3, 4)
        positions = self._sample_floor_positions(spawner_count)
        cycle_ms = 4500
        return [
            {
                "kind": "burrow_spawner",
                "pos": pos,
                "cycle_ms": cycle_ms,
                "telegraph_ms": 1500,
                "max_spawns": 4,
                "offset_ms": (cycle_ms // spawner_count) * index,
                "spawns_done": 0,
                "pending_spawn": False,
            }
            for index, pos in enumerate(positions)
        ]

    def _build_boulder_run_configs(self):
        """Pick 2-3 lane rows and spawn one telegraphed boulder per lane.

        Lanes alternate direction; phases are staggered so boulders don't
        all strike on the same beat.
        """
        candidate_rows = [3, 6, 9, 12]
        boulder_count = random.randint(2, 3)
        random.shuffle(candidate_rows)
        lane_rows = sorted(candidate_rows[:boulder_count])
        cycle_ms = 3600
        configs = []
        for index, row in enumerate(lane_rows):
            cy = row * TILE_SIZE + TILE_SIZE // 2
            direction = 1 if index % 2 == 0 else -1
            configs.append({
                "kind": "boulder",
                "lane_y": cy,
                "pos": (-1000, cy),
                "direction": direction,
                "cycle_ms": cycle_ms,
                "telegraph_ms": 900,
                "speed": 6,
                "damage": 10,
                "knockback_px": 32,
                "damage_cooldown_ms": 700,
                "offset_ms": (cycle_ms // boulder_count) * index,
            })
        return configs

    def _build_shrine_circle_configs(self):
        """Lay a 3x3 GLYPH_TILE shrine in the room centre + place the glyph entity.

        The entity tracks the glyph tile coords; while the player stands
        on any of them, ``apply_room_pressure`` slows every enemy in the
        room (see ShrineGlyph).
        """
        cx_col = ROOM_COLS // 2
        cy_row = ROOM_ROWS // 2
        glyph_tiles = set()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                col = cx_col + dc
                row = cy_row + dr
                if 1 <= col < ROOM_COLS - 1 and 1 <= row < ROOM_ROWS - 1:
                    if self.grid[row][col] == FLOOR:
                        self.grid[row][col] = GLYPH_TILE
                        glyph_tiles.add((col, row))
        cx = cx_col * TILE_SIZE + TILE_SIZE // 2
        cy = cy_row * TILE_SIZE + TILE_SIZE // 2
        return [
            {
                "kind": "shrine_glyph",
                "pos": (cx, cy),
                "glyph_tiles": glyph_tiles,
                "slow_ms": 600,
            }
        ]

    def _build_rune_altar_configs(self):
        """Generate one rune altar centred in the room with three rune offers.

        The offered rune ids are sampled at room-build time so the choice is
        stable across visits.  ``consumed`` flips to True after the player
        commits a pick via :meth:`consume_rune_altar`.
        """
        cx = (ROOM_COLS // 2) * TILE_SIZE + TILE_SIZE // 2
        cy = (ROOM_ROWS // 2) * TILE_SIZE + TILE_SIZE // 2
        offered = rune_rules.generate_altar_offer(random)
        return [
            {
                "kind": "rune_altar",
                "label": self.room_plan.objective_label or "Rune Altar",
                "pos": (cx, cy),
                "offered_rune_ids": list(offered),
                "consumed": False,
            }
        ]

    def pending_rune_altar(self, player):
        """Return the first non-consumed altar config the player overlaps, or ``None``.

        Tracks a per-altar ``snoozed`` flag so that cancelling the pick prompt
        does not immediately re-trigger.  The flag clears once the player
        steps out of interaction range.
        """
        if self.room_plan is None or self.room_plan.objective_rule != "rune_altar":
            return None
        result = None
        for config in self.objective_entity_configs:
            if config.get("kind") != "rune_altar":
                continue
            if config.get("consumed"):
                continue
            if not config.get("offered_rune_ids"):
                continue
            ax, ay = config["pos"]
            px, py = player.rect.center
            in_range = (px - ax) ** 2 + (py - ay) ** 2 <= 36 ** 2
            if not in_range:
                config["snoozed"] = False
                continue
            if config.get("snoozed"):
                continue
            if result is None:
                result = config
        return result

    def consume_rune_altar(self, altar_config):
        """Mark *altar_config* as consumed so it does not re-offer on revisit."""
        altar_config["consumed"] = True

    def snooze_rune_altar(self, altar_config):
        """Mark *altar_config* as snoozed until the player leaves interaction range."""
        altar_config["snoozed"] = True

    def _build_trap_gauntlet_configs(self):
        trap_variant = self.room_plan.objective_variant or "sweeper_lanes"
        lane_count = max(2, min(4, self.room_plan.objective_entity_count or 3))
        if trap_variant == "crusher_corridors":
            lane_count = 2
        elif trap_variant == "mixed_lanes":
            lane_count = max(3, lane_count)
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
            lane_hazard = self._trap_lane_hazard_kind(trap_variant, index)
            if lane_hazard == "vent_lanes":
                hazard_config = self._trap_vent_config(
                    controller,
                    orientation,
                    offset,
                    lane_count,
                    index,
                )
                configs.append(hazard_config)
                configs.extend(
                    _safe_spot_configs(hazard_config, index)
                )
            elif lane_hazard == "crusher_corridors":
                crusher_configs = self._trap_crusher_configs(
                    controller,
                    orientation,
                    offset,
                    index,
                )
                for crusher_cfg in crusher_configs:
                    configs.append(crusher_cfg)
                    configs.extend(
                        _safe_spot_configs(crusher_cfg, index)
                    )
            else:
                hazard_config = self._trap_sweeper_config(
                    controller,
                    orientation,
                    offset,
                    lane_count,
                    index,
                )
                configs.append(hazard_config)
                configs.extend(
                    _safe_spot_configs(hazard_config, index)
                )
            for active_switch_bank in self._trap_switch_banks(trap_variant, switch_bank):
                configs.append(
                    self._trap_switch_config(
                        controller,
                        orientation,
                        offset,
                        lane_labels[index],
                        index,
                        active_switch_bank,
                    )
                )
        return configs

    @staticmethod
    def _trap_lane_hazard_kind(trap_variant, lane_index):
        if trap_variant == "mixed_lanes":
            return ("sweeper_lanes", "vent_lanes", "crusher_corridors")[lane_index % 3]
        return trap_variant

    @staticmethod
    def _trap_switch_banks(trap_variant, primary_switch_bank):
        if trap_variant == "mixed_lanes":
            return (primary_switch_bank, "checkpoint")
        return (primary_switch_bank,)

    def _build_puzzle_plate_configs(self):
        variant = self._puzzle_variant()
        plate_count = self.room_plan.objective_entity_count or (4 if variant in {"paired_runes", "staggered_plates"} else 3)
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
                        "plate_id": index,
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
                        "plate_id": index,
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
            controller["target_sequence"] = self._puzzle_target_sequence(variant, plate_count)
        controller["configs"] = configs
        return configs

    def _trap_sweeper_config(self, controller, orientation, offset, lane_count, lane_index):
        travel_min = 4 * TILE_SIZE + TILE_SIZE // 2
        if orientation == "horizontal":
            travel_max = (ROOM_COLS - 5) * TILE_SIZE + TILE_SIZE // 2
            center = self._offset_to_pixel((0, offset))
            start_x = self._trap_travel_start(travel_min, travel_max, lane_count, lane_index)
            position = (start_x, center[1])
            lane_center_px = center[1]
        else:
            travel_max = (ROOM_ROWS - 5) * TILE_SIZE + TILE_SIZE // 2
            center = self._offset_to_pixel((offset, 0))
            start_y = self._trap_travel_start(travel_min, travel_max, lane_count, lane_index)
            position = (center[0], start_y)
            lane_center_px = center[0]

        lane_thickness = 3 * TILE_SIZE
        safe_spots = _compute_sweeper_safe_spots(
            orientation, travel_min, travel_max, lane_center_px, lane_thickness,
        )
        return {
            "kind": "trap_sweeper",
            "lane_index": lane_index,
            "controller": controller,
            "orientation": orientation,
            "pos": position,
            "travel_min": travel_min,
            "travel_max": travel_max,
            "direction": 1 if lane_index % 2 == 0 else -1,
            "speed": 1.5,
            "challenge_speed": 0.9,
            "damage": 8,
            "damage_cooldown_ms": 350,
            "damage_cooldown_until": 0,
            "lane_thickness": lane_thickness,
            "safe_spots": safe_spots,
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

        lane_thickness = 3 * TILE_SIZE
        cycle_ms = 2800
        active_ms = 1800
        safe_spots = _compute_timed_safe_spots(
            orientation, travel_min, travel_max, center, lane_thickness,
            cycle_ms, active_ms,
        )
        return {
            "kind": "trap_vent_lane",
            "lane_index": lane_index,
            "controller": controller,
            "orientation": orientation,
            "center": center,
            "emitter_pos": emitter_pos,
            "travel_min": travel_min,
            "travel_max": travel_max,
            "cycle_ms": cycle_ms,
            "active_ms": active_ms,
            "challenge_cycle_ms": 2200,
            "challenge_active_ms": 1700,
            "phase_offset_ms": lane_index * 200,
            "damage": 7,
            "damage_cooldown_ms": 280,
            "damage_cooldown_until": 0,
            "lane_thickness": lane_thickness,
            "safe_spots": safe_spots,
            "active": lane_index != controller["safe_lane"],
        }

    def _trap_switch_config(self, controller, orientation, offset, label, lane_index, switch_bank):
        if orientation == "horizontal":
            if switch_bank == "checkpoint":
                col = ROOM_COLS // 2
            else:
                col = 2 if switch_bank == "left" else ROOM_COLS - 3
            row = ROOM_ROWS // 2 + offset
        else:
            col = ROOM_COLS // 2 + offset
            if switch_bank == "checkpoint":
                row = ROOM_ROWS // 2
            else:
                row = 2 if switch_bank == "top" else ROOM_ROWS - 3

        return {
            "kind": "trap_lane_switch",
            "lane_index": lane_index,
            "label": label,
            "controller": controller,
            "switch_bank": switch_bank,
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
                lane_thickness = 3 * TILE_SIZE
                cycle_ms = 2400
                active_ms = 1300
                zone_w = lane_thickness
                configs.append(
                    {
                        "kind": "trap_crusher",
                        "lane_index": lane_index,
                        "controller": controller,
                        "emitter_pos": (center_x, emitter_y),
                        "zone_rect": (center_x - zone_w // 2, lane_center - lane_thickness // 2, zone_w, lane_thickness),
                        "cycle_ms": cycle_ms,
                        "active_ms": active_ms,
                        "challenge_cycle_ms": 1800,
                        "challenge_active_ms": 1200,
                        "phase_offset_ms": phase_index * 350 + lane_index * 175,
                        "damage": 9,
                        "damage_cooldown_ms": 350,
                        "damage_cooldown_until": 0,
                        "safe_spots": [],
                        "active": lane_index != controller["safe_lane"],
                    }
                )
        else:
            lane_center = self._offset_to_pixel((offset, 0))[0]
            emitter_x = 2 * TILE_SIZE if offset < 0 else (ROOM_COLS - 3) * TILE_SIZE
            for phase_index, row in enumerate((ROOM_ROWS // 2 - 2, ROOM_ROWS // 2 + 2)):
                center_y = row * TILE_SIZE + TILE_SIZE // 2
                lane_thickness = 3 * TILE_SIZE
                cycle_ms = 2400
                active_ms = 1300
                zone_h = lane_thickness
                configs.append(
                    {
                        "kind": "trap_crusher",
                        "lane_index": lane_index,
                        "controller": controller,
                        "emitter_pos": (emitter_x, center_y),
                        "zone_rect": (lane_center - lane_thickness // 2, center_y - zone_h // 2, lane_thickness, zone_h),
                        "cycle_ms": cycle_ms,
                        "active_ms": active_ms,
                        "challenge_cycle_ms": 1800,
                        "challenge_active_ms": 1200,
                        "phase_offset_ms": phase_index * 350 + lane_index * 175,
                        "damage": 9,
                        "damage_cooldown_ms": 350,
                        "damage_cooldown_until": 0,
                        "safe_spots": [],
                        "active": lane_index != controller["safe_lane"],
                    }
                )
        return configs

    def _carve_trap_gauntlet_lanes(self):
        controller = self._trap_controller()
        if controller is None:
            return

        # Fill the entire interior with walls so only explicitly carved areas are walkable.
        for r in range(1, ROOM_ROWS - 1):
            for c in range(1, ROOM_COLS - 1):
                if self.grid[r][c] not in {DOOR, PORTAL}:
                    self.grid[r][c] = WALL

        if controller.get("variant") == "crusher_corridors":
            self._shape_crusher_corridors(controller)
        elif controller.get("variant") == "mixed_lanes":
            self._shape_mixed_lanes(controller)
        else:
            # sweeper_lanes and vent_lanes share the same lane geometry
            orientation = controller["orientation"]
            for offset in controller["lane_offsets"]:
                if orientation == "horizontal":
                    row = ROOM_ROWS // 2 + offset
                    for r in range(max(1, row - 1), min(ROOM_ROWS - 1, row + 2)):
                        for c in range(1, ROOM_COLS - 1):
                            if self.grid[r][c] not in {DOOR, PORTAL}:
                                self.grid[r][c] = FLOOR
                else:
                    col = ROOM_COLS // 2 + offset
                    for c in range(max(1, col - 1), min(ROOM_COLS - 1, col + 2)):
                        for r in range(1, ROOM_ROWS - 1):
                            if self.grid[r][c] not in {DOOR, PORTAL}:
                                self.grid[r][c] = FLOOR

        # Always carve the entry lobby and reward arena last so they override any wall
        # placed by variant handlers (e.g. mixed_lanes separator logic).
        self._carve_gauntlet_endpoints(controller)

    def _carve_gauntlet_endpoints(self, controller):
        """Open a small entry lobby (player-side) and a reward arena (chest-side).

        This lets the player choose their lane from the entry and converge at the
        chest from any lane once they reach the far end.
        """
        orientation = controller.get("orientation", "horizontal")
        switch_bank = controller.get("switch_bank", "left")
        lane_offsets = controller.get("lane_offsets", (0,))

        if orientation == "horizontal":
            center = ROOM_ROWS // 2
            lane_min = max(1, center + min(lane_offsets) - 1)
            lane_max = min(ROOM_ROWS - 2, center + max(lane_offsets) + 1)
            if switch_bank == "left":
                entry_cols = range(1, 1 + _GAUNTLET_ENTRY_DEPTH)
                reward_cols = range(ROOM_COLS - 1 - _GAUNTLET_REWARD_DEPTH, ROOM_COLS - 1)
            else:
                entry_cols = range(ROOM_COLS - 1 - _GAUNTLET_ENTRY_DEPTH, ROOM_COLS - 1)
                reward_cols = range(1, 1 + _GAUNTLET_REWARD_DEPTH)
            for c in (*entry_cols, *reward_cols):
                for r in range(lane_min, lane_max + 1):
                    if self.grid[r][c] not in {DOOR, PORTAL}:
                        self.grid[r][c] = FLOOR
        else:
            center = ROOM_COLS // 2
            lane_min = max(1, center + min(lane_offsets) - 1)
            lane_max = min(ROOM_COLS - 2, center + max(lane_offsets) + 1)
            if switch_bank == "top":
                entry_rows = range(1, 1 + _GAUNTLET_ENTRY_DEPTH)
                reward_rows = range(ROOM_ROWS - 1 - _GAUNTLET_REWARD_DEPTH, ROOM_ROWS - 1)
            else:
                entry_rows = range(ROOM_ROWS - 1 - _GAUNTLET_ENTRY_DEPTH, ROOM_ROWS - 1)
                reward_rows = range(1, 1 + _GAUNTLET_REWARD_DEPTH)
            for r in (*entry_rows, *reward_rows):
                for c in range(lane_min, lane_max + 1):
                    if self.grid[r][c] not in {DOOR, PORTAL}:
                        self.grid[r][c] = FLOOR

    def _shape_mixed_lanes(self, controller):
        orientation = controller["orientation"]
        lane_offsets = tuple(controller["lane_offsets"])

        if orientation == "horizontal":
            for offset in lane_offsets:
                row = ROOM_ROWS // 2 + offset
                for current_row in range(max(1, row - 1), min(ROOM_ROWS - 1, row + 2)):
                    for col in range(1, ROOM_COLS - 1):
                        if self.grid[current_row][col] not in {DOOR, PORTAL}:
                            self.grid[current_row][col] = FLOOR

            separator_rows = [
                ROOM_ROWS // 2 + (lane_offsets[index] + lane_offsets[index + 1]) // 2
                for index in range(len(lane_offsets) - 1)
            ]
            entry_cols = range(1, 4) if controller.get("switch_bank") == "left" else range(ROOM_COLS - 4, ROOM_COLS - 1)
            checkpoint_cols = range(max(1, ROOM_COLS // 2 - 1), min(ROOM_COLS - 1, ROOM_COLS // 2 + 2))
            gap_cols = set(entry_cols) | set(checkpoint_cols)

            for row in separator_rows:
                for col in range(1, ROOM_COLS - 1):
                    if self.grid[row][col] in {DOOR, PORTAL}:
                        continue
                    self.grid[row][col] = FLOOR if col in gap_cols else WALL
            return

        for offset in lane_offsets:
            col = ROOM_COLS // 2 + offset
            for current_col in range(max(1, col - 1), min(ROOM_COLS - 1, col + 2)):
                for row in range(1, ROOM_ROWS - 1):
                    if self.grid[row][current_col] not in {DOOR, PORTAL}:
                        self.grid[row][current_col] = FLOOR

        separator_cols = [
            ROOM_COLS // 2 + (lane_offsets[index] + lane_offsets[index + 1]) // 2
            for index in range(len(lane_offsets) - 1)
        ]
        entry_rows = range(1, 4) if controller.get("switch_bank") == "top" else range(ROOM_ROWS - 4, ROOM_ROWS - 1)
        checkpoint_rows = range(max(1, ROOM_ROWS // 2 - 1), min(ROOM_ROWS - 1, ROOM_ROWS // 2 + 2))
        gap_rows = set(entry_rows) | set(checkpoint_rows)

        for col in separator_cols:
            for row in range(1, ROOM_ROWS - 1):
                if self.grid[row][col] in {DOOR, PORTAL}:
                    continue
                self.grid[row][col] = FLOOR if row in gap_rows else WALL

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
                        if self.grid[row][col] not in {DOOR, PORTAL}:
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
                        if self.grid[row][col] not in {DOOR, PORTAL}:
                            self.grid[row][col] = FLOOR

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
        challenge_offset = 0
        if controller.get("variant") == "mixed_lanes":
            lane_offsets = controller.get("lane_offsets", ())
            challenge_lane = controller.get("challenge_lane", 0)
            if 0 <= challenge_lane < len(lane_offsets):
                challenge_offset = lane_offsets[challenge_lane]

        if controller.get("orientation") == "horizontal":
            col = ROOM_COLS - 3 if switch_bank == "left" else 2
            row = ROOM_ROWS // 2 + challenge_offset
        else:
            col = ROOM_COLS // 2 + challenge_offset
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

    def _stealth_patrol_points(self, position, patrol_offset=None, shape="line"):
        if patrol_offset is None:
            center_x = ROOM_COLS // 2 * TILE_SIZE + TILE_SIZE // 2
            center_y = ROOM_ROWS // 2 * TILE_SIZE + TILE_SIZE // 2
            delta_x = position[0] - center_x
            delta_y = position[1] - center_y

            if abs(delta_x) >= abs(delta_y):
                patrol_offset = (0, 2)
            else:
                patrol_offset = (2, 0)

        ox = patrol_offset[0] * TILE_SIZE
        oy = patrol_offset[1] * TILE_SIZE
        # Perpendicular vector for shapes that need a second axis.
        px = -patrol_offset[1] * TILE_SIZE
        py = patrol_offset[0] * TILE_SIZE

        shape_key = (shape or "line").strip().lower()
        if shape_key == "triangle":
            offsets = [
                (0, 0),
                (ox, oy),
                (px // 2, py // 2),
            ]
        elif shape_key == "square":
            offsets = [
                (0, 0),
                (ox, oy),
                (ox + px, oy + py),
                (px, py),
            ]
        elif shape_key == "zigzag":
            offsets = [
                (0, 0),
                (ox // 2, oy // 2 + py // 2),
                (ox, oy),
                (ox + ox // 2, oy + oy // 2 - py // 2),
            ]
        else:  # line (default)
            offsets = [
                (0, 0),
                (ox, oy),
                (-ox, -oy),
            ]

        patrol_points = [
            self._clamp_objective_pixel((position[0] + dx, position[1] + dy))
            for dx, dy in offsets
        ]
        return tuple(dict.fromkeys(patrol_points))

    @staticmethod
    def _clamp_objective_pixel(position):
        min_px = TILE_SIZE + TILE_SIZE // 2
        max_x = (ROOM_COLS - 2) * TILE_SIZE + TILE_SIZE // 2
        max_y = (ROOM_ROWS - 2) * TILE_SIZE + TILE_SIZE // 2
        return (
            max(min_px, min(max_x, int(position[0]))),
            max(min_px, min(max_y, int(position[1]))),
        )

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

    def _random_floor_pos(self, margin=3, door_buffer_tiles=None):
        """Return a (px, py) on a FLOOR tile.

        ``margin`` keeps the candidate ``margin`` tiles inside the room
        border.  ``door_buffer_tiles`` (defaults to
        ``ENEMY_DOOR_BUFFER_TILES``) rejects any tile within that
        Chebyshev distance of an open-door opening so enemies never
        spawn directly on top of an entry point.
        """
        if door_buffer_tiles is None:
            door_buffer_tiles = ENEMY_DOOR_BUFFER_TILES
        door_tiles = self._door_tile_set() if door_buffer_tiles > 0 else ()
        for _ in range(200):
            c = random.randint(margin, ROOM_COLS - 1 - margin)
            r = random.randint(margin, ROOM_ROWS - 1 - margin)
            if self.grid[r][c] != FLOOR:
                continue
            if door_tiles and self._near_door_tile(c, r, door_tiles, door_buffer_tiles):
                continue
            return (c * TILE_SIZE + TILE_SIZE // 2,
                    r * TILE_SIZE + TILE_SIZE // 2)
        # fallback: center
        return (ROOM_COLS // 2 * TILE_SIZE + TILE_SIZE // 2,
                ROOM_ROWS // 2 * TILE_SIZE + TILE_SIZE // 2)

    def _door_tile_set(self):
        """Return the set of (col, row) tiles forming each open-door opening."""
        mid_col = ROOM_COLS // 2
        mid_row = ROOM_ROWS // 2
        half = DOOR_WIDTH // 2
        tiles = set()
        if self.doors.get("top"):
            for dc in range(-half, half + 1):
                tiles.add((mid_col + dc, 0))
        if self.doors.get("bottom"):
            for dc in range(-half, half + 1):
                tiles.add((mid_col + dc, ROOM_ROWS - 1))
        if self.doors.get("left"):
            for dr in range(-half, half + 1):
                tiles.add((0, mid_row + dr))
        if self.doors.get("right"):
            for dr in range(-half, half + 1):
                tiles.add((ROOM_COLS - 1, mid_row + dr))
        return tiles

    @staticmethod
    def _near_door_tile(col, row, door_tiles, buffer_tiles):
        for dc, dr in door_tiles:
            if max(abs(col - dc), abs(row - dr)) <= buffer_tiles:
                return True
        return False

    def _gen_enemy_configs(self):
        return self._gen_enemy_configs_for_range(self._enemy_count_range)

    def _build_enemy_palette(self):
        """Pick up to ``ROOM_MAX_DISTINCT_ENEMY_TYPES`` distinct classes.

        Sampling is weighted by ``self._enemy_type_weights`` (truncated or
        padded to match ``ENEMY_CLASSES``) and uses no-replacement so the
        same class never appears twice in the palette.  The result is
        cached on the room so reinforcement spawns reuse it.
        """
        cached = getattr(self, "_enemy_palette", None)
        if cached:
            return cached
        weights = list(self._enemy_type_weights or [])
        # Pad/truncate to match ENEMY_CLASSES length.
        if len(weights) < len(ENEMY_CLASSES):
            weights = weights + [0] * (len(ENEMY_CLASSES) - len(weights))
        elif len(weights) > len(ENEMY_CLASSES):
            weights = weights[: len(ENEMY_CLASSES)]
        if all(w <= 0 for w in weights):
            weights = [1] * len(ENEMY_CLASSES)

        cap = ROOM_MAX_DISTINCT_ENEMY_TYPES
        # If sentries are spawned by an objective in this room, reserve one
        # slot so total visible types still fits in ``ROOM_MAX_DISTINCT_ENEMY_TYPES``.
        if self._room_uses_sentries():
            cap = max(1, cap - 1)

        pool_classes = list(ENEMY_CLASSES)
        pool_weights = list(weights)
        chosen = []
        chosen_weights = []
        while pool_classes and len(chosen) < cap:
            if all(w <= 0 for w in pool_weights):
                break
            idx = random.choices(range(len(pool_classes)), weights=pool_weights, k=1)[0]
            chosen.append(pool_classes.pop(idx))
            chosen_weights.append(pool_weights.pop(idx))
        self._enemy_palette = (tuple(chosen), tuple(chosen_weights))
        return self._enemy_palette

    def _room_uses_sentries(self):
        if self.room_plan is not None and self.room_plan.objective_rule == "avoid_alarm_zones":
            return True
        for cfg in getattr(self, "objective_entity_configs", ()) or ():
            if cfg.get("kind") == "alarm_beacon":
                return True
        return False

    def _gen_enemy_configs_for_range(self, enemy_count_range):
        if enemy_count_range:
            lo, hi = enemy_count_range
        else:
            lo, hi = ENEMY_MIN_PER_ROOM, ENEMY_MAX_PER_ROOM
        count = random.randint(lo, hi)
        palette_classes, palette_weights = self._build_enemy_palette()
        configs = []
        for _ in range(count):
            if palette_classes and any(w > 0 for w in palette_weights):
                cls = random.choices(palette_classes, weights=palette_weights, k=1)[0]
            elif palette_classes:
                cls = random.choice(palette_classes)
            else:
                cls = random.choice(ENEMY_CLASSES)
            pos = self._random_floor_pos(margin=4)
            configs.append((cls, pos))
        return configs

    # ── tuning test room ─────────────────────────────────
    def _build_tuning_test_room(self):
        """Hand-tuned bespoke layout for the room-test 'Tuning Test Room'.

        Each terrain type and enemy type gets its own labeled section so a
        designer can walk to it, exercise its mechanics, and tune values.
        Spawned enemies are flagged frozen via ``self.frozen_enemies`` so
        the dungeon spawner constructs them with ``is_frozen=True``.

        To extend this room with a new terrain or enemy type, append an
        entry to ``terrain_sections`` or ``enemy_sections`` below.  The
        single source of truth for what the test room exercises lives in
        this method.
        """
        # Reset the interior to plain FLOOR so any random terrain or stray
        # portal placement from the parent constructor is wiped.  Borders
        # (walls) and door cells are preserved.
        for r in range(1, ROOM_ROWS - 1):
            for c in range(1, ROOM_COLS - 1):
                if self.grid[r][c] != DOOR:
                    self.grid[r][c] = FLOOR
        self._portal_cells = []

        # Each section is (terrain_const, col_start, label_text); each one
        # paints a 3×3 patch in rows 2-4 starting at col_start.
        terrain_sections = (
            (MUD,   2,  "MUD"),
            (ICE,   6,  "ICE"),
            (WATER, 10, "WATER"),
            (WALL,  14, "WALL"),
        )
        for terrain, col, _label in terrain_sections:
            for r in range(2, 5):
                for c in range(col, col + 3):
                    self.grid[r][c] = terrain

        # Hazard-tile showcase (Phase 1 biome-room foundations).  Each
        # hazard gets a single 1×1 cell on row 7 with a label above on row 6.
        hazard_sections = (
            (SPIKE_PATCH, 2,  "SPIKE"),
            (QUICKSAND,   4,  "QUICKSAND"),
            (PIT_TILE,    6,  "PIT"),
            (CURRENT,     8,  "CURRENT"),
            (THIN_ICE,    10, "THIN ICE"),
            (HEARTH,      12, "HEARTH"),
            (CART_RAIL,   14, "RAIL"),
            (GLYPH_TILE,  16, "GLYPH"),
        )
        hazard_row = 7
        for tile, col, _label in hazard_sections:
            self.grid[hazard_row][col] = tile
        # Wire a sample push vector for the CURRENT showcase cell so
        # apply_terrain_effects has something to push the player with.
        self.current_vectors[(8, hazard_row)] = (1.0, 0.0)

        # Single PORTAL tile in the upper-right corner; its cell is tracked
        # so portal_center_pixel() / level-complete logic still works.
        portal_row, portal_col = 3, 18
        self.grid[portal_row][portal_col] = PORTAL
        self._portal_cells = [(portal_row, portal_col)]
        self._portal_active = True

        # Frozen enemy showcase placed along row 9.  Order mirrors the
        # ENEMY_CLASSES tuple so adding a new enemy type just means
        # appending a row here.  SentryEnemy is included even though it
        # lives outside ``ENEMY_CLASSES`` so the test room can exercise its
        # sprite/attack telegraph alongside the rest.
        enemy_sections = (
            (PatrolEnemy,   2,  "PATROL"),
            (RandomEnemy,   5,  "RANDOM"),
            (ChaserEnemy,   8,  "CHASER"),
            (PulsatorEnemy, 11, "PULSATOR"),
            (LauncherEnemy, 14, "LAUNCHER"),
            (SentryEnemy,   17, "SENTRY"),
        )
        enemy_row = 9
        self.enemy_configs = [
            (cls, (col * TILE_SIZE + TILE_SIZE // 2,
                   enemy_row * TILE_SIZE + TILE_SIZE // 2))
            for cls, col, _label in enemy_sections
        ]
        self.frozen_enemies = True
        # Attacks start disabled in the test room; F2 toggles them on/off
        # at runtime via :meth:`Room.toggle_enemy_attacks`.
        self.enemy_attacks_enabled = False
        # Slain test enemies respawn 2 seconds after death so designers can
        # repeatedly exercise damage / death effects without leaving the room.
        self.respawn_enemies_after_ms = 2000

        # Floating world-space labels rendered by draw_overlay_labels().
        def _cell_center(c, r):
            return (c * TILE_SIZE + TILE_SIZE // 2,
                    r * TILE_SIZE + TILE_SIZE // 2)

        labels = []
        for terrain, col, label in terrain_sections:
            del terrain
            labels.append((label, _cell_center(col + 1, 1)))
        for tile, col, label in hazard_sections:
            del tile
            labels.append((label, _cell_center(col, hazard_row - 1)))
        labels.append(("PORTAL", _cell_center(portal_col, 1)))
        labels.append(("FLOOR", _cell_center(10, 6)))
        labels.append(("DOOR", _cell_center(2, ROOM_ROWS // 2)))
        for cls, col, label in enemy_sections:
            del cls
            labels.append((label, _cell_center(col, enemy_row + 2)))
        labels.append(("F2: TOGGLE ATTACKS", _cell_center(10, ROOM_ROWS - 2)))
        labels.append(("PLAYER SPAWN", _cell_center(3, 12)))
        self.tuning_test_labels = labels

        # Strip any objective entities the parent constructor may have
        # built; the tuning room has no objective gating.
        self.objective_entity_configs = []
        # No chest in the test room: keep visual focus on the sections.
        self.chest_pos = None

    def toggle_enemy_attacks(self, enemy_group=None):
        """Flip ``enemy_attacks_enabled`` and propagate to live enemies.

        The dungeon owns the live ``enemy_group``; pass it in so spawned
        enemies have their ``attacks_disabled`` flag updated immediately.
        Returns the new ``enemy_attacks_enabled`` value.
        """
        self.enemy_attacks_enabled = not self.enemy_attacks_enabled
        if enemy_group is not None:
            for enemy in enemy_group:
                enemy.attacks_disabled = not self.enemy_attacks_enabled
        return self.enemy_attacks_enabled

    def update_enemy_respawns(self, now_ticks, enemy_group):
        """Return ``[(cls, (px, py)), ...]`` of test enemies due for respawn.

        For rooms with ``respawn_enemies_after_ms`` set, the first time a
        configured enemy slot is found missing from ``enemy_group`` we record
        a respawn deadline.  Once ``now_ticks`` reaches the deadline the
        slot is reported back for the caller to re-instantiate, and the
        timer for that slot is cleared.  Returns an empty list when the
        room has no respawn delay configured.
        """
        if self.respawn_enemies_after_ms is None:
            return []
        present_positions = {
            (enemy.rect.centerx, enemy.rect.centery) for enemy in enemy_group
        }
        new_spawns = []
        for idx, (cls, pos) in enumerate(self.enemy_configs):
            if pos in present_positions:
                self._enemy_respawn_due_at.pop(idx, None)
                continue
            due = self._enemy_respawn_due_at.get(idx)
            if due is None:
                self._enemy_respawn_due_at[idx] = (
                    now_ticks + self.respawn_enemies_after_ms
                )
            elif now_ticks >= due:
                new_spawns.append((cls, pos))
                self._enemy_respawn_due_at.pop(idx, None)
        return new_spawns

    @property
    def doors_sealed(self):
        """True while the room's main objective remains incomplete.

        A non-exit room's main objective is to clear its initial enemies.
        An exit room's main objective is its planned objective rule (e.g.
        ``holdout_timer``, ``charge_plates``).  Rooms with no enemies and
        no exit-objective are never sealed.  Test rooms that auto-respawn
        enemies (``respawn_enemies_after_ms``) are never sealed either.
        """
        if self.respawn_enemies_after_ms is not None:
            return False
        has_initial_enemies = bool(self.enemy_configs)
        if has_initial_enemies and not self.enemies_cleared:
            return True
        if self.is_exit and self.room_plan is not None:
            rule = self.room_plan.objective_rule
            if rule and rule != "immediate" and self.objective_status != "completed":
                return True
        return False

    def draw_overlay_labels(self, surface):
        """Render world-space labels for the tuning test room (no-op otherwise)."""
        if not self.tuning_test_labels:
            return
        font = _tuning_label_font()
        if font is None:
            return
        for text, (cx, cy) in self.tuning_test_labels:
            outline = font.render(text, True, COLOR_BLACK)
            ow, oh = outline.get_size()
            ox = cx - ow // 2
            oy = cy - oh // 2
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                surface.blit(outline, (ox + dx, oy + dy))
            fill = font.render(text, True, COLOR_WHITE)
            surface.blit(fill, (ox, oy))
