"""Data-driven dungeon and level definitions.

Each dungeon has a unique terrain type and five levels of escalating
difficulty.  Add new entries to DUNGEONS to create additional dungeons —
they will automatically appear in the dungeon-select screen.
"""
from enemies import PatrolEnemy, RandomEnemy, ChaserEnemy


def _level(
    path_length,
    enemy_count_range,
    enemy_type_weights,
    *,
    branch_count_range,
    branch_length_range,
    pacing_profile,
):
    return {
        "path_length": path_length,
        "enemy_count_range": enemy_count_range,
        "enemy_type_weights": enemy_type_weights,
        "branch_count_range": branch_count_range,
        "branch_length_range": branch_length_range,
        "pacing_profile": pacing_profile,
    }

# ── Level template ──────────────────────────────────────
# Each level dict contains:
#   path_length        – rooms from start to exit portal
#   enemy_count_range  – (min, max) enemies per room
#   enemy_type_weights – [PatrolEnemy, RandomEnemy, ChaserEnemy] weights

_MUD_LEVELS = [
    _level(3, (1, 2), [50, 35, 15], branch_count_range=(0, 0), branch_length_range=(1, 1), pacing_profile="balanced"),
    _level(5, (1, 3), [40, 35, 25], branch_count_range=(1, 1), branch_length_range=(1, 1), pacing_profile="balanced"),
    _level(7, (2, 3), [30, 35, 35], branch_count_range=(1, 2), branch_length_range=(1, 2), pacing_profile="balanced"),
    _level(9, (2, 4), [25, 30, 45], branch_count_range=(2, 2), branch_length_range=(1, 2), pacing_profile="backloaded"),
    _level(12, (3, 5), [20, 25, 55], branch_count_range=(2, 3), branch_length_range=(2, 3), pacing_profile="backloaded"),
]

_ICE_LEVELS = [
    _level(3, (1, 2), [45, 25, 30], branch_count_range=(0, 0), branch_length_range=(1, 1), pacing_profile="balanced"),
    _level(5, (1, 3), [35, 25, 40], branch_count_range=(1, 1), branch_length_range=(1, 2), pacing_profile="frontloaded"),
    _level(7, (2, 3), [25, 30, 45], branch_count_range=(1, 2), branch_length_range=(2, 2), pacing_profile="frontloaded"),
    _level(9, (2, 4), [20, 30, 50], branch_count_range=(1, 2), branch_length_range=(2, 3), pacing_profile="balanced"),
    _level(12, (3, 5), [15, 25, 60], branch_count_range=(2, 2), branch_length_range=(2, 4), pacing_profile="backloaded"),
]

_WATER_LEVELS = [
    _level(3, (1, 2), [45, 40, 15], branch_count_range=(0, 0), branch_length_range=(1, 1), pacing_profile="balanced"),
    _level(5, (1, 3), [35, 40, 25], branch_count_range=(1, 2), branch_length_range=(1, 2), pacing_profile="balanced"),
    _level(7, (2, 3), [25, 45, 30], branch_count_range=(2, 2), branch_length_range=(1, 2), pacing_profile="backloaded"),
    _level(9, (2, 4), [20, 45, 35], branch_count_range=(2, 3), branch_length_range=(2, 3), pacing_profile="backloaded"),
    _level(12, (3, 5), [15, 40, 45], branch_count_range=(3, 3), branch_length_range=(2, 4), pacing_profile="backloaded"),
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
