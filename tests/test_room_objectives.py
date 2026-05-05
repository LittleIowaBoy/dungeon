import unittest
from types import SimpleNamespace

import pygame

from objective_entities import AlarmBeacon, AltarAnchor, EscortNPC, HoldoutStabilizer, HoldoutZone, PressurePlate, PuzzleStabilizer, TrapCrusher, TrapLaneSwitch, TrapSweeper, TrapVentLane
from room import FLOOR, PORTAL, WALL, Room
from room_plan import RoomPlan, RoomTemplate
from settings import ROOM_COLS, ROOM_ROWS, TILE_SIZE


def _offsets_to_pixels(offsets):
    points = []
    for dc, dr in offsets:
        col = ROOM_COLS // 2 + dc
        row = ROOM_ROWS // 2 + dr
        points.append((col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2))
    return tuple(points)


def _template(room_id, display_name, *, objective_variant=""):
    return RoomTemplate(
        room_id=room_id,
        display_name=display_name,
        objective_kind=room_id,
        combat_pressure="mid",
        decision_complexity="mid",
        topology_role="mid_run",
        min_depth=0,
        max_depth=None,
        branch_preference="either",
        generation_weight=1,
        enabled=True,
        implementation_status="prototype",
        objective_variant=objective_variant,
        notes="",
    )


def _plan(
    room_id,
    *,
    objective_rule,
    is_exit=True,
    guaranteed_chest=False,
    chest_spawn_chance=None,
    enemy_count_range=(1, 2),
    duration=None,
    objective_variant="",
    reward_tier="standard",
    chest_locked_until_complete=False,
    objective_entity_count=0,
    scripted_wave_sizes=(),
    holdout_zone_radius=0,
    holdout_zone_min_radius=0,
    holdout_zone_shrink_ms=0,
    holdout_zone_migrate_ms=0,
    holdout_zone_migration_offsets=(),
    holdout_relief_count=0,
    holdout_relief_delay_ms=0,
    holdout_stabilizer_migration_delay_ms=0,
    ritual_role_script=(),
    ritual_reinforcement_count=0,
    ritual_link_mode="",
    ritual_payoff_kind="",
    ritual_payoff_label="",
    ritual_wrong_strike_spawn_count=0,
    objective_label="",
    objective_layout_offsets=(),
    objective_spawn_offset=None,
    objective_patrol_offset=None,
    objective_radius=0,
    objective_trigger_padding=0,
    objective_max_hp=0,
    objective_move_speed=0.0,
    objective_guide_radius=0,
    objective_exit_radius=0,
    objective_damage_cooldown_ms=0,
    puzzle_reinforcement_count=0,
    puzzle_stall_duration_ms=0,
    puzzle_stabilizer_count=0,
    puzzle_stabilizer_hp=0,
    puzzle_camp_pulse_damage=0,
    puzzle_camp_pulse_interval_ms=0,
    puzzle_camp_pulse_grace_ms=0,
    puzzle_camp_pulse_radius=0,
    trap_intensity_scale=1.0,
    trap_speed_scale=1.0,
    trap_challenge_reward_kind="chest_upgrade",
):
    return RoomPlan(
        position=(0, 0),
        depth=2,
        path_kind="main_path",
        is_exit=is_exit,
        template=_template(
            room_id,
            room_id.replace("_", " ").title(),
            objective_variant=objective_variant,
        ),
        terrain_type="mud",
        enemy_count_range=enemy_count_range,
        enemy_type_weights=(50, 35, 15),
        objective_rule=objective_rule,
        objective_duration_ms=duration,
        guaranteed_chest=guaranteed_chest,
        chest_spawn_chance=1.0 if chest_spawn_chance is None and guaranteed_chest else chest_spawn_chance,
        terrain_patch_count_range=(1, 1),
        terrain_patch_size_range=(2, 2),
        clear_center=True,
        reward_tier=reward_tier,
        chest_locked_until_complete=chest_locked_until_complete,
        objective_entity_count=objective_entity_count,
        scripted_wave_sizes=scripted_wave_sizes,
        holdout_zone_radius=holdout_zone_radius,
        holdout_zone_min_radius=holdout_zone_min_radius,
        holdout_zone_shrink_ms=holdout_zone_shrink_ms,
        holdout_zone_migrate_ms=holdout_zone_migrate_ms,
        holdout_zone_migration_offsets=holdout_zone_migration_offsets,
        holdout_relief_count=holdout_relief_count,
        holdout_relief_delay_ms=holdout_relief_delay_ms,
        holdout_stabilizer_migration_delay_ms=holdout_stabilizer_migration_delay_ms,
        ritual_role_script=ritual_role_script,
        ritual_reinforcement_count=ritual_reinforcement_count,
        ritual_link_mode=ritual_link_mode,
        ritual_payoff_kind=ritual_payoff_kind,
        ritual_payoff_label=ritual_payoff_label,
        ritual_wrong_strike_spawn_count=ritual_wrong_strike_spawn_count,
        objective_label=objective_label,
        objective_layout_offsets=objective_layout_offsets,
        objective_spawn_offset=objective_spawn_offset,
        objective_patrol_offset=objective_patrol_offset,
        objective_radius=objective_radius,
        objective_trigger_padding=objective_trigger_padding,
        objective_max_hp=objective_max_hp,
        objective_move_speed=objective_move_speed,
        objective_guide_radius=objective_guide_radius,
        objective_exit_radius=objective_exit_radius,
        objective_damage_cooldown_ms=objective_damage_cooldown_ms,
        puzzle_reinforcement_count=puzzle_reinforcement_count,
        puzzle_stall_duration_ms=puzzle_stall_duration_ms,
        puzzle_stabilizer_count=puzzle_stabilizer_count,
        puzzle_stabilizer_hp=puzzle_stabilizer_hp,
        puzzle_camp_pulse_damage=puzzle_camp_pulse_damage,
        puzzle_camp_pulse_interval_ms=puzzle_camp_pulse_interval_ms,
        puzzle_camp_pulse_grace_ms=puzzle_camp_pulse_grace_ms,
        puzzle_camp_pulse_radius=puzzle_camp_pulse_radius,
        trap_intensity_scale=trap_intensity_scale,
        trap_speed_scale=trap_speed_scale,
        trap_challenge_reward_kind=trap_challenge_reward_kind,
    )


class RoomObjectiveTests(unittest.TestCase):
    def test_trap_gauntlet_room_plan_removes_enemies_and_guarantees_chest(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Lane Switch",
                objective_trigger_padding=18,
            ),
        )

        self.assertEqual(room.enemy_configs, [])
        self.assertIsNotNone(room.chest_pos)
        self.assertEqual(
            sum(1 for config in room.objective_entity_configs if config["kind"] == "trap_sweeper"),
            3,
        )
        self.assertEqual(
            sum(1 for config in room.objective_entity_configs if config["kind"] == "trap_lane_switch"),
            3,
        )
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Safe lane Middle | Bonus route Bottom")

    def test_trap_lane_switch_changes_the_safe_lane_and_deactivates_matching_sweeper(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Lane Switch",
                objective_trigger_padding=18,
            ),
        )

        switch_config = next(
            config
            for config in room.objective_entity_configs
            if config["kind"] == "trap_lane_switch" and config["lane_index"] == 0
        )
        player = SimpleNamespace(rect=TrapLaneSwitch(switch_config).rect.copy())

        switched = TrapLaneSwitch(switch_config).sync_player_overlap(player)

        self.assertTrue(switched)
        self.assertEqual(room._trap_controller()["safe_lane"], 0)

        safe_sweeper_config = next(
            config
            for config in room.objective_entity_configs
            if config["kind"] == "trap_sweeper" and config["lane_index"] == 0
        )
        unsafe_sweeper_config = next(
            config
            for config in room.objective_entity_configs
            if config["kind"] == "trap_sweeper" and config["lane_index"] == 1
        )

        TrapSweeper(safe_sweeper_config).update(1000)
        TrapSweeper(unsafe_sweeper_config).update(1000)

        self.assertFalse(safe_sweeper_config["active"])
        self.assertTrue(unsafe_sweeper_config["active"])
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Safe lane Top | Bonus route Bottom")

    def test_trap_challenge_lane_upgrades_reward_tier(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Lane Switch",
                objective_trigger_padding=18,
                reward_tier="branch_bonus",
            ),
        )

        challenge_switch = next(
            config
            for config in room.objective_entity_configs
            if config["kind"] == "trap_lane_switch" and config["lane_index"] == 2
        )
        player = SimpleNamespace(rect=TrapLaneSwitch(challenge_switch).rect.copy())
        TrapLaneSwitch(challenge_switch).sync_player_overlap(player)

        update = room.update_objective(1000, [])

        self.assertEqual(update, {"kind": "upgrade_reward_chest", "reward_tier": "finale_bonus", "reward_kind": "chest_upgrade"})
        self.assertEqual(room.chest_reward_tier(), "finale_bonus")
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Challenge lane Bottom | Reward upgraded")

    def test_trap_challenge_lane_payload_carries_biome_reward_kind(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Lane Switch",
                objective_trigger_padding=18,
                reward_tier="branch_bonus",
                trap_challenge_reward_kind="stat_shard",
            ),
        )
        challenge_switch = next(
            config
            for config in room.objective_entity_configs
            if config["kind"] == "trap_lane_switch" and config["lane_index"] == 2
        )
        player = SimpleNamespace(rect=TrapLaneSwitch(challenge_switch).rect.copy())
        TrapLaneSwitch(challenge_switch).sync_player_overlap(player)

        update = room.update_objective(1000, [])

        self.assertEqual(update["reward_kind"], "stat_shard")
        self.assertEqual(
            room.objective_hud_state(1000)["label"],
            "Objective: Challenge lane Bottom | Stat shard claimed",
        )

    def test_trap_challenge_lane_label_reflects_tempo_rune_reward(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Lane Switch",
                objective_trigger_padding=18,
                reward_tier="branch_bonus",
                trap_challenge_reward_kind="tempo_rune",
            ),
        )
        challenge_switch = next(
            config
            for config in room.objective_entity_configs
            if config["kind"] == "trap_lane_switch" and config["lane_index"] == 2
        )
        player = SimpleNamespace(rect=TrapLaneSwitch(challenge_switch).rect.copy())
        TrapLaneSwitch(challenge_switch).sync_player_overlap(player)
        update = room.update_objective(1000, [])

        self.assertEqual(update["reward_kind"], "tempo_rune")
        self.assertEqual(
            room.objective_hud_state(1000)["label"],
            "Objective: Challenge lane Bottom | Tempo rune claimed",
        )

    def test_trap_challenge_lane_label_reflects_mobility_consumable_reward(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Lane Switch",
                objective_trigger_padding=18,
                reward_tier="branch_bonus",
                trap_challenge_reward_kind="mobility_consumable",
            ),
        )
        challenge_switch = next(
            config
            for config in room.objective_entity_configs
            if config["kind"] == "trap_lane_switch" and config["lane_index"] == 2
        )
        player = SimpleNamespace(rect=TrapLaneSwitch(challenge_switch).rect.copy())
        TrapLaneSwitch(challenge_switch).sync_player_overlap(player)
        update = room.update_objective(1000, [])

        self.assertEqual(update["reward_kind"], "mobility_consumable")
        self.assertEqual(
            room.objective_hud_state(1000)["label"],
            "Objective: Challenge lane Bottom | Mobility charge claimed",
        )

    def test_trap_gauntlet_can_build_vent_lane_variant(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Vent Switch",
                objective_trigger_padding=18,
                objective_variant="vent_lanes",
            ),
        )

        vents = [
            config for config in room.objective_entity_configs if config["kind"] == "trap_vent_lane"
        ]
        switches = [
            config for config in room.objective_entity_configs if config["kind"] == "trap_lane_switch"
        ]

        self.assertEqual(len(vents), 3)
        self.assertEqual(len(switches), 3)
        vent = TrapVentLane(vents[0])
        vent.update(1000)
        self.assertIn(room._playtest_identifier_detail(1000), {
            "Solve: Step on a lane switch to shut down one vent lane. The challenge lane still pulses but upgrades the chest.",
        })

    def test_trap_gauntlet_can_build_crusher_corridor_variant(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=2,
                objective_label="Crusher Switch",
                objective_trigger_padding=18,
                objective_variant="crusher_corridors",
            ),
        )

        crushers = [
            config for config in room.objective_entity_configs if config["kind"] == "trap_crusher"
        ]
        switches = [
            config for config in room.objective_entity_configs if config["kind"] == "trap_lane_switch"
        ]

        self.assertEqual(len(crushers), 4)
        self.assertEqual(len(switches), 2)
        crusher = TrapCrusher(crushers[0])
        crusher.update(1000)
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Safe lane Top | Bonus route Bottom")
        self.assertEqual(
            room._playtest_identifier_detail(1000),
            "Solve: Pick a corridor and time the crushers. The challenge corridor stays active but upgrades the chest.",
        )

    def test_trap_gauntlet_can_build_mixed_lane_variant(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Gate Switch",
                objective_trigger_padding=18,
                objective_variant="mixed_lanes",
            ),
        )

        sweepers = [
            config for config in room.objective_entity_configs if config["kind"] == "trap_sweeper"
        ]
        vents = [
            config for config in room.objective_entity_configs if config["kind"] == "trap_vent_lane"
        ]
        crushers = [
            config for config in room.objective_entity_configs if config["kind"] == "trap_crusher"
        ]
        switches = [
            config for config in room.objective_entity_configs if config["kind"] == "trap_lane_switch"
        ]

        self.assertEqual(len(sweepers), 1)
        self.assertEqual(len(vents), 1)
        self.assertEqual(len(crushers), 2)
        self.assertEqual(len(switches), 6)
        self.assertEqual({config["switch_bank"] for config in switches}, {"left", "checkpoint"})
        controller = room._trap_controller()
        challenge_offset = controller["lane_offsets"][controller["challenge_lane"]]
        expected_chest_y = room._offset_to_pixel((0, challenge_offset))[1]
        self.assertEqual(room.chest_pos[1], expected_chest_y)
        separator_rows = [
            ROOM_ROWS // 2 + (controller["lane_offsets"][index] + controller["lane_offsets"][index + 1]) // 2
            for index in range(len(controller["lane_offsets"]) - 1)
        ]
        self.assertEqual(room.tile_at(5, separator_rows[0]), WALL)
        self.assertEqual(room.tile_at(5, separator_rows[1]), WALL)
        self.assertEqual(room.tile_at(ROOM_COLS // 2, separator_rows[0]), FLOOR)
        self.assertEqual(room.tile_at(ROOM_COLS // 2, separator_rows[1]), FLOOR)
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Safe lane Middle | Bonus route Bottom")

        checkpoint_switch = next(
            config
            for config in switches
            if config["switch_bank"] == "checkpoint" and config["lane_index"] == 2
        )
        player = SimpleNamespace(rect=TrapLaneSwitch(checkpoint_switch).rect.copy())

        switched = TrapLaneSwitch(checkpoint_switch).sync_player_overlap(player)

        self.assertTrue(switched)
        self.assertEqual(room._trap_controller()["safe_lane"], 2)
        self.assertTrue(room._trap_challenge_route_selected())
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Challenge lane Bottom | Bonus route Bottom")
        self.assertEqual(
            room._playtest_identifier_detail(1000),
            "Solve: Use the entry and checkpoint switches to reroute through mixed trap lanes. The challenge lane keeps every hazard live but upgrades the chest.",
        )

    def test_trap_gauntlet_default_intensity_keeps_base_hazard_damage(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Gate Switch",
                objective_trigger_padding=18,
                objective_variant="mixed_lanes",
                trap_intensity_scale=1.0,
            ),
        )
        sweepers = [c for c in room.objective_entity_configs if c["kind"] == "trap_sweeper"]
        vents = [c for c in room.objective_entity_configs if c["kind"] == "trap_vent_lane"]
        crushers = [c for c in room.objective_entity_configs if c["kind"] == "trap_crusher"]
        self.assertEqual(sweepers[0]["damage"], 8)
        self.assertEqual(vents[0]["damage"], 7)
        self.assertEqual(crushers[0]["damage"], 9)

    def test_trap_gauntlet_high_intensity_scales_hazard_damage_up(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Gate Switch",
                objective_trigger_padding=18,
                objective_variant="mixed_lanes",
                trap_intensity_scale=1.4,
            ),
        )
        sweepers = [c for c in room.objective_entity_configs if c["kind"] == "trap_sweeper"]
        vents = [c for c in room.objective_entity_configs if c["kind"] == "trap_vent_lane"]
        crushers = [c for c in room.objective_entity_configs if c["kind"] == "trap_crusher"]
        self.assertEqual(sweepers[0]["damage"], 11)  # round(8 * 1.4)
        self.assertEqual(vents[0]["damage"], 10)  # round(7 * 1.4)
        self.assertEqual(crushers[0]["damage"], 13)  # round(9 * 1.4)

    def test_trap_gauntlet_low_intensity_scales_hazard_damage_down(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Gate Switch",
                objective_trigger_padding=18,
                objective_variant="mixed_lanes",
                trap_intensity_scale=0.8,
            ),
        )
        sweepers = [c for c in room.objective_entity_configs if c["kind"] == "trap_sweeper"]
        vents = [c for c in room.objective_entity_configs if c["kind"] == "trap_vent_lane"]
        crushers = [c for c in room.objective_entity_configs if c["kind"] == "trap_crusher"]
        self.assertEqual(sweepers[0]["damage"], 6)  # round(8 * 0.8)
        self.assertEqual(vents[0]["damage"], 6)  # round(7 * 0.8)
        self.assertEqual(crushers[0]["damage"], 7)  # round(9 * 0.8)

    def test_trap_gauntlet_default_speed_scale_keeps_base_hazard_timings(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Gate Switch",
                objective_trigger_padding=18,
                objective_variant="mixed_lanes",
                trap_speed_scale=1.0,
            ),
        )
        sweepers = [c for c in room.objective_entity_configs if c["kind"] == "trap_sweeper"]
        vents = [c for c in room.objective_entity_configs if c["kind"] == "trap_vent_lane"]
        crushers = [c for c in room.objective_entity_configs if c["kind"] == "trap_crusher"]
        self.assertAlmostEqual(sweepers[0]["speed"], 1.5)
        self.assertAlmostEqual(sweepers[0]["challenge_speed"], 0.9)
        self.assertEqual(vents[0]["cycle_ms"], 2800)
        self.assertEqual(vents[0]["active_ms"], 1800)
        self.assertEqual(vents[0]["challenge_cycle_ms"], 2200)
        self.assertEqual(crushers[0]["cycle_ms"], 2400)
        self.assertEqual(crushers[0]["challenge_active_ms"], 1200)

    def test_trap_gauntlet_high_speed_scale_quickens_hazard_timings(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Gate Switch",
                objective_trigger_padding=18,
                objective_variant="mixed_lanes",
                trap_speed_scale=1.25,
            ),
        )
        sweepers = [c for c in room.objective_entity_configs if c["kind"] == "trap_sweeper"]
        vents = [c for c in room.objective_entity_configs if c["kind"] == "trap_vent_lane"]
        crushers = [c for c in room.objective_entity_configs if c["kind"] == "trap_crusher"]
        self.assertAlmostEqual(sweepers[0]["speed"], 1.5 * 1.25)
        self.assertAlmostEqual(sweepers[0]["challenge_speed"], 0.9 * 1.25)
        self.assertEqual(vents[0]["cycle_ms"], round(2800 / 1.25))  # 2240
        self.assertEqual(vents[0]["active_ms"], round(1800 / 1.25))  # 1440
        self.assertEqual(crushers[0]["cycle_ms"], round(2400 / 1.25))  # 1920
        self.assertEqual(crushers[0]["challenge_active_ms"], round(1200 / 1.25))  # 960

    def test_trap_gauntlet_low_speed_scale_slows_hazard_timings(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                objective_label="Gate Switch",
                objective_trigger_padding=18,
                objective_variant="mixed_lanes",
                trap_speed_scale=0.85,
            ),
        )
        sweepers = [c for c in room.objective_entity_configs if c["kind"] == "trap_sweeper"]
        vents = [c for c in room.objective_entity_configs if c["kind"] == "trap_vent_lane"]
        crushers = [c for c in room.objective_entity_configs if c["kind"] == "trap_crusher"]
        self.assertAlmostEqual(sweepers[0]["speed"], 1.5 * 0.85)
        self.assertAlmostEqual(sweepers[0]["challenge_speed"], 0.9 * 0.85)
        self.assertEqual(vents[0]["cycle_ms"], round(2800 / 0.85))  # 3294
        self.assertEqual(crushers[0]["cycle_ms"], round(2400 / 0.85))  # 2824
        self.assertEqual(crushers[0]["active_ms"], round(1300 / 0.85))  # 1529

    def test_ordered_puzzle_resets_when_player_activates_wrong_plate(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="ordered_plates",
                objective_label="Seal",
                objective_entity_count=3,
            ),
        )
        room.on_enter(1000)

        first_plate = room.objective_entity_configs[0]
        third_plate = room.objective_entity_configs[2]

        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Charge seals 0/3 | Next 1")

        first_sprite = PressurePlate(first_plate)
        first_sprite.update(1050)
        first_sprite.sync_player_overlap(SimpleNamespace(rect=first_sprite.rect.copy()))
        self.assertEqual(room.objective_hud_state(1100)["label"], "Objective: Charge seals 1/3 | Next 2")

        third_sprite = PressurePlate(third_plate)
        third_sprite.update(1150)
        third_sprite.sync_player_overlap(SimpleNamespace(rect=third_sprite.rect.copy()))
        self.assertFalse(any(config["activated"] for config in room.objective_entity_configs))
        update = room.update_objective(1200, [])
        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertEqual(update["source"], "puzzle_reaction")
        self.assertEqual(len(update["enemy_configs"]), 1)
        self.assertIn("Reset on 3", room.objective_hud_state(1200)["label"])
        self.assertIn("Pressure spike", room.objective_hud_state(1200)["label"])

    def test_paired_rune_puzzle_tracks_matching_pairs(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="paired_runes",
                objective_label="Rune",
                objective_entity_count=4,
            ),
        )

        a_plates = [
            config for config in room.objective_entity_configs if config.get("pair_label") == "A"
        ]

        PressurePlate(a_plates[0]).sync_player_overlap(SimpleNamespace(rect=PressurePlate(a_plates[0]).rect.copy()))
        self.assertIn("Match A", room.objective_hud_state(1000)["label"])

        PressurePlate(a_plates[1]).sync_player_overlap(SimpleNamespace(rect=PressurePlate(a_plates[1]).rect.copy()))

        self.assertTrue(all(config["activated"] for config in a_plates))
        self.assertEqual(room.objective_hud_state(1100)["label"], "Objective: Match runes 1/2")

    def test_staggered_puzzle_variant_uses_sequence_targets_and_reset_pressure(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="staggered_plates",
                objective_label="Seal",
                objective_entity_count=4,
            ),
        )
        room.on_enter(1000)

        first_plate = next(config for config in room.objective_entity_configs if config["telegraph_text"] == "1")
        second_plate = next(config for config in room.objective_entity_configs if config["telegraph_text"] == "2")

        first_sprite = PressurePlate(first_plate)
        first_sprite.update(1050)
        first_sprite.sync_player_overlap(SimpleNamespace(rect=first_sprite.rect.copy()))

        self.assertEqual(room.objective_hud_state(1100)["label"], "Objective: Charge seals 1/4 | Next 3")

        second_sprite = PressurePlate(second_plate)
        second_sprite.update(1150)
        second_sprite.sync_player_overlap(SimpleNamespace(rect=second_sprite.rect.copy()))

        update = room.update_objective(1200, [])

        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertEqual(update["source"], "puzzle_reaction")
        self.assertEqual(room._puzzle_controller()["progress_index"], 0)
        self.assertEqual(room.objective_hud_state(1200)["label"], "Objective: Charge seals 0/4 | Next 1 | Reset on 2 | Pressure spike")
        self.assertEqual(
            room._playtest_identifier_detail(1200),
            "Solve: Follow the staggered seals order 1, 3, 2, 4. Wrong steps or stalling summon reinforcements.",
        )

    def test_paired_rune_puzzle_summons_reinforcement_after_stalling(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="paired_runes",
                objective_label="Rune",
                objective_entity_count=4,
            ),
        )
        room.on_enter(1000)

        first_a_plate = next(
            config for config in room.objective_entity_configs if config.get("pair_label") == "A"
        )
        first_a_sprite = PressurePlate(first_a_plate)
        first_a_sprite.update(1000)
        first_a_sprite.sync_player_overlap(SimpleNamespace(rect=first_a_sprite.rect.copy()))

        update = room.update_objective(3600, [])

        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertEqual(update["source"], "puzzle_reaction")
        self.assertEqual(len(update["enemy_configs"]), 1)
        self.assertFalse(any(config.get("primed") for config in room.objective_entity_configs))
        self.assertIsNone(room._puzzle_controller()["pending_pair_label"])
        self.assertEqual(room.objective_hud_state(3600)["label"], "Objective: Match runes 0/2 | Pressure spike")

    def test_puzzle_metadata_tunes_pressure_window_and_flash(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="paired_runes",
                objective_label="Rune",
                objective_entity_count=4,
                puzzle_reinforcement_count=2,
                puzzle_stall_duration_ms=1200,
            ),
        )
        room.on_enter(1000)

        first_a_plate = next(
            config for config in room.objective_entity_configs if config.get("pair_label") == "A"
        )
        first_a_sprite = PressurePlate(first_a_plate)
        first_a_sprite.update(1000)
        first_a_sprite.sync_player_overlap(SimpleNamespace(rect=first_a_sprite.rect.copy()))

        self.assertIsNone(room.update_objective(2100, []))

        update = room.update_objective(2300, [])
        first_a_sprite.update(2300)

        self.assertEqual(room._puzzle_controller()["stall_duration_ms"], 1200)
        self.assertEqual(room._puzzle_controller()["reaction_enemy_count"], 2)
        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertEqual(len(update["enemy_configs"]), 2)
        self.assertIsNotNone(first_a_sprite._penalty_flash_state())

    def test_puzzle_stabilizer_skips_next_expected_plate_when_destroyed(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="staggered_plates",
                objective_label="Glyph",
                objective_entity_count=4,
                puzzle_reinforcement_count=2,
                puzzle_stall_duration_ms=2200,
                puzzle_stabilizer_count=1,
                puzzle_stabilizer_hp=10,
            ),
        )
        room.on_enter(1000)

        stabilizer_config = next(
            config
            for config in room.objective_entity_configs
            if config.get("kind") == "puzzle_stabilizer"
        )
        plate_one = next(
            config
            for config in room.objective_entity_configs
            if config.get("kind") == "pressure_plate" and config.get("telegraph_text") == "1"
        )

        # Charge the first staggered plate (sequence 1, 3, 2, 4) so the next
        # expected plate becomes telegraph 3.
        plate_one_sprite = PressurePlate(plate_one)
        plate_one_sprite.update(1050)
        plate_one_sprite.sync_player_overlap(SimpleNamespace(rect=plate_one_sprite.rect.copy()))
        self.assertEqual(room.objective_hud_state(1100)["label"], "Objective: Charge glyphs 1/4 | Next 3")

        # Smash the stabilizer to claim the optional skip.
        stabilizer_sprite = PuzzleStabilizer(stabilizer_config)
        stabilizer_sprite.update(1200)
        destroyed = stabilizer_sprite.take_damage(stabilizer_config["max_hp"])
        self.assertTrue(destroyed)
        self.assertTrue(stabilizer_config["destroyed"])
        self.assertTrue(stabilizer_config["consumed"])

        plate_three = next(
            config
            for config in room.objective_entity_configs
            if config.get("kind") == "pressure_plate" and config.get("telegraph_text") == "3"
        )
        self.assertTrue(plate_three["activated"])
        self.assertEqual(room._puzzle_controller()["progress_index"], 2)

        # The HUD should report the skip and the next expected target should
        # advance to telegraph 2 (third entry in the staggered sequence).
        hud_label = room.objective_hud_state(1200)["label"]
        self.assertIn("Charge glyphs 2/4", hud_label)
        self.assertIn("Next 2", hud_label)
        self.assertIn("Stabilizer skip", hud_label)

        # Skip cancels any pending stall reaction so the destroy strike does
        # not also immediately summon reinforcements.
        self.assertIsNone(room.update_objective(1300, []))

    def test_puzzle_stabilizer_skips_one_pair_for_paired_runes(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="paired_runes",
                objective_label="Rune",
                objective_entity_count=4,
                puzzle_reinforcement_count=2,
                puzzle_stall_duration_ms=2200,
                puzzle_stabilizer_count=1,
                puzzle_stabilizer_hp=10,
            ),
        )
        room.on_enter(1000)

        stabilizer_config = next(
            config
            for config in room.objective_entity_configs
            if config.get("kind") == "puzzle_stabilizer"
        )
        pair_a_configs = [
            config
            for config in room.objective_entity_configs
            if config.get("kind") == "pressure_plate" and config.get("pair_label") == "A"
        ]
        pair_b_configs = [
            config
            for config in room.objective_entity_configs
            if config.get("kind") == "pressure_plate" and config.get("pair_label") == "B"
        ]
        self.assertEqual(len(pair_a_configs), 2)
        self.assertEqual(len(pair_b_configs), 2)
        self.assertEqual(room.remaining_puzzle_plates(), 4)

        # Half-prime pair B so the stabilizer should prefer to finish it.
        first_b_sprite = PressurePlate(pair_b_configs[0])
        first_b_sprite.update(1050)
        first_b_sprite.sync_player_overlap(SimpleNamespace(rect=first_b_sprite.rect.copy()))
        controller = room._puzzle_controller()
        self.assertEqual(controller["pending_pair_label"], "B")

        stabilizer_sprite = PuzzleStabilizer(stabilizer_config)
        stabilizer_sprite.update(1200)
        destroyed = stabilizer_sprite.take_damage(stabilizer_config["max_hp"])
        self.assertTrue(destroyed)
        self.assertTrue(stabilizer_config["consumed"])

        # Both B plates should now be activated and the half-primed state cleared.
        self.assertTrue(all(config.get("activated") for config in pair_b_configs))
        self.assertFalse(any(config.get("primed") for config in pair_b_configs))
        self.assertIsNone(controller["pending_pair_label"])
        self.assertEqual(room.remaining_puzzle_plates(), 2)

        hud_label = room.objective_hud_state(1200)["label"]
        self.assertIn("Stabilizer skip", hud_label)

        # Skip cancels any pending stall reaction.
        self.assertIsNone(room.update_objective(1300, []))

        # Playtest hint advertises the shortcut for paired_runes too.
        fresh = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="paired_runes",
                objective_label="Rune",
                objective_entity_count=4,
                puzzle_stabilizer_count=1,
                puzzle_stabilizer_hp=10,
            ),
        )
        fresh.on_enter(0)
        self.assertIn(
            "Shatter the optional stabilizer to skip one step.",
            fresh._playtest_identifier_detail(0),
        )

    def test_solved_plate_camp_pulse_damages_lingering_player(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="staggered_plates",
                objective_label="Glyph",
                objective_entity_count=4,
                puzzle_reinforcement_count=2,
                puzzle_stall_duration_ms=10000,  # keep stall reaction inert
                puzzle_camp_pulse_damage=3,
                puzzle_camp_pulse_interval_ms=500,
                puzzle_camp_pulse_grace_ms=400,
                puzzle_camp_pulse_radius=40,
            ),
        )
        room.on_enter(0)

        plate_one_config = next(
            config
            for config in room.objective_entity_configs
            if config.get("kind") == "pressure_plate" and config.get("telegraph_text") == "1"
        )
        plate_one = PressurePlate(plate_one_config)
        plate_one.update(0)
        plate_one.sync_player_overlap(SimpleNamespace(rect=plate_one.rect.copy()))
        self.assertTrue(plate_one_config["activated"])
        self.assertEqual(plate_one_config["activated_at"], 0)

        damage_log = []

        class _StubPlayer:
            def __init__(self, rect):
                self.rect = rect

            def take_damage(self, amount, damage_type=None):
                damage_log.append(amount)

        on_plate = _StubPlayer(plate_one.rect.copy())
        far_away = _StubPlayer(pygame.Rect(0, 0, 16, 16))

        # Inside grace window: no pulse yet.
        plate_one.update(200)
        self.assertFalse(plate_one.apply_player_pressure(on_plate))
        self.assertEqual(damage_log, [])

        # Outside the radius: still no pulse even after grace.
        plate_one.update(500)
        self.assertFalse(plate_one.apply_player_pressure(far_away))
        self.assertEqual(damage_log, [])

        # On the plate after grace expires: first pulse fires, HUD penalty
        # tagged as a camp pulse.
        plate_one.update(500)
        self.assertTrue(plate_one.apply_player_pressure(on_plate))
        self.assertEqual(damage_log, [3])
        controller = room._puzzle_controller()
        self.assertEqual(controller["last_penalty_at"], 500)
        self.assertEqual(controller["last_penalty_reason"], "camp")
        self.assertIn("Camp pulse", room.objective_hud_state(500)["label"])

        # Second call within the interval is gated.
        plate_one.update(800)
        self.assertFalse(plate_one.apply_player_pressure(on_plate))
        self.assertEqual(damage_log, [3])

        # Once the interval elapses another pulse lands.
        plate_one.update(1100)
        self.assertTrue(plate_one.apply_player_pressure(on_plate))
        self.assertEqual(damage_log, [3, 3])

    def test_solved_plate_camp_pulse_disabled_when_unconfigured(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_variant="staggered_plates",
                objective_label="Glyph",
                objective_entity_count=4,
            ),
        )
        room.on_enter(0)

        plate_one_config = next(
            config
            for config in room.objective_entity_configs
            if config.get("kind") == "pressure_plate" and config.get("telegraph_text") == "1"
        )
        plate_one = PressurePlate(plate_one_config)
        plate_one.update(0)
        plate_one.sync_player_overlap(SimpleNamespace(rect=plate_one.rect.copy()))

        damage_log = []

        class _StubPlayer:
            def __init__(self, rect):
                self.rect = rect

            def take_damage(self, amount, damage_type=None):
                damage_log.append(amount)

        plate_one.update(5000)
        self.assertFalse(
            plate_one.apply_player_pressure(_StubPlayer(plate_one.rect.copy()))
        )
        self.assertEqual(damage_log, [])

    def test_playtest_identifier_describes_holdout_circle_room(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=6000,
                holdout_zone_radius=96,
            ),
        )

        state = room.playtest_identifier_state(1000)

        self.assertTrue(state["visible"])
        self.assertEqual(state["title"], "Room: Survival Holdout")
        self.assertIn("holdout circle", state["detail"])

    def test_playtest_identifier_describes_stealth_failure_state(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "stealth_passage",
                objective_rule="avoid_alarm_zones",
                objective_entity_count=1,
            ),
        )
        room.objective_entity_configs[0]["triggered"] = True

        state = room.playtest_identifier_state(1000)

        self.assertEqual(state["title"], "Room: Stealth Passage")
        self.assertEqual(state["detail"], "Solve: Stealth failed. Clear the room to proceed.")

    def test_playtest_identifier_describes_standard_combat_room(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan(
                "standard_combat",
                objective_rule="clear_enemies",
                is_exit=False,
            ),
        )

        state = room.playtest_identifier_state(1000)

        self.assertEqual(state["title"], "Room: Standard Combat")
        self.assertEqual(state["detail"], "Solve: Defeat the enemies and continue onward.")

    def test_holdout_timer_unlocks_portal_after_duration(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("survival_holdout", objective_rule="holdout_timer", duration=5000),
        )

        room.on_enter(1000)
        room.update_objective(4000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertNotEqual(center_col, PORTAL)

        room.update_objective(7000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_holdout_timer_spawns_reinforcement_waves_before_completion(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("survival_holdout", objective_rule="holdout_timer", duration=6000, enemy_count_range=(1, 1)),
        )

        initial_count = len(room.enemy_configs)
        room.on_enter(1000)

        first_wave = room.update_objective(3200, [])
        self.assertEqual(first_wave["kind"], "spawn_enemies")
        self.assertEqual(len(first_wave["enemy_configs"]), 1)
        self.assertEqual(len(room.enemy_configs), initial_count + 1)
        self.assertIn("Wave 1/2", room.objective_hud_state(3200)["label"])

        second_wave = room.update_objective(5200, [])
        self.assertEqual(second_wave["kind"], "spawn_enemies")
        self.assertEqual(len(second_wave["enemy_configs"]), 2)
        self.assertEqual(len(room.enemy_configs), initial_count + 3)

        room.update_objective(7100, [])
        self.assertEqual(room.objective_status, "completed")

    def test_holdout_zone_pauses_timer_until_player_reenters_circle(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=6000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1, 2, 3),
                holdout_zone_radius=96,
            ),
        )

        room.on_enter(1000)
        self.assertEqual(room.objective_target_info((0, 0))[0], "Holdout")
        room.update_objective(4000, [])
        self.assertEqual(room.objective_status, "active")
        self.assertIn("Return to circle", room.objective_hud_state(4000)["label"])

        room.objective_entity_configs[0]["occupied"] = True
        room.update_objective(7000, [])
        self.assertEqual(room.objective_status, "active")

        room.update_objective(10000, [])
        self.assertEqual(room.objective_status, "completed")

    def test_holdout_stabilizer_delays_next_wave_and_becomes_optional_target(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=6000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1, 2),
                holdout_zone_radius=96,
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )
        holdout_zone["occupied"] = True

        self.assertEqual(room.objective_target_info((0, 0))[0], "Stabilizer")
        self.assertEqual(room.minimap_objective_marker(), ("holdout", "Stabilizer"))

        stabilizer_config = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_stabilizer"
        )
        stabilizer = HoldoutStabilizer(stabilizer_config)
        stabilizer.update(1500)
        stabilizer.sync_player_overlap(SimpleNamespace(rect=stabilizer.rect.copy()))

        self.assertTrue(stabilizer_config["used"])
        self.assertIn("Pressure eased", room.objective_hud_state(1500)["label"])
        self.assertIsNotNone(stabilizer._activation_flash_state())
        self.assertIsNone(room.update_objective(3200, []))

        delayed_wave = room.update_objective(4700, [])

        self.assertEqual(delayed_wave["kind"], "spawn_enemies")
        self.assertEqual(delayed_wave["source"], "holdout_timer")
        self.assertEqual(len(delayed_wave["enemy_configs"]), 1)

    def test_holdout_room_uses_metadata_label_for_targets(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=6000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1, 2),
                holdout_zone_radius=96,
                objective_label="Beacon",
            ),
        )

        self.assertEqual(room.objective_target_info((0, 0))[0], "Beacon")
        self.assertEqual(room.minimap_objective_marker(), ("holdout", "Beacon"))

    def test_holdout_metadata_tunes_relief_count_and_delay(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=6000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1, 2),
                holdout_zone_radius=96,
                holdout_relief_count=2,
                holdout_relief_delay_ms=1000,
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )
        holdout_zone["occupied"] = True
        stabilizers = [
            config for config in room.objective_entity_configs if config["kind"] == "holdout_stabilizer"
        ]

        self.assertEqual(len(stabilizers), 2)
        self.assertTrue(all(config["relief_delay_ms"] == 1000 for config in stabilizers))

        first_stabilizer = HoldoutStabilizer(stabilizers[0])
        first_stabilizer.update(1500)
        first_stabilizer.sync_player_overlap(SimpleNamespace(rect=first_stabilizer.rect.copy()))

        self.assertIsNone(room.update_objective(2800, []))

        delayed_wave = room.update_objective(4100, [])

        self.assertEqual(delayed_wave["kind"], "spawn_enemies")
        self.assertEqual(len(delayed_wave["enemy_configs"]), 1)

    def test_holdout_zone_radius_shrinks_to_contested_floor_over_duration(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=8000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1,),
                holdout_zone_radius=100,
                holdout_zone_min_radius=50,
                holdout_zone_shrink_ms=4000,
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )
        holdout_zone["occupied"] = True
        self.assertEqual(holdout_zone["radius"], 100)
        self.assertEqual(holdout_zone["initial_radius"], 100)
        self.assertEqual(holdout_zone["min_radius"], 50)

        # Halfway through the shrink window the radius should be ~halfway down.
        room.update_objective(3000, [])
        self.assertEqual(holdout_zone["radius"], 75)
        hud_label = room.objective_hud_state(3000)["label"]
        self.assertIn("Zone 75%", hud_label)

        # Past the shrink window the radius clamps at the contested-ground floor.
        room.update_objective(6000, [])
        self.assertEqual(holdout_zone["radius"], 50)
        self.assertIn("Zone 50%", room.objective_hud_state(6000)["label"])

        # Playtest hint surfaces the contested-ground rule.
        detail = room.playtest_identifier_state(6000)["detail"]
        self.assertIn("shrinks to contested ground", detail)

    def test_holdout_zone_without_shrink_keeps_initial_radius_and_hides_zone_suffix(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=6000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1, 2),
                holdout_zone_radius=96,
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )
        holdout_zone["occupied"] = True
        self.assertEqual(holdout_zone["radius"], 96)
        self.assertEqual(holdout_zone["min_radius"], 96)
        self.assertEqual(holdout_zone.get("shrink_ms", 0), 0)

        room.update_objective(4000, [])
        self.assertEqual(holdout_zone["radius"], 96)
        self.assertNotIn("Zone ", room.objective_hud_state(4000)["label"])

    def test_holdout_zone_migrates_between_anchors_and_pauses_progress(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=12000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1,),
                holdout_zone_radius=96,
                holdout_zone_migrate_ms=4000,
                holdout_zone_migration_offsets=((-5, -3), (5, 3)),
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )
        anchors = holdout_zone["anchors"]
        self.assertEqual(len(anchors), 3)
        self.assertEqual(holdout_zone["anchor_index"], 0)
        initial_pos = holdout_zone["pos"]

        # Park the player on the initial anchor and accumulate some progress.
        holdout_zone["occupied"] = True
        room.update_objective(3500, [])
        progress_before = room._holdout_progress_ms
        self.assertGreater(progress_before, 0)
        self.assertEqual(holdout_zone["pos"], initial_pos)
        self.assertEqual(holdout_zone["anchor_index"], 0)

        # Cross the first migration boundary: zone hops to the next anchor and
        # forcibly clears occupancy so the player has to chase it.
        room.update_objective(5500, [])
        self.assertEqual(holdout_zone["anchor_index"], 1)
        self.assertEqual(holdout_zone["pos"], anchors[1])
        self.assertFalse(holdout_zone["occupied"])
        self.assertEqual(holdout_zone["last_migrated_at"], 5500)

        # The HUD surfaces the migration banner and the "return to circle" hint.
        hud_label = room.objective_hud_state(5500)["label"]
        self.assertIn("Zone moved", hud_label)
        self.assertIn("Return to circle", hud_label)

        # Driving the HoldoutZone sprite proves the rect follows the new pos so
        # downstream overlap and minimap projections see the relocated anchor.
        sprite = HoldoutZone(holdout_zone)
        sprite.update(5500)
        self.assertEqual(sprite.rect.center, anchors[1])

        # While the player is outside the new circle, progress does not advance.
        progress_at_migration = room._holdout_progress_ms
        room.update_objective(7000, [])
        self.assertEqual(room._holdout_progress_ms, progress_at_migration)

        # The migration banner clears once the HUD-flash window elapses.
        self.assertNotIn("Zone moved", room.objective_hud_state(8000)["label"])

        # Crossing the second boundary cycles to the third anchor.
        room.update_objective(9200, [])
        self.assertEqual(holdout_zone["anchor_index"], 2)
        self.assertEqual(holdout_zone["pos"], anchors[2])

        # Playtest hint mentions migration when migrate_ms is configured.
        detail = room.playtest_identifier_state(9200)["detail"]
        self.assertIn("migrates between anchors", detail)

    def test_holdout_zone_migration_disabled_when_no_offsets(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=8000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1,),
                holdout_zone_radius=96,
                holdout_zone_migrate_ms=2000,
                holdout_zone_migration_offsets=(),
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )
        self.assertEqual(len(holdout_zone["anchors"]), 1)
        self.assertEqual(holdout_zone["migrate_ms"], 0)

        starting_pos = holdout_zone["pos"]
        room.update_objective(6000, [])
        self.assertEqual(holdout_zone["pos"], starting_pos)
        self.assertIsNone(holdout_zone["last_migrated_at"])
        detail = room.playtest_identifier_state(6000)["detail"]
        self.assertNotIn("migrates between anchors", detail)

    def test_holdout_stabilizer_anchors_zone_and_defers_migration(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=12000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1,),
                holdout_zone_radius=96,
                holdout_zone_migrate_ms=4000,
                holdout_zone_migration_offsets=((-5, -3), (5, 3)),
                holdout_relief_count=1,
                holdout_relief_delay_ms=1000,
                holdout_stabilizer_migration_delay_ms=4000,
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )
        stabilizer_config = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_stabilizer"
        )

        # The stabilizer config should know about both the zone and the anchor delay.
        self.assertIs(stabilizer_config["zone_config"], holdout_zone)
        self.assertEqual(stabilizer_config["migration_delay_ms"], 4000)
        self.assertEqual(holdout_zone["migration_baseline_ms"], 0)
        self.assertEqual(holdout_zone["migrations_completed"], 0)

        # Playtest hint mentions the anchor side benefit while a stabilizer is unused.
        detail = room.playtest_identifier_state(1000)["detail"]
        self.assertIn("anchor the current circle", detail)

        # Park the player on the initial anchor and use the stabilizer just before
        # the first migration boundary would normally fire (5000 ticks).
        holdout_zone["occupied"] = True
        stabilizer = HoldoutStabilizer(stabilizer_config)
        stabilizer.update(4500)
        stabilizer.sync_player_overlap(SimpleNamespace(rect=stabilizer.rect.copy()))

        self.assertTrue(stabilizer_config["used"])
        self.assertEqual(holdout_zone["migration_baseline_ms"], 4000)
        self.assertEqual(holdout_zone["migration_anchor_until"], 8500)

        # The HUD surfaces the new "Zone anchored" banner instead of a migration banner.
        hud_label = room.objective_hud_state(4500)["label"]
        self.assertIn("Zone anchored", hud_label)
        self.assertNotIn("Zone moved", hud_label)
        # Stabilizer also delays the next reinforcement wave (existing relief behavior).
        self.assertIn("Pressure eased", hud_label)

        # Past the original migration boundary, the zone should still be at anchor 0
        # because the baseline shift deferred the next migration by 4000 ms.
        room.update_objective(5500, [])
        self.assertEqual(holdout_zone["anchor_index"], 0)
        self.assertIsNone(holdout_zone["last_migrated_at"])

        # Migration should fire only once the deferred boundary is reached
        # (started_at=1000, baseline=4000, migrate_ms=4000 -> at 9000+).
        room.update_objective(9100, [])
        self.assertEqual(holdout_zone["anchor_index"], 1)
        self.assertEqual(holdout_zone["last_migrated_at"], 9100)

        # And the anchor banner clears once the grace window elapses.
        self.assertNotIn("Zone anchored", room.objective_hud_state(9000)["label"])

    def test_holdout_stabilizer_skips_migration_defer_when_room_has_no_migration(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=8000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1, 2),
                holdout_zone_radius=96,
                holdout_relief_count=1,
                holdout_relief_delay_ms=1000,
                holdout_stabilizer_migration_delay_ms=4000,
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )
        stabilizer_config = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_stabilizer"
        )

        # No migration anchors means the migration delay should not engage.
        self.assertEqual(holdout_zone["migrate_ms"], 0)

        holdout_zone["occupied"] = True
        stabilizer = HoldoutStabilizer(stabilizer_config)
        stabilizer.update(2000)
        stabilizer.sync_player_overlap(SimpleNamespace(rect=stabilizer.rect.copy()))

        self.assertTrue(stabilizer_config["used"])
        self.assertEqual(holdout_zone["migration_baseline_ms"], 0)
        self.assertIsNone(holdout_zone["migration_anchor_until"])
        # Existing relief behavior is unaffected.
        self.assertIn("Pressure eased", room.objective_hud_state(2000)["label"])

    def test_minimap_objective_status_reflects_holdout_zone_state(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=12000,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1,),
                holdout_zone_radius=96,
                holdout_zone_min_radius=48,
                holdout_zone_shrink_ms=8000,
                holdout_zone_migrate_ms=4000,
                holdout_zone_migration_offsets=((-5, -3), (5, 3)),
                holdout_relief_count=1,
                holdout_relief_delay_ms=1000,
                holdout_stabilizer_migration_delay_ms=4000,
            ),
        )

        room.on_enter(1000)
        holdout_zone = next(
            config for config in room.objective_entity_configs if config["kind"] == "holdout_zone"
        )

        # Fresh zone with full radius and no recent migration → no status hint.
        self.assertIsNone(room.minimap_objective_status(1000))

        # Partially shrunk zone surfaces the "shrinking" hint.
        holdout_zone["radius"] = 80
        self.assertEqual(room.minimap_objective_status(1500), "shrinking")

        # Fully contested floor surfaces the "contested" hint.
        holdout_zone["radius"] = holdout_zone["min_radius"]
        self.assertEqual(room.minimap_objective_status(2000), "contested")

        # An active anchor window dominates over shrink state.
        holdout_zone["migration_anchor_until"] = 5000
        self.assertEqual(room.minimap_objective_status(4500), "anchored")

        # A very recent migration dominates over the anchor window.
        holdout_zone["last_migrated_at"] = 4500
        self.assertEqual(room.minimap_objective_status(4500), "migrating")

        # No now_ticks → cannot evaluate transient banners; falls back to radius state.
        holdout_zone["last_migrated_at"] = None
        holdout_zone["migration_anchor_until"] = None
        self.assertEqual(room.minimap_objective_status(None), "contested")

    def test_minimap_objective_status_is_none_for_non_holdout_rooms(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "claim_relic",
                objective_rule="claim_relic_before_lockdown",
                duration=8000,
                enemy_count_range=(0, 0),
            ),
        )
        room.on_enter(1000)
        self.assertIsNone(room.minimap_objective_status(1500))

    def test_minimap_objective_status_reflects_active_role_for_role_chain_rituals(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                ritual_role_script=("summon", "pulse", "ward"),
                ritual_link_mode="role_chain",
            ),
        )
        configs = room.objective_entity_configs

        self.assertEqual(room.minimap_objective_status(0), "summon")
        configs[0]["destroyed"] = True
        self.assertEqual(room.minimap_objective_status(0), "pulse")
        configs[1]["destroyed"] = True
        self.assertEqual(room.minimap_objective_status(0), "ward")
        configs[2]["destroyed"] = True
        # All altars down → no active role to telegraph.
        self.assertIsNone(room.minimap_objective_status(0))

    def test_minimap_objective_status_is_none_for_non_role_chain_ritual_rooms(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(0, 0),
                objective_entity_count=3,
                ritual_role_script=("ward", "pulse", "summon"),
                ritual_link_mode="ward_shields_others",
            ),
        )
        # Ward-shielding mode does not opt into the role telegraph (no ordered chain).
        self.assertIsNone(room.minimap_objective_status(0))

    def test_terminal_reward_chest_stays_locked_until_holdout_completes(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "survival_holdout",
                objective_rule="holdout_timer",
                duration=5000,
                guaranteed_chest=True,
                reward_tier="finale_bonus",
                chest_locked_until_complete=True,
            ),
        )

        room.on_enter(1000)
        self.assertFalse(room.allows_chest_open(2000))

        room.update_objective(7000, [])
        self.assertTrue(room.allows_chest_open(7000))

    def test_escort_room_unlocks_portal_when_escort_reaches_exit(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_protection", objective_rule="escort_to_exit", enemy_count_range=(1, 1)),
        )

        room.on_enter(1000)
        self.assertEqual(room.objective_target_info((0, 0))[0], "Escort")
        self.assertEqual(room.minimap_objective_marker(), ("escort", "Escort"))
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Protect Escort HP 26/26")

        room.objective_entity_configs[0]["reached_exit"] = True
        room.update_objective(2000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_escort_completion_emits_despawn_escort_update(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_protection", objective_rule="escort_to_exit", enemy_count_range=(1, 1)),
        )
        room.on_enter(1000)
        room.objective_entity_configs[0]["reached_exit"] = True
        update = room.update_objective(2000, [])
        self.assertEqual(update["kind"], "despawn_escort")
        self.assertIn("pos", update)
        self.assertTrue(room.objective_entity_configs[0]["destroyed"])
        # Idempotent: a subsequent update should not re-emit.
        followup = room.update_objective(2100, [])
        self.assertIsNone(followup)

    def test_bomb_carrier_completion_emits_despawn_escort_update(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_bomb_carrier", objective_rule="escort_bomb_to_exit", enemy_count_range=(1, 1)),
        )
        room.on_enter(1000)
        room.objective_entity_configs[0]["reached_exit"] = True
        update = room.update_objective(2000, [])
        self.assertEqual(update["kind"], "despawn_escort")
        self.assertIn("pos", update)
        self.assertTrue(room.objective_entity_configs[0]["destroyed"])

    def test_escort_room_uses_metadata_profile(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "escort_protection",
                objective_rule="escort_to_exit",
                enemy_count_range=(1, 1),
                objective_label="Pilgrim",
                objective_spawn_offset=(-3, 0),
                objective_max_hp=30,
                objective_move_speed=1.5,
                objective_guide_radius=120,
                objective_exit_radius=18,
                objective_damage_cooldown_ms=750,
            ),
        )

        escort = room.objective_entity_configs[0]
        self.assertEqual(escort["label"], "Pilgrim")
        self.assertEqual(escort["pos"], _offsets_to_pixels(((-3, 0),))[0])
        self.assertEqual(escort["max_hp"], 30)
        self.assertEqual(escort["speed"], 1.5)
        self.assertEqual(escort["guide_radius"], 120)
        self.assertEqual(escort["exit_radius"], 18)
        self.assertEqual(escort["damage_cooldown_ms"], 750)
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Protect Pilgrim HP 30/30")

    def test_escort_room_test_entry_repositions_escort_near_player(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_protection", objective_rule="escort_to_exit", enemy_count_range=(1, 1)),
        )

        player_position = _offsets_to_pixels(((0, 0),))[0]
        room.on_enter(1000, player_position=player_position, room_test=True)

        self.assertEqual(room.objective_entity_configs[0]["pos"], _offsets_to_pixels(((1, 0),))[0])

    def test_escort_room_entry_repositions_escort_next_to_player(self):
        room = Room(
            {"top": False, "bottom": False, "left": True, "right": False},
            is_exit=True,
            room_plan=_plan("escort_protection", objective_rule="escort_to_exit", enemy_count_range=(1, 1)),
        )

        room.on_enter(1000, entry_direction="left", player_position=(60, 300))

        # Entering from the left: preferred spawn is 1 tile toward the entry
        # door (col 0), but that is a DOOR tile and not walkable.  The next
        # preferred offset is perpendicular up (col 1, row 6) = pixel (60, 260).
        self.assertEqual(room.objective_entity_configs[0]["pos"], (60, 260))

    def test_escort_room_goal_marker_matches_exit_portal_center(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_protection", objective_rule="escort_to_exit", enemy_count_range=(1, 1)),
        )

        escort = room.objective_entity_configs[0]

        self.assertEqual(escort["goal_pos"], room.portal_center_pixel())
        self.assertEqual(escort["goal_radius"], escort["exit_radius"])

    def test_escort_npc_draw_overlay_highlights_goal_position(self):
        surface = pygame.Surface((ROOM_COLS * TILE_SIZE, ROOM_ROWS * TILE_SIZE), pygame.SRCALPHA)
        escort = EscortNPC(
            {
                "pos": (60, 300),
                "current_hp": 26,
                "max_hp": 26,
                "goal_pos": (100, 300),
                "goal_radius": 24,
                "requires_safe_path": False,
                "waiting_for_clearance": False,
                "destroyed": False,
                "reached_exit": False,
            }
        )

        escort.draw_overlay(surface)

        self.assertNotEqual(surface.get_at((80, 300)), pygame.Color(0, 0, 0, 0))

    def test_escort_room_allows_cleanup_completion_if_escort_falls(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_protection", objective_rule="escort_to_exit", enemy_count_range=(1, 1)),
        )

        room.on_enter(1000)
        room.objective_entity_configs[0]["destroyed"] = True
        room.update_objective(1500, [object()])

        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertNotEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "escort_down")
        self.assertIsNone(room.objective_target_info((0, 0)))
        self.assertEqual(room.objective_hud_state(1500)["label"], "Objective: Escort down, clear the room")

        room.update_objective(2000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_puzzle_room_uses_metadata_layout_and_label(self):
        offsets = ((-2, -1), (2, 1))
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "puzzle_gated_doors",
                objective_rule="charge_plates",
                enemy_count_range=(1, 1),
                objective_label="Rune",
                objective_entity_count=2,
                objective_layout_offsets=offsets,
                objective_trigger_padding=20,
            ),
        )

        self.assertEqual(room.objective_target_info((0, 0))[0], "Rune")
        self.assertEqual(room.minimap_objective_marker(), ("puzzle", "Rune"))
        self.assertEqual([config["pos"] for config in room.objective_entity_configs], list(_offsets_to_pixels(offsets)))
        self.assertTrue(all(config["label"] == "Rune" for config in room.objective_entity_configs))
        self.assertTrue(all(config["trigger_padding"] == 20 for config in room.objective_entity_configs))

    def test_bomb_carrier_room_requires_safe_path_before_advancing(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_bomb_carrier", objective_rule="escort_bomb_to_exit", enemy_count_range=(1, 1)),
        )

        room.on_enter(1000)
        self.assertEqual(room.objective_target_info((0, 0))[0], "Carrier")
        self.assertEqual(room.minimap_objective_marker(), ("escort", "Carrier"))
        self.assertFalse(room.escort_allows_advance([object()]))

        room.objective_entity_configs[0]["waiting_for_clearance"] = True
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Clear a safe lane HP 30/30")

        room.objective_entity_configs[0]["reached_exit"] = True
        room.update_objective(2000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_bomb_carrier_room_allows_cleanup_completion_if_carrier_falls(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_bomb_carrier", objective_rule="escort_bomb_to_exit", enemy_count_range=(1, 1)),
        )

        room.on_enter(1000)
        room.objective_entity_configs[0]["destroyed"] = True
        room.update_objective(1500, [object()])

        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertNotEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "carrier_down")
        self.assertEqual(room.objective_hud_state(1500)["label"], "Objective: Carrier down, clear the room")

        room.update_objective(2000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_puzzle_room_unlocks_portal_after_all_seals_are_charged(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("puzzle_gated_doors", objective_rule="charge_plates", enemy_count_range=(1, 1)),
        )

        room.on_enter(1000)
        self.assertEqual(room.objective_target_info((0, 0))[0], "Seal")
        self.assertEqual(room.minimap_objective_marker(), ("puzzle", "Seal"))
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Charge seals 0/3 | Next 1")

        for config in room.objective_entity_configs:
            config["activated"] = True

        room.update_objective(2000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_resource_race_unlocks_portal_when_relic_is_secured_in_time(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "resource_race",
                objective_rule="claim_relic_before_lockdown",
                duration=5000,
                guaranteed_chest=True,
                enemy_count_range=(1, 1),
                objective_variant="relic_cache",
            ),
        )

        room.on_enter(1000)
        self.assertTrue(room.allows_chest_open(5500))
        self.assertEqual(room.objective_target_info((0, 0))[0], "Relic")
        self.assertEqual(room.minimap_objective_marker(), ("relic", "Relic"))
        self.assertEqual(room.objective_hud_state(1500)["label"], "Objective: Secure the relic 4.5s")

        room.notify_chest_opened(3000)
        room.update_objective(3200, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")
        self.assertEqual(room.objective_target_info((0, 0))[0], "Exit")

    def test_resource_race_allows_reclaim_after_rivals_steal_back_the_relic(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "resource_race",
                objective_rule="claim_relic_before_lockdown",
                duration=5000,
                guaranteed_chest=True,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1,),
                objective_variant="relic_cache",
            ),
        )

        room.on_enter(1000)
        room.notify_chest_opened(2500)

        self.assertIsNone(room.update_objective(2600, [object()]))
        self.assertIn("Objective: Escape with the relic", room.objective_hud_state(2600)["label"])
        self.assertIn("Rival reclaim", room.objective_hud_state(2600)["label"])

        update = room.update_objective(4600, [object()])

        self.assertEqual(update, {"kind": "restore_chest"})
        self.assertFalse(room.chest_looted)
        self.assertEqual(room.objective_status, "active")
        self.assertTrue(room.allows_chest_open(7000))
        self.assertEqual(room.objective_target_info((0, 0))[0], "Relic")
        self.assertEqual(room.objective_hud_state(4600)["label"], "Objective: Reclaim the relic")
        self.assertEqual(
            room._playtest_identifier_detail(4600),
            "Solve: Rival claimants stole the relic back. Interrupt them and reclaim it.",
        )

        room.notify_chest_opened(4700)
        room.update_objective(4800, [])

        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_resource_race_forfeits_relic_after_timer_and_requires_cleanup(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "resource_race",
                objective_rule="claim_relic_before_lockdown",
                duration=5000,
                guaranteed_chest=True,
                enemy_count_range=(1, 1),
                objective_variant="relic_cache",
            ),
        )

        room.on_enter(1000)
        self.assertFalse(room.allows_chest_open(6000))

        update = room.update_objective(6000, [object()])
        self.assertEqual(update, {"kind": "forfeit_chest"})
        self.assertTrue(room.chest_looted)
        self.assertEqual(room.objective_status, "lost_race")
        self.assertIsNone(room.objective_target_info((0, 0)))
        self.assertEqual(room.objective_hud_state(6000)["label"], "Objective: Relic lost, clear the room")

        room.update_objective(6500, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_resource_race_spawns_claimant_pressure_waves_before_lockdown(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "resource_race",
                objective_rule="claim_relic_before_lockdown",
                duration=6000,
                guaranteed_chest=True,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1, 2),
                objective_variant="relic_cache",
            ),
        )

        initial_enemy_count = len(room.enemy_configs)
        room.on_enter(1000)

        update = room.update_objective(3000, [object()])

        self.assertEqual(update["kind"], "spawn_enemies")
        self.assertEqual(update["source"], "resource_race")
        self.assertEqual(len(update["enemy_configs"]), 1)
        self.assertEqual(len(room.enemy_configs), initial_enemy_count + 1)
        self.assertIn("Claim pressure 1/2", room.objective_hud_state(3000)["label"])
        self.assertEqual(
            room._playtest_identifier_detail(3000),
            "Solve: Reach the relic before rival claimants finish locking it down.",
        )

    def test_resource_race_variant_updates_relic_labels(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "resource_race",
                objective_rule="claim_relic_before_lockdown",
                duration=5000,
                guaranteed_chest=True,
                objective_variant="heartstone_shard",
            ),
        )

        self.assertEqual(room.objective_target_info((0, 0))[0], "Heartstone")
        self.assertEqual(room.minimap_objective_marker(), ("relic", "Heartstone"))
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Secure the heartstone 5.0s")

    def test_stealth_passage_locks_exit_and_spawns_reinforcements_after_alarm(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "stealth_passage",
                objective_rule="avoid_alarm_zones",
                enemy_count_range=(0, 0),
            ),
        )

        room.on_enter(1000)
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_target_info((0, 0))[0], "Exit")
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Slip through unseen")

        room.objective_entity_configs[0]["triggered"] = True
        update = room.update_objective(2000, [])
        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertEqual(len(update["enemy_configs"]), 2)
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertNotEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "alarm")
        self.assertEqual(room.objective_hud_state(2000)["label"], "Objective: Alarm raised, clear the room")

        room.update_objective(2500, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_stealth_passage_uses_metadata_layout_and_radius(self):
        offsets = ((-3, 0), (3, 0))
        patrol_offset = (0, 3)
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "stealth_passage",
                objective_rule="avoid_alarm_zones",
                enemy_count_range=(0, 0),
                objective_label="Ward",
                objective_entity_count=2,
                objective_layout_offsets=offsets,
                objective_patrol_offset=patrol_offset,
                objective_radius=48,
            ),
        )

        self.assertEqual(len(room.objective_entity_configs), 2)
        self.assertEqual([config["pos"] for config in room.objective_entity_configs], list(_offsets_to_pixels(offsets)))
        self.assertTrue(all(config["label"] == "Ward" for config in room.objective_entity_configs))
        self.assertTrue(all(config["radius"] == 48 for config in room.objective_entity_configs))
        first_pos = _offsets_to_pixels((offsets[0],))[0]
        self.assertEqual(
            room.objective_entity_configs[0]["patrol_points"],
            (
                first_pos,
                (first_pos[0], first_pos[1] + 3 * TILE_SIZE),
                (first_pos[0], first_pos[1] - 3 * TILE_SIZE),
            ),
        )

    def test_alarm_beacon_patrols_and_uses_forward_vision_cone(self):
        beacon = AlarmBeacon(
            {
                "kind": "alarm_beacon",
                "label": "Alarm",
                "pos": (100, 100),
                "radius": 60,
                "triggered": False,
                "patrol_points": ((100, 100), (160, 100)),
                "patrol_cycle_ms": 2000,
                "vision_angle_deg": 70,
            }
        )

        beacon.update(500)
        self.assertGreater(beacon.rect.centerx, 100)

        behind_player = SimpleNamespace(rect=pygame.Rect(0, 0, 16, 16))
        behind_player.rect.center = (90, beacon.rect.centery)
        self.assertFalse(beacon.sync_player_overlap(behind_player))
        self.assertFalse(beacon._config["triggered"])

        ahead_player = SimpleNamespace(rect=pygame.Rect(0, 0, 16, 16))
        ahead_player.rect.center = (170, beacon.rect.centery)
        self.assertTrue(beacon.sync_player_overlap(ahead_player))
        self.assertTrue(beacon._config["triggered"])

    def test_stealth_passage_search_phase_grants_brief_escape_window_before_lockdown(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "stealth_passage",
                objective_rule="avoid_alarm_zones",
                enemy_count_range=(0, 0),
                duration=2000,
            ),
        )

        room.on_enter(1000)
        room.objective_entity_configs[0]["triggered"] = True

        update = room.update_objective(2000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]

        self.assertIsNone(update)
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "search")
        self.assertIn("Search phase", room.objective_hud_state(2000)["label"])
        self.assertEqual(
            room._playtest_identifier_detail(2000),
            "Solve: Detection is rising. Reach the exit or avoid any more alarms before lockdown starts.",
        )

        room.objective_entity_configs[1]["triggered"] = True
        update = room.update_objective(2500, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]

        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertEqual(len(update["enemy_configs"]), 2)
        self.assertNotEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "alarm")

    def test_stealth_passage_spawns_bonus_cache_when_undetected(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "stealth_passage",
                objective_rule="avoid_alarm_zones",
                enemy_count_range=(0, 0),
                chest_spawn_chance=0.0,
                reward_tier="standard",
            ),
        )

        room.chest_pos = None
        update = room.update_objective(1500, [])

        self.assertEqual(update["kind"], "spawn_reward_chest")
        self.assertEqual(update["reward_tier"], "branch_bonus")
        self.assertIsNotNone(room.chest_pos)
        self.assertEqual(room.chest_reward_tier(), "branch_bonus")
        self.assertIn("Bonus cache armed", room.objective_hud_state(1500)["label"])
        self.assertEqual(
            room._playtest_identifier_detail(1500),
            "Solve: Avoid the alarm beacons, claim the bonus cache, and slip through unseen.",
        )

    def test_stealth_passage_forfeits_bonus_cache_after_alarm(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "stealth_passage",
                objective_rule="avoid_alarm_zones",
                enemy_count_range=(0, 0),
                duration=2000,
                guaranteed_chest=True,
                reward_tier="branch_bonus",
            ),
        )

        room.update_objective(1200, [])
        room.objective_entity_configs[0]["triggered"] = True

        update = room.update_objective(2000, [])

        self.assertEqual(update["kind"], "forfeit_chest")
        self.assertTrue(room.chest_looted)
        self.assertEqual(room.objective_status, "search")

    def test_stealth_passage_escape_variant_keeps_portal_open_after_alarm(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "stealth_passage",
                objective_rule="avoid_alarm_zones",
                objective_variant="escape_on_alarm",
                enemy_count_range=(0, 0),
            ),
        )

        room.on_enter(1000)
        room.objective_entity_configs[0]["triggered"] = True
        update = room.update_objective(2000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]

        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "alarm")
        self.assertEqual(
            room.objective_hud_state(2000)["label"],
            "Objective: Alarm raised, escape or clear pursuit",
        )
        self.assertEqual(
            room._playtest_identifier_detail(2000),
            "Solve: Stealth failed. Break through the pursuit or sprint for the exit while it stays open.",
        )

    def test_stealth_passage_release_variant_reopens_portal_after_alarm_delay(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "stealth_passage",
                objective_rule="avoid_alarm_zones",
                objective_variant="release_on_alarm",
                enemy_count_range=(0, 0),
                duration=2000,
            ),
        )

        room.on_enter(1000)
        room.objective_entity_configs[0]["triggered"] = True
        room.objective_entity_configs[1]["triggered"] = True

        update = room.update_objective(2000, [object()])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertNotEqual(center_col, PORTAL)
        self.assertEqual(room.objective_hud_state(2000)["label"], "Objective: Alarm raised 2.0s | Hold out")
        self.assertEqual(
            room._playtest_identifier_detail(2000),
            "Solve: Stealth failed. Hold out until the seals release, or clear the room early.",
        )

        room.update_objective(4100, [object()])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "escape")
        self.assertEqual(room.objective_hud_state(4100)["label"], "Objective: Alarm raised, seals broken | Escape")
        self.assertEqual(
            room._playtest_identifier_detail(4100),
            "Solve: Stealth failed. The seals broke. Escape before pursuit corners you, or clear the room.",
        )

    def test_ritual_objective_unlocks_portal_after_altars_are_destroyed(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("ritual_disruption", objective_rule="destroy_altars", enemy_count_range=(1, 1)),
        )

        room.on_enter(1000)
        room.update_objective(1500, [object()])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertNotEqual(center_col, PORTAL)
        self.assertEqual(room.remaining_objective_entities(), 3)

        for config in room.objective_entity_configs:
            config["destroyed"] = True
        room.update_objective(2000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")

    def test_ritual_summon_altars_spawn_defenders_on_destruction(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=4,
                ritual_role_script=("summon", "pulse", "ward", "summon"),
                ritual_reinforcement_count=2,
            ),
        )

        initial_enemy_count = len(room.enemy_configs)
        self.assertEqual(len(room.objective_entity_configs), 4)
        self.assertIn("2 summoners", room.objective_hud_state(1000)["label"])

        room.objective_entity_configs[0]["destroyed"] = True
        update = room.update_objective(1500, [object()])

        self.assertEqual(update["kind"], "spawn_enemies")
        self.assertEqual(update["source"], "ritual_reaction")
        self.assertEqual(len(update["enemy_configs"]), 2)
        self.assertEqual(len(room.enemy_configs), initial_enemy_count + 2)

    def test_ritual_ward_links_shield_other_altars_until_ward_falls(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=3,
                ritual_role_script=("ward", "pulse", "summon"),
                ritual_link_mode="ward_shields_others",
            ),
        )

        altar_configs = room.objective_entity_configs
        self.assertFalse(altar_configs[0]["invulnerable"])
        self.assertTrue(altar_configs[1]["invulnerable"])
        self.assertTrue(altar_configs[2]["invulnerable"])

        altar_configs[0]["destroyed"] = True
        room.update_objective(1500, [object()])

        self.assertFalse(altar_configs[1]["invulnerable"])
        self.assertFalse(altar_configs[2]["invulnerable"])

    def test_ritual_role_chain_enforces_kill_order_from_role_script(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=3,
                ritual_role_script=("summon", "pulse", "ward"),
                ritual_link_mode="role_chain",
            ),
        )

        altar_configs = room.objective_entity_configs
        # Indices map 1:1 to roles for a 3-altar/3-role script.
        self.assertEqual(altar_configs[0]["role"], "summon")
        self.assertEqual(altar_configs[1]["role"], "pulse")
        self.assertEqual(altar_configs[2]["role"], "ward")

        # Initial state: only the first script role (summon) is vulnerable.
        self.assertFalse(altar_configs[0]["invulnerable"])
        self.assertTrue(altar_configs[1]["invulnerable"])
        self.assertTrue(altar_configs[2]["invulnerable"])

        # HUD and playtest hint reflect the active role.
        hud_label = room.objective_hud_state(0)["label"]
        self.assertIn("Break summon first", hud_label)
        self.assertIn("Break the summon", room.playtest_identifier_state(0)["detail"])

        # Down the summon altar — pulse is now the active role.
        altar_configs[0]["destroyed"] = True
        room.update_objective(1000, [object()])
        self.assertFalse(altar_configs[1]["invulnerable"])
        self.assertTrue(altar_configs[2]["invulnerable"])
        self.assertIn("Break pulse first", room.objective_hud_state(1000)["label"])

        # Down pulse — ward is now exposed and no other role shields remain.
        altar_configs[1]["destroyed"] = True
        room.update_objective(2000, [object()])
        self.assertFalse(altar_configs[2]["invulnerable"])
        # No more shielded altars → no shield suffix.
        self.assertNotIn("shielded", room.objective_hud_state(2000)["label"])

    def test_ritual_wrong_strike_spawns_reinforcements_and_flashes_hud(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=3,
                ritual_role_script=("summon", "pulse", "ward"),
                ritual_link_mode="role_chain",
                ritual_wrong_strike_spawn_count=1,
            ),
        )

        altar_configs = room.objective_entity_configs
        # Altar at index 1 (pulse) is shielded by role_chain.
        self.assertTrue(altar_configs[1]["invulnerable"])
        shielded = AltarAnchor(altar_configs[1])
        initial_enemies = len(room.enemy_configs)

        # Strike a shielded altar — take_damage rejects damage but stamps the
        # wrong-struck flag so the room can punish the player.
        damaged = shielded.take_damage(5)
        self.assertFalse(damaged)
        self.assertTrue(altar_configs[1].get("wrong_struck_pending"))

        update = room.update_objective(1500, [object()])

        self.assertIsNotNone(update)
        self.assertEqual(update["kind"], "spawn_enemies")
        self.assertEqual(update["source"], "ritual_wrong_strike")
        self.assertEqual(len(update["enemy_configs"]), 1)
        self.assertEqual(len(room.enemy_configs), initial_enemies + 1)
        self.assertIsNotNone(room._ritual_last_wrong_strike_at)
        self.assertIn("Wrong target", room.objective_hud_state(1500)["label"])
        # Flag was consumed.
        self.assertFalse(altar_configs[1].get("wrong_struck_pending"))

    def test_ritual_wrong_strike_throttled_within_cooldown(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=3,
                ritual_role_script=("summon", "pulse", "ward"),
                ritual_link_mode="role_chain",
                ritual_wrong_strike_spawn_count=1,
            ),
        )

        altar_configs = room.objective_entity_configs
        shielded = AltarAnchor(altar_configs[1])
        shielded.take_damage(5)
        first = room.update_objective(1000, [object()])
        self.assertIsNotNone(first)
        enemies_after_first = len(room.enemy_configs)

        # Second wrong strike inside the cooldown window: stamp consumed but
        # no fresh spawn.
        shielded.take_damage(5)
        second = room.update_objective(1500, [object()])
        self.assertIsNone(second)
        self.assertEqual(len(room.enemy_configs), enemies_after_first)

    def test_ritual_wrong_strike_does_not_fire_on_legitimate_kill(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=3,
                ritual_role_script=("summon", "pulse", "ward"),
                ritual_link_mode="role_chain",
                ritual_wrong_strike_spawn_count=1,
            ),
        )

        altar_configs = room.objective_entity_configs
        # Index 0 (summon) is the active role and is vulnerable.
        self.assertFalse(altar_configs[0]["invulnerable"])
        active = AltarAnchor(altar_configs[0])
        initial_enemies = len(room.enemy_configs)
        active.take_damage(5)

        self.assertFalse(altar_configs[0].get("wrong_struck_pending", False))
        update = room.update_objective(1000, [object()])
        # update may be None or a ritual_reaction update, but never a wrong-strike spawn.
        if update is not None:
            self.assertNotEqual(update.get("source"), "ritual_wrong_strike")
        self.assertIsNone(room._ritual_last_wrong_strike_at)
        # No wrong-strike enemy spawned.
        self.assertEqual(len(room.enemy_configs), initial_enemies)

    def test_ritual_role_glyph_color_is_bright_for_active_role_and_dim_for_shielded(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=3,
                ritual_role_script=("summon", "pulse", "ward"),
                ritual_link_mode="role_chain",
            ),
        )

        configs = room.objective_entity_configs
        from objective_entities import _ALTAR_ROLE_COLORS

        summon_bright, _ = _ALTAR_ROLE_COLORS["summon"]
        pulse_bright, pulse_dim = _ALTAR_ROLE_COLORS["pulse"]
        ward_bright, ward_dim = _ALTAR_ROLE_COLORS["ward"]

        # Initial state: only the summon role is vulnerable; pulse + ward dim.
        summon = AltarAnchor(configs[0])
        pulse = AltarAnchor(configs[1])
        ward = AltarAnchor(configs[2])
        self.assertEqual(summon.role_glyph_color(), summon_bright)
        self.assertEqual(pulse.role_glyph_color(), pulse_dim)
        self.assertEqual(ward.role_glyph_color(), ward_dim)

        # After the summon altar falls, pulse becomes bright while ward stays dim.
        configs[0]["destroyed"] = True
        room.update_objective(1000, [object()])
        self.assertEqual(pulse.role_glyph_color(), pulse_bright)
        self.assertEqual(ward.role_glyph_color(), ward_dim)

    def test_ritual_role_glyph_color_returns_none_when_role_missing(self):
        config = {
            "kind": "altar",
            "pos": (160, 120),
            "max_hp": 30,
            "current_hp": 30,
            "variant_id": "spore_totem",
        }
        altar = AltarAnchor(config)
        self.assertIsNone(altar.role_glyph_color())

    def test_ritual_role_glyph_renders_above_altar_when_role_present(self):
        config = {
            "kind": "altar",
            "pos": (160, 120),
            "max_hp": 30,
            "current_hp": 30,
            "variant_id": "spore_totem",
            "role": "summon",
        }
        altar = AltarAnchor(config)
        surface = pygame.Surface((320, 240))
        altar.draw_overlay(surface)
        # Sample a pixel just above the altar where the glyph triangle sits.
        cx, _ = altar.rect.center
        sample_y = altar.rect.top - 9
        pixel = surface.get_at((cx, sample_y))[:3]
        # The glyph is bright orange-red for "summon"; the surface starts black.
        self.assertNotEqual(pixel, (0, 0, 0))

    def test_ritual_pulse_window_variant_only_takes_damage_during_active_pulse(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=1,
                objective_variant="frost_obelisk",
                ritual_role_script=("pulse",),
                ritual_link_mode="pulse_gates_damage",
            ),
        )

        altar_config = room.objective_entity_configs[0]
        altar = AltarAnchor(altar_config)

        closed_tick = altar_config["pulse_active_ms"] + 10
        altar.update(closed_tick)
        current_hp = altar.current_hp
        altar.take_damage(5)

        self.assertFalse(altar_config["window_vulnerable"])
        self.assertEqual(altar.current_hp, current_hp)
        self.assertIn("Wait for pulse", room.objective_hud_state(closed_tick)["label"])

        altar.update(0)
        current_hp = altar.current_hp
        altar.take_damage(5)

        self.assertTrue(altar_config["window_vulnerable"])
        self.assertEqual(altar.current_hp, current_hp - 5)
        self.assertIn("Strike on pulse 1 open", room.objective_hud_state(0)["label"])
        self.assertEqual(
            room._playtest_identifier_detail(0),
            "Solve: Strike the ritual obelisks only while their pulse windows are active.",
        )

    def test_ritual_completion_reveals_reliquary_payoff(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                chest_spawn_chance=0.0,
                ritual_payoff_kind="reveal_reliquary",
                ritual_payoff_label="Reliquary",
            ),
        )

        room.chest_pos = None
        for config in room.objective_entity_configs:
            config["destroyed"] = True

        update = room.update_objective(2000, [])

        self.assertEqual(update["kind"], "spawn_reward_chest")
        self.assertIsNotNone(room.chest_pos)
        self.assertEqual(room.objective_status, "completed")
        self.assertEqual(room.objective_target_info((0, 0))[0], "Reliquary")
        self.assertEqual(room.minimap_objective_marker(), ("relic", "Reliquary"))
        self.assertEqual(room.objective_hud_state(2000)["label"], "Objective: Claim revealed reliquary")

    def test_timed_extraction_unlocks_portal_after_chest_is_opened(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "timed_extraction",
                objective_rule="loot_then_timer",
                duration=8000,
                guaranteed_chest=True,
            ),
        )

        room.on_enter(1000)
        room.update_objective(1500, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertNotEqual(center_col, PORTAL)

        room.chest_looted = True
        room.notify_chest_opened(2000)
        room.update_objective(2500, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "escape")

    def test_timed_extraction_overtime_spawns_reinforcements_once(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "timed_extraction",
                objective_rule="loot_then_timer",
                duration=5000,
                guaranteed_chest=True,
                enemy_count_range=(1, 1),
            ),
        )

        initial_count = len(room.enemy_configs)
        room.on_enter(1000)
        room.chest_looted = True
        room.notify_chest_opened(2000)

        update = room.update_objective(8001, [])
        self.assertEqual(room.objective_status, "overtime")
        self.assertEqual(update["kind"], "spawn_reinforcements")
        self.assertEqual(len(update["enemy_configs"]), 2)
        self.assertEqual(len(room.enemy_configs), initial_count + 2)

        second_update = room.update_objective(9000, [])
        self.assertIsNone(second_update)

    def test_timed_extraction_spawns_pursuit_wave_before_overtime(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "timed_extraction",
                objective_rule="loot_then_timer",
                duration=6000,
                guaranteed_chest=True,
                enemy_count_range=(1, 1),
                scripted_wave_sizes=(1, 2),
            ),
        )

        initial_count = len(room.enemy_configs)
        room.on_enter(1000)
        room.chest_looted = True
        room.notify_chest_opened(2000)

        update = room.update_objective(4000, [])

        self.assertEqual(update["kind"], "spawn_enemies")
        self.assertEqual(update["source"], "timed_extraction")
        self.assertEqual(len(update["enemy_configs"]), 1)
        self.assertEqual(len(room.enemy_configs), initial_count + 1)
        self.assertEqual(room.objective_status, "collapse")
        self.assertIn("Pursuit 1/2", room.objective_hud_state(4000)["label"])
        self.assertIn("Route closing", room.objective_hud_state(4000)["label"])
        self.assertEqual(
            room._playtest_identifier_detail(4000),
            "Solve: Reach the exit with the relic while pursuit waves close the route behind you and preserve the payout.",
        )

    def test_timed_extraction_seals_portal_during_collapse_until_pursuit_is_cleared(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "timed_extraction",
                objective_rule="loot_then_timer",
                duration=6000,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
                scripted_wave_sizes=(1, 2),
            ),
        )

        room.on_enter(1000)
        room.chest_looted = True
        room.notify_chest_opened(2000)

        update = room.update_objective(4000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]

        self.assertEqual(update["kind"], "spawn_enemies")
        self.assertEqual(room.objective_status, "collapse")
        self.assertNotEqual(center_col, PORTAL)

        room.update_objective(4500, [object()])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(room.objective_status, "collapse")
        self.assertNotEqual(center_col, PORTAL)

        room.update_objective(5000, [])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(room.objective_status, "escape")
        self.assertEqual(center_col, PORTAL)

    def test_timed_extraction_clean_clear_exposes_completion_bonus(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "timed_extraction",
                objective_rule="loot_then_timer",
                duration=6000,
                guaranteed_chest=True,
                reward_tier="branch_bonus",
            ),
        )

        room.on_enter(1000)
        room.chest_looted = True
        room.notify_chest_opened(2000)

        room.update_objective(3000, [])

        self.assertIn("Preserve payout", room.objective_hud_state(3000)["label"])
        self.assertEqual(
            room._playtest_identifier_detail(3000),
            "Solve: Reach the exit with the relic before time runs out to preserve the bonus payout.",
        )
        self.assertEqual(room.claim_timed_extraction_completion_bonus(), 14)
        self.assertEqual(room.claim_timed_extraction_completion_bonus(), 0)

    def test_timed_extraction_overtime_cuts_completion_bonus(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "timed_extraction",
                objective_rule="loot_then_timer",
                duration=5000,
                guaranteed_chest=True,
                reward_tier="finale_bonus",
            ),
        )

        room.on_enter(1000)
        room.chest_looted = True
        room.notify_chest_opened(2000)
        room.update_objective(8001, [])

        self.assertEqual(
            room.objective_hud_state(8001)["label"],
            "Objective: Escape under pressure | Payout reduced",
        )
        self.assertEqual(
            room._playtest_identifier_detail(8001),
            "Solve: Escape under pressure before reinforcements overwhelm you. Overtime cuts the extraction payout.",
        )
        self.assertEqual(room.claim_timed_extraction_completion_bonus(), 0)

    def test_timed_extraction_bonus_state_reports_availability(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "timed_extraction",
                objective_rule="loot_then_timer",
                duration=5000,
                guaranteed_chest=True,
                reward_tier="branch_bonus",
            ),
        )
        # Before chest looted: amount fixed by tier, but not yet available.
        state = room.timed_extraction_bonus_state()
        self.assertIsNotNone(state)
        self.assertFalse(state["available"])
        self.assertEqual(state["amount"], 14)

        room.on_enter(1000)
        room.notify_chest_opened(2000)
        room.update_objective(2500, [])
        state = room.timed_extraction_bonus_state()
        self.assertTrue(state["available"])
        self.assertEqual(state["amount"], 14)

        # Once claimed, no longer available.
        room.claim_timed_extraction_completion_bonus()
        state = room.timed_extraction_bonus_state()
        self.assertFalse(state["available"])

    def test_timed_extraction_bonus_state_none_for_other_rules(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_protection", objective_rule="escort_to_exit", enemy_count_range=(1, 1)),
        )
        self.assertIsNone(room.timed_extraction_bonus_state())

    def test_objective_compass_hint_reflects_pending_room_goal(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "timed_extraction",
                objective_rule="loot_then_timer",
                duration=5000,
                guaranteed_chest=True,
            ),
        )

        self.assertEqual(room.objective_target_info((100, 100))[0], "Relic")
        room.chest_looted = True
        room.notify_chest_opened(2000)
        self.assertEqual(room.objective_target_info((100, 100))[0], "Exit")

    def test_ritual_room_tracks_spatial_altar_targets(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("ritual_disruption", objective_rule="destroy_altars", enemy_count_range=(1, 1)),
        )

        label, target_pos = room.objective_target_info((0, 0))

        self.assertEqual(label, "Altar")
        self.assertIn(target_pos, {config["pos"] for config in room.objective_entity_configs})

    def test_ritual_variant_updates_target_label_and_hud_pulse_state(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=RoomPlan(
                position=(0, 0),
                depth=2,
                path_kind="main_path",
                is_exit=True,
                template=RoomTemplate(
                    room_id="ritual_disruption",
                    display_name="Spore Totem Grove",
                    objective_kind="ritual",
                    combat_pressure="mid_high",
                    decision_complexity="high",
                    topology_role="mid_run",
                    min_depth=0,
                    max_depth=None,
                    branch_preference="either",
                    generation_weight=1,
                    enabled=True,
                    implementation_status="prototype",
                    objective_variant="spore_totem",
                    notes="",
                ),
                terrain_type="mud",
                enemy_count_range=(1, 1),
                enemy_type_weights=(50, 35, 15),
                objective_rule="destroy_altars",
                clear_center=True,
            ),
        )

        label, _target_pos = room.objective_target_info((0, 0))

        self.assertEqual(label, "Totem")
        self.assertEqual(room.minimap_objective_marker(), ("altar", "Totem"))
        self.assertIn("Pulse active", room.objective_hud_state(0)["label"])

    def test_timed_extraction_variant_updates_relic_labels(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=RoomPlan(
                position=(0, 0),
                depth=2,
                path_kind="main_path",
                is_exit=True,
                template=RoomTemplate(
                    room_id="timed_extraction",
                    display_name="Mire Cache Extraction",
                    objective_kind="timed_extraction",
                    combat_pressure="mid",
                    decision_complexity="mid_high",
                    topology_role="mid_run",
                    min_depth=0,
                    max_depth=None,
                    branch_preference="either",
                    generation_weight=1,
                    enabled=True,
                    implementation_status="prototype",
                    objective_variant="mire_cache",
                    notes="",
                ),
                terrain_type="mud",
                enemy_count_range=(1, 1),
                enemy_type_weights=(50, 35, 15),
                objective_rule="loot_then_timer",
                objective_duration_ms=5000,
                guaranteed_chest=True,
                chest_spawn_chance=1.0,
                clear_center=True,
            ),
        )

        self.assertEqual(room.objective_target_info((0, 0))[0], "Cache")
        self.assertEqual(room.minimap_objective_marker(), ("relic", "Cache"))
        self.assertEqual(room.objective_hud_state(0)["label"], "Objective: Secure the cache")


class SporeTotemWardRegressionTests(unittest.TestCase):
    def _make_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "ritual_disruption",
                objective_rule="destroy_altars",
                enemy_count_range=(1, 1),
                objective_entity_count=3,
                ritual_role_script=("summon", "pulse", "ward"),
                ritual_link_mode="ward_shields_others",
            ),
        )

    def test_other_altars_take_damage_after_ward_destroyed_via_take_damage(self):
        room = self._make_room()
        configs = room.objective_entity_configs
        # ward is index 2 (role_script "summon,pulse,ward")
        self.assertEqual(configs[2]["role"], "ward")
        ward = AltarAnchor(configs[2])
        summon = AltarAnchor(configs[0])

        # Initially the non-ward altars are shielded.
        self.assertTrue(configs[0]["invulnerable"])
        self.assertFalse(summon.take_damage(99))

        # Kill the ward through its sprite (matches in-game flow).
        ward.take_damage(ward.max_hp + 100)
        self.assertTrue(configs[2]["destroyed"])

        # update_objective should refresh ritual links so other altars become vulnerable.
        room.update_objective(1500, [object()])

        self.assertFalse(configs[0]["invulnerable"])
        previous_hp = summon.current_hp
        damaged = summon.take_damage(3)
        # damaged is True only when killed; check HP decreased instead.
        self.assertLess(summon.current_hp, previous_hp)


class HeartstoneClaimTests(unittest.TestCase):
    def _make_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "resource_race",
                objective_rule="claim_relic_before_lockdown",
                duration=6800,
                guaranteed_chest=True,
                enemy_count_range=(1, 1),
                objective_variant="heartstone_shard",
            ),
        )

    def test_chest_open_spawns_heartstone_and_keeps_portal_sealed(self):
        room = self._make_room()
        room.on_enter(1000)
        # No heartstone before the chest is opened.
        self.assertIsNone(room.heartstone_state())

        room.notify_chest_opened(2000)
        state = room.heartstone_state()
        self.assertIsNotNone(state)
        self.assertFalse(state["carried"])
        self.assertFalse(state["delivered"])
        # Portal stays sealed for the heartstone variant.
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertNotEqual(center_col, PORTAL)

        # First update_objective tick after pickup emits the spawn update.
        update = room.update_objective(2100, [])
        self.assertEqual(update["kind"], "spawn_heartstone")
        self.assertEqual(update["position"], state["pos"])
        # Subsequent ticks do not re-emit the spawn.
        followup = room.update_objective(2200, [])
        self.assertIsNone(followup)

    def test_completion_requires_delivery_not_just_enemy_clear(self):
        room = self._make_room()
        room.on_enter(1000)
        room.notify_chest_opened(2000)
        room.update_objective(2100, [])  # consume spawn update

        # Even with no enemies, no delivery -> not completed, portal sealed.
        room.update_objective(2200, [])
        self.assertNotEqual(room.objective_status, "completed")
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertNotEqual(center_col, PORTAL)

        # Pickup + deliver flips status to completed and unseals portal.
        room.notify_heartstone_picked_up()
        room.notify_heartstone_delivered()
        room.update_objective(2300, [])
        self.assertEqual(room.objective_status, "completed")
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)

    def test_dropped_heartstone_can_be_picked_up_again(self):
        room = self._make_room()
        room.on_enter(1000)
        room.notify_chest_opened(2000)
        room.update_objective(2100, [])

        room.notify_heartstone_picked_up()
        self.assertTrue(room.heartstone_state()["carried"])

        # Damage drop happens at player position (60, 80).
        room.notify_heartstone_dropped((60, 80))
        state = room.heartstone_state()
        self.assertFalse(state["carried"])
        self.assertEqual(state["pos"], (60, 80))

        # Re-pickup is allowed.
        room.notify_heartstone_picked_up()
        self.assertTrue(room.heartstone_state()["carried"])

    def test_non_heartstone_resource_race_unaffected(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan(
                "resource_race",
                objective_rule="claim_relic_before_lockdown",
                duration=5000,
                guaranteed_chest=True,
                enemy_count_range=(1, 1),
                objective_variant="relic_cache",
            ),
        )
        room.on_enter(1000)
        room.notify_chest_opened(2000)
        # Portal active immediately for non-heartstone variant.
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertIsNone(room.heartstone_state())


class SecondaryObjectiveSeamTests(unittest.TestCase):
    def _make_room(self):
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=_plan("escort_protection", objective_rule="escort_to_exit", enemy_count_range=(1, 1)),
        )

    def test_mark_primary_failed_engages_secondary_and_seals_doors(self):
        room = self._make_room()
        room.on_enter(1000)
        self.assertFalse(room._secondary_objective_active)
        room._mark_primary_failed("escort_down")
        self.assertTrue(room._secondary_objective_active)
        self.assertEqual(room.objective_status, "escort_down")
        self.assertFalse(room._portal_active)
        self.assertTrue(room.doors_sealed)

    def test_check_secondary_objective_completes_when_enemies_clear(self):
        room = self._make_room()
        room.on_enter(1000)
        room._mark_primary_failed("escort_down")
        completed = room._check_secondary_objective(1500, [object()])
        self.assertFalse(completed)
        self.assertEqual(room.objective_status, "escort_down")
        completed = room._check_secondary_objective(1600, [])
        self.assertTrue(completed)
        self.assertEqual(room.objective_status, "completed")
        self.assertTrue(room._portal_active)

    def test_check_secondary_objective_noop_when_primary_still_active(self):
        room = self._make_room()
        room.on_enter(1000)
        # Primary still alive: secondary helper must not complete the room.
        completed = room._check_secondary_objective(1100, [])
        self.assertFalse(completed)
        self.assertNotEqual(room.objective_status, "completed")


if __name__ == "__main__":
    unittest.main()
