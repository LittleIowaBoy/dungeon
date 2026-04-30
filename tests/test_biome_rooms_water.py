"""Phase 0 scaffold — Water biome (Sunken Ruins) room template registration.

Validates that the four water-biome templates exist in the content DB with
the expected scaffold-state defaults (disabled, weight 0, prototype) so
later slices can flip them on individually.
"""
import unittest

import content_db


WATER_ROOM_IDS = (
    "water_river_room",
    "water_waterfall_room",
    "water_spirit_room",
    "water_tide_lord_arena",
)


class WaterTemplateScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.by_id = {
            t["room_id"]: t for t in content_db.BASE_ROOM_TEMPLATES
        }

    def test_all_four_templates_registered(self):
        for room_id in WATER_ROOM_IDS:
            self.assertIn(room_id, self.by_id, f"Missing scaffold: {room_id}")

    def test_scaffolds_disabled_with_zero_weight(self):
        for room_id in WATER_ROOM_IDS:
            template = self.by_id[room_id]
            self.assertEqual(template["enabled"], 0,
                             f"{room_id} should start disabled")
            self.assertEqual(template["generation_weight"], 0,
                             f"{room_id} should start with zero weight")
            self.assertEqual(template["implementation_status"], "prototype")

    def test_finale_template_metadata(self):
        arena = self.by_id["water_tide_lord_arena"]
        self.assertEqual(arena["topology_role"], "finale")
        self.assertEqual(arena["min_depth"], 2)
        self.assertEqual(arena["terminal_preference"], "prefer")
        self.assertEqual(arena["repeat_cooldown"], 0)
        self.assertTrue(arena.get("guaranteed_chest", False))

    def test_spirit_room_min_depth(self):
        # Water spirits are tougher content, so gate to depth >= 2 like
        # the analogous Earth deep-cuts (boulder/cave-in/burrower).
        self.assertEqual(self.by_id["water_spirit_room"]["min_depth"], 2)


if __name__ == "__main__":
    unittest.main()
