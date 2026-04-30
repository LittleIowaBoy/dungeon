import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import content_db


class RoomContentBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "room_content.db")
        self.db_patch = patch.object(content_db, "_DB_PATH", self.db_path)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_bootstrap_creates_seeded_base_table_and_empty_dungeon_placeholders(self):
        content_db.ensure_room_content_db()

        conn = sqlite3.connect(self.db_path)
        try:
            table_names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }

            self.assertIn(content_db.BASE_ROOM_TEMPLATE_TABLE, table_names)
            for table_name in content_db.DUNGEON_ROOM_TEMPLATE_TABLES.values():
                self.assertIn(table_name, table_names)
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                dungeon_id = next(
                    dungeon_id
                    for dungeon_id, candidate in content_db.DUNGEON_ROOM_TEMPLATE_TABLES.items()
                    if candidate == table_name
                )
                self.assertEqual(count, len(content_db.DUNGEON_ROOM_TEMPLATE_OVERRIDES[dungeon_id]))

            rows = conn.execute(
                f"SELECT room_id, enabled, implementation_status, objective_variant, "
                f"path_stage_min, path_stage_max, terminal_preference, repeat_cooldown, reward_affinity, "
                f"objective_rule, scripted_wave_sizes, holdout_zone_radius, objective_entity_count, "
                f"holdout_relief_count, holdout_relief_delay_ms, ritual_role_script, ritual_reinforcement_count, ritual_link_mode, ritual_payoff_kind, ritual_payoff_label, ritual_wrong_strike_spawn_count, objective_label, objective_layout_offsets, "
                f"objective_spawn_offset, objective_patrol_offset, objective_radius, objective_trigger_padding, objective_max_hp, "
                f"objective_move_speed, objective_guide_radius, objective_exit_radius, objective_damage_cooldown_ms, "
                f"puzzle_reinforcement_count, puzzle_stall_duration_ms "
                f"FROM {content_db.BASE_ROOM_TEMPLATE_TABLE}"
            ).fetchall()
        finally:
            conn.close()

        seeded_templates = {
            room_id: (
                enabled,
                status,
                objective_variant,
                path_stage_min,
                path_stage_max,
                terminal_preference,
                repeat_cooldown,
                reward_affinity,
                objective_rule,
                scripted_wave_sizes,
                holdout_zone_radius,
                objective_entity_count,
                holdout_relief_count,
                holdout_relief_delay_ms,
                ritual_role_script,
                ritual_reinforcement_count,
                ritual_link_mode,
                ritual_payoff_kind,
                ritual_payoff_label,
                ritual_wrong_strike_spawn_count,
                objective_label,
                objective_layout_offsets,
                objective_spawn_offset,
                objective_patrol_offset,
                objective_radius,
                objective_trigger_padding,
                objective_max_hp,
                objective_move_speed,
                objective_guide_radius,
                objective_exit_radius,
                objective_damage_cooldown_ms,
                puzzle_reinforcement_count,
                puzzle_stall_duration_ms,
            )
            for (
                room_id,
                enabled,
                status,
                objective_variant,
                path_stage_min,
                path_stage_max,
                terminal_preference,
                repeat_cooldown,
                reward_affinity,
                objective_rule,
                scripted_wave_sizes,
                holdout_zone_radius,
                objective_entity_count,
                holdout_relief_count,
                holdout_relief_delay_ms,
                ritual_role_script,
                ritual_reinforcement_count,
                ritual_link_mode,
                ritual_payoff_kind,
                ritual_payoff_label,
                ritual_wrong_strike_spawn_count,
                objective_label,
                objective_layout_offsets,
                objective_spawn_offset,
                objective_patrol_offset,
                objective_radius,
                objective_trigger_padding,
                objective_max_hp,
                objective_move_speed,
                objective_guide_radius,
                objective_exit_radius,
                objective_damage_cooldown_ms,
                puzzle_reinforcement_count,
                puzzle_stall_duration_ms,
            ) in rows
        }
        self.assertEqual(set(seeded_templates), {
            "standard_combat",
            "escort_protection",
            "escort_bomb_carrier",
            "puzzle_gated_doors",
            "survival_holdout",
            "ritual_disruption",
            "resource_race",
            "trap_gauntlet",
            "stealth_passage",
            "timed_extraction",
            "rune_altar_chamber",
            "earth_stalagmite_field",
            "earth_quicksand_trap",
            "earth_crystal_vein",
            "earth_tremor_chamber",
            "earth_mushroom_grove",
            "earth_cave_in",
            "earth_mining_carts",
            "earth_burrower_den",
            "earth_echo_cavern",
            "earth_boulder_run",
            "earth_shrine_circle",
            "earth_golem_arena",
            "water_river_room",
            "water_waterfall_room",
            "water_spirit_room",
            "water_tide_lord_arena",
        })
        self.assertEqual(seeded_templates["standard_combat"], (1, "implemented", "", 0, 1, "avoid", 0, "any", "immediate", "", 0, 0, 0, 0, "", 0, "", "", "", 0, "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0, 0, 0))
        self.assertEqual(seeded_templates["survival_holdout"], (1, "prototype", "", 4, 4, "prefer", 2, "finale", "holdout_timer", "1,2,3", 96, 0, 1, 1500, "", 0, "", "", "", 0, "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0, 0, 0))
        self.assertEqual(seeded_templates["ritual_disruption"], (1, "prototype", "altar_anchor", 2, 4, "any", 1, "any", "destroy_altars", "", 0, 3, 0, 0, "summon,pulse,ward", 2, "ward_shields_others", "reveal_reliquary", "Reliquary", 0, "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0, 0, 0))
        self.assertEqual(seeded_templates["trap_gauntlet"], (1, "prototype", "crusher_corridors", 0, 4, "any", 1, "branch", "immediate", "", 0, 3, 0, 0, "", 0, "", "", "", 0, "Lane Switch", "", "", "", 0, 18, 0, 0.0, 0, 0, 0, 0, 0))
        self.assertEqual(seeded_templates["timed_extraction"], (1, "prototype", "relic_cache", 2, 4, "any", 1, "any", "loot_then_timer", "1,2", 0, 0, 0, 0, "", 0, "", "", "", 0, "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0, 0, 0))
        self.assertEqual(seeded_templates["escort_protection"], (1, "prototype", "", 2, 4, "any", 1, "finale", "escort_to_exit", "", 0, 0, 0, 0, "", 0, "", "", "", 0, "Escort", "", "-6,0", "", 0, 0, 26, 1.2, 92, 24, 500, 0, 0))
        self.assertEqual(seeded_templates["escort_bomb_carrier"], (1, "prototype", "", 3, 4, "any", 1, "finale", "escort_bomb_to_exit", "", 0, 0, 0, 0, "", 0, "", "", "", 0, "Carrier", "", "-6,0", "", 0, 0, 30, 1.0, 92, 24, 500, 0, 0))
        self.assertEqual(seeded_templates["puzzle_gated_doors"], (1, "prototype", "ordered_plates", 1, 3, "avoid", 1, "any", "charge_plates", "", 0, 3, 0, 0, "", 0, "", "", "", 0, "Seal", "-5,-3;5,-3;0,4", "", "", 0, 10, 0, 0.0, 0, 0, 0, 1, 2500))
        self.assertEqual(seeded_templates["resource_race"], (1, "prototype", "relic_cache", 2, 4, "any", 1, "any", "claim_relic_before_lockdown", "1,2", 0, 0, 0, 0, "", 0, "", "", "", 0, "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0, 0, 0))
        self.assertEqual(seeded_templates["stealth_passage"], (1, "prototype", "", 0, 2, "avoid", 1, "branch", "avoid_alarm_zones", "", 0, 3, 0, 0, "", 0, "", "", "", 0, "Alarm", "-4,-2;4,-2;0,4", "", "0,2", 34, 0, 0, 0.0, 0, 0, 0, 0, 0))

    def test_bootstrap_is_idempotent_and_load_room_catalog_merges_base_with_placeholder(self):
        content_db.ensure_room_content_db()
        content_db.ensure_room_content_db()

        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {content_db.BASE_ROOM_TEMPLATE_TABLE}"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(count, len(content_db.BASE_ROOM_TEMPLATES))

        catalog = content_db.load_room_catalog("mud_caverns")
        self.assertEqual(len(catalog), len(content_db.BASE_ROOM_TEMPLATES))
        self.assertEqual(
            {template["room_id"] for template in catalog},
            {template["room_id"] for template in content_db.BASE_ROOM_TEMPLATES},
        )

        ritual = next(template for template in catalog if template["room_id"] == "ritual_disruption")
        relic = next(template for template in catalog if template["room_id"] == "timed_extraction")
        race = next(template for template in catalog if template["room_id"] == "resource_race")
        stealth = next(template for template in catalog if template["room_id"] == "stealth_passage")
        escort = next(template for template in catalog if template["room_id"] == "escort_protection")
        trap = next(template for template in catalog if template["room_id"] == "trap_gauntlet")
        puzzle = next(template for template in catalog if template["room_id"] == "puzzle_gated_doors")
        holdout = next(template for template in catalog if template["room_id"] == "survival_holdout")
        self.assertEqual(ritual["objective_variant"], "spore_totem")
        self.assertEqual(ritual["ritual_link_mode"], "role_chain")
        self.assertIn("script order", ritual["notes"])
        self.assertEqual(relic["objective_variant"], "mire_cache")
        self.assertEqual(relic["scripted_wave_sizes"], "1,2,2")
        self.assertEqual(race["display_name"], "Heartstone Claim")
        self.assertEqual(race["objective_variant"], "heartstone_shard")
        self.assertEqual(race["scripted_wave_sizes"], "1,2,2")
        self.assertEqual(stealth["display_name"], "Quicksand Ward Path")
        self.assertEqual(stealth["objective_label"], "Shrine")
        self.assertEqual(stealth["objective_variant"], "release_on_alarm")
        self.assertEqual(stealth["objective_duration_ms"], 2400)
        self.assertEqual(stealth["objective_patrol_offset"], "0,2")
        self.assertEqual(escort["display_name"], "Shrine Pilgrim Escort")
        self.assertEqual(escort["objective_label"], "Pilgrim")
        self.assertEqual(holdout["display_name"], "Shrine Ring Stand")
        self.assertEqual(holdout["objective_label"], "Shrine")
        self.assertEqual(trap["display_name"], "Boulder Sweep Run")
        self.assertEqual(trap["objective_variant"], "sweeper_lanes")
        self.assertEqual(trap["trap_intensity_scale"], 1.4)
        self.assertEqual(trap["trap_speed_scale"], 0.85)
        self.assertEqual(trap["trap_challenge_reward_kind"], "stat_shard")
        self.assertEqual(trap["trap_intensity_scale"], 1.4)
        self.assertEqual(puzzle["display_name"], "Rune Lock Gallery")
        self.assertEqual(puzzle["objective_variant"], "ordered_plates")
        self.assertEqual(puzzle["puzzle_reinforcement_count"], 1)
        self.assertEqual(puzzle["puzzle_stall_duration_ms"], 3000)
        self.assertEqual(puzzle["puzzle_stabilizer_count"], 1)
        self.assertEqual(puzzle["puzzle_stabilizer_hp"], 10)
        self.assertEqual(puzzle["puzzle_camp_pulse_damage"], 1)
        self.assertEqual(puzzle["puzzle_camp_pulse_interval_ms"], 1100)
        self.assertIn("cave-in dust", puzzle["notes"])

        frozen_catalog = content_db.load_room_catalog("frozen_depths")
        frozen_race = next(template for template in frozen_catalog if template["room_id"] == "resource_race")
        frozen_stealth = next(template for template in frozen_catalog if template["room_id"] == "stealth_passage")
        frozen_escort = next(template for template in frozen_catalog if template["room_id"] == "escort_bomb_carrier")
        frozen_holdout = next(template for template in frozen_catalog if template["room_id"] == "survival_holdout")
        frozen_trap = next(template for template in frozen_catalog if template["room_id"] == "trap_gauntlet")
        frozen_puzzle = next(template for template in frozen_catalog if template["room_id"] == "puzzle_gated_doors")
        frozen_ritual = next(template for template in frozen_catalog if template["room_id"] == "ritual_disruption")
        frozen_relic = next(template for template in frozen_catalog if template["room_id"] == "timed_extraction")
        self.assertEqual(frozen_trap["display_name"], "Frost Vent Gauntlet")
        self.assertEqual(frozen_trap["objective_variant"], "vent_lanes")
        self.assertEqual(frozen_trap["trap_intensity_scale"], 0.8)
        self.assertEqual(frozen_trap["trap_speed_scale"], 1.25)
        self.assertEqual(frozen_trap["trap_challenge_reward_kind"], "tempo_rune")
        self.assertEqual(frozen_trap["trap_intensity_scale"], 0.8)
        self.assertEqual(frozen_puzzle["display_name"], "Mirror Rune Gallery")
        self.assertEqual(frozen_puzzle["objective_variant"], "paired_runes")
        self.assertEqual(frozen_puzzle["puzzle_reinforcement_count"], 2)
        self.assertEqual(frozen_puzzle["puzzle_stall_duration_ms"], 1800)
        self.assertEqual(frozen_puzzle["puzzle_stabilizer_count"], 1)
        self.assertEqual(frozen_puzzle["puzzle_stabilizer_hp"], 12)
        self.assertEqual(frozen_puzzle["puzzle_camp_pulse_damage"], 1)
        self.assertEqual(frozen_puzzle["puzzle_camp_pulse_interval_ms"], 1200)
        self.assertIn("shatter the optional stabilizer", frozen_puzzle["notes"])
        self.assertIn("frostbite", frozen_puzzle["notes"])
        self.assertEqual(frozen_ritual["ritual_link_mode"], "pulse_gates_damage")
        self.assertEqual(frozen_race["objective_variant"], "glacier_core")
        self.assertEqual(frozen_race["scripted_wave_sizes"], "1,1,2")
        self.assertEqual(frozen_stealth["display_name"], "Whiteout Watch")
        self.assertEqual(frozen_stealth["objective_variant"], "escape_on_alarm")
        self.assertEqual(frozen_stealth["objective_duration_ms"], 2600)
        self.assertEqual(frozen_stealth["objective_patrol_offset"], "2,0")
        self.assertEqual(frozen_escort["display_name"], "Frost Charge Run")
        self.assertEqual(frozen_holdout["holdout_relief_count"], 2)
        self.assertEqual(frozen_relic["scripted_wave_sizes"], "1,2,3")

        sunken_catalog = content_db.load_room_catalog("sunken_ruins")
        sunken_race = next(template for template in sunken_catalog if template["room_id"] == "resource_race")
        sunken_stealth = next(template for template in sunken_catalog if template["room_id"] == "stealth_passage")
        sunken_escort = next(template for template in sunken_catalog if template["room_id"] == "escort_protection")
        sunken_holdout = next(template for template in sunken_catalog if template["room_id"] == "survival_holdout")
        sunken_trap = next(template for template in sunken_catalog if template["room_id"] == "trap_gauntlet")
        sunken_puzzle = next(template for template in sunken_catalog if template["room_id"] == "puzzle_gated_doors")
        sunken_relic = next(template for template in sunken_catalog if template["room_id"] == "timed_extraction")
        self.assertEqual(sunken_race["objective_variant"], "tide_pearl")
        self.assertEqual(sunken_race["scripted_wave_sizes"], "1,2,3")
        self.assertEqual(sunken_stealth["objective_label"], "Watcher")
        self.assertEqual(sunken_stealth["objective_variant"], "escape_on_alarm")
        self.assertEqual(sunken_stealth["objective_patrol_offset"], "1,-2")
        self.assertEqual(sunken_escort["display_name"], "River Guide Escort")
        self.assertEqual(sunken_holdout["objective_label"], "Beacon")
        self.assertEqual(sunken_trap["display_name"], "Floodgate Hazard Run")
        self.assertEqual(sunken_trap["objective_variant"], "mixed_lanes")
        self.assertEqual(sunken_trap["trap_intensity_scale"], 1.15)
        self.assertEqual(sunken_trap["trap_challenge_reward_kind"], "mobility_consumable")
        self.assertIn("checkpoint switches", sunken_trap["notes"])
        self.assertEqual(sunken_puzzle["display_name"], "Tidal Counter-Seals")
        self.assertEqual(sunken_puzzle["objective_variant"], "staggered_plates")
        self.assertIn("staggered tidal glyph order", sunken_puzzle["notes"])
        self.assertEqual(sunken_relic["scripted_wave_sizes"], "1,2,3")

    def test_bootstrap_migrates_existing_tables_with_objective_variant_column(self):
        old_table_sql = (
            "("
            "room_id TEXT PRIMARY KEY, "
            "display_name TEXT NOT NULL, "
            "objective_kind TEXT NOT NULL, "
            "combat_pressure TEXT NOT NULL, "
            "decision_complexity TEXT NOT NULL, "
            "topology_role TEXT NOT NULL, "
            "min_depth INTEGER NOT NULL DEFAULT 0, "
            "max_depth INTEGER, "
            "branch_preference TEXT NOT NULL DEFAULT 'either', "
            "generation_weight INTEGER NOT NULL DEFAULT 1, "
            "enabled INTEGER NOT NULL DEFAULT 1, "
            "implementation_status TEXT NOT NULL DEFAULT 'planned', "
            "notes TEXT NOT NULL DEFAULT ''"
            ")"
        )
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(f"CREATE TABLE {content_db.BASE_ROOM_TEMPLATE_TABLE} {old_table_sql}")
            for table_name in content_db.DUNGEON_ROOM_TEMPLATE_TABLES.values():
                conn.execute(f"CREATE TABLE {table_name} {old_table_sql}")
            conn.commit()
        finally:
            conn.close()

        content_db.ensure_room_content_db()

        conn = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1] for row in conn.execute(
                    f"PRAGMA table_info({content_db.BASE_ROOM_TEMPLATE_TABLE})"
                ).fetchall()
            }
        finally:
            conn.close()

        self.assertIn("objective_variant", columns)
        self.assertIn("path_stage_min", columns)
        self.assertIn("path_stage_max", columns)
        self.assertIn("terminal_preference", columns)
        self.assertIn("repeat_cooldown", columns)
        self.assertIn("reward_affinity", columns)
        self.assertIn("objective_rule", columns)
        self.assertIn("objective_duration_ms", columns)
        self.assertIn("enemy_minimum_bonus", columns)
        self.assertIn("enemy_scale_factor", columns)
        self.assertIn("guaranteed_chest", columns)
        self.assertIn("chest_spawn_chance", columns)
        self.assertIn("terrain_patch_count_range", columns)
        self.assertIn("terrain_patch_size_range", columns)
        self.assertIn("clear_center", columns)
        self.assertIn("terminal_chest_lock", columns)
        self.assertIn("objective_entity_count", columns)
        self.assertIn("scripted_wave_sizes", columns)
        self.assertIn("holdout_zone_radius", columns)
        self.assertIn("holdout_relief_count", columns)
        self.assertIn("holdout_relief_delay_ms", columns)
        self.assertIn("ritual_role_script", columns)
        self.assertIn("ritual_reinforcement_count", columns)
        self.assertIn("ritual_link_mode", columns)
        self.assertIn("ritual_payoff_kind", columns)
        self.assertIn("ritual_payoff_label", columns)
        self.assertIn("objective_label", columns)
        self.assertIn("objective_layout_offsets", columns)
        self.assertIn("objective_spawn_offset", columns)
        self.assertIn("objective_patrol_offset", columns)
        self.assertIn("objective_radius", columns)
        self.assertIn("objective_trigger_padding", columns)
        self.assertIn("objective_max_hp", columns)
        self.assertIn("objective_move_speed", columns)
        self.assertIn("objective_guide_radius", columns)
        self.assertIn("objective_exit_radius", columns)
        self.assertIn("objective_damage_cooldown_ms", columns)
        self.assertIn("puzzle_reinforcement_count", columns)
        self.assertIn("puzzle_stall_duration_ms", columns)


if __name__ == "__main__":
    unittest.main()