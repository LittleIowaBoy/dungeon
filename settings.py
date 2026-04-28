import ctypes
import sys


# ── Display ──────────────────────────────────────────────
TILE_SIZE = 40
FPS = 60

_MIN_SCREEN_WIDTH = 800
_MIN_SCREEN_HEIGHT = 600
_WINDOW_MARGIN_X = 40
_WINDOW_MARGIN_Y = 80


def _align_down(value, step):
    return max(step, (value // step) * step)


def _desktop_work_area_size():
    if sys.platform == "win32":
        try:
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            rect = RECT()
            spi_get_work_area = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(
                spi_get_work_area, 0, ctypes.byref(rect), 0
            ):
                return rect.right - rect.left, rect.bottom - rect.top
        except Exception:
            pass

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return width, height
    except Exception:
        return _MIN_SCREEN_WIDTH, _MIN_SCREEN_HEIGHT


_desktop_width, _desktop_height = _desktop_work_area_size()
SCREEN_WIDTH = _align_down(
    max(_MIN_SCREEN_WIDTH, _desktop_width - _WINDOW_MARGIN_X),
    TILE_SIZE,
)
SCREEN_HEIGHT = _align_down(
    max(_MIN_SCREEN_HEIGHT, _desktop_height - _WINDOW_MARGIN_Y),
    TILE_SIZE,
)

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

PLAYTEST_ROOM_IDENTIFIER_ENABLED = True

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
COLOR_DOOR_TWO_WAY = (70, 200, 90)
COLOR_DOOR_ONE_WAY = (235, 215, 70)
COLOR_DOOR_NONE    = (210, 70, 70)
COLOR_DOOR_SEALED  = (180, 90, 30)

# biome-room hazard tiles (Phase 1 of biome room expansion)
COLOR_QUICKSAND  = (155, 130, 80)   # earth: drowning patch
COLOR_SPIKE_PATCH = (130, 110, 90)  # earth: stalagmites / water: coral (re-tinted in render)
COLOR_PIT_TILE   = (15, 15, 25)     # earth/ice: collapsed pit (lethal)
COLOR_CURRENT    = (40, 110, 170)   # water: directional current
COLOR_THIN_ICE   = (200, 230, 250)  # ice: cracks under foot
COLOR_HEARTH     = (220, 110, 40)   # ice: warming safe spot
COLOR_CART_RAIL  = (70, 60, 50)     # earth: rail tile (cosmetic)
COLOR_GLYPH_TILE = (90, 160, 200)   # water: ordered-touch puzzle glyph

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
COLOR_HAMMER_HIT = (220, 220, 220, 120)

# HUD
COLOR_HEALTH_BAR = (220, 30, 30)
COLOR_HEALTH_BG  = (60, 20, 20)

# ── Player stats ──────────────────────────────────
PLAYER_BASE_SPEED   = 3.0    # pixels per frame
PLAYER_MAX_HP       = 100
PLAYER_SIZE         = 28     # pixels (square)
INVINCIBILITY_MS    = 1000   # 1 second
FLASH_INTERVAL_MS   = 100

# ── Consumable items ────────────────────────────────────
# Health potions
HEAL_SMALL          = 25
HEAL_MEDIUM         = 50
HEAL_LARGE          = 100
POTION_SMALL_MAX    = 3
POTION_MEDIUM_MAX   = 2
POTION_LARGE_MAX    = 1

# Speed boost (inventory consumable — timed)
SPEED_BOOST_DURATION_MS = 20_000   # 20 seconds
SPEED_BOOST_MULTIPLIER  = 2.0     # doubles base speed
SPEED_BOOST_MAX         = 3

# Attack boost (inventory consumable — timed)
ATTACK_BOOST_DURATION_MS = 20_000  # 20 seconds
ATTACK_BOOST_MULTIPLIER  = 2.0    # doubles damage
ATTACK_BOOST_MAX         = 1

# Armor
ARMOR_HP = 50

# Weapon +1 upgrades
WEAPON_PLUS_MULTIPLIER = 1.5

# Compass
COMPASS_MAX  = 1
COMPASS_USES = 3
COMPASS_DISPLAY_MS = 5000  # how long direction shows after use

# ── Shop prices ─────────────────────────────────────────
PRICE_POTION_SMALL  = 10
PRICE_POTION_MEDIUM = 25
PRICE_POTION_LARGE  = 50
PRICE_SPEED_BOOST   = 20
PRICE_ATTACK_BOOST  = 30
PRICE_ARMOR         = 40
PRICE_WEAPON_PLUS   = 75
PRICE_COMPASS       = 35

# ── Colors (new items) ─────────────────────────────────
COLOR_ARMOR        = (100, 140, 200)    # steel blue
COLOR_ARMOR_BAR    = (100, 140, 200)
COLOR_ARMOR_BG     = (30, 40, 60)
COLOR_SPEED_GLOW   = (40, 220, 220)     # cyan
COLOR_ATTACK_GLOW  = (255, 50, 50, 160) # red, semi-transparent
COLOR_COMPASS      = (220, 200, 60)     # gold

# ── Loot drop weights (database-driven) ────────────────
# weights for inventory loot drops from enemies
LOOT_WEIGHT_POTION_SMALL  = 20
LOOT_WEIGHT_POTION_MEDIUM = 6
LOOT_WEIGHT_POTION_LARGE  = 2
LOOT_WEIGHT_SPEED_BOOST   = 10
LOOT_WEIGHT_ATTACK_BOOST  = 4

# chest loot has slightly better odds for rare items
CHEST_LOOT_WEIGHT_POTION_SMALL  = 15
CHEST_LOOT_WEIGHT_POTION_MEDIUM = 10
CHEST_LOOT_WEIGHT_POTION_LARGE  = 5
CHEST_LOOT_WEIGHT_SPEED_BOOST   = 12
CHEST_LOOT_WEIGHT_ATTACK_BOOST  = 8

# ── Weapon stats  (damage, range_tiles, cooldown_ms) ────
SWORD_DAMAGE   = 30
SWORD_RANGE    = 1.5
SWORD_COOLDOWN = 400

SPEAR_DAMAGE   = 20
SPEAR_RANGE    = 4.5
SPEAR_WIDTH    = 0.5
SPEAR_COOLDOWN = 250

AXE_DAMAGE     = 30
AXE_RANGE      = 1.5
AXE_COOLDOWN   = 1200

HAMMER_DAMAGE   = 84
HAMMER_COOLDOWN = 800

ATTACK_DURATION_MS = 150     # how long the hitbox sprite lives

# ── Enemy stats ─────────────────────────────────────────
PATROL_HP      = 30
PATROL_SPEED   = 1.5
PATROL_DAMAGE  = 10
PATROL_ATTACK_TRIGGER  = 2.0 * TILE_SIZE   # range to begin telegraph
PATROL_ATTACK_RADIUS   = 1.5 * TILE_SIZE   # radius of 360° strike
PATROL_ATTACK_DAMAGE   = 12
PATROL_ATTACK_WINDUP_MS  = 450
PATROL_ATTACK_STRIKE_MS  = 180
PATROL_ATTACK_COOLDOWN_MS = 1200

RANDOM_HP      = 20
RANDOM_SPEED   = 1.8
RANDOM_DAMAGE  = 8
RANDOM_ATTACK_TRIGGER = 4.0 * TILE_SIZE
RANDOM_ATTACK_RANGE   = 4.0 * TILE_SIZE   # length of forward line
RANDOM_ATTACK_WIDTH   = int(0.75 * TILE_SIZE)
RANDOM_ATTACK_DAMAGE  = 10
RANDOM_ATTACK_WINDUP_MS  = 500
RANDOM_ATTACK_STRIKE_MS  = 160
RANDOM_ATTACK_COOLDOWN_MS = 1500

CHASER_HP      = 40
CHASER_SPEED   = 1.8        # 60 % of player base applied later
CHASER_DAMAGE  = 12
CHASE_RADIUS   = 6 * TILE_SIZE   # pixels
CHASE_LOST_RADIUS = 8 * TILE_SIZE
CHASER_ATTACK_TRIGGER = 1.5 * TILE_SIZE
CHASER_ATTACK_SIZE    = 2 * TILE_SIZE
CHASER_ATTACK_OFFSET  = int(0.75 * TILE_SIZE)
CHASER_ATTACK_DAMAGE  = 14
CHASER_ATTACK_WINDUP_MS  = 350
CHASER_ATTACK_STRIKE_MS  = 160
CHASER_ATTACK_COOLDOWN_MS = 900

# Pulsator: stationary-section enemy that emits expanding damage rings.
COLOR_PULSATOR  = (180, 90, 200)
PULSATOR_HP     = 35
PULSATOR_SPEED  = 1.2
PULSATOR_ANCHOR_RADIUS_TILES = 3
PULSATOR_ANCHOR_WAIT_MS  = 300
PULSATOR_WINDUP_MS       = 600
PULSATOR_RING_SPEED      = 3.5            # pixels per frame
PULSATOR_RING_THICKNESS  = int(0.6 * TILE_SIZE)
PULSATOR_RING_MAX_RADIUS = 5 * TILE_SIZE
PULSATOR_RING_DAMAGE     = 14
PULSATOR_COOLDOWN_MS     = 250            # short rest after ring dissipates

# Launcher: ranged enemy that fires a slow projectile then retreats.
COLOR_LAUNCHER  = (60, 150, 200)
LAUNCHER_HP     = 25
LAUNCHER_SPEED  = 1.4                      # base move speed
LAUNCHER_RETREAT_SPEED = 1.0
LAUNCHER_RANGE  = 7 * TILE_SIZE            # detection range
LAUNCHER_ATTACK_WINDUP_MS = 500
LAUNCHER_ATTACK_STRIKE_MS = 80             # brief "fire" frame
LAUNCHER_ATTACK_COOLDOWN_MS = 1600
LAUNCHER_RETREAT_MS = 1400
LAUNCHER_PROJECTILE_SPEED  = 4.5
LAUNCHER_PROJECTILE_RANGE  = 9 * TILE_SIZE
LAUNCHER_PROJECTILE_DAMAGE = 12
LAUNCHER_PROJECTILE_SIZE   = 12

# Sentry: stealth-room patroller that explodes on contact.
COLOR_SENTRY    = (220, 220, 60)
SENTRY_HP       = 25
SENTRY_PATROL_SPEED  = 1.2
SENTRY_CHASE_SPEED   = 2.6
SENTRY_SIGHT_RADIUS  = 4 * TILE_SIZE
SENTRY_DETONATE_RADIUS = int(1.0 * TILE_SIZE)
SENTRY_EXPLOSION_RADIUS = int(2.0 * TILE_SIZE)
SENTRY_EXPLOSION_DAMAGE = 45
SENTRY_ALERT_FLASH_MS   = 200
SENTRY_ARM_MS           = 600

# ── Spawn placement ─────────────────────────────────────
ENEMY_DOOR_BUFFER_TILES = 3
ROOM_MAX_DISTINCT_ENEMY_TYPES = 3

# Telegraph flash cadence (shared across all enemies).
ENEMY_TELEGRAPH_FLASH_INTERVAL_MS = 80

# Default enemy counts (overridden per-level via dungeon_config.py)
ENEMY_MIN_PER_ROOM = 1
ENEMY_MAX_PER_ROOM = 4

# ── Drops ───────────────────────────────────────────────
DROP_CHANCE = 0.40           # 40 %


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
    # Biome-room hazard tiles.  ``pit_tile`` is lethal so its speed is
    # nominal; ``quicksand`` uses the slowest non-zero multiplier so the
    # player can still attempt to escape before the drowning timer fires.
    "quicksand":   0.3,
    "spike_patch": 1.0,
    "pit_tile":    1.0,
    "current":     1.0,
    "thin_ice":    1.0,
    "hearth":      1.0,
    "cart_rail":   1.0,
    "glyph_tile":  1.0,
}
ICE_FRICTION = 0.92          # velocity *= friction each frame on ice

# ── Hazard tile tuning (Phase 1 biome-room expansion) ───
# Passive hazards (spike_patch, coral, frostbite) deal a small consistent
# tick.  Active hazards (thin_ice collapse, cave-in burst, etc.) telegraph
# via the existing enemy attack-state pattern and live in their entities.
HAZARD_TICK_MS = 500
HAZARD_TICK_DAMAGE = 1
# Quicksand drowning: total time to lethal once player enters the patch.
QUICKSAND_DROWN_MS = 3000
# Current tile push speed (pixels / frame, applied additively after movement).
CURRENT_PUSH_SPEED = 1.6

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
