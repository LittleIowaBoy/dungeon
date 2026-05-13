"""Risk/Reward Danger Mode — math, constants, and pact definitions.

This module is the single source of truth for all Danger Mode scaling math.
All other systems import from here; no magic numbers should live elsewhere.
"""

# ── Pressure ──────────────────────────────────────────────────────────────────
PRESSURE_LEVEL_MAX: int = 20

# 30-second window of uninterrupted combat to trigger time-decay (-1 pressure)
PRESSURE_TIME_DECAY_INTERVAL_MS: int = 30_000

# Pressure lost when the player skips (bypasses without entering) a danger branch
DANGER_BRANCH_SKIP_DECAY: int = 2

# ── Hunter ────────────────────────────────────────────────────────────────────
HUNTER_SPAWN_CHANCE: float = 0.40
# Double Hunter is spawned on a danger-branch room at peak pressure
HUNTER_DANGER_BRANCH_COUNT: int = 2
HUNTER_EXCLUSIVE_WEAPON_DROP_CHANCE: float = 0.25
HUNTER_WEAPON_POOL: list[str] = [
    "hunter_heavy_blade",
    "hunter_spectral_bow",
    "hunter_void_blade",
]

# ── Pacts ─────────────────────────────────────────────────────────────────────
MAX_PACTS_PER_RUN: int = 2

# Each pact entry is a dict with:
#   display_name  – shown in the shrine UI
#   description   – tooltip / choice screen text
#   drawback_*    – negative effect metadata (consumed by relevant systems)
#   bonus_*       – positive effect metadata
PACTS: dict[str, dict] = {
    "blood_pact": {
        "display_name": "Blood Pact",
        "description": "-25% max HP — coins ×1.5 and chest tier floor raised",
        # Applied by loadout_rules when pact is active
        "max_hp_mult": 0.75,
        # Applied by chest.py / reward logic
        "coin_mult": 1.5,
        # Forces chest tier to at least branch_bonus
        "chest_tier_floor": "branch_bonus",
    },
    "hex_of_fragility": {
        "display_name": "Hex of Fragility",
        "description": "+25% enemy damage — gain +1 rune equip slot",
        # Applied by combat_rules when delivering damage to player
        "enemy_damage_mult": 1.25,
        # Applied by rune_rules to expand rune slot capacity for this run
        "rune_slot_bonus": 1,
    },
}

# ── Reward tier ordering (for tier bump logic) ────────────────────────────────
_TIER_ORDER: list[str] = ["standard", "branch_bonus", "finale_bonus"]


def _tier_index(tier: str) -> int:
    try:
        return _TIER_ORDER.index(tier)
    except ValueError:
        return 0


# ── Scaling helpers ───────────────────────────────────────────────────────────

def compute_enemy_scale_boost(pressure_level: int) -> float:
    """Return additive HP/damage multiplier based on current pressure.

    0.0 at level 0, linearly scaling to 0.5 (50%) at PRESSURE_LEVEL_MAX.
    """
    if pressure_level <= 0:
        return 0.0
    clamped = min(pressure_level, PRESSURE_LEVEL_MAX)
    return 0.5 * (clamped / PRESSURE_LEVEL_MAX)


def compute_coin_multiplier(pressure_level: int) -> float:
    """Return coin multiplier based on current pressure.

    1.0 at level 0, linearly scaling to 2.0 at PRESSURE_LEVEL_MAX.
    """
    if pressure_level <= 0:
        return 1.0
    clamped = min(pressure_level, PRESSURE_LEVEL_MAX)
    return 1.0 + (clamped / PRESSURE_LEVEL_MAX)


def compute_reward_tier_bump(pressure_level: int, base_tier: str) -> str:
    """Possibly elevate *base_tier* based on pressure level.

    Pressure ≥ 10 → at least "branch_bonus".
    Pressure == 20 → always "finale_bonus".
    """
    if pressure_level >= PRESSURE_LEVEL_MAX:
        return "finale_bonus"
    if pressure_level >= PRESSURE_LEVEL_MAX // 2:
        bumped_index = max(_tier_index(base_tier), _tier_index("branch_bonus"))
        return _TIER_ORDER[bumped_index]
    return base_tier


def pressure_increment_on_clean_room() -> int:
    """How much pressure increases when the player clears a room without taking damage."""
    return 2


def pressure_increment_on_damaged_room() -> int:
    """How much pressure increases when the player clears a room after taking damage."""
    return 1


def pressure_decrement_on_death() -> int:
    """Pressure reset on player death — runs reset entirely, so this is informational."""
    return PRESSURE_LEVEL_MAX
