import os
import tempfile
import unittest
from unittest.mock import patch

import pygame

import save_system
from player import Player
from progress import PlayerProgress


class SaveSystemRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "save_data.db")
        self.db_patch = patch.object(save_system, "_DB_PATH", self.db_path)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_save_load_round_trip_rebuilds_runtime_loadout_from_persisted_state(self):
        progress = PlayerProgress()
        progress.coins = 47
        progress.armor_hp = 5
        progress.compass_uses = 2
        progress.equipped_slots["weapon_1"] = "axe"
        progress.equipped_slots["weapon_2"] = "hammer"
        progress.weapon_upgrades["hammer"] = 2

        save_system.save_progress(progress)
        loaded = save_system.load_progress()

        player = Player(32, 32)
        player.reset_for_dungeon(loaded)

        self.assertEqual(loaded.equipped_slots["weapon_1"], "axe")
        self.assertEqual(loaded.equipped_slots["weapon_2"], "hammer")
        self.assertEqual(player.weapon_ids, ["axe", "hammer"])
        self.assertEqual([weapon.name for weapon in player.weapons], ["Axe", "Hammer"])
        self.assertEqual(player.weapon_upgrade_tier("hammer"), 2)
        self.assertEqual(player.armor_hp, 5)
        self.assertEqual(player.compass_uses, 2)

    def test_save_load_round_trip_migrates_legacy_upgrade_into_runtime_loadout(self):
        progress = PlayerProgress()
        progress.equipped_slots["weapon_1"] = "axe"
        progress.equipped_slots["weapon_2"] = "spear"
        progress.inventory["axe_plus"] = 1

        save_system.save_progress(progress)
        loaded = save_system.load_progress()

        player = Player(32, 32)
        player.reset_for_dungeon(loaded)

        self.assertNotIn("axe_plus", loaded.inventory)
        self.assertEqual(loaded.weapon_upgrades["axe"], 1)
        self.assertEqual(player.weapon_ids, ["axe", "spear"])
        self.assertEqual(player.weapon_upgrade_tier("axe"), 1)


if __name__ == "__main__":
    unittest.main()