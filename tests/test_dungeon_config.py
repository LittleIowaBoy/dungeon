import unittest

from dungeon_config import get_dungeon, get_difficulty_preset, DIFFICULTY_PRESETS


class DungeonConfigTests(unittest.TestCase):
    def test_dungeons_expose_distinct_biome_terrain_and_names(self):
        self.assertEqual(get_dungeon("mud_caverns")["terrain_type"], "mud")
        self.assertEqual(get_dungeon("frozen_depths")["terrain_type"], "ice")
        self.assertEqual(get_dungeon("sunken_ruins")["terrain_type"], "water")
        self.assertEqual(get_dungeon("mud_caverns")["name"], "Mud Caverns")
        self.assertEqual(get_dungeon("frozen_depths")["name"], "Frozen Depths")
        self.assertEqual(get_dungeon("sunken_ruins")["name"], "Sunken Ruins")

    def test_dungeons_expose_run_profile_with_required_fields(self):
        for dungeon_id in ("mud_caverns", "frozen_depths", "sunken_ruins"):
            profile = get_dungeon(dungeon_id)["run_profile"]
            self.assertIn("enemy_count_range", profile)
            self.assertIn("enemy_type_weights", profile)
            self.assertIn("pacing_profile", profile)

    def test_difficulty_presets_expose_required_fields(self):
        for difficulty in ("default", "medium", "hard"):
            preset = get_difficulty_preset(difficulty)
            self.assertIn("grid_size", preset)
            self.assertIn("min_distance", preset)
            self.assertIn("enemy_count_scale", preset)

    def test_difficulty_preset_grid_sizes_increase_with_difficulty(self):
        sizes = [get_difficulty_preset(d)["grid_size"] for d in ("default", "medium", "hard")]
        self.assertLess(sizes[0], sizes[1])
        self.assertLess(sizes[1], sizes[2])