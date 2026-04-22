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
                self.assertEqual(count, 2)

            rows = conn.execute(
                f"SELECT room_id, enabled, implementation_status, objective_variant, "
                f"path_stage_min, path_stage_max, terminal_preference, repeat_cooldown, reward_affinity, "
                f"objective_rule, scripted_wave_sizes, holdout_zone_radius, objective_entity_count, "
                f"ritual_role_script, ritual_reinforcement_count, ritual_link_mode, ritual_payoff_kind, ritual_payoff_label, objective_label, objective_layout_offsets, "
                f"objective_spawn_offset, objective_radius, objective_trigger_padding, objective_max_hp, "
                f"objective_move_speed, objective_guide_radius, objective_exit_radius, objective_damage_cooldown_ms "
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
                ritual_role_script,
                ritual_reinforcement_count,
                ritual_link_mode,
                ritual_payoff_kind,
                ritual_payoff_label,
                objective_label,
                objective_layout_offsets,
                objective_spawn_offset,
                objective_radius,
                objective_trigger_padding,
                objective_max_hp,
                objective_move_speed,
                objective_guide_radius,
                objective_exit_radius,
                objective_damage_cooldown_ms,
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
                ritual_role_script,
                ritual_reinforcement_count,
                ritual_link_mode,
                ritual_payoff_kind,
                ritual_payoff_label,
                objective_label,
                objective_layout_offsets,
                objective_spawn_offset,
                objective_radius,
                objective_trigger_padding,
                objective_max_hp,
                objective_move_speed,
                objective_guide_radius,
                objective_exit_radius,
                objective_damage_cooldown_ms,
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
        })
        self.assertEqual(seeded_templates["standard_combat"], (1, "implemented", "", 0, 1, "avoid", 0, "any", "immediate", "", 0, 0, "", 0, "", "", "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0))
        self.assertEqual(seeded_templates["survival_holdout"], (1, "prototype", "", 4, 4, "prefer", 2, "finale", "holdout_timer", "1,2,3", 96, 0, "", 0, "", "", "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0))
        self.assertEqual(seeded_templates["ritual_disruption"], (1, "prototype", "altar_anchor", 2, 4, "any", 1, "any", "destroy_altars", "", 0, 3, "summon,pulse,ward", 2, "ward_shields_others", "reveal_reliquary", "Reliquary", "", "", "", 0, 0, 0, 0.0, 0, 0, 0))
        self.assertEqual(seeded_templates["trap_gauntlet"], (1, "prototype", "", 0, 4, "any", 1, "branch", "immediate", "", 0, 0, "", 0, "", "", "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0))
        self.assertEqual(seeded_templates["timed_extraction"], (1, "prototype", "relic_cache", 2, 4, "any", 1, "any", "loot_then_timer", "", 0, 0, "", 0, "", "", "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0))
        self.assertEqual(seeded_templates["escort_protection"], (1, "prototype", "", 2, 4, "any", 1, "finale", "escort_to_exit", "", 0, 0, "", 0, "", "", "", "Escort", "", "-6,0", 0, 0, 22, 1.2, 92, 24, 500))
        self.assertEqual(seeded_templates["escort_bomb_carrier"], (1, "prototype", "", 3, 4, "any", 1, "finale", "escort_bomb_to_exit", "", 0, 0, "", 0, "", "", "", "Carrier", "", "-6,0", 0, 0, 26, 1.0, 92, 24, 500))
        self.assertEqual(seeded_templates["puzzle_gated_doors"], (1, "prototype", "", 1, 3, "avoid", 1, "any", "charge_plates", "", 0, 3, "", 0, "", "", "", "Seal", "-5,-3;5,-3;0,4", "", 0, 10, 0, 0.0, 0, 0, 0))
        self.assertEqual(seeded_templates["resource_race"], (1, "prototype", "relic_cache", 2, 4, "any", 1, "any", "claim_relic_before_lockdown", "", 0, 0, "", 0, "", "", "", "", "", "", 0, 0, 0, 0.0, 0, 0, 0))
        self.assertEqual(seeded_templates["stealth_passage"], (1, "prototype", "", 0, 2, "avoid", 1, "branch", "avoid_alarm_zones", "", 0, 3, "", 0, "", "", "", "Alarm", "-4,-2;4,-2;0,4", "", 34, 0, 0, 0.0, 0, 0, 0))

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
        self.assertEqual(ritual["objective_variant"], "spore_totem")
        self.assertEqual(relic["objective_variant"], "mire_cache")

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
        self.assertIn("ritual_role_script", columns)
        self.assertIn("ritual_reinforcement_count", columns)
        self.assertIn("ritual_link_mode", columns)
        self.assertIn("ritual_payoff_kind", columns)
        self.assertIn("ritual_payoff_label", columns)
        self.assertIn("objective_label", columns)
        self.assertIn("objective_layout_offsets", columns)
        self.assertIn("objective_spawn_offset", columns)
        self.assertIn("objective_radius", columns)
        self.assertIn("objective_trigger_padding", columns)
        self.assertIn("objective_max_hp", columns)
        self.assertIn("objective_move_speed", columns)
        self.assertIn("objective_guide_radius", columns)
        self.assertIn("objective_exit_radius", columns)
        self.assertIn("objective_damage_cooldown_ms", columns)


if __name__ == "__main__":
    unittest.main()