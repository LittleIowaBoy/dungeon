import unittest

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
    )


class RoomObjectiveTests(unittest.TestCase):
    def test_trap_gauntlet_room_plan_removes_enemies_and_guarantees_chest(self):
        room = Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=False,
            room_plan=_plan(
                "trap_gauntlet",
                objective_rule="immediate",
                is_exit=False,
                guaranteed_chest=True,
                enemy_count_range=(0, 0),
            ),
        )

        self.assertEqual(room.enemy_configs, [])
        self.assertIsNotNone(room.chest_pos)

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
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Protect Escort HP 22/22")

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
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Clear a safe lane HP 26/26")

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
        self.assertEqual(room.objective_hud_state(1000)["label"], "Objective: Charge seals 0/3")

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
        room.update_objective(3200, [object()])
        center_col = room.grid[len(room.grid) // 2][len(room.grid[0]) // 2]
        self.assertEqual(center_col, PORTAL)
        self.assertEqual(room.objective_status, "completed")
        self.assertEqual(room.objective_target_info((0, 0))[0], "Exit")

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