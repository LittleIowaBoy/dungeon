import unittest

from room_test_catalog import build_room_test_plan, load_room_test_entries


class RoomTestCatalogTests(unittest.TestCase):
    def test_load_room_test_entries_keeps_base_rooms_and_adds_biome_variants(self):
        entries = load_room_test_entries()

        standard_entries = [entry for entry in entries if entry.room_id == "standard_combat"]
        ritual_entries = [entry for entry in entries if entry.room_id == "ritual_disruption"]

        self.assertEqual(len(standard_entries), 1)
        self.assertFalse(standard_entries[0].is_biome_variant)
        self.assertEqual(standard_entries[0].context_label, "Base Layout")
        self.assertEqual(standard_entries[0].profile_dungeon_id, "mud_caverns")

        self.assertEqual(len(ritual_entries), 4)
        self.assertEqual(
            [entry.context_label for entry in ritual_entries],
            ["Base Layout", "Mud Caverns", "Frozen Depths", "Sunken Ruins"],
        )
        self.assertEqual(
            [entry.display_name for entry in ritual_entries],
            [
                "Ritual Disruption",
                "Spore Totem Grove",
                "Frost Obelisk Break",
                "Tidal Idol Collapse",
            ],
        )

    def test_build_room_test_plan_uses_selected_variant_profile_and_context(self):
        entry = next(
            entry
            for entry in load_room_test_entries()
            if entry.entry_id == "biome:frozen_depths:ritual_disruption"
        )

        plan = build_room_test_plan(entry)

        self.assertEqual(plan.room_id, "ritual_disruption")
        self.assertEqual(plan.display_name, "Frost Obelisk Break")
        self.assertEqual(plan.objective_variant, "frost_obelisk")
        self.assertEqual(plan.terrain_type, "ice")
        self.assertEqual(plan.depth, 3)
        self.assertEqual(plan.path_kind, "main_path")
        self.assertTrue(plan.is_exit)
        self.assertEqual(plan.reward_tier, "finale_bonus")
        self.assertEqual(plan.enemy_type_weights, (25, 25, 50))

    def test_load_room_test_entries_includes_trap_biome_variants(self):
        entries = [
            entry
            for entry in load_room_test_entries()
            if entry.room_id == "trap_gauntlet"
        ]

        self.assertEqual(
            [entry.context_label for entry in entries],
            ["Base Layout", "Mud Caverns", "Frozen Depths", "Sunken Ruins"],
        )
        self.assertEqual(
            [entry.display_name for entry in entries],
            [
                "Trap Gauntlet",
                "Boulder Sweep Run",
                "Frost Vent Gauntlet",
                "Floodgate Hazard Run",
            ],
        )
        self.assertEqual(entries[-1].objective_variant, "mixed_lanes")


if __name__ == "__main__":
    unittest.main()