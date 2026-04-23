import random
import unittest

from room_selector import RoomSelector


_ROOM_PLAN_DEFAULTS = {
    "escort_protection": {
        "objective_rule": "escort_to_exit",
        "enemy_minimum_bonus": 1,
        "enemy_scale_factor": 1.25,
        "terrain_patch_count_range": "1,3",
        "terrain_patch_size_range": "2,3",
        "clear_center": True,
        "terminal_chest_lock": True,
        "objective_label": "Escort",
        "objective_spawn_offset": "-6,0",
        "objective_max_hp": 26,
        "objective_move_speed": 1.2,
        "objective_guide_radius": 92,
        "objective_exit_radius": 24,
        "objective_damage_cooldown_ms": 500,
    },
    "escort_bomb_carrier": {
        "objective_rule": "escort_bomb_to_exit",
        "enemy_minimum_bonus": 1,
        "enemy_scale_factor": 1.0,
        "terrain_patch_count_range": "1,3",
        "terrain_patch_size_range": "2,3",
        "clear_center": True,
        "terminal_chest_lock": True,
        "objective_label": "Carrier",
        "objective_spawn_offset": "-6,0",
        "objective_max_hp": 30,
        "objective_move_speed": 1.0,
        "objective_guide_radius": 92,
        "objective_exit_radius": 24,
        "objective_damage_cooldown_ms": 500,
    },
    "puzzle_gated_doors": {
        "objective_variant": "ordered_plates",
        "objective_rule": "charge_plates",
        "terrain_patch_count_range": "2,4",
        "terrain_patch_size_range": "2,3",
        "clear_center": True,
        "terminal_chest_lock": True,
        "objective_entity_count": 3,
        "objective_label": "Seal",
        "objective_layout_offsets": "-5,-3;5,-3;0,4",
        "objective_trigger_padding": 10,
        "puzzle_reinforcement_count": 1,
        "puzzle_stall_duration_ms": 2500,
    },
    "survival_holdout": {
        "objective_rule": "holdout_timer",
        "objective_duration_ms": 9000,
        "enemy_minimum_bonus": 1,
        "enemy_scale_factor": 1.5,
        "terrain_patch_count_range": "2,4",
        "terrain_patch_size_range": "2,3",
        "clear_center": True,
        "terminal_chest_lock": True,
        "scripted_wave_sizes": "1,2,3",
        "holdout_zone_radius": 96,
        "holdout_relief_count": 1,
        "holdout_relief_delay_ms": 1500,
    },
    "ritual_disruption": {
        "objective_rule": "destroy_altars",
        "enemy_minimum_bonus": 1,
        "enemy_scale_factor": 1.25,
        "terrain_patch_count_range": "2,5",
        "terrain_patch_size_range": "2,4",
        "clear_center": True,
        "terminal_chest_lock": True,
        "objective_entity_count": 3,
        "ritual_role_script": "summon,pulse,ward",
        "ritual_reinforcement_count": 2,
        "ritual_link_mode": "ward_shields_others",
        "ritual_payoff_kind": "reveal_reliquary",
        "ritual_payoff_label": "Reliquary",
    },
    "resource_race": {
        "objective_rule": "claim_relic_before_lockdown",
        "objective_duration_ms": 7000,
        "enemy_minimum_bonus": 1,
        "enemy_scale_factor": 1.25,
        "guaranteed_chest": True,
        "chest_spawn_chance": 1.0,
        "terrain_patch_count_range": "2,4",
        "terrain_patch_size_range": "2,4",
        "clear_center": True,
        "scripted_wave_sizes": "1,2",
    },
    "trap_gauntlet": {
        "objective_variant": "crusher_corridors",
        "objective_rule": "immediate",
        "enemy_scale_factor": 0.0,
        "guaranteed_chest": True,
        "chest_spawn_chance": 1.0,
        "terrain_patch_count_range": "6,9",
        "terrain_patch_size_range": "3,6",
        "clear_center": True,
        "objective_entity_count": 3,
        "objective_label": "Lane Switch",
        "objective_trigger_padding": 18,
    },
    "stealth_passage": {
        "objective_rule": "avoid_alarm_zones",
        "objective_duration_ms": 2200,
        "enemy_scale_factor": 0.0,
        "terrain_patch_count_range": "1,3",
        "terrain_patch_size_range": "2,3",
        "clear_center": True,
        "objective_entity_count": 3,
        "objective_label": "Alarm",
        "objective_layout_offsets": "-4,-2;4,-2;0,4",
        "objective_radius": 34,
    },
    "timed_extraction": {
        "objective_rule": "loot_then_timer",
        "objective_duration_ms": 8000,
        "enemy_minimum_bonus": 1,
        "enemy_scale_factor": 1.0,
        "guaranteed_chest": True,
        "chest_spawn_chance": 1.0,
        "terrain_patch_count_range": "3,5",
        "terrain_patch_size_range": "2,4",
        "clear_center": True,
        "scripted_wave_sizes": "1,2",
    },
}


def _template(
    room_id,
    *,
    topology_role,
    branch_preference="either",
    min_depth=0,
    max_depth=None,
    enabled=1,
    generation_weight=1,
    path_stage_min=0,
    path_stage_max=4,
    terminal_preference="any",
    repeat_cooldown=0,
    reward_affinity="any",
    **plan_overrides,
):
    room_defaults = dict(_ROOM_PLAN_DEFAULTS.get(room_id, {}))
    room_defaults.update(plan_overrides)
    return {
        "room_id": room_id,
        "display_name": room_id.replace("_", " ").title(),
        "objective_kind": room_id,
        "combat_pressure": "mid",
        "decision_complexity": "mid",
        "topology_role": topology_role,
        "min_depth": min_depth,
        "max_depth": max_depth,
        "branch_preference": branch_preference,
        "generation_weight": generation_weight,
        "enabled": enabled,
        "implementation_status": "prototype" if enabled else "planned",
        "objective_variant": room_defaults.get("objective_variant", ""),
        "path_stage_min": path_stage_min,
        "path_stage_max": path_stage_max,
        "terminal_preference": terminal_preference,
        "repeat_cooldown": repeat_cooldown,
        "reward_affinity": reward_affinity,
        "objective_rule": room_defaults.get("objective_rule", "immediate"),
        "objective_duration_ms": room_defaults.get("objective_duration_ms"),
        "enemy_minimum_bonus": room_defaults.get("enemy_minimum_bonus", 0),
        "enemy_scale_factor": room_defaults.get("enemy_scale_factor", 1.0),
        "guaranteed_chest": room_defaults.get("guaranteed_chest", False),
        "chest_spawn_chance": room_defaults.get("chest_spawn_chance"),
        "terrain_patch_count_range": room_defaults.get("terrain_patch_count_range", ""),
        "terrain_patch_size_range": room_defaults.get("terrain_patch_size_range", ""),
        "clear_center": room_defaults.get("clear_center", False),
        "terminal_chest_lock": room_defaults.get("terminal_chest_lock", False),
        "objective_entity_count": room_defaults.get("objective_entity_count", 0),
        "scripted_wave_sizes": room_defaults.get("scripted_wave_sizes", ""),
        "holdout_zone_radius": room_defaults.get("holdout_zone_radius", 0),
        "holdout_relief_count": room_defaults.get("holdout_relief_count", 0),
        "holdout_relief_delay_ms": room_defaults.get("holdout_relief_delay_ms", 0),
        "ritual_role_script": room_defaults.get("ritual_role_script", ""),
        "ritual_reinforcement_count": room_defaults.get("ritual_reinforcement_count", 0),
        "ritual_link_mode": room_defaults.get("ritual_link_mode", ""),
        "ritual_payoff_kind": room_defaults.get("ritual_payoff_kind", ""),
        "ritual_payoff_label": room_defaults.get("ritual_payoff_label", ""),
        "objective_label": room_defaults.get("objective_label", ""),
        "objective_layout_offsets": room_defaults.get("objective_layout_offsets", ""),
        "objective_spawn_offset": room_defaults.get("objective_spawn_offset", ""),
        "objective_radius": room_defaults.get("objective_radius", 0),
        "objective_trigger_padding": room_defaults.get("objective_trigger_padding", 0),
        "objective_max_hp": room_defaults.get("objective_max_hp", 0),
        "objective_move_speed": room_defaults.get("objective_move_speed", 0.0),
        "objective_guide_radius": room_defaults.get("objective_guide_radius", 0),
        "objective_exit_radius": room_defaults.get("objective_exit_radius", 0),
        "objective_damage_cooldown_ms": room_defaults.get("objective_damage_cooldown_ms", 0),
        "puzzle_reinforcement_count": room_defaults.get("puzzle_reinforcement_count", 0),
        "puzzle_stall_duration_ms": room_defaults.get("puzzle_stall_duration_ms", 0),
        "notes": "",
    }


class RoomSelectorTests(unittest.TestCase):
    def make_selector(self, catalog):
        return RoomSelector(
            "mud_caverns",
            "mud",
            (1, 2),
            (50, 35, 15),
            catalog=catalog,
            rng=random.Random(0),
        )

    def test_start_room_forces_standard_combat(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("trap_gauntlet", topology_role="branch", branch_preference="branch"),
            )
        )

        plan = selector.build_room_plan((0, 0), 0, "main_path")

        self.assertEqual(plan.room_id, "standard_combat")
        self.assertEqual(plan.objective_rule, "immediate")
        self.assertEqual(plan.enemy_count_range, (1, 2))

    def test_early_main_path_prefers_lower_complexity_room_families(self):
        selector = self.make_selector(
            (
                _template(
                    "standard_combat",
                    topology_role="opener",
                    max_depth=None,
                    generation_weight=1,
                    path_stage_min=0,
                    path_stage_max=1,
                ),
                _template(
                    "ritual_disruption",
                    topology_role="mid_run",
                    min_depth=0,
                    generation_weight=100,
                    path_stage_min=2,
                    path_stage_max=4,
                ),
            )
        )

        plan = selector.build_room_plan(
            (1, 0),
            1,
            "main_path",
            path_id="main",
            path_index=1,
            path_length=5,
            path_progress=0.25,
            difficulty_band=1,
        )

        self.assertEqual(plan.room_id, "standard_combat")

    def test_exit_room_prefers_finale_holdout_plan(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("survival_holdout", topology_role="finale", min_depth=4),
            )
        )

        plan = selector.build_room_plan((4, 0), 4, "main_path", is_exit=True)

        self.assertEqual(plan.room_id, "survival_holdout")
        self.assertEqual(plan.objective_rule, "holdout_timer")
        self.assertEqual(plan.objective_duration_ms, 9000)
        self.assertEqual(plan.enemy_count_range, (3, 4))
        self.assertTrue(plan.clear_center)
        self.assertEqual(plan.scripted_wave_sizes, (1, 2, 3))
        self.assertEqual(plan.holdout_zone_radius, 96)
        self.assertEqual(plan.holdout_relief_count, 1)
        self.assertEqual(plan.holdout_relief_delay_ms, 1500)

    def test_holdout_room_can_emit_relief_metadata(self):
        selector = self.make_selector(
            (
                _template(
                    "survival_holdout",
                    topology_role="finale",
                    min_depth=4,
                    holdout_relief_count=2,
                    holdout_relief_delay_ms=900,
                ),
            )
        )

        plan = selector.build_room_plan((4, 0), 4, "main_path", is_exit=True)

        self.assertEqual(plan.room_id, "survival_holdout")
        self.assertEqual(plan.holdout_relief_count, 2)
        self.assertEqual(plan.holdout_relief_delay_ms, 900)

    def test_exit_room_can_emit_escort_protection_rule(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("survival_holdout", topology_role="finale", min_depth=4, generation_weight=1),
                _template("escort_protection", topology_role="mid_run", min_depth=2, generation_weight=100),
            )
        )

        plan = selector.build_room_plan((4, 0), 4, "main_path", is_exit=True)

        self.assertEqual(plan.room_id, "escort_protection")
        self.assertEqual(plan.objective_rule, "escort_to_exit")
        self.assertEqual(plan.enemy_count_range, (2, 3))
        self.assertTrue(plan.clear_center)
        self.assertEqual(plan.objective_label, "Escort")
        self.assertEqual(plan.objective_spawn_offset, (-6, 0))
        self.assertEqual(plan.objective_max_hp, 26)

    def test_exit_room_can_emit_escort_bomb_carrier_rule(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("survival_holdout", topology_role="finale", min_depth=4, generation_weight=1),
                _template("escort_bomb_carrier", topology_role="mid_run", min_depth=3, generation_weight=100),
            )
        )

        plan = selector.build_room_plan((4, 1), 4, "main_path", is_exit=True)

        self.assertEqual(plan.room_id, "escort_bomb_carrier")
        self.assertEqual(plan.objective_rule, "escort_bomb_to_exit")
        self.assertEqual(plan.enemy_count_range, (2, 3))
        self.assertTrue(plan.clear_center)

    def test_branch_room_prefers_trap_gauntlet(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template(
                    "trap_gauntlet",
                    topology_role="branch",
                    branch_preference="branch",
                    min_depth=1,
                ),
            )
        )

        plan = selector.build_room_plan((1, 1), 2, "branch")

        self.assertEqual(plan.room_id, "trap_gauntlet")
        self.assertEqual(plan.enemy_count_range, (0, 0))
        self.assertTrue(plan.guaranteed_chest)
        self.assertEqual(plan.chest_spawn_chance, 1.0)
        self.assertTrue(plan.clear_center)
        self.assertEqual(plan.objective_variant, "crusher_corridors")
        self.assertEqual(plan.objective_entity_count, 3)
        self.assertEqual(plan.objective_label, "Lane Switch")
        self.assertEqual(plan.objective_trigger_padding, 18)

    def test_branch_room_can_emit_trap_variant_metadata(self):
        selector = self.make_selector(
            (
                _template(
                    "trap_gauntlet",
                    topology_role="branch",
                    branch_preference="branch",
                    objective_variant="vent_lanes",
                ),
            )
        )

        plan = selector.build_room_plan((1, 1), 2, "branch")

        self.assertEqual(plan.room_id, "trap_gauntlet")
        self.assertEqual(plan.objective_variant, "vent_lanes")

    def test_puzzle_room_can_emit_paired_variant_metadata(self):
        selector = self.make_selector(
            (
                _template(
                    "puzzle_gated_doors",
                    topology_role="wildcard",
                    objective_variant="paired_runes",
                    objective_entity_count=4,
                    objective_label="Rune",
                    puzzle_reinforcement_count=2,
                    puzzle_stall_duration_ms=1800,
                ),
            )
        )

        plan = selector.build_room_plan((2, 1), 2, "main_path")

        self.assertEqual(plan.room_id, "puzzle_gated_doors")
        self.assertEqual(plan.objective_variant, "paired_runes")
        self.assertEqual(plan.objective_entity_count, 4)
        self.assertEqual(plan.objective_label, "Rune")
        self.assertEqual(plan.puzzle_reinforcement_count, 2)
        self.assertEqual(plan.puzzle_stall_duration_ms, 1800)

    def test_early_branch_prefers_trap_or_stealth_over_mid_run_objectives(self):
        selector = self.make_selector(
            (
                _template(
                    "trap_gauntlet",
                    topology_role="branch",
                    branch_preference="branch",
                    min_depth=1,
                    path_stage_min=0,
                    path_stage_max=4,
                    reward_affinity="branch",
                ),
                _template(
                    "ritual_disruption",
                    topology_role="mid_run",
                    min_depth=1,
                    generation_weight=100,
                    path_stage_min=2,
                    path_stage_max=4,
                ),
            )
        )

        plan = selector.build_room_plan(
            (1, 1),
            2,
            "branch",
            path_id="branch_1",
            path_index=0,
            path_length=2,
            path_progress=0.0,
            difficulty_band=0,
        )

        self.assertEqual(plan.room_id, "trap_gauntlet")

    def test_path_terminal_branch_room_guarantees_bonus_chest_metadata(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template(
                    "trap_gauntlet",
                    topology_role="branch",
                    branch_preference="branch",
                    min_depth=1,
                ),
            )
        )

        plan = selector.build_room_plan(
            (1, 1),
            2,
            "branch",
            path_id="branch_1",
            path_index=1,
            path_length=2,
            path_progress=1.0,
            difficulty_band=4,
            is_path_terminal=True,
            reward_tier="branch_bonus",
        )

        self.assertTrue(plan.guaranteed_chest)
        self.assertEqual(plan.reward_tier, "branch_bonus")
        self.assertTrue(plan.is_path_terminal)

    def test_path_terminal_exit_room_locks_reward_chest_until_objective_completion(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("survival_holdout", topology_role="finale", min_depth=4),
            )
        )

        plan = selector.build_room_plan(
            (4, 0),
            4,
            "main_path",
            is_exit=True,
            path_id="main",
            path_index=4,
            path_length=5,
            path_progress=1.0,
            difficulty_band=4,
            is_path_terminal=True,
            reward_tier="finale_bonus",
        )

        self.assertTrue(plan.guaranteed_chest)
        self.assertEqual(plan.reward_tier, "finale_bonus")
        self.assertTrue(plan.chest_locked_until_complete)

    def test_late_holdout_terminal_gains_an_extra_scripted_wave(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("survival_holdout", topology_role="finale", min_depth=4),
            )
        )

        plan = selector.build_room_plan(
            (4, 0),
            4,
            "main_path",
            is_exit=True,
            path_id="main",
            path_index=4,
            path_length=5,
            path_progress=1.0,
            difficulty_band=4,
            is_path_terminal=True,
            reward_tier="finale_bonus",
        )

        self.assertEqual(plan.scripted_wave_sizes, (1, 2, 3, 4))
        self.assertEqual(plan.holdout_zone_radius, 96)

    def test_mid_run_room_can_emit_ritual_or_timed_extraction_rules(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("ritual_disruption", topology_role="mid_run", min_depth=2),
                _template("timed_extraction", topology_role="mid_run", min_depth=2),
            )
        )

        plan = selector.build_room_plan((2, 0), 3, "main_path")

        self.assertIn(plan.room_id, {"ritual_disruption", "timed_extraction"})
        if plan.room_id == "ritual_disruption":
            self.assertEqual(plan.objective_rule, "destroy_altars")
            self.assertEqual(plan.enemy_count_range, (2, 3))
            self.assertFalse(plan.guaranteed_chest)
        else:
            self.assertEqual(plan.objective_rule, "loot_then_timer")
            self.assertEqual(plan.objective_duration_ms, 8000)
            self.assertEqual(plan.scripted_wave_sizes, (1, 2))
            self.assertTrue(plan.guaranteed_chest)

    def test_terminal_ritual_plan_scales_altar_count_and_role_script(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("ritual_disruption", topology_role="mid_run", min_depth=2),
            )
        )

        plan = selector.build_room_plan(
            (3, 1),
            4,
            "branch",
            path_id="branch_1",
            path_index=2,
            path_length=3,
            path_progress=1.0,
            difficulty_band=4,
            is_path_terminal=True,
            reward_tier="branch_bonus",
        )

        self.assertEqual(plan.objective_entity_count, 4)
        self.assertEqual(plan.ritual_role_script, ("summon", "pulse", "ward", "ward"))
        self.assertEqual(plan.ritual_link_mode, "ward_shields_others")
        self.assertEqual(plan.ritual_payoff_kind, "reveal_reliquary")
        self.assertEqual(plan.ritual_payoff_label, "Reliquary")

    def test_ritual_room_can_emit_pulse_window_link_mode(self):
        selector = self.make_selector(
            (
                _template(
                    "ritual_disruption",
                    topology_role="mid_run",
                    min_depth=2,
                    objective_variant="frost_obelisk",
                    ritual_link_mode="pulse_gates_damage",
                ),
            )
        )

        plan = selector.build_room_plan((2, 0), 3, "main_path")

        self.assertEqual(plan.room_id, "ritual_disruption")
        self.assertEqual(plan.objective_variant, "frost_obelisk")
        self.assertEqual(plan.ritual_link_mode, "pulse_gates_damage")

    def test_late_main_path_prefers_heavier_objective_rooms(self):
        selector = self.make_selector(
            (
                _template(
                    "standard_combat",
                    topology_role="opener",
                    max_depth=None,
                    generation_weight=1,
                    path_stage_min=0,
                    path_stage_max=1,
                ),
                _template(
                    "escort_protection",
                    topology_role="mid_run",
                    min_depth=0,
                    generation_weight=100,
                    path_stage_min=2,
                    path_stage_max=4,
                    reward_affinity="finale",
                ),
            )
        )

        plan = selector.build_room_plan(
            (3, 0),
            3,
            "main_path",
            path_id="main",
            path_index=3,
            path_length=5,
            path_progress=0.75,
            difficulty_band=3,
        )

        self.assertEqual(plan.room_id, "escort_protection")

    def test_path_rules_avoid_immediate_room_family_repeats_on_same_path(self):
        selector = self.make_selector(
            (
                _template(
                    "ritual_disruption",
                    topology_role="mid_run",
                    min_depth=0,
                    generation_weight=100,
                    path_stage_min=2,
                    path_stage_max=4,
                    repeat_cooldown=1,
                ),
                _template(
                    "resource_race",
                    topology_role="mid_run",
                    min_depth=0,
                    generation_weight=1,
                    path_stage_min=2,
                    path_stage_max=4,
                    repeat_cooldown=1,
                ),
            )
        )

        first_plan = selector.build_room_plan(
            (2, 0),
            2,
            "main_path",
            path_id="main",
            path_index=2,
            path_length=5,
            path_progress=0.5,
            difficulty_band=2,
        )
        second_plan = selector.build_room_plan(
            (3, 0),
            3,
            "main_path",
            path_id="main",
            path_index=3,
            path_length=5,
            path_progress=0.75,
            difficulty_band=3,
        )

        self.assertEqual(first_plan.room_id, "ritual_disruption")
        self.assertEqual(second_plan.room_id, "resource_race")

    def test_wildcard_room_can_emit_puzzle_rule(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("puzzle_gated_doors", topology_role="wildcard", min_depth=2),
            )
        )

        plan = selector.build_room_plan((2, 1), 3, "main_path")

        self.assertEqual(plan.room_id, "puzzle_gated_doors")
        self.assertEqual(plan.objective_rule, "charge_plates")
        self.assertTrue(plan.clear_center)
        self.assertEqual(plan.objective_label, "Seal")
        self.assertEqual(plan.objective_layout_offsets, ((-5, -3), (5, -3), (0, 4)))
        self.assertEqual(plan.objective_trigger_padding, 10)

    def test_exit_room_can_emit_resource_race_when_weighted_above_holdout(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("survival_holdout", topology_role="finale", min_depth=4, generation_weight=1),
                _template("resource_race", topology_role="mid_run", min_depth=2, generation_weight=100),
            )
        )

        plan = selector.build_room_plan((4, 0), 4, "main_path", is_exit=True)

        self.assertEqual(plan.room_id, "resource_race")
        self.assertEqual(plan.objective_rule, "claim_relic_before_lockdown")
        self.assertEqual(plan.objective_duration_ms, 7000)
        self.assertEqual(plan.scripted_wave_sizes, (1, 2))
        self.assertTrue(plan.guaranteed_chest)
        self.assertTrue(plan.clear_center)

    def test_exit_room_can_emit_stealth_passage_rule(self):
        selector = self.make_selector(
            (
                _template("standard_combat", topology_role="opener", max_depth=1),
                _template("stealth_passage", topology_role="wildcard", min_depth=2),
            )
        )

        plan = selector.build_room_plan((3, 0), 3, "main_path", is_exit=True)

        self.assertEqual(plan.room_id, "stealth_passage")
        self.assertEqual(plan.objective_rule, "avoid_alarm_zones")
        self.assertEqual(plan.objective_duration_ms, 2200)
        self.assertEqual(plan.enemy_count_range, (0, 0))
        self.assertTrue(plan.clear_center)
        self.assertEqual(plan.objective_label, "Alarm")
        self.assertEqual(plan.objective_layout_offsets, ((-4, -2), (4, -2), (0, 4)))
        self.assertEqual(plan.objective_radius, 34)


if __name__ == "__main__":
    unittest.main()