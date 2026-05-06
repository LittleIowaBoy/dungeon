import os
import random
import unittest
from types import SimpleNamespace

import pygame

from dungeon import Dungeon
from dungeon_config import get_dungeon
from dungeon_topology import TopologyPlanner
from objective_entities import TrapLaneSwitch


class TopologyPlannerTests(unittest.TestCase):
    def test_planner_builds_connected_rooms_with_start_and_exit(self):
        plan = TopologyPlanner(grid_size=7, min_distance=3).build()

        # start and exit are distinct, sufficiently separated
        self.assertNotEqual(plan.start_pos, plan.exit_pos)
        manhattan = abs(plan.start_pos[0] - plan.exit_pos[0]) + abs(plan.start_pos[1] - plan.exit_pos[1])
        self.assertGreaterEqual(manhattan, 3)

        # main path starts at start_pos, ends at exit_pos
        self.assertEqual(plan.main_path[0], plan.start_pos)
        self.assertEqual(plan.exit_pos, plan.main_path[-1])

        # no duplicate room positions
        self.assertEqual(len(set(plan.rooms)), len(plan.rooms))

        # every room has at least one open door
        for room in plan.rooms.values():
            self.assertTrue(any(room.doors.values()))

    def test_planner_assigns_path_metadata_and_terminal_rewards(self):
        # Use a fixed seed and branch_count_range to guarantee at least one branch.
        plan = TopologyPlanner(
            grid_size=7, min_distance=3,
            branch_count_range=(1, 2),
            rng=random.Random(0),
        ).build()

        for index, pos in enumerate(plan.main_path):
            room = plan.rooms[pos]
            self.assertEqual(room.path_id, "main")
            self.assertEqual(room.path_index, index)
            self.assertEqual(room.path_length, len(plan.main_path))
            self.assertGreaterEqual(room.path_progress, 0.0)
            self.assertLessEqual(room.path_progress, 1.0)

        exit_room = plan.rooms[plan.exit_pos]
        self.assertTrue(exit_room.is_path_terminal)
        self.assertEqual(exit_room.reward_tier, "finale_bonus")

        branch_terminal_rooms = [
            room for room in plan.rooms.values()
            if room.path_kind == "branch" and room.is_path_terminal
        ]
        self.assertGreaterEqual(len(branch_terminal_rooms), 1)
        for room in branch_terminal_rooms:
            self.assertEqual(room.reward_tier, "branch_bonus")

    def test_planner_records_bfs_distance_metadata(self):
        plan = TopologyPlanner(grid_size=7, min_distance=3).build()

        # start room has distance 0
        self.assertEqual(plan.rooms[plan.start_pos].distance_from_start, 0)
        # exit room has distance_to_exit 0
        self.assertEqual(plan.rooms[plan.exit_pos].distance_to_exit, 0)
        # exit room has max distance_from_start in main path
        exit_d = plan.rooms[plan.exit_pos].distance_from_start
        for pos in plan.main_path:
            self.assertLessEqual(plan.rooms[pos].distance_from_start, exit_d + len(plan.main_path))

    def test_planner_difficulty_band_increases_toward_exit(self):
        plan = TopologyPlanner(grid_size=7, min_distance=3, rng=random.Random(42)).build()

        start_band = plan.rooms[plan.start_pos].difficulty_band
        exit_band = plan.rooms[plan.exit_pos].difficulty_band
        self.assertEqual(start_band, 0)
        self.assertEqual(exit_band, 4)

    def test_planner_marks_exit_as_main_path_finale(self):
        plan = TopologyPlanner(grid_size=9, min_distance=5).build()

        exit_room = plan.rooms[plan.exit_pos]

        self.assertTrue(exit_room.is_exit)
        self.assertEqual(exit_room.path_kind, "main_path")
        self.assertEqual(exit_room.depth, len(plan.main_path) - 1)

    def test_planner_honors_explicit_branch_shape_settings(self):
        plan = TopologyPlanner(
            grid_size=9,
            min_distance=4,
            branch_count_range=(2, 2),
            branch_length_range=(1, 1),
            pacing_profile="backloaded",
            rng=random.Random(0),
        ).build()

        self.assertEqual(len(plan.branch_paths), 2)
        self.assertTrue(all(len(path) == 2 for path in plan.branch_paths))
        self.assertTrue(all(plan.rooms[path[0]].depth >= 3 for path in plan.branch_paths))

    def test_planner_enforces_min_distance_separation(self):
        for seed in range(20):
            plan = TopologyPlanner(grid_size=5, min_distance=3, rng=random.Random(seed)).build()
            dist = abs(plan.start_pos[0] - plan.exit_pos[0]) + abs(plan.start_pos[1] - plan.exit_pos[1])
            self.assertGreaterEqual(dist, 3, msg=f"seed={seed}")

    def test_all_rooms_are_bfs_reachable_from_start(self):
        """Every room must be reachable via door connections from start_pos."""
        from collections import deque
        plan = TopologyPlanner(grid_size=7, min_distance=3).build()

        # Build adjacency from doors
        reachable = {plan.start_pos}
        queue = deque([plan.start_pos])
        while queue:
            pos = queue.popleft()
            room = plan.rooms[pos]
            from settings import DIR_OFFSETS
            for direction, has_door in room.doors.items():
                if not has_door:
                    continue
                ox, oy = DIR_OFFSETS[direction]
                neighbor = (pos[0] + ox, pos[1] + oy)
                if neighbor in plan.rooms and neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

        self.assertEqual(reachable, set(plan.rooms.keys()))


class DungeonTopologyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        # Dungeon construction uses the global RNG; seed for determinism
        # so layout-shape assertions (branch counts, terminals) don't
        # depend on test execution order.
        self._rng_state = random.getstate()
        random.seed(0)

    def tearDown(self):
        random.setstate(self._rng_state)

    def test_dungeon_uses_planned_doors_and_preseeds_branches(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"))

        branch_positions = [
            pos for pos, room in dungeon._topology_plan.rooms.items() if room.path_kind == "branch"
        ]
        self.assertGreaterEqual(len(branch_positions), 1)

        for pos, topology_room in dungeon._topology_plan.rooms.items():
            self.assertIn(pos, dungeon.rooms)
            self.assertEqual(dungeon.rooms[pos].doors, topology_room.doors)
            self.assertEqual(dungeon.room_plans[pos].path_kind, topology_room.path_kind)
            self.assertEqual(dungeon.room_plans[pos].path_id, topology_room.path_id)
            self.assertEqual(dungeon.room_plans[pos].reward_tier, topology_room.reward_tier)

    def test_dungeon_uses_run_profile_branch_generation_settings(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"))

        self.assertIsNotNone(dungeon._branch_count_range)
        self.assertIsNotNone(dungeon._branch_length_range)
        self.assertIsNotNone(dungeon._pacing_profile)

    def test_second_to_last_main_path_room_is_boss_slot(self):
        # Use a fixed seed so the path length is deterministic.
        plan = TopologyPlanner(
            grid_size=7, min_distance=3, rng=random.Random(0)
        ).build()

        main_path = plan.main_path
        self.assertGreaterEqual(len(main_path), 3)

        boss_slot_pos = main_path[-2]
        boss_room = plan.rooms[boss_slot_pos]
        self.assertTrue(boss_room.is_boss_slot, "second-to-last main-path room should be boss slot")
        self.assertFalse(boss_room.is_path_terminal)
        self.assertFalse(boss_room.is_exit)
        self.assertEqual(boss_room.reward_tier, "finale_bonus")

        # Only the designated position should be marked.
        for pos, room in plan.rooms.items():
            if pos == boss_slot_pos:
                self.assertTrue(room.is_boss_slot)
            else:
                self.assertFalse(room.is_boss_slot)

    def test_path_terminal_rooms_spawn_guaranteed_reward_chests(self):
        # Use a fixed-seed TopologyPlanner with branch_count_range=(1,2) so
        # this test always has at least two terminal rooms (exit + 1 branch
        # terminal) without depending on random layout luck.
        plan = TopologyPlanner(
            grid_size=5, min_distance=3,
            branch_count_range=(1, 2),
            rng=random.Random(0),
        ).build()

        terminal_positions = [
            pos for pos, room in plan.rooms.items() if room.is_path_terminal
        ]
        self.assertGreaterEqual(len(terminal_positions), 2)

        # Build a real Dungeon so we can verify chests and reward_tier.
        dungeon = Dungeon(get_dungeon("mud_caverns"))
        for pos, room in dungeon._topology_plan.rooms.items():
            if room.is_path_terminal:
                self.assertIsNotNone(dungeon.rooms[pos].chest_pos)
                self.assertNotEqual(dungeon.room_plans[pos].reward_tier, "standard")

    def test_boss_slot_room_always_spawns_boss_template(self):
        # Verify that over several random runs the boss slot always gets the
        # biome boss template (earth_golem_arena for mud_caverns).
        for seed in range(20):
            dungeon = Dungeon(get_dungeon("mud_caverns"))
            main_path = dungeon._topology_plan.main_path
            if len(main_path) < 3:
                continue  # degenerate path — skip
            boss_pos = main_path[-2]
            plan = dungeon.room_plans[boss_pos]
            self.assertEqual(
                plan.room_id,
                "earth_golem_arena",
                msg=f"boss slot should be earth_golem_arena (seed={seed})",
            )
            # Boss slot must receive a finale-level reward tier.
            self.assertEqual(plan.reward_tier, "finale_bonus")

    def test_trap_gauntlet_reward_upgrade_persists_across_room_reload(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"))
        trap_position = next(
            (pos for pos, plan in dungeon.room_plans.items() if plan.room_id == "trap_gauntlet"),
            None,
        )
        if trap_position is None:
            self.skipTest("No trap_gauntlet room in this random dungeon layout")
        dungeon.current_pos = trap_position
        dungeon._load_room_sprites()

        room = dungeon.current_room
        starting_tier = room.chest_reward_tier()
        challenge_switch = next(
            config
            for config in room.objective_entity_configs
            if config["kind"] == "trap_lane_switch" and config["lane_index"] == 2
        )
        player = SimpleNamespace(rect=TrapLaneSwitch(challenge_switch).rect.copy())
        TrapLaneSwitch(challenge_switch).sync_player_overlap(player)
        room.update_objective(1000, [])

        dungeon._load_room_sprites()

        expected_tier = "finale_bonus" if starting_tier == "branch_bonus" else "branch_bonus"
        self.assertEqual(room.chest_reward_tier(), expected_tier)
        chest = next(iter(dungeon.chest_group))
        self.assertEqual(chest.reward_tier, expected_tier)

    def test_minimap_marks_locked_exit_as_objective_room(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"))
        dungeon.current_pos = dungeon.exit_pos
        dungeon.visited.add(dungeon.exit_pos)
        dungeon.current_room._set_portal_active(False)

        snapshot = dungeon.minimap_snapshot()
        exit_entry = next(room for room in snapshot["rooms"] if room["pos"] == dungeon.exit_pos)

        self.assertEqual(exit_entry["kind"], "objective")

    def test_minimap_snapshot_includes_current_room_objective_marker(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"))
        dungeon.current_room.minimap_objective_marker = lambda: ("relic", "Cache")

        snapshot = dungeon.minimap_snapshot()
        current_entry = next(room for room in snapshot["rooms"] if room["pos"] == dungeon.current_pos)

        self.assertEqual(current_entry["objective_marker"], ("relic", "Cache"))


if __name__ == "__main__":
    unittest.main()