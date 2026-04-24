"""Static rune definitions for the rune system.

Runes are collectible per-dungeon power-ups with strong tradeoffs.  Each
rune is uniquely owned within a single dungeon run and is wiped when the
run ends (completion or death).

This module is the single source of truth for rune metadata.  Effect
resolution lives in :mod:`rune_rules` and the actual gameplay hooks live
in the various rule modules (attack_rules, combat_rules, etc.).
"""

from dataclasses import dataclass


# ── slot categories ─────────────────────────────────────
RUNE_CATEGORY_STAT = "stat"
RUNE_CATEGORY_BEHAVIOR = "behavior"
RUNE_CATEGORY_IDENTITY = "identity"

RUNE_CATEGORIES = (
    RUNE_CATEGORY_STAT,
    RUNE_CATEGORY_BEHAVIOR,
    RUNE_CATEGORY_IDENTITY,
)

# Slot capacity per category.  Picking a rune for a full category
# requires the player to confirm replacement of an existing rune.
RUNE_SLOT_CAPACITY = {
    RUNE_CATEGORY_STAT:     3,
    RUNE_CATEGORY_BEHAVIOR: 1,
    RUNE_CATEGORY_IDENTITY: 1,
}

# ── rarity tiers (also used as altar offer weights) ─────
RUNE_RARITY_COMMON   = "common"
RUNE_RARITY_UNCOMMON = "uncommon"
RUNE_RARITY_LEGENDARY = "legendary"

RUNE_RARITY_WEIGHTS = {
    RUNE_RARITY_COMMON:    70,
    RUNE_RARITY_UNCOMMON:  25,
    RUNE_RARITY_LEGENDARY:  5,
}


@dataclass(frozen=True, slots=True)
class RuneDefinition:
    rune_id: str
    name: str
    category: str
    rarity: str
    bonus_text: str
    tradeoff_text: str
    flavor: str = ""

    @property
    def label(self):
        return self.name


# ── stat runes (16 = 12 base + 4 expansion) ─────────────
_STAT_RUNES = (
    # Offensive
    RuneDefinition(
        rune_id="bloodthirst",
        name="Bloodthirst",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+50% damage on the first hit you land in each room.",
        tradeoff_text="All subsequent hits in that room deal -20% damage.",
    ),
    RuneDefinition(
        rune_id="glass_cannon",
        name="Glass Cannon",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+80% damage dealt.",
        tradeoff_text="-50% maximum HP.",
    ),
    RuneDefinition(
        rune_id="executioner",
        name="Executioner",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+100% damage to enemies below 25% HP.",
        tradeoff_text="-30% damage to enemies above 25% HP.",
    ),
    RuneDefinition(
        rune_id="berserker",
        name="Berserker",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+5% damage stacking per kill in a room.",
        tradeoff_text="Stack resets to zero on taking any damage.",
    ),
    # Defensive
    RuneDefinition(
        rune_id="ironhide",
        name="Ironhide",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+60 maximum HP.",
        tradeoff_text="-20% movement speed.",
    ),
    RuneDefinition(
        rune_id="turtle_shell",
        name="Turtle Shell",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+40% damage reduction.",
        tradeoff_text="Cannot dodge.",
    ),
    RuneDefinition(
        rune_id="last_stand",
        name="Last Stand",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+200% damage reduction while below 15% HP.",
        tradeoff_text="No damage reduction above 15% HP.",
    ),
    RuneDefinition(
        rune_id="thorns",
        name="Thorns",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="Reflect 30% of damage taken to the attacker.",
        tradeoff_text="Your own attacks deal -25% damage.",
    ),
    # Mobility
    RuneDefinition(
        rune_id="sprinter",
        name="Sprinter",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+50% movement speed.",
        tradeoff_text="-30% attack speed.",
    ),
    RuneDefinition(
        rune_id="slippery",
        name="Slippery",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+40% dodge distance.",
        tradeoff_text="Dodge cooldown becomes 2s instead of 0.5s.",
    ),
    RuneDefinition(
        rune_id="ghost_step",
        name="Ghost Step",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="Pass through enemies while dodging.",
        tradeoff_text="Dodging no longer grants invincibility frames.",
    ),
    RuneDefinition(
        rune_id="momentum",
        name="Momentum",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="+10% damage stacking per second of continuous movement.",
        tradeoff_text="Dealing damage resets the stack.",
    ),
    # Expansion
    RuneDefinition(
        rune_id="vampire_lord",
        name="Vampire Lord",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="Heal 5% of maximum HP on each kill.",
        tradeoff_text="-30% maximum HP.",
    ),
    RuneDefinition(
        rune_id="featherweight",
        name="Featherweight",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="Dodge cooldown is halved.",
        tradeoff_text="-40% maximum HP.",
    ),
    RuneDefinition(
        rune_id="heavy_hitter",
        name="Heavy Hitter",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="First hit on each enemy deals +120% damage.",
        tradeoff_text="Weapon cooldown is +50%.",
    ),
    RuneDefinition(
        rune_id="iron_will",
        name="Iron Will",
        category=RUNE_CATEGORY_STAT,
        rarity=RUNE_RARITY_COMMON,
        bonus_text="Immune to all negative status effects.",
        tradeoff_text="-25% damage dealt.",
    ),
)


# ── behavior runes (9 = 6 base + 3 expansion) ───────────
_BEHAVIOR_RUNES = (
    # Attack behavior
    RuneDefinition(
        rune_id="ricochet",
        name="Ricochet",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Attacks bounce to a second nearby enemy.",
        tradeoff_text="Cannot hit the same enemy twice per attack.",
    ),
    RuneDefinition(
        rune_id="shockwave",
        name="Shockwave",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Attacks send a slow shockwave forward dealing 150% damage.",
        tradeoff_text="Direct attack hitbox is removed; only shockwaves damage.",
    ),
    RuneDefinition(
        rune_id="vampiric_strike",
        name="Vampiric Strike",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Kills heal you for 8 HP.",
        tradeoff_text="Cannot pick up health potions or use healing shrines.",
    ),
    # Ability behavior
    RuneDefinition(
        rune_id="afterimage",
        name="Afterimage",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Dodging leaves a damaging decoy at your origin for 2s.",
        tradeoff_text="Dodge distance is halved.",
    ),
    RuneDefinition(
        rune_id="overclock",
        name="Overclock",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Active ability fires twice in rapid succession.",
        tradeoff_text="Active ability cooldown is tripled.",
    ),
    RuneDefinition(
        rune_id="chain_reaction",
        name="Chain Reaction",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Status effects spread to all enemies within 3 tiles.",
        tradeoff_text="You are also affected by any status effect you apply.",
    ),
    # Expansion
    RuneDefinition(
        rune_id="boomerang",
        name="Boomerang",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Projectile attacks return to you, dealing damage on the way back.",
        tradeoff_text="Outbound trip deals zero damage.",
    ),
    RuneDefinition(
        rune_id="shrapnel_burst",
        name="Shrapnel Burst",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Kills explode for 80% weapon damage in a 2-tile radius.",
        tradeoff_text="You take 50% of the explosion damage if standing inside it.",
    ),
    RuneDefinition(
        rune_id="static_charge",
        name="Static Charge",
        category=RUNE_CATEGORY_BEHAVIOR,
        rarity=RUNE_RARITY_UNCOMMON,
        bonus_text="Movement builds charge; next attack discharges for +200% damage.",
        tradeoff_text="Standing still dissipates the charge twice as fast.",
    ),
)


# ── identity runes (5 = 3 base + 2 expansion) ───────────
_IDENTITY_RUNES = (
    RuneDefinition(
        rune_id="the_pacifist",
        name="The Pacifist",
        category=RUNE_CATEGORY_IDENTITY,
        rarity=RUNE_RARITY_LEGENDARY,
        bonus_text="Enemies who collide take 500% of your normal damage; +100% movement speed.",
        tradeoff_text="You deal zero direct damage; picking up any weapon destroys this rune.",
    ),
    RuneDefinition(
        rune_id="glass_soul",
        name="Glass Soul",
        category=RUNE_CATEGORY_IDENTITY,
        rarity=RUNE_RARITY_LEGENDARY,
        bonus_text="Damage instead grants 2s invincibility; healing converts to attack speed.",
        tradeoff_text="Maximum HP locked at 1; being stunned kills you instantly.",
    ),
    RuneDefinition(
        rune_id="time_anchor",
        name="Time Anchor",
        category=RUNE_CATEGORY_IDENTITY,
        rarity=RUNE_RARITY_LEGENDARY,
        bonus_text="Time slows to 20% while standing still; full meter triggers a 3s freeze.",
        tradeoff_text="Moving snaps time back to normal; meter empties while moving.",
    ),
    RuneDefinition(
        rune_id="necromancer",
        name="Necromancer",
        category=RUNE_CATEGORY_IDENTITY,
        rarity=RUNE_RARITY_LEGENDARY,
        bonus_text="Every 3rd kill becomes a temporary ally for 10s; allies share your damage.",
        tradeoff_text="Ally death deals 25% of their max HP to you.",
    ),
    RuneDefinition(
        rune_id="the_conduit",
        name="The Conduit",
        category=RUNE_CATEGORY_IDENTITY,
        rarity=RUNE_RARITY_LEGENDARY,
        bonus_text="Every hit splits 60/40 between target and the nearest other enemy.",
        tradeoff_text="Splash also damages escort NPCs and friendly entities.",
    ),
)


# ── public registry ─────────────────────────────────────
RUNE_DATABASE: dict[str, RuneDefinition] = {
    rune.rune_id: rune
    for rune in (*_STAT_RUNES, *_BEHAVIOR_RUNES, *_IDENTITY_RUNES)
}


def all_runes():
    """Return every rune definition, in registration order."""
    return tuple(RUNE_DATABASE.values())


def get_rune(rune_id):
    """Return the :class:`RuneDefinition` for *rune_id* or ``None``."""
    return RUNE_DATABASE.get(rune_id)


def runes_by_category(category):
    """Return all runes in the given slot category."""
    return tuple(rune for rune in RUNE_DATABASE.values() if rune.category == category)


def runes_by_rarity(rarity):
    """Return all runes of the given rarity tier."""
    return tuple(rune for rune in RUNE_DATABASE.values() if rune.rarity == rarity)
