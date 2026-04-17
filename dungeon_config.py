"""Data-driven dungeon and level definitions.

Each dungeon has a unique terrain type and five levels of escalating
difficulty.  Add new entries to DUNGEONS to create additional dungeons —
they will automatically appear in the dungeon-select screen.
"""
from enemies import PatrolEnemy, RandomEnemy, ChaserEnemy

# ── Level template ──────────────────────────────────────
# Each level dict contains:
#   path_length        – rooms from start to exit portal
#   enemy_count_range  – (min, max) enemies per room
#   enemy_type_weights – [PatrolEnemy, RandomEnemy, ChaserEnemy] weights

_MUD_LEVELS = [
    {"path_length": 3, "enemy_count_range": (1, 2), "enemy_type_weights": [50, 35, 15]},
    {"path_length": 5, "enemy_count_range": (1, 3), "enemy_type_weights": [40, 35, 25]},
    {"path_length": 7, "enemy_count_range": (2, 3), "enemy_type_weights": [30, 35, 35]},
    {"path_length": 9, "enemy_count_range": (2, 4), "enemy_type_weights": [25, 30, 45]},
    {"path_length": 12, "enemy_count_range": (3, 5), "enemy_type_weights": [20, 25, 55]},
]

_ICE_LEVELS = [
    {"path_length": 3, "enemy_count_range": (1, 2), "enemy_type_weights": [50, 35, 15]},
    {"path_length": 5, "enemy_count_range": (1, 3), "enemy_type_weights": [40, 35, 25]},
    {"path_length": 7, "enemy_count_range": (2, 3), "enemy_type_weights": [30, 35, 35]},
    {"path_length": 9, "enemy_count_range": (2, 4), "enemy_type_weights": [25, 30, 45]},
    {"path_length": 12, "enemy_count_range": (3, 5), "enemy_type_weights": [20, 25, 55]},
]

_WATER_LEVELS = [
    {"path_length": 3, "enemy_count_range": (1, 2), "enemy_type_weights": [50, 35, 15]},
    {"path_length": 5, "enemy_count_range": (1, 3), "enemy_type_weights": [40, 35, 25]},
    {"path_length": 7, "enemy_count_range": (2, 3), "enemy_type_weights": [30, 35, 35]},
    {"path_length": 9, "enemy_count_range": (2, 4), "enemy_type_weights": [25, 30, 45]},
    {"path_length": 12, "enemy_count_range": (3, 5), "enemy_type_weights": [20, 25, 55]},
]


# ── Dungeon definitions ────────────────────────────────
# terrain_type must match a room tile constant ("mud", "ice", "water").
# enemy_classes order must match the weight lists above.

DUNGEONS = [
    {
        "id": "mud_caverns",
        "name": "Mud Caverns",
        "terrain_type": "mud",
        "locked": False,
        "levels": _MUD_LEVELS,
    },
    {
        "id": "frozen_depths",
        "name": "Frozen Depths",
        "terrain_type": "ice",
        "locked": False,
        "levels": _ICE_LEVELS,
    },
    {
        "id": "sunken_ruins",
        "name": "Sunken Ruins",
        "terrain_type": "water",
        "locked": False,
        "levels": _WATER_LEVELS,
    },
]

# The enemy classes list whose order corresponds to the weight indices.
ENEMY_CLASSES_ORDERED = [PatrolEnemy, RandomEnemy, ChaserEnemy]


def get_dungeon(dungeon_id):
    """Return the dungeon config dict for *dungeon_id*, or None."""
    for d in DUNGEONS:
        if d["id"] == dungeon_id:
            return d
    return None


def get_level(dungeon_id, level_index):
    """Return the level config dict for a given dungeon and level index."""
    d = get_dungeon(dungeon_id)
    if d is None or level_index < 0 or level_index >= len(d["levels"]):
        return None
    return d["levels"][level_index]
