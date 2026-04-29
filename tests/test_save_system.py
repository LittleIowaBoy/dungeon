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

    def test_save_load_round_trip_persists_equipped_runes(self):
        import rune_rules
        from rune_catalog import (
            RUNE_CATEGORY_BEHAVIOR,
            RUNE_CATEGORY_IDENTITY,
            RUNE_CATEGORY_STAT,
            runes_by_category,
        )

        progress = PlayerProgress()
        stat_id = runes_by_category(RUNE_CATEGORY_STAT)[0].rune_id
        behavior_id = runes_by_category(RUNE_CATEGORY_BEHAVIOR)[0].rune_id
        identity_id = runes_by_category(RUNE_CATEGORY_IDENTITY)[0].rune_id
        rune_rules.equip_rune(progress, stat_id)
        rune_rules.equip_rune(progress, behavior_id)
        rune_rules.equip_rune(progress, identity_id)

        save_system.save_progress(progress)
        loaded = save_system.load_progress()

        self.assertTrue(rune_rules.has_rune(loaded, stat_id))
        self.assertTrue(rune_rules.has_rune(loaded, behavior_id))
        self.assertTrue(rune_rules.has_rune(loaded, identity_id))

        player = Player(32, 32)
        player.reset_for_dungeon(loaded)
        self.assertTrue(rune_rules.has_rune(player, stat_id))
        self.assertTrue(rune_rules.has_rune(player, behavior_id))
        self.assertTrue(rune_rules.has_rune(player, identity_id))

    def test_save_load_round_trip_persists_meta_keystones(self):
        progress = PlayerProgress()
        progress.meta_keystones = 2

        save_system.save_progress(progress)
        loaded = save_system.load_progress()

        self.assertEqual(loaded.meta_keystones, 2)


if __name__ == "__main__":
    unittest.main()