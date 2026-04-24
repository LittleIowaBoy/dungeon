import unittest
from types import SimpleNamespace

from progress import PlayerProgress


class PlayerProgressTransitionTests(unittest.TestCase):
    def make_player(self, coins=0, armor_hp=0, compass_uses=0):
        return SimpleNamespace(
            coins=coins,
            armor_hp=armor_hp,
            compass_uses=compass_uses,
        )

    def test_begin_dungeon_run_returns_revert_snapshot(self):
        progress = PlayerProgress()
        progress.coins = 14
        progress.inventory = {"health_potion_small": 2}
        progress.armor_hp = 6
        progress.compass_uses = 1

        snapshot = progress.begin_dungeon_run("mud_caves")

        self.assertTrue(progress.get_dungeon("mud_caves").is_alive)
        self.assertEqual(snapshot["coins"], 14)
        self.assertEqual(snapshot["inventory"], {"health_potion_small": 2})
        self.assertEqual(snapshot["armor_hp"], 6)
        self.assertEqual(snapshot["compass_uses"], 1)

    def test_complete_dungeon_from_runtime_marks_completed(self):
        progress = PlayerProgress()
        progress.begin_dungeon_run("mud_caves")
        player = self.make_player(coins=25, armor_hp=9, compass_uses=2)

        progress.complete_dungeon_from_runtime("mud_caves", player)

        dungeon = progress.get_dungeon("mud_caves")
        self.assertTrue(dungeon.completed)
        self.assertEqual(progress.coins, 25)
        self.assertEqual(progress.armor_hp, 9)
        self.assertEqual(progress.compass_uses, 2)

    def test_abandon_dungeon_run_restores_snapshot_without_aliasing_inventory(self):
        progress = PlayerProgress()
        progress.coins = 10
        progress.inventory = {"health_potion_small": 1}
        progress.armor_hp = 4
        progress.compass_uses = 1
        snapshot = progress.snapshot_run_state()

        progress.coins = 99
        progress.inventory["speed_boost"] = 3
        progress.armor_hp = 0
        progress.compass_uses = 0
        progress.abandon_dungeon_run(snapshot)

        self.assertEqual(progress.coins, 10)
        self.assertEqual(progress.inventory, {"health_potion_small": 1})
        self.assertEqual(progress.armor_hp, 4)
        self.assertEqual(progress.compass_uses, 1)

    def test_resolve_dungeon_death_syncs_runtime_then_applies_penalties(self):
        progress = PlayerProgress()
        progress.begin_dungeon_run("mud_caves")
        progress.weapon_upgrades["sword"] = 2
        progress.inventory["compass"] = 1
        progress.inventory["armor"] = 1
        player = self.make_player(coins=31, armor_hp=7, compass_uses=2)

        progress.resolve_dungeon_death("mud_caves", player)

        dungeon = progress.get_dungeon("mud_caves")
        self.assertFalse(dungeon.is_alive)
        self.assertEqual(progress.coins, 31)
        self.assertEqual(progress.armor_hp, 0)
        self.assertEqual(progress.compass_uses, 0)
        self.assertEqual(progress.weapon_upgrades["sword"], 0)
        self.assertNotIn("compass", progress.inventory)
        self.assertNotIn("armor", progress.inventory)

    def test_ensure_loadout_state_normalizes_invalid_and_duplicate_equipment(self):
        progress = PlayerProgress()
        progress.equipped_slots = {
            "weapon_1": "sword",
            "weapon_2": "sword",
            "helmet": "spear",
            "chest": None,
            "arms": None,
            "legs": None,
        }
        progress.equipment_storage = {}
        progress.weapon_upgrades = {"sword": "2", "spear": -1, "axe": None, "hammer": 1}

        progress.ensure_loadout_state()

        self.assertEqual(progress.equipped_slots["weapon_1"], "sword")
        self.assertIsNone(progress.equipped_slots["weapon_2"])
        self.assertIsNone(progress.equipped_slots["helmet"])
        self.assertEqual(progress.equipment_storage["sword"], 1)
        self.assertEqual(progress.equipment_storage["spear"], 1)
        self.assertEqual(progress.weapon_upgrades, {
            "sword": 2,
            "spear": 0,
            "axe": 0,
            "hammer": 1,
        })

    def test_can_equip_prevents_duplicate_weapon_assignment(self):
        progress = PlayerProgress()
        progress.equipped_slots["weapon_1"] = "sword"
        progress.equipped_slots["weapon_2"] = None
        progress.equipment_storage["sword"] = 1

        self.assertFalse(progress.can_equip("weapon_2", "sword"))


class PlayerProgressRuneTests(unittest.TestCase):
    def _equip_some_runes(self, progress):
        import rune_rules
        from rune_catalog import (
            RUNE_CATEGORY_BEHAVIOR,
            RUNE_CATEGORY_STAT,
            runes_by_category,
        )
        stat_id = runes_by_category(RUNE_CATEGORY_STAT)[0].rune_id
        behavior_id = runes_by_category(RUNE_CATEGORY_BEHAVIOR)[0].rune_id
        rune_rules.equip_rune(progress, stat_id)
        rune_rules.equip_rune(progress, behavior_id)
        return stat_id, behavior_id

    def test_snapshot_and_restore_round_trip_includes_runes(self):
        import rune_rules
        progress = PlayerProgress()
        stat_id, behavior_id = self._equip_some_runes(progress)

        snapshot = progress.snapshot_run_state()
        rune_rules.clear_loadout(progress)
        self.assertFalse(rune_rules.has_rune(progress, stat_id))

        progress.restore_run_state(snapshot)
        self.assertTrue(rune_rules.has_rune(progress, stat_id))
        self.assertTrue(rune_rules.has_rune(progress, behavior_id))

    def test_complete_dungeon_wipes_runes(self):
        import rune_rules
        progress = PlayerProgress()
        progress.begin_dungeon_run("mud_caves")
        stat_id, _ = self._equip_some_runes(progress)
        player = SimpleNamespace(
            coins=0, armor_hp=0, compass_uses=0,
            equipped_runes=progress.equipped_runes,
        )

        progress.complete_dungeon_from_runtime("mud_caves", player)

        self.assertFalse(rune_rules.has_rune(progress, stat_id))

    def test_die_in_dungeon_wipes_runes(self):
        import rune_rules
        progress = PlayerProgress()
        progress.begin_dungeon_run("mud_caves")
        stat_id, _ = self._equip_some_runes(progress)

        progress.die_in_dungeon("mud_caves")

        self.assertFalse(rune_rules.has_rune(progress, stat_id))


if __name__ == "__main__":
    unittest.main()