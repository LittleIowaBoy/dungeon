import unittest

from dungeon_config import get_dungeon, get_level


class DungeonConfigTests(unittest.TestCase):
    def test_dungeons_expose_distinct_biome_terrain_and_names(self):
        self.assertEqual(get_dungeon("mud_caverns")["terrain_type"], "mud")
        self.assertEqual(get_dungeon("frozen_depths")["terrain_type"], "ice")
        self.assertEqual(get_dungeon("sunken_ruins")["terrain_type"], "water")
        self.assertEqual(get_dungeon("mud_caverns")["name"], "Mud Caverns")
        self.assertEqual(get_dungeon("frozen_depths")["name"], "Frozen Depths")
        self.assertEqual(get_dungeon("sunken_ruins")["name"], "Sunken Ruins")

    def test_biomes_use_distinct_progression_profiles(self):
        ice_mid = get_level("frozen_depths", 2)
        water_late = get_level("sunken_ruins", 3)
        mud_late = get_level("mud_caverns", 3)

        self.assertEqual(ice_mid["pacing_profile"], "frontloaded")
        self.assertEqual(ice_mid["branch_length_range"], (2, 2))
        self.assertEqual(water_late["branch_count_range"], (2, 3))
        self.assertEqual(water_late["pacing_profile"], "backloaded")
        self.assertEqual(mud_late["branch_count_range"], (2, 2))
        self.assertNotEqual(ice_mid["enemy_type_weights"], water_late["enemy_type_weights"])