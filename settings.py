# ── Display ──────────────────────────────────────────────
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TILE_SIZE = 40
FPS = 60

# ── Room grid (in tiles) ────────────────────────────────
ROOM_COLS = SCREEN_WIDTH // TILE_SIZE   # 20
ROOM_ROWS = SCREEN_HEIGHT // TILE_SIZE  # 15

# ── Dungeon limits ──────────────────────────────────────
# PORTAL_DISTANCE is now driven per-level via dungeon_config.py
DEFAULT_PORTAL_DISTANCE = 5  # fallback only
MAX_DUNGEON_RADIUS = 7       # base hard boundary; scales with path length

# ── Door ────────────────────────────────────────────────
DOOR_WIDTH = 2               # tiles wide

# ── Colors ──────────────────────────────────────────────
COLOR_BLACK      = (0, 0, 0)
COLOR_WHITE      = (255, 255, 255)
COLOR_DARK_GRAY  = (50, 50, 50)
COLOR_GRAY       = (100, 100, 100)
COLOR_LIGHT_GRAY = (170, 170, 170)

# entities
COLOR_PLAYER     = (60, 120, 220)
COLOR_PATROL     = (200, 40, 40)
COLOR_RANDOM     = (220, 140, 30)
COLOR_CHASER     = (140, 20, 20)

# terrain
COLOR_FLOOR      = (60, 60, 60)
COLOR_WALL       = (100, 100, 100)
COLOR_MUD        = (90, 70, 50)
COLOR_ICE        = (160, 210, 240)
COLOR_WATER      = (50, 80, 130)
COLOR_DOOR       = (170, 170, 140)
COLOR_PORTAL     = (160, 60, 220)

# items
COLOR_HEALTH_POTION = (30, 200, 60)
COLOR_COIN          = (240, 220, 40)
COLOR_SPEED_BOOST   = (40, 220, 220)

# chests
COLOR_CHEST         = (140, 90, 30)
COLOR_CHEST_LOOTED  = (80, 50, 20)

# attack hitbox
COLOR_SWORD_HIT  = (255, 255, 200, 120)
COLOR_SPEAR_HIT  = (200, 255, 200, 120)
COLOR_AXE_HIT    = (255, 200, 200, 120)

# HUD
COLOR_HEALTH_BAR = (220, 30, 30)
COLOR_HEALTH_BG  = (60, 20, 20)
COLOR_HUD_TEXT   = (230, 230, 230)

# ── Player stats ────────────────────────────────────────
PLAYER_BASE_SPEED   = 3.0    # pixels per frame
PLAYER_MAX_HP       = 100
PLAYER_SIZE         = 28     # pixels (square)
INVINCIBILITY_MS    = 1000   # 1 second
FLASH_INTERVAL_MS   = 100

# ── Speed boost ─────────────────────────────────────────
SPEED_BOOST_AMOUNT = 0.10    # +10 % per pickup
SPEED_CAP          = 1.5     # max multiplier

# ── Item values ─────────────────────────────────────────
HEAL_AMOUNT = 25

# ── Weapon stats  (damage, range_tiles, cooldown_ms) ────
SWORD_DAMAGE   = 15
SWORD_RANGE    = 1.5
SWORD_COOLDOWN = 400
SWORD_ARC_DEG  = 90

SPEAR_DAMAGE   = 10
SPEAR_RANGE    = 3.0
SPEAR_WIDTH    = 0.5
SPEAR_COOLDOWN = 250

AXE_DAMAGE     = 20
AXE_RANGE      = 1.5
AXE_COOLDOWN   = 600

ATTACK_DURATION_MS = 150     # how long the hitbox sprite lives

# ── Enemy stats ─────────────────────────────────────────
PATROL_HP      = 30
PATROL_SPEED   = 1.5
PATROL_DAMAGE  = 10

RANDOM_HP      = 20
RANDOM_SPEED   = 1.8
RANDOM_DAMAGE  = 8

CHASER_HP      = 40
CHASER_SPEED   = 1.8        # 60 % of player base applied later
CHASER_DAMAGE  = 12
CHASE_RADIUS   = 6 * TILE_SIZE   # pixels
CHASE_LOST_RADIUS = 8 * TILE_SIZE

# Default enemy counts (overridden per-level via dungeon_config.py)
ENEMY_MIN_PER_ROOM = 1
ENEMY_MAX_PER_ROOM = 4

# ── Drops ───────────────────────────────────────────────
DROP_CHANCE = 0.40           # 40 %
# weights: coin, health_potion, speed_boost
DROP_WEIGHTS = [50, 35, 15]

# ── Chests ──────────────────────────────────────────────
CHEST_SPAWN_CHANCE = 0.30
CHEST_MIN_ITEMS = 1
CHEST_MAX_ITEMS = 3
CHEST_INTERACT_DIST = 1.5 * TILE_SIZE

# ── Terrain speed multipliers ───────────────────────────
TERRAIN_SPEED = {
    "floor": 1.0,
    "mud":   0.5,
    "water": 0.75,
    "ice":   1.0,   # ice uses momentum, not a simple multiplier
}
ICE_FRICTION = 0.92          # velocity *= friction each frame on ice

# ── Terrain generation ──────────────────────────────────
TERRAIN_PATCH_MIN = 2
TERRAIN_PATCH_MAX = 4
TERRAIN_PATCH_SIZE_MIN = 3
TERRAIN_PATCH_SIZE_MAX = 6

# ── Directions mapping ──────────────────────────────────
DIR_OFFSETS = {
    "top":    (0, -1),
    "bottom": (0, 1),
    "left":   (-1, 0),
    "right":  (1, 0),
}
OPPOSITE_DIR = {
    "top": "bottom",
    "bottom": "top",
    "left": "right",
    "right": "left",
}
