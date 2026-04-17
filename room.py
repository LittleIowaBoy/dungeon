"""Room: tile grid, terrain, walls/doors, enemy/chest spawn configs."""
import random
import pygame
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


class Room:
    """A single dungeon room stored as a ROOM_COLS×ROOM_ROWS tile grid."""

    def __init__(self, doors, is_exit=False, terrain_type=None,
                 enemy_count_range=None, enemy_type_weights=None):
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

        # build grid
        self.grid = [[FLOOR] * ROOM_COLS for _ in range(ROOM_ROWS)]
        self._place_walls()
        self._place_doors()
        self._place_terrain()
        if is_exit:
            self._place_portal()

        # spawn configs (created once, enemies re-instantiated on each visit)
        self.enemy_configs = self._gen_enemy_configs()

        # chest
        self.chest_pos = None  # (px, py) or None
        self.chest_looted = False
        if random.random() < CHEST_SPAWN_CHANCE:
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
        count = random.randint(TERRAIN_PATCH_MIN, TERRAIN_PATCH_MAX)
        for _ in range(count):
            if self._terrain_type:
                kind = self._terrain_type
            else:
                kind = random.choice(_TERRAIN_POOL)
            w = random.randint(TERRAIN_PATCH_SIZE_MIN, TERRAIN_PATCH_SIZE_MAX)
            h = random.randint(TERRAIN_PATCH_SIZE_MIN, TERRAIN_PATCH_SIZE_MAX)
            sc = random.randint(2, ROOM_COLS - 2 - w)
            sr = random.randint(2, ROOM_ROWS - 2 - h)
            for r in range(sr, min(sr + h, ROOM_ROWS - 1)):
                for c in range(sc, min(sc + w, ROOM_COLS - 1)):
                    if self.grid[r][c] == FLOOR:
                        self.grid[r][c] = kind

    def _place_portal(self):
        cx, cy = ROOM_COLS // 2, ROOM_ROWS // 2
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                r, c = cy + dr, cx + dc
                if 0 < r < ROOM_ROWS - 1 and 0 < c < ROOM_COLS - 1:
                    self.grid[r][c] = PORTAL

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
        if self._enemy_count_range:
            lo, hi = self._enemy_count_range
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
