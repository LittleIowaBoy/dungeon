import os
import random
import unittest

import pygame

from dungeon import Dungeon
from dungeon_config import get_dungeon
from dungeon_topology import TopologyPlanner


class TopologyPlannerTests(unittest.TestCase):
    def test_planner_builds_main_path_and_branch_rooms_without_overlap(self):
        plan = TopologyPlanner(path_length=7, radius=9).build()

        self.assertEqual(len(plan.main_path), 8)
        self.assertEqual(plan.main_path[0], (0, 0))
        self.assertEqual(plan.exit_pos, plan.main_path[-1])
        self.assertEqual(len(set(plan.rooms)), len(plan.rooms))

        branch_rooms = [room for room in plan.rooms.values() if room.path_kind == "branch"]
        self.assertGreaterEqual(len(branch_rooms), 1)
        self.assertGreaterEqual(len(plan.branch_paths), 1)

        for room in plan.rooms.values():
            self.assertTrue(any(room.doors.values()))

    def test_planner_assigns_path_metadata_and_terminal_rewards(self):
        plan = TopologyPlanner(path_length=7, radius=9).build()

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
            room for room in plan.rooms.values() if room.path_kind == "branch" and room.is_path_terminal
        ]
        self.assertGreaterEqual(len(branch_terminal_rooms), 1)
        for room in branch_terminal_rooms:
            self.assertEqual(room.reward_tier, "branch_bonus")

    def test_planner_marks_exit_as_main_path_finale(self):
        plan = TopologyPlanner(path_length=12, radius=14).build()

        exit_room = plan.rooms[plan.exit_pos]

        self.assertTrue(exit_room.is_exit)
        self.assertEqual(exit_room.path_kind, "main_path")
        self.assertEqual(exit_room.depth, len(plan.main_path) - 1)

    def test_planner_honors_explicit_branch_shape_settings(self):
        plan = TopologyPlanner(
            path_length=12,
            radius=14,
            branch_count_range=(2, 2),
            branch_length_range=(1, 1),
            pacing_profile="backloaded",
            rng=random.Random(0),
        ).build()

        self.assertEqual(len(plan.branch_paths), 2)
        self.assertTrue(all(len(path) == 2 for path in plan.branch_paths))
        self.assertTrue(all(plan.rooms[path[0]].depth >= 3 for path in plan.branch_paths))


class DungeonTopologyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_dungeon_uses_planned_doors_and_preseeds_branches(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"), level_index=2)

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

    def test_dungeon_uses_level_branch_generation_settings(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"), level_index=3)

        self.assertEqual(dungeon._branch_count_range, (2, 2))
        self.assertEqual(dungeon._branch_length_range, (1, 2))
        self.assertEqual(dungeon._pacing_profile, "backloaded")

    def test_path_terminal_rooms_spawn_guaranteed_reward_chests(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"), level_index=4)

        terminal_positions = [
            pos for pos, room in dungeon._topology_plan.rooms.items() if room.is_path_terminal
        ]

        self.assertGreaterEqual(len(terminal_positions), 2)
        for pos in terminal_positions:
            self.assertIsNotNone(dungeon.rooms[pos].chest_pos)
            self.assertNotEqual(dungeon.room_plans[pos].reward_tier, "standard")

    def test_minimap_marks_locked_exit_as_objective_room(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"), level_index=4)
        dungeon.current_pos = dungeon.exit_pos
        dungeon.visited.add(dungeon.exit_pos)
        dungeon.current_room._set_portal_active(False)

        snapshot = dungeon.minimap_snapshot()
        exit_entry = next(room for room in snapshot["rooms"] if room["pos"] == dungeon.exit_pos)

        self.assertEqual(exit_entry["kind"], "objective")

    def test_minimap_snapshot_includes_current_room_objective_marker(self):
        dungeon = Dungeon(get_dungeon("mud_caverns"), level_index=4)
        dungeon.current_room.minimap_objective_marker = lambda: ("relic", "Cache")

        snapshot = dungeon.minimap_snapshot()
        current_entry = next(room for room in snapshot["rooms"] if room["pos"] == dungeon.current_pos)

        self.assertEqual(current_entry["objective_marker"], ("relic", "Cache"))


if __name__ == "__main__":
    unittest.main()