"""Data-driven dungeon definitions.

Each dungeon now represents a single exploration floor rather than a five-level
campaign.  Generation parameters (grid size, minimum start-to-portal distance)
are driven by the selected difficulty preset rather than a level index.
"""
from enemies import PatrolEnemy, RandomEnemy, ChaserEnemy, PulsatorEnemy, LauncherEnemy


# ── Difficulty presets ─────────────────────────────────
# grid_size:    the dungeon is generated on an N×N coordinate grid.
# min_distance: minimum Manhattan distance between the spawn and portal rooms.
# Enemy counts and branch density can scale with difficulty too.

DIFFICULTY_PRESETS = {
    "default": {
        "grid_size": 5,
        "min_distance": 3,
        "enemy_count_scale": 1.0,
    },
    "medium": {
        "grid_size": 7,
        "min_distance": 5,
        "enemy_count_scale": 1.25,
    },
    "hard": {
        "grid_size": 10,
        "min_distance": 7,
        "enemy_count_scale": 1.5,
    },
}


def _run_profile(
    enemy_count_range,
    enemy_type_weights,
    *,
    branch_count_range,
    branch_length_range,
    pacing_profile,
):
    """Single-floor run profile that replaces the old per-level arrays."""
    return {
        "enemy_count_range": enemy_count_range,
        "enemy_type_weights": enemy_type_weights,
        "branch_count_range": branch_count_range,
        "branch_length_range": branch_length_range,
        "pacing_profile": pacing_profile,
    }


# ── Per-dungeon run profiles ──────────────────────────
# Enemy type weights: [PatrolEnemy, RandomEnemy, ChaserEnemy, PulsatorEnemy, LauncherEnemy]
# (SentryEnemy is NOT in this list — it spawns only via stealth-room
# objective configs, not the random palette.)

_MUD_PROFILE   = _run_profile((1, 4), [30, 30, 25, 10, 5],  branch_count_range=(1, 3), branch_length_range=(1, 3), pacing_profile="balanced")
_ICE_PROFILE   = _run_profile((1, 4), [20, 20, 40, 10, 10], branch_count_range=(1, 3), branch_length_range=(1, 4), pacing_profile="frontloaded")
_WATER_PROFILE = _run_profile((1, 4), [25, 30, 25, 10, 10], branch_count_range=(2, 3), branch_length_range=(1, 3), pacing_profile="backloaded")


# ── Dungeon definitions ────────────────────────────────
# terrain_type must match a room tile constant ("mud", "ice", "water").

DUNGEONS = [
    {
        "id": "mud_caverns",
        "name": "Mud Caverns",
        "terrain_type": "mud",
        "locked": False,
        "run_profile": _MUD_PROFILE,
    },
    {
        "id": "frozen_depths",
        "name": "Frozen Depths",
        "terrain_type": "ice",
        "locked": False,
        "run_profile": _ICE_PROFILE,
    },
    {
        "id": "sunken_ruins",
        "name": "Sunken Ruins",
        "terrain_type": "water",
        "locked": False,
        "run_profile": _WATER_PROFILE,
    },
]

# The enemy classes list whose order corresponds to the weight indices.
ENEMY_CLASSES_ORDERED = [PatrolEnemy, RandomEnemy, ChaserEnemy, PulsatorEnemy, LauncherEnemy]


def get_dungeon(dungeon_id):
    """Return the dungeon config dict for *dungeon_id*, or None."""
    for d in DUNGEONS:
        if d["id"] == dungeon_id:
            return d
    return None


def get_difficulty_preset(difficulty: str) -> dict:
    """Return the preset dict for a difficulty name, defaulting to 'default'."""
    return DIFFICULTY_PRESETS.get(difficulty, DIFFICULTY_PRESETS["default"])

