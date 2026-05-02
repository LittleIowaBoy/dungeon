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

# Biome challenge-route reward activations (see item_catalog.py
# `biome_reward` category; awarded by trap-gauntlet routes).
STAT_SHARD_MAX_HP_BONUS      = 10        # permanent +max_hp per shard spent
TEMPO_RUNE_DURATION_MS       = 30_000    # extended attack-boost window (30 s)
MOBILITY_CHARGE_DURATION_MS  = 6_000     # short, sharper speed burst (6 s)

# Shop conversion rules for surplus biome trophies. Players can spend
# `BIOME_TROPHY_EXCHANGE_RATIO` of any one biome trophy to receive 1 of a
# different biome trophy at the post-run shop. The ratio is intentionally
# steep (3:1) so the conversion is a salvage outlet, not a farming loop.
BIOME_TROPHY_IDS             = ("stat_shard", "tempo_rune", "mobility_charge")
BIOME_TROPHY_EXCHANGE_RATIO  = 3
# Maps a dungeon's `terrain_type` to its biome challenge-route trophy.
# Used by UI surfaces (dungeon-select cards) to show, per biome, how many
# trophies the player has banked toward the next prismatic-keystone craft.
TERRAIN_TROPHY_IDS           = {
    "mud":   "stat_shard",
    "ice":   "tempo_rune",
    "water": "mobility_charge",
}
# Biome attunement (T17): a *second* meta-progression token, distinct from
# keystones.  Earned by completing the same biome's dungeon repeatedly
# (every `BIOME_ATTUNEMENT_THRESHOLD` completions in a single biome grants
# one attunement, capped at `BIOME_ATTUNEMENT_MAX_PER_BIOME`).  Each
# attunement of a biome grants +1 of that biome's trophy at the start of
# every run in that biome — a *biome-specialist* perk that complements
# the universal coin bonus from keystones.
BIOME_ATTUNEMENT_THRESHOLD       = 3
BIOME_ATTUNEMENT_MAX_PER_BIOME   = 3
# Rare crafted trophy: spend 1 of each biome trophy at the shop to gain 1.
BIOME_TROPHY_KEYSTONE_ID     = "prismatic_keystone"
# Permanent meta-progression for keystones.  Crafted keystones are stored on
# `progress.meta_keystones`, not the per-run inventory.  Each owned keystone
# adds the next tier's coin bonus to the start of every dungeon run.  Tiered
# scaling makes the cap (`KEYSTONE_MAX_OWNED`) feel earned: the 3rd keystone
# is worth 4× the 1st.  Cumulative totals: 1→25, 2→75, 3→175.
KEYSTONE_MAX_OWNED           = 3
KEYSTONE_TIER_COIN_BONUSES   = (25, 50, 100)

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

# ── Golem mini-boss (Earth biome finale) ───────────────
# Golem is a slow, high-HP melee/ranged hybrid. At range it telegraphs
# and hurls a heavy boulder; in melee it telegraphs a circular ground
# slam.  When ``phase_2`` is set externally (by the BossController on
# 50% HP), the Golem unlocks ``ENRAGE`` charges — a brief, faster dash
# attack that fires only when the player is at mid range (between melee
# and throw range).
GOLEM_HP                       = 800
GOLEM_SPEED                    = 0.6
GOLEM_COLOR                    = (140, 110, 80)
GOLEM_SIZE                     = 56
GOLEM_MELEE_TRIGGER            = int(2.2 * TILE_SIZE)
GOLEM_THROW_RANGE              = int(8.0 * TILE_SIZE)
GOLEM_SLAM_RADIUS              = int(2.6 * TILE_SIZE)
GOLEM_SLAM_DAMAGE              = 28
GOLEM_SLAM_WINDUP_MS           = 900
GOLEM_SLAM_STRIKE_MS           = 140
GOLEM_SLAM_COOLDOWN_MS         = 1300
GOLEM_THROW_WINDUP_MS          = 1100
GOLEM_THROW_STRIKE_MS          = 80
GOLEM_THROW_COOLDOWN_MS        = 1500
GOLEM_BOULDER_SPEED            = 3.5
GOLEM_BOULDER_RANGE            = int(10.0 * TILE_SIZE)
GOLEM_BOULDER_DAMAGE           = 22
GOLEM_BOULDER_SIZE             = 22
GOLEM_ENRAGE_TRIGGER_MIN       = int(2.5 * TILE_SIZE)
GOLEM_ENRAGE_TRIGGER_MAX       = int(6.0 * TILE_SIZE)
GOLEM_ENRAGE_DAMAGE            = 24
GOLEM_ENRAGE_WINDUP_MS         = 700
GOLEM_ENRAGE_STRIKE_MS         = 220
GOLEM_ENRAGE_COOLDOWN_MS       = 1700
GOLEM_ENRAGE_DASH_SPEED        = 5.5

# Golem shards — fast melee minions summoned at 75% / 50% / 25% HP.
GOLEM_SHARD_HP                 = 30
GOLEM_SHARD_SPEED              = 1.9
GOLEM_SHARD_COLOR              = (180, 150, 110)
GOLEM_SHARD_SIZE               = 18
GOLEM_SHARD_ATTACK_TRIGGER     = int(0.9 * TILE_SIZE)
GOLEM_SHARD_ATTACK_SIZE        = int(0.7 * TILE_SIZE)
GOLEM_SHARD_ATTACK_OFFSET      = 4
GOLEM_SHARD_ATTACK_DAMAGE      = 8
GOLEM_SHARD_ATTACK_WINDUP_MS   = 250
GOLEM_SHARD_ATTACK_STRIKE_MS   = 80
GOLEM_SHARD_ATTACK_COOLDOWN_MS = 500

# ── Golem armor set (Earth biome boss loot) ────────────
# Defensive set with one offensive perk per limb.  Each piece grants a
# small +max_hp bump plus a slot-themed multiplier; full set ≈ +30 HP,
# +5% crit, +10% damage reduction, +5% movement, +5% outgoing damage.
GOLEM_SET_HP_PER_PIECE         = 5
GOLEM_HUSK_HP_BONUS            = 15           # chest piece is the bulk of the HP
GOLEM_CROWN_CRIT_CHANCE        = 0.05         # +5% crit chance from helmet
GOLEM_HUSK_DR_FRACTION         = 0.10         # 10% reduction (dmg ×0.90)
GOLEM_STRIDE_SPEED_BONUS       = 0.05         # +5% movement multiplier
GOLEM_FISTS_DAMAGE_BONUS       = 0.05         # +5% outgoing damage
GOLEM_CRIT_MULTIPLIER          = 2.0          # 2x damage on crit
# Boss-loot drop probabilities applied per defeat.  Each defeat rolls
# twice: a guaranteed-rate first piece and a slim chance for a second.
GOLEM_LOOT_PRIMARY_CHANCE      = 0.10
GOLEM_LOOT_SECONDARY_CHANCE    = 0.02

# ── Spawn placement ─────────────────────────────────────
ENEMY_DOOR_BUFFER_TILES = 3
ROOM_MAX_DISTINCT_ENEMY_TYPES = 3

# Telegraph flash cadence (shared across all enemies).
ENEMY_TELEGRAPH_FLASH_INTERVAL_MS = 80

# Default enemy counts (overridden per-level via dungeon_config.py).
# Raised from (1, 4) → (2, 6) to make rooms feel populated.  The actual
# ceiling varies by dungeon profile and difficulty band (see dungeon_config.py
# and room_selector._scale_enemy_count_for_difficulty_band).
# NOTE: If enemy stats are tuned (HP, attack damage, attack cooldown, or
# speed), re-evaluate these caps.  Higher damage or faster cooldowns shrink
# the comfortable count ceiling; lower damage or slower cooldowns allow more.
ENEMY_MIN_PER_ROOM = 2
ENEMY_MAX_PER_ROOM = 6

# Per-type spawn caps used by Room._gen_enemy_configs_for_range.
# Chaser and Pulsator are the two highest-threat types: Chaser has the
# highest HP (40) and tightest attack cooldown (900 ms); Pulsator fires
# ring AoE with only a 250 ms rest.  Packing more than these caps into a
# single room creates unavoidable damage.  Other types are uncapped because
# they're individually easier to dodge.
# NOTE: Revisit if CHASER_ATTACK_COOLDOWN_MS, CHASER_HP, PULSATOR_COOLDOWN_MS,
# or PULSATOR_RING_DAMAGE are changed — tighter cooldowns / higher damage
# will require lower caps; looser values can tolerate higher counts.
ENEMY_TYPE_CAP_CHASER    = 3
ENEMY_TYPE_CAP_PULSATOR  = 2

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
# Stalagmite spike tiles: damage is dealt only on the frame the player
# moves ONTO a new spike tile (per-tile entry).  Standing motionless on a
# spike tile and stepping off do NOT deal damage.  This is distinct from
# the legacy ``HAZARD_TICK_*`` cadence used by passive bloom hazards.
STALAGMITE_STEP_DAMAGE = 5
# Stalagmite Field room polish (Phase 1).  Tunes the post-placement pass
# that turns the random rectangle patches into a more navigable obstacle
# field.  ``DOOR_BUFFER`` is the chebyshev radius around each door tile
# kept clear of spikes.  ``SINGLETON_COUNT_RANGE`` lets a few isolated
# spikes scatter across remaining floor for visual texture.  When the
# BFS path-carve runs, each spike removed becomes the base of a 1-tile
# corridor between an entrance and the room centre.
STALAGMITE_FIELD_DOOR_BUFFER       = 2
STALAGMITE_FIELD_SINGLETON_COUNT_RANGE = (3, 5)
# Quicksand Trap polish: chebyshev radius around each open door kept
# clear of QUICKSAND tiles so the player never spawns on top of a pull
# zone.  A BFS connectivity pass guarantees each entrance has a fully
# walkable (no-quicksand) path to the room centre.
QUICKSAND_TRAP_DOOR_BUFFER         = 2
# Quicksand pull: while a player stands on a QUICKSAND tile, the runtime
# applies a small per-frame push toward the tile centre.  Standing still
# drifts the player into the centre of the patch; escaping requires the
# dodge ability (which grants i-frames + a 2.4x speed burst that lets the
# player break free).  Pull is suppressed while the player is invincible
# (dodge / spawn i-frames) so dodging always wins the tug-of-war.
QUICKSAND_PULL_SPEED = 0.6
# Boulder Run hazards: vertical boulders periodically spawn from a single
# source wall (top OR bottom, chosen per room instance) and roll in a
# straight line to the opposite wall.  Each boulder picks a random speed
# from BOULDER_BASE_SPEED_RANGE; spawn cadence is a random interval
# from BOULDER_SPAWN_INTERVAL_RANGE_MS.  Door columns are excluded so
# spawn lanes never overlap an exit.
BOULDER_BASE_SPEED_RANGE = (4.0, 7.0)
BOULDER_SPAWN_INTERVAL_RANGE_MS = (700, 1500)
BOULDER_DAMAGE = 10
# Current tile push speed (pixels / frame, applied additively after movement).
CURRENT_PUSH_SPEED = 1.6
# Water River Room polish: chebyshev radius around each open door kept
# clear of CURRENT tiles so the player never spawns directly into the
# river's push.  A BFS connectivity pass treats CURRENT as walkable so
# every entrance has a path to the room centre even when the river
# bisects the room.
WATER_RIVER_DOOR_BUFFER = 2
# Water River band width (in tiles), inclusive range.  The river spans
# the full room along one axis at a width chosen from this range.
WATER_RIVER_WIDTH_RANGE = (2, 3)
# Water Waterfall Room polish: a vertical CURRENT band hugs one of the
# side walls (left or right) and a small WATER pool collects at its
# base.  The cascade hides a guaranteed chest the player has to push
# through the current to reach.
WATER_WATERFALL_BAND_WIDTH = 3
WATER_WATERFALL_POOL_RADIUS = 2
WATER_WATERFALL_DOOR_BUFFER = 1
# Water Spirit Room polish: several WATER pool patches are placed at
# random interior positions, each housing a stationary WaterSpiritEnemy.
WATER_SPIRIT_POOL_COUNT_RANGE = (2, 3)
WATER_SPIRIT_POOL_RADIUS      = 2
WATER_SPIRIT_DOOR_BUFFER      = 3
# WaterSpiritEnemy stats.
WATER_SPIRIT_HP                  = 1        # functionally invulnerable (take_damage is a no-op)
COLOR_WATER_SPIRIT               = (80, 180, 255)
WATER_SPIRIT_PROJECTILE_SPEED    = 2
WATER_SPIRIT_PROJECTILE_RANGE    = 280
WATER_SPIRIT_PROJECTILE_DAMAGE   = 10
WATER_SPIRIT_PROJECTILE_SIZE     = 10
WATER_SPIRIT_ATTACK_WINDUP_MS    = 800
WATER_SPIRIT_ATTACK_STRIKE_MS    = 120
WATER_SPIRIT_ATTACK_COOLDOWN_MS  = 2200
WATER_SPIRIT_ATTACK_TRIGGER      = 380  # px; only attacks when player is within this range
# WaterSpiritEnemy anchor cycle: periodic vulnerability window.
# Every INTERVAL ms the spirit becomes mortal for DURATION ms, then restores.
WATER_SPIRIT_ANCHOR_INTERVAL_MS  = 5000   # ms between anchor events
WATER_SPIRIT_ANCHOR_DURATION_MS  = 2000   # ms the spirit stays vulnerable
WATER_SPIRIT_ANCHOR_HP           = 40     # HP granted during the window
COLOR_WATER_SPIRIT_ANCHORED      = (220, 240, 255)  # bright flash while anchored

# ── WATER tile submersion hazard ─────────────────────────────────────────────
# Standing in a WATER tile for longer than DELAY ms triggers damage every
# TICK ms until the player leaves the tile.  Invincibility frames suppress
# each tick.  Moving off the tile resets the timer.
WATER_SUBMERSION_DELAY_MS    = 2000   # ms before first submersion tick
WATER_SUBMERSION_TICK_MS     = 800    # ms between subsequent ticks
WATER_SUBMERSION_TICK_DAMAGE = 5      # HP per tick

# ── Enemy CURRENT push ────────────────────────────────────────────────────────
# Fraction of CURRENT_PUSH_SPEED applied to enemies standing on CURRENT tiles.
# Frozen and immobilised enemies are not affected.
ENEMY_CURRENT_PUSH_FACTOR    = 0.5

# ── Escort-NPC follow behaviour ───────────────────────────────────────────────
# Distance (px) the escort NPC trails behind the player.  The NPC targets a
# point this many pixels behind the player in the player's direction of motion,
# so it always visually lags just behind them rather than running alongside.
ESCORT_FOLLOW_DISTANCE_PX = 44


# Walking onto a THIN_ICE tile increments a per-tile step counter stored on
# the room.  After THIN_ICE_STEPS_TO_CRACK steps on the same tile, that tile
# collapses to PIT_TILE (lethal).  The cracking is permanent for the room's
# lifetime; tiles do not regenerate between visits.
THIN_ICE_STEPS_TO_CRACK = 3
# How long (ms) a cracked-through thin-ice pit waits before regenerating back
# into a fresh THIN_ICE tile.
THIN_ICE_RESPAWN_MS = 15_000

# Crack-stage overlay colours for thin-ice tiles.  Index 0 = first step
# (lightest crack lines), ascending up to THIN_ICE_STEPS_TO_CRACK - 1 (final
# stage just before collapse).  Each value is an RGBA colour drawn on top of
# the base COLOR_THIN_ICE tile so only the crack lines are visible.
THIN_ICE_CRACK_COLORS = (
    (160, 200, 230, 140),   # stage 1 – visible hairline crossing cracks
    (110, 160, 210, 210),   # stage 2 – heavy fracture network
    # stage 3 = collapse; no overlay needed (tile becomes PIT_TILE)
)

# ── Pit fall animation ────────────────────────────────────────────────────────
# When a player contacts a PIT_TILE (or cracks through thin ice), rather than
# dying instantly the player plays a three-phase fall animation:
#   1. "falling"  — slides to the center of the pit tile over SLIDE_MS.
#   2. "shrinking" — sprite shrinks from full size to nothing over SHRINK_MS.
#   3. "pause"    — brief invisible pause before respawn (PAUSE_MS).
# Then the player is placed on the nearest walkable non-pit tile and granted
# extended i-frames (RESPAWN_IFRAMES_MS) that drive the standard flash visual.
# ANIM_TOTAL_MS covers the entire animation and is used as the initial i-frame
# window so damage is blocked for the full duration of the fall.
PIT_FALL_SLIDE_MS            = 300    # ms to glide player to pit center
PIT_FALL_SHRINK_MS           = 600    # ms to shrink sprite from full → nothing
PIT_FALL_PAUSE_MS            = 250    # ms pause while fully shrunk before respawn
PIT_FALL_ANIM_TOTAL_MS       = 1150   # SLIDE + SHRINK + PAUSE  (i-frame cover)
PIT_FALL_RESPAWN_IFRAMES_MS  = 2500   # i-frames granted on respawn (drives flash)
PIT_FALL_HP_PENALTY          = 15     # HP deducted on respawn; never lethal

# Thin Ice Field room polish constants (analog of STALAGMITE_FIELD_*).
ICE_THIN_ICE_FIELD_DOOR_BUFFER          = 2
ICE_THIN_ICE_FIELD_SINGLETON_COUNT_RANGE = (4, 7)

# ── IceCrystalEnemy (ice_crystal_room) ───────────────────────────────────────
# Stationary crystal pillars that periodically blast nearby targets with
# a freezing pulse.  They are immortal room fixtures; wave-spawned crystal
# shards created by a future boss may be mortal.
ICE_CRYSTAL_HP               = 1          # effectively invulnerable
COLOR_ICE_CRYSTAL            = (180, 230, 255)
COLOR_ICE_CRYSTAL_PULSE      = (220, 245, 255)   # tint during active pulse
ICE_CRYSTAL_SIZE             = 20         # sprite size (px)
ICE_CRYSTAL_PULSE_RADIUS     = 96         # px; players within this radius get frozen
ICE_CRYSTAL_PULSE_INTERVAL_MS = 4500      # ms between pulse events
ICE_CRYSTAL_PULSE_WINDUP_MS  = 900        # telegraph (crystal brightens)
ICE_CRYSTAL_PULSE_STRIKE_MS  = 200        # active damage window
ICE_CRYSTAL_PULSE_COOLDOWN_MS = 3400      # return-to-idle window
ICE_CRYSTAL_FREEZE_DURATION_MS = 1200     # how long the applied FROZEN status lasts
# Ice Crystal Room layout constants.
ICE_CRYSTAL_ROOM_CRYSTAL_COUNT = 3        # number of crystals placed per room
ICE_CRYSTAL_ROOM_DOOR_BUFFER   = 3        # chebyshev radius around doors kept crystal-free

# ── Tide Lord mini-boss (water_tide_lord_arena) ─────────────────────────────
# Slow-moving water-biome boss with two telegraphed attacks:
#   Tide Crash  — close-range AOE circle (like Golem slam).
#   Wave Surge  — fan of water projectiles; phase 2 widens the fan.
# At 75 / 50 / 25 % HP the BossController summons WaterSpirit adds.
TIDE_LORD_HP                    = 650
TIDE_LORD_SPEED                 = 0.65
COLOR_TIDE_LORD                 = (30, 90, 190)
TIDE_LORD_SIZE                  = 52

# Tide Crash: close-range AOE slam.
TIDE_LORD_CRASH_RANGE           = int(2.0 * TILE_SIZE)   # trigger distance (px)
TIDE_LORD_CRASH_RADIUS          = int(2.4 * TILE_SIZE)   # hitbox radius (px)
TIDE_LORD_CRASH_DAMAGE          = 30
TIDE_LORD_CRASH_WINDUP_MS       = 900
TIDE_LORD_CRASH_STRIKE_MS       = 160
TIDE_LORD_CRASH_COOLDOWN_MS     = 1400

# Wave Surge: radial fan of projectiles.
TIDE_LORD_SURGE_RANGE           = int(9.0 * TILE_SIZE)   # trigger distance (px)
TIDE_LORD_SURGE_WINDUP_MS       = 1100
TIDE_LORD_SURGE_STRIKE_MS       = 120
TIDE_LORD_SURGE_COOLDOWN_MS     = 2000
TIDE_LORD_SURGE_SPREAD_DEG      = 30   # degrees between adjacent shots in fan
TIDE_LORD_SURGE_SHOTS_P1        = 3    # phase-1 fan width
TIDE_LORD_SURGE_SHOTS_P2        = 5    # phase-2 fan width (unlocked at 50 % HP)

# Wave Surge projectile.
TIDE_LORD_PROJECTILE_SPEED      = 3.2
TIDE_LORD_PROJECTILE_RANGE      = int(10.0 * TILE_SIZE)
TIDE_LORD_PROJECTILE_DAMAGE     = 16
TIDE_LORD_PROJECTILE_SIZE       = 14

# Arena layout.
TIDE_LORD_ARENA_FLOOD_RADIUS    = 4    # tile radius of central WATER disc
TIDE_LORD_ARENA_CURRENT_BAND    = 2    # tile width of outward-CURRENT ring
TIDE_LORD_WAVE_SPAWN_RADIUS     = int(4 * TILE_SIZE)  # px from boss centre for wave spawns

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
