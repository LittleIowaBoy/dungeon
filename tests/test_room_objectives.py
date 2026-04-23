import unittest
from types import SimpleNamespace

import pygame

from objective_entities import AltarAnchor, EscortNPC, HoldoutStabilizer, PressurePlate, TrapCrusher, TrapLaneSwitch, TrapSweeper, TrapVentLane
from room import PORTAL, Room
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
    holdout_relief_count=0,
    holdout_relief_delay_ms=0,
    ritual_role_script=(),
    ritual_reinforcement_count=0,
    ritual_link_mode="",
    ritual_payoff_kind="",
    ritual_payoff_label="",
    objective_label="",
    objective_layout_offsets=(),
    objective_spawn_offset=None,
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
        holdout_relief_count=holdout_relief_count,
        holdout_relief_delay_ms=holdout_relief_delay_ms,
        ritual_role_script=ritual_role_script,
        ritual_reinforcement_count=ritual_reinforcement_count,
        ritual_link_mode=ritual_link_mode,
        ritual_payoff_kind=ritual_payoff_kind,
        ritual_payoff_label=ritual_payoff_label,
        objective_label=objective_label,
        objective_layout_offsets=objective_layout_offsets,
        objective_spawn_offset=objective_spawn_offset,
        objective_radius=objective_radius,
        objective_trigger_padding=objective_trigger_padding,
        objective_max_hp=objective_max_hp,
        objective_move_speed=objective_move_speed,
        objective_guide_radius=objective_guide_radius,
        objective_exit_radius=objective_exit_radius,
        objective_damage_cooldown_ms=objective_damage_cooldown_ms,
        puzzle_reinforcement_count=puzzle_reinforcement_count,
        puzzle_stall_duration_ms=puzzle_stall_duration_ms,
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

        self.assertEqual(update, {"kind": "upgrade_reward_chest", "reward_tier": "finale_bonus"})
        self.assertEqual(room.chest_reward_tier(), "finale_bonus")
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Challenge lane Bottom | Reward upgraded")

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

        self.assertEqual(room.objective_entity_configs[0]["pos"], (100, 300))

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
                objective_radius=48,
            ),
        )

        self.assertEqual(len(room.objective_entity_configs), 2)
        self.assertEqual([config["pos"] for config in room.objective_entity_configs], list(_offsets_to_pixels(offsets)))
        self.assertTrue(all(config["label"] == "Ward" for config in room.objective_entity_configs))
        self.assertTrue(all(config["radius"] == 48 for config in room.objective_entity_configs))

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
            "Solve: Reach the exit with the relic while pursuit waves close the route behind you.",
        )

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


if __name__ == "__main__":
    unittest.main()