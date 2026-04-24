"""SQLite-backed room content catalog.

This database is separate from save_data.db because room templates are
reference content, not mutable player progress.
"""

import os
import sqlite3


_DB_PATH = os.path.join(os.path.dirname(__file__), "room_content.db")

BASE_ROOM_TEMPLATE_TABLE = "base_room_templates"
DUNGEON_ROOM_TEMPLATE_TABLES = {
    "mud_caverns": "mud_caverns_room_templates",
    "frozen_depths": "frozen_depths_room_templates",
    "sunken_ruins": "sunken_ruins_room_templates",
}

ROOM_TEMPLATE_COLUMNS = (
    "room_id",
    "display_name",
    "objective_kind",
    "combat_pressure",
    "decision_complexity",
    "topology_role",
    "min_depth",
    "max_depth",
    "branch_preference",
    "generation_weight",
    "enabled",
    "implementation_status",
    "objective_variant",
    "path_stage_min",
    "path_stage_max",
    "terminal_preference",
    "repeat_cooldown",
    "reward_affinity",
    "objective_rule",
    "objective_duration_ms",
    "enemy_minimum_bonus",
    "enemy_scale_factor",
    "guaranteed_chest",
    "chest_spawn_chance",
    "terrain_patch_count_range",
    "terrain_patch_size_range",
    "clear_center",
    "terminal_chest_lock",
    "objective_entity_count",
    "scripted_wave_sizes",
    "holdout_zone_radius",
    "holdout_relief_count",
    "holdout_relief_delay_ms",
    "ritual_role_script",
    "ritual_reinforcement_count",
    "ritual_link_mode",
    "ritual_payoff_kind",
    "ritual_payoff_label",
    "objective_label",
    "objective_layout_offsets",
    "objective_spawn_offset",
    "objective_radius",
    "objective_trigger_padding",
    "objective_max_hp",
    "objective_move_speed",
    "objective_guide_radius",
    "objective_exit_radius",
    "objective_damage_cooldown_ms",
    "puzzle_reinforcement_count",
    "puzzle_stall_duration_ms",
    "notes",
)


def _plan_shape(
    *,
    objective_rule="immediate",
    objective_duration_ms=None,
    enemy_minimum_bonus=0,
    enemy_scale_factor=1.0,
    guaranteed_chest=False,
    chest_spawn_chance=None,
    terrain_patch_count_range="",
    terrain_patch_size_range="",
    clear_center=False,
    terminal_chest_lock=False,
    objective_entity_count=0,
    scripted_wave_sizes="",
    holdout_zone_radius=0,
    holdout_relief_count=0,
    holdout_relief_delay_ms=0,
    ritual_role_script="",
    ritual_reinforcement_count=0,
    ritual_link_mode="",
    ritual_payoff_kind="",
    ritual_payoff_label="",
    objective_label="",
    objective_layout_offsets="",
    objective_spawn_offset="",
    objective_radius=0,
    objective_trigger_padding=0,
    objective_max_hp=0,
    objective_move_speed=0.0,
    objective_guide_radius=0,
    objective_exit_radius=0,
    objective_damage_cooldown_ms=0,
    puzzle_reinforcement_count=0,
    puzzle_stall_duration_ms=0,
):
    return {
        "objective_rule": objective_rule,
        "objective_duration_ms": objective_duration_ms,
        "enemy_minimum_bonus": enemy_minimum_bonus,
        "enemy_scale_factor": enemy_scale_factor,
        "guaranteed_chest": int(bool(guaranteed_chest)),
        "chest_spawn_chance": chest_spawn_chance,
        "terrain_patch_count_range": terrain_patch_count_range,
        "terrain_patch_size_range": terrain_patch_size_range,
        "clear_center": int(bool(clear_center)),
        "terminal_chest_lock": int(bool(terminal_chest_lock)),
        "objective_entity_count": objective_entity_count,
        "scripted_wave_sizes": scripted_wave_sizes,
        "holdout_zone_radius": holdout_zone_radius,
        "holdout_relief_count": holdout_relief_count,
        "holdout_relief_delay_ms": holdout_relief_delay_ms,
        "ritual_role_script": ritual_role_script,
        "ritual_reinforcement_count": ritual_reinforcement_count,
        "ritual_link_mode": ritual_link_mode,
        "ritual_payoff_kind": ritual_payoff_kind,
        "ritual_payoff_label": ritual_payoff_label,
        "objective_label": objective_label,
        "objective_layout_offsets": objective_layout_offsets,
        "objective_spawn_offset": objective_spawn_offset,
        "objective_radius": objective_radius,
        "objective_trigger_padding": objective_trigger_padding,
        "objective_max_hp": objective_max_hp,
        "objective_move_speed": objective_move_speed,
        "objective_guide_radius": objective_guide_radius,
        "objective_exit_radius": objective_exit_radius,
        "objective_damage_cooldown_ms": objective_damage_cooldown_ms,
        "puzzle_reinforcement_count": puzzle_reinforcement_count,
        "puzzle_stall_duration_ms": puzzle_stall_duration_ms,
    }

BASE_ROOM_TEMPLATES = (
    {
        "room_id": "standard_combat",
        "display_name": "Standard Combat",
        "objective_kind": "combat",
        "combat_pressure": "mid",
        "decision_complexity": "low",
        "topology_role": "opener",
        "min_depth": 0,
        "max_depth": 1,
        "branch_preference": "either",
        "generation_weight": 10,
        "enabled": 1,
        "implementation_status": "implemented",
        "objective_variant": "",
        "path_stage_min": 0,
        "path_stage_max": 1,
        "terminal_preference": "avoid",
        "repeat_cooldown": 0,
        "reward_affinity": "any",
        **_plan_shape(),
        "notes": "Baseline kill-all room used to establish pacing and difficulty.",
    },
    {
        "room_id": "escort_protection",
        "display_name": "Escort And Protection",
        "objective_kind": "escort",
        "combat_pressure": "high",
        "decision_complexity": "high",
        "topology_role": "mid_run",
        "min_depth": 2,
        "max_depth": None,
        "branch_preference": "main_path",
        "generation_weight": 3,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "",
        "path_stage_min": 2,
        "path_stage_max": 4,
        "terminal_preference": "any",
        "repeat_cooldown": 1,
        "reward_affinity": "finale",
        **_plan_shape(
            objective_rule="escort_to_exit",
            enemy_minimum_bonus=1,
            enemy_scale_factor=1.25,
            terrain_patch_count_range="1,3",
            terrain_patch_size_range="2,3",
            clear_center=True,
            terminal_chest_lock=True,
            objective_label="Escort",
            objective_spawn_offset="-6,0",
            objective_max_hp=26,
            objective_move_speed=1.2,
            objective_guide_radius=92,
            objective_exit_radius=24,
            objective_damage_cooldown_ms=500,
        ),
        "notes": "Protect a fragile survivor as they advance toward the exit under enemy pressure.",
    },
    {
        "room_id": "escort_bomb_carrier",
        "display_name": "Escort Bomb Carrier",
        "objective_kind": "escort_variant",
        "combat_pressure": "high",
        "decision_complexity": "high",
        "topology_role": "mid_run",
        "min_depth": 3,
        "max_depth": None,
        "branch_preference": "main_path",
        "generation_weight": 2,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "",
        "path_stage_min": 3,
        "path_stage_max": 4,
        "terminal_preference": "any",
        "repeat_cooldown": 1,
        "reward_affinity": "finale",
        **_plan_shape(
            objective_rule="escort_bomb_to_exit",
            enemy_minimum_bonus=1,
            enemy_scale_factor=1.0,
            terrain_patch_count_range="1,3",
            terrain_patch_size_range="2,3",
            clear_center=True,
            terminal_chest_lock=True,
            objective_label="Carrier",
            objective_spawn_offset="-6,0",
            objective_max_hp=30,
            objective_move_speed=1.0,
            objective_guide_radius=92,
            objective_exit_radius=24,
            objective_damage_cooldown_ms=500,
        ),
        "notes": "Guide a volatile carrier who only advances once the path is fully cleared.",
    },
    {
        "room_id": "puzzle_gated_doors",
        "display_name": "Puzzle-Gated Doors",
        "objective_kind": "puzzle",
        "combat_pressure": "mid",
        "decision_complexity": "high",
        "topology_role": "wildcard",
        "min_depth": 2,
        "max_depth": None,
        "branch_preference": "either",
        "generation_weight": 3,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "ordered_plates",
        "path_stage_min": 1,
        "path_stage_max": 3,
        "terminal_preference": "avoid",
        "repeat_cooldown": 1,
        "reward_affinity": "any",
        **_plan_shape(
            objective_rule="charge_plates",
            terrain_patch_count_range="2,4",
            terrain_patch_size_range="2,3",
            clear_center=True,
            terminal_chest_lock=True,
            objective_entity_count=3,
            objective_label="Seal",
            objective_layout_offsets="-5,-3;5,-3;0,4",
            objective_trigger_padding=10,
            puzzle_reinforcement_count=1,
            puzzle_stall_duration_ms=2500,
        ),
        "notes": "Exit stays locked until the player charges visible seal plates while under combat pressure.",
    },
    {
        "room_id": "survival_holdout",
        "display_name": "Survival Holdout",
        "objective_kind": "survival",
        "combat_pressure": "high",
        "decision_complexity": "low",
        "topology_role": "finale",
        "min_depth": 4,
        "max_depth": None,
        "branch_preference": "main_path",
        "generation_weight": 4,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "",
        "path_stage_min": 4,
        "path_stage_max": 4,
        "terminal_preference": "prefer",
        "repeat_cooldown": 2,
        "reward_affinity": "finale",
        **_plan_shape(
            objective_rule="holdout_timer",
            objective_duration_ms=9000,
            enemy_minimum_bonus=1,
            enemy_scale_factor=1.5,
            terrain_patch_count_range="2,4",
            terrain_patch_size_range="2,3",
            clear_center=True,
            terminal_chest_lock=True,
            scripted_wave_sizes="1,2,3",
            holdout_zone_radius=96,
            holdout_relief_count=1,
            holdout_relief_delay_ms=1500,
        ),
        "notes": "Survive until a timer expires while enemy pressure escalates, using optional stabilizers to delay reinforcements.",
    },
    {
        "room_id": "ritual_disruption",
        "display_name": "Ritual Disruption",
        "objective_kind": "ritual",
        "combat_pressure": "mid_high",
        "decision_complexity": "high",
        "topology_role": "mid_run",
        "min_depth": 2,
        "max_depth": None,
        "branch_preference": "either",
        "generation_weight": 3,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "altar_anchor",
        "path_stage_min": 2,
        "path_stage_max": 4,
        "terminal_preference": "any",
        "repeat_cooldown": 1,
        "reward_affinity": "any",
        **_plan_shape(
            objective_rule="destroy_altars",
            enemy_minimum_bonus=1,
            enemy_scale_factor=1.25,
            terrain_patch_count_range="2,5",
            terrain_patch_size_range="2,4",
            clear_center=True,
            terminal_chest_lock=True,
            objective_entity_count=3,
            ritual_role_script="summon,pulse,ward",
            ritual_reinforcement_count=2,
            ritual_link_mode="ward_shields_others",
            ritual_payoff_kind="reveal_reliquary",
            ritual_payoff_label="Reliquary",
        ),
        "notes": "Destroy enemy altars, with each destroyed altar enraging the survivors.",
    },
    {
        "room_id": "resource_race",
        "display_name": "Resource Race",
        "objective_kind": "race",
        "combat_pressure": "mid_high",
        "decision_complexity": "mid",
        "topology_role": "mid_run",
        "min_depth": 2,
        "max_depth": None,
        "branch_preference": "either",
        "generation_weight": 3,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "relic_cache",
        "path_stage_min": 2,
        "path_stage_max": 4,
        "terminal_preference": "any",
        "repeat_cooldown": 1,
        "reward_affinity": "any",
        **_plan_shape(
            objective_rule="claim_relic_before_lockdown",
            objective_duration_ms=7000,
            enemy_minimum_bonus=1,
            enemy_scale_factor=1.25,
            guaranteed_chest=True,
            chest_spawn_chance=1.0,
            terrain_patch_count_range="2,4",
            terrain_patch_size_range="2,4",
            clear_center=True,
            scripted_wave_sizes="1,2",
        ),
        "notes": "Secure the contested relic before raiders lock it down as claimant pressure escalates.",
    },
    {
        "room_id": "trap_gauntlet",
        "display_name": "Trap Gauntlet",
        "objective_kind": "traversal",
        "combat_pressure": "low",
        "decision_complexity": "low",
        "topology_role": "branch",
        "min_depth": 1,
        "max_depth": None,
        "branch_preference": "branch",
        "generation_weight": 2,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "crusher_corridors",
        "path_stage_min": 0,
        "path_stage_max": 4,
        "terminal_preference": "any",
        "repeat_cooldown": 1,
        "reward_affinity": "branch",
        **_plan_shape(
            objective_rule="immediate",
            enemy_scale_factor=0.0,
            guaranteed_chest=True,
            chest_spawn_chance=1.0,
            terrain_patch_count_range="6,9",
            terrain_patch_size_range="3,6",
            clear_center=True,
            objective_entity_count=3,
            objective_label="Lane Switch",
            objective_trigger_padding=18,
        ),
        "notes": "Switchable sweeper lanes create a traversal puzzle before the player reaches the reward chest.",
    },
    {
        "room_id": "stealth_passage",
        "display_name": "Stealth Passage",
        "objective_kind": "stealth",
        "combat_pressure": "low",
        "decision_complexity": "high",
        "topology_role": "wildcard",
        "min_depth": 2,
        "max_depth": None,
        "branch_preference": "either",
        "generation_weight": 1,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "",
        "path_stage_min": 0,
        "path_stage_max": 2,
        "terminal_preference": "avoid",
        "repeat_cooldown": 1,
        "reward_affinity": "branch",
        **_plan_shape(
            objective_rule="avoid_alarm_zones",
            objective_duration_ms=2200,
            enemy_scale_factor=0.0,
            terrain_patch_count_range="1,3",
            terrain_patch_size_range="2,3",
            clear_center=True,
            objective_entity_count=3,
            objective_label="Alarm",
            objective_layout_offsets="-4,-2;4,-2;0,4",
            objective_radius=34,
        ),
        "notes": "Slip through visible alarm wards before the search phase escalates into a lockdown fight.",
    },
    {
        "room_id": "timed_extraction",
        "display_name": "Timed Extraction",
        "objective_kind": "timed_extraction",
        "combat_pressure": "mid",
        "decision_complexity": "mid_high",
        "topology_role": "mid_run",
        "min_depth": 2,
        "max_depth": None,
        "branch_preference": "either",
        "generation_weight": 3,
        "enabled": 1,
        "implementation_status": "prototype",
        "objective_variant": "relic_cache",
        "path_stage_min": 2,
        "path_stage_max": 4,
        "terminal_preference": "any",
        "repeat_cooldown": 1,
        "reward_affinity": "any",
        **_plan_shape(
            objective_rule="loot_then_timer",
            objective_duration_ms=8000,
            enemy_minimum_bonus=1,
            enemy_scale_factor=1.0,
            guaranteed_chest=True,
            chest_spawn_chance=1.0,
            terrain_patch_count_range="3,5",
            terrain_patch_size_range="2,4",
            clear_center=True,
            scripted_wave_sizes="1,2",
        ),
        "notes": "Grab a valuable objective and escape before pursuit waves close the route behind you.",
    },
)


def _override_template(room_id, **updates):
    base = next(template for template in BASE_ROOM_TEMPLATES if template["room_id"] == room_id)
    overridden = dict(base)
    overridden.update(updates)
    return overridden


DUNGEON_ROOM_TEMPLATE_OVERRIDES = {
    "mud_caverns": (
        _override_template(
            "escort_protection",
            display_name="Shrine Pilgrim Escort",
            objective_label="Pilgrim",
            objective_max_hp=28,
            objective_move_speed=1.15,
            objective_guide_radius=96,
            objective_damage_cooldown_ms=450,
            notes="Guide the shrine pilgrim through collapsing earth lanes before the cavern seals behind them.",
        ),
        _override_template(
            "escort_bomb_carrier",
            display_name="Powder Cart Push",
            objective_label="Sapper",
            objective_max_hp=32,
            objective_move_speed=0.95,
            objective_guide_radius=88,
            objective_exit_radius=22,
            objective_damage_cooldown_ms=550,
            notes="Protect the sapper pushing unstable powder charges through boulder-strewn corridors.",
        ),
        _override_template(
            "survival_holdout",
            display_name="Shrine Ring Stand",
            objective_label="Shrine",
            holdout_zone_radius=88,
            scripted_wave_sizes="1,2,2",
            holdout_relief_count=1,
            holdout_relief_delay_ms=1400,
            notes="Hold the shrine ring while stabilizers buy breathing room against the cave-in pressure.",
        ),
        _override_template(
            "resource_race",
            display_name="Heartstone Claim",
            objective_variant="heartstone_shard",
            objective_duration_ms=6800,
            scripted_wave_sizes="1,2,2",
            notes="Reach the heartstone before rival claimants lock the quarry down around it.",
        ),
        _override_template(
            "trap_gauntlet",
            display_name="Boulder Sweep Run",
            objective_variant="sweeper_lanes",
            notes="Thread through moving stone sweepers, or risk the challenge lane for a better cache.",
        ),
        _override_template(
            "stealth_passage",
            display_name="Quicksand Ward Path",
            objective_label="Shrine",
            objective_layout_offsets="-5,-2;5,-2;0,4",
            objective_radius=38,
            objective_duration_ms=2400,
            notes="Slip between buried shrine wards before the quicksand search phase escalates into a cave lockdown.",
        ),
        _override_template(
            "puzzle_gated_doors",
            display_name="Rune Lock Gallery",
            objective_variant="ordered_plates",
            objective_label="Rune",
            puzzle_reinforcement_count=1,
            puzzle_stall_duration_ms=3000,
            notes="Follow the numbered rune order while the room punishes resets.",
        ),
        _override_template(
            "ritual_disruption",
            display_name="Spore Totem Grove",
            objective_variant="spore_totem",
            generation_weight=4,
            notes="Destroy spore totems while fungal pulse rings punish camping.",
        ),
        _override_template(
            "timed_extraction",
            display_name="Mire Cache Extraction",
            objective_variant="mire_cache",
            scripted_wave_sizes="1,2,2",
            notes="Secure the mire cache, then push out before the marsh closes in.",
        ),
    ),
    "frozen_depths": (
        _override_template(
            "escort_protection",
            display_name="Icebound Archivist Escort",
            objective_label="Archivist",
            objective_max_hp=24,
            objective_move_speed=1.3,
            objective_guide_radius=100,
            objective_exit_radius=22,
            objective_damage_cooldown_ms=450,
            notes="Keep the archivist moving across brittle ice lanes before whiteout hunters close in.",
        ),
        _override_template(
            "escort_bomb_carrier",
            display_name="Frost Charge Run",
            objective_label="Saboteur",
            objective_max_hp=28,
            objective_move_speed=1.05,
            objective_guide_radius=100,
            objective_exit_radius=22,
            objective_damage_cooldown_ms=500,
            notes="Cover the saboteur carrying frost charges through exposed ice corridors.",
        ),
        _override_template(
            "survival_holdout",
            display_name="Crystal Beacon Hold",
            objective_label="Beacon",
            holdout_zone_radius=104,
            scripted_wave_sizes="1,2,2",
            holdout_relief_count=2,
            holdout_relief_delay_ms=1200,
            notes="Hold the crystal beacon while stabilizers cut through whiteout pressure for a moment.",
        ),
        _override_template(
            "resource_race",
            display_name="Glacier Core Claim",
            objective_variant="glacier_core",
            objective_duration_ms=7200,
            scripted_wave_sizes="1,1,2",
            notes="Secure the glacier core before icebound claimants and frost wards seal the chamber.",
        ),
        _override_template(
            "trap_gauntlet",
            display_name="Frost Vent Gauntlet",
            objective_variant="vent_lanes",
            objective_label="Vent Switch",
            notes="Use the switches to quiet one frost-vent lane, or take the challenge route for better loot.",
        ),
        _override_template(
            "stealth_passage",
            display_name="Whiteout Watch",
            objective_label="Crystal",
            objective_layout_offsets="-5,-1;5,-1;0,5",
            objective_radius=40,
            objective_duration_ms=2600,
            notes="Cross the whiteout under crystal watchposts before the search phase hardens into lockdown.",
        ),
        _override_template(
            "puzzle_gated_doors",
            display_name="Mirror Rune Gallery",
            objective_variant="paired_runes",
            objective_label="Rune",
            objective_entity_count=4,
            puzzle_reinforcement_count=2,
            puzzle_stall_duration_ms=1800,
            notes="Match rune pairs in the right sequence while the room telegraphs the next symbol.",
        ),
        _override_template(
            "ritual_disruption",
            display_name="Frost Obelisk Break",
            objective_variant="frost_obelisk",
            ritual_link_mode="pulse_gates_damage",
            generation_weight=4,
            notes="Shatter frost obelisks during their pulse windows while cold bursts punish stationary play.",
        ),
        _override_template(
            "timed_extraction",
            display_name="Reliquary Extraction",
            objective_variant="glacier_reliquary",
            scripted_wave_sizes="1,2,3",
            notes="Claim the reliquary and escape before reinforcements lock the ice lanes.",
        ),
    ),
    "sunken_ruins": (
        _override_template(
            "escort_protection",
            display_name="River Guide Escort",
            objective_label="Guide",
            objective_max_hp=27,
            objective_move_speed=1.25,
            objective_guide_radius=104,
            objective_exit_radius=24,
            objective_damage_cooldown_ms=450,
            notes="Protect the river guide while they lead you through flooded channels and shifting currents.",
        ),
        _override_template(
            "escort_bomb_carrier",
            display_name="Flood Charge Run",
            objective_label="Diver",
            objective_max_hp=29,
            objective_move_speed=1.0,
            objective_guide_radius=102,
            objective_exit_radius=24,
            objective_damage_cooldown_ms=500,
            notes="Escort the diver carrying flood charges past submerged ambush lanes.",
        ),
        _override_template(
            "survival_holdout",
            display_name="Tide Beacon Hold",
            objective_label="Beacon",
            holdout_zone_radius=100,
            scripted_wave_sizes="1,2,3",
            holdout_relief_count=2,
            holdout_relief_delay_ms=1300,
            notes="Hold the tide beacon while stabilizers blunt the next flood surge for a moment.",
        ),
        _override_template(
            "resource_race",
            display_name="Pearl Claim",
            objective_variant="tide_pearl",
            objective_duration_ms=6600,
            scripted_wave_sizes="1,2,3",
            notes="Secure the tide pearl before the chamber fills with rival divers and flood pressure.",
        ),
        _override_template(
            "trap_gauntlet",
            display_name="Floodgate Hazard Run",
            objective_variant="mixed_lanes",
            notes="Use the entry and checkpoint switches to reroute through a mixed floodgate gauntlet of sweepers, vents, and crushers, then commit to the challenge lane for the vault cache.",
        ),
        _override_template(
            "stealth_passage",
            display_name="Tide Watch Passage",
            objective_label="Watcher",
            objective_layout_offsets="-4,-3;4,-3;0,3",
            objective_radius=36,
            objective_duration_ms=2100,
            notes="Slip past tide watchers before the search phase gives way to a flooded lockdown.",
        ),
        _override_template(
            "puzzle_gated_doors",
            display_name="Tidal Counter-Seals",
            objective_variant="staggered_plates",
            objective_label="Glyph",
            objective_entity_count=4,
            puzzle_reinforcement_count=2,
            puzzle_stall_duration_ms=2200,
            notes="Follow the staggered tidal glyph order while waves punish resets and lingering on the wrong marker.",
        ),
        _override_template(
            "ritual_disruption",
            display_name="Tidal Idol Collapse",
            objective_variant="tidal_idol",
            generation_weight=4,
            notes="Break tidal idols while wave pulses pressure the player out of the center.",
        ),
        _override_template(
            "timed_extraction",
            display_name="Sarcophagus Extraction",
            objective_variant="sunken_sarcophagus",
            scripted_wave_sizes="1,2,3",
            notes="Secure the sarcophagus and escape before the chamber floods with enemies.",
        ),
    ),
}


def _room_template_table_sql(table_name):
    return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
    room_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    objective_kind TEXT NOT NULL,
    combat_pressure TEXT NOT NULL,
    decision_complexity TEXT NOT NULL,
    topology_role TEXT NOT NULL,
    min_depth INTEGER NOT NULL DEFAULT 0,
    max_depth INTEGER,
    branch_preference TEXT NOT NULL DEFAULT 'either',
    generation_weight INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    implementation_status TEXT NOT NULL DEFAULT 'planned',
    objective_variant TEXT NOT NULL DEFAULT '',
    path_stage_min INTEGER NOT NULL DEFAULT 0,
    path_stage_max INTEGER NOT NULL DEFAULT 4,
    terminal_preference TEXT NOT NULL DEFAULT 'any',
    repeat_cooldown INTEGER NOT NULL DEFAULT 0,
    reward_affinity TEXT NOT NULL DEFAULT 'any',
    objective_rule TEXT NOT NULL DEFAULT 'immediate',
    objective_duration_ms INTEGER,
    enemy_minimum_bonus INTEGER NOT NULL DEFAULT 0,
    enemy_scale_factor REAL NOT NULL DEFAULT 1.0,
    guaranteed_chest INTEGER NOT NULL DEFAULT 0,
    chest_spawn_chance REAL,
    terrain_patch_count_range TEXT NOT NULL DEFAULT '',
    terrain_patch_size_range TEXT NOT NULL DEFAULT '',
    clear_center INTEGER NOT NULL DEFAULT 0,
    terminal_chest_lock INTEGER NOT NULL DEFAULT 0,
    objective_entity_count INTEGER NOT NULL DEFAULT 0,
    scripted_wave_sizes TEXT NOT NULL DEFAULT '',
    holdout_zone_radius INTEGER NOT NULL DEFAULT 0,
    holdout_relief_count INTEGER NOT NULL DEFAULT 0,
    holdout_relief_delay_ms INTEGER NOT NULL DEFAULT 0,
    ritual_role_script TEXT NOT NULL DEFAULT '',
    ritual_reinforcement_count INTEGER NOT NULL DEFAULT 0,
    ritual_link_mode TEXT NOT NULL DEFAULT '',
    ritual_payoff_kind TEXT NOT NULL DEFAULT '',
    ritual_payoff_label TEXT NOT NULL DEFAULT '',
    objective_label TEXT NOT NULL DEFAULT '',
    objective_layout_offsets TEXT NOT NULL DEFAULT '',
    objective_spawn_offset TEXT NOT NULL DEFAULT '',
    objective_radius INTEGER NOT NULL DEFAULT 0,
    objective_trigger_padding INTEGER NOT NULL DEFAULT 0,
    objective_max_hp INTEGER NOT NULL DEFAULT 0,
    objective_move_speed REAL NOT NULL DEFAULT 0.0,
    objective_guide_radius INTEGER NOT NULL DEFAULT 0,
    objective_exit_radius INTEGER NOT NULL DEFAULT 0,
    objective_damage_cooldown_ms INTEGER NOT NULL DEFAULT 0,
    puzzle_reinforcement_count INTEGER NOT NULL DEFAULT 0,
    puzzle_stall_duration_ms INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT ''
);
"""


_SCHEMA = "\n".join(
    [
        _room_template_table_sql(BASE_ROOM_TEMPLATE_TABLE),
        *[
            _room_template_table_sql(table_name)
            for table_name in DUNGEON_ROOM_TEMPLATE_TABLES.values()
        ],
    ]
)


def _get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    _ensure_schema_columns(conn)
    return conn


def ensure_room_content_db():
    """Create the room-content database and seed shared templates."""
    conn = _get_conn()
    try:
        _seed_base_room_templates(conn)
        _seed_dungeon_room_templates(conn)
        conn.commit()
    finally:
        conn.close()


def get_dungeon_room_template_table(dungeon_id):
    """Return the dungeon-specific room-template table name for a dungeon."""
    return DUNGEON_ROOM_TEMPLATE_TABLES[dungeon_id]


def load_room_catalog(dungeon_id):
    """Return the merged base and dungeon-specific room catalog."""
    ensure_room_content_db()

    conn = _get_conn()
    try:
        templates = {
            template["room_id"]: template
            for template in _fetch_room_templates(conn, BASE_ROOM_TEMPLATE_TABLE)
        }
        for template in _fetch_room_templates(
            conn, get_dungeon_room_template_table(dungeon_id)
        ):
            templates[template["room_id"]] = template
        return tuple(templates[key] for key in sorted(templates))
    finally:
        conn.close()


def _fetch_room_templates(conn, table_name):
    rows = conn.execute(
        f"SELECT {', '.join(ROOM_TEMPLATE_COLUMNS)} FROM {table_name} ORDER BY room_id"
    ).fetchall()
    return tuple(dict(row) for row in rows)


def _seed_base_room_templates(conn):
    column_list = ", ".join(ROOM_TEMPLATE_COLUMNS)
    placeholders = ", ".join("?" for _ in ROOM_TEMPLATE_COLUMNS)
    update_clause = ", ".join(
        f"{column}=excluded.{column}" for column in ROOM_TEMPLATE_COLUMNS[1:]
    )

    for template in BASE_ROOM_TEMPLATES:
        values = tuple(template[column] for column in ROOM_TEMPLATE_COLUMNS)
        conn.execute(
            f"INSERT INTO {BASE_ROOM_TEMPLATE_TABLE} ({column_list}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(room_id) DO UPDATE SET {update_clause}",
            values,
        )


def _seed_dungeon_room_templates(conn):
    column_list = ", ".join(ROOM_TEMPLATE_COLUMNS)
    placeholders = ", ".join("?" for _ in ROOM_TEMPLATE_COLUMNS)
    update_clause = ", ".join(
        f"{column}=excluded.{column}" for column in ROOM_TEMPLATE_COLUMNS[1:]
    )

    for dungeon_id, templates in DUNGEON_ROOM_TEMPLATE_OVERRIDES.items():
        table_name = get_dungeon_room_template_table(dungeon_id)
        for template in templates:
            values = tuple(template[column] for column in ROOM_TEMPLATE_COLUMNS)
            conn.execute(
                f"INSERT INTO {table_name} ({column_list}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT(room_id) DO UPDATE SET {update_clause}",
                values,
            )


def _ensure_schema_columns(conn):
    missing_column_defaults = {
        "objective_variant": "TEXT NOT NULL DEFAULT ''",
        "path_stage_min": "INTEGER NOT NULL DEFAULT 0",
        "path_stage_max": "INTEGER NOT NULL DEFAULT 4",
        "terminal_preference": "TEXT NOT NULL DEFAULT 'any'",
        "repeat_cooldown": "INTEGER NOT NULL DEFAULT 0",
        "reward_affinity": "TEXT NOT NULL DEFAULT 'any'",
        "objective_rule": "TEXT NOT NULL DEFAULT 'immediate'",
        "objective_duration_ms": "INTEGER",
        "enemy_minimum_bonus": "INTEGER NOT NULL DEFAULT 0",
        "enemy_scale_factor": "REAL NOT NULL DEFAULT 1.0",
        "guaranteed_chest": "INTEGER NOT NULL DEFAULT 0",
        "chest_spawn_chance": "REAL",
        "terrain_patch_count_range": "TEXT NOT NULL DEFAULT ''",
        "terrain_patch_size_range": "TEXT NOT NULL DEFAULT ''",
        "clear_center": "INTEGER NOT NULL DEFAULT 0",
        "terminal_chest_lock": "INTEGER NOT NULL DEFAULT 0",
        "objective_entity_count": "INTEGER NOT NULL DEFAULT 0",
        "scripted_wave_sizes": "TEXT NOT NULL DEFAULT ''",
        "holdout_zone_radius": "INTEGER NOT NULL DEFAULT 0",
        "holdout_relief_count": "INTEGER NOT NULL DEFAULT 0",
        "holdout_relief_delay_ms": "INTEGER NOT NULL DEFAULT 0",
        "ritual_role_script": "TEXT NOT NULL DEFAULT ''",
        "ritual_reinforcement_count": "INTEGER NOT NULL DEFAULT 0",
        "ritual_link_mode": "TEXT NOT NULL DEFAULT ''",
        "ritual_payoff_kind": "TEXT NOT NULL DEFAULT ''",
        "ritual_payoff_label": "TEXT NOT NULL DEFAULT ''",
        "objective_label": "TEXT NOT NULL DEFAULT ''",
        "objective_layout_offsets": "TEXT NOT NULL DEFAULT ''",
        "objective_spawn_offset": "TEXT NOT NULL DEFAULT ''",
        "objective_radius": "INTEGER NOT NULL DEFAULT 0",
        "objective_trigger_padding": "INTEGER NOT NULL DEFAULT 0",
        "objective_max_hp": "INTEGER NOT NULL DEFAULT 0",
        "objective_move_speed": "REAL NOT NULL DEFAULT 0.0",
        "objective_guide_radius": "INTEGER NOT NULL DEFAULT 0",
        "objective_exit_radius": "INTEGER NOT NULL DEFAULT 0",
        "objective_damage_cooldown_ms": "INTEGER NOT NULL DEFAULT 0",
        "puzzle_reinforcement_count": "INTEGER NOT NULL DEFAULT 0",
        "puzzle_stall_duration_ms": "INTEGER NOT NULL DEFAULT 0",
    }
    for table_name in (BASE_ROOM_TEMPLATE_TABLE, *DUNGEON_ROOM_TEMPLATE_TABLES.values()):
        existing = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_def in missing_column_defaults.items():
            if column_name in existing:
                continue
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
            )