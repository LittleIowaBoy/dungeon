import unittest
from unittest.mock import patch

from chest import Chest


class ChestRewardTierTests(unittest.TestCase):
    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_reward_tier_adds_bonus_loot_rolls(self, _mock_randint, _mock_choices):
        standard = Chest(50, 50, reward_tier="standard")
        branch = Chest(50, 50, reward_tier="branch_bonus")
        finale = Chest(50, 50, reward_tier="finale_bonus")

        self.assertEqual(len(standard.contents), 1)
        self.assertEqual(len(branch.contents), 2)
        self.assertEqual(len(finale.contents), 3)

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_set_reward_tier_rerolls_unopened_contents(self, _mock_randint, _mock_choices):
        chest = Chest(50, 50, reward_tier="standard")

        chest.set_reward_tier("branch_bonus")

        self.assertEqual(chest.reward_tier, "branch_bonus")
        self.assertEqual(len(chest.contents), 2)


class ChestRewardKindTests(unittest.TestCase):
    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_default_chest_upgrade_kind_does_not_append_bonus_loot(self, _mock_randint, _mock_choices):
        chest = Chest(50, 50, reward_kind="chest_upgrade")

        self.assertEqual(chest.contents, [("coin",)])

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_stat_shard_kind_appends_attack_boost_bonus(self, _mock_randint, _mock_choices):
        chest = Chest(50, 50, reward_kind="stat_shard")

        self.assertIn(("loot", "stat_shard"), chest.contents)
        self.assertEqual(len(chest.contents), 2)

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_tempo_rune_kind_appends_armor_bonus(self, _mock_randint, _mock_choices):
        chest = Chest(50, 50, reward_kind="tempo_rune")

        self.assertIn(("loot", "tempo_rune"), chest.contents)

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_mobility_consumable_kind_appends_speed_boost_bonus(self, _mock_randint, _mock_choices):
        chest = Chest(50, 50, reward_kind="mobility_consumable")

        self.assertIn(("loot", "mobility_charge"), chest.contents)

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_set_reward_kind_rerolls_with_biome_bonus_loot(self, _mock_randint, _mock_choices):
        chest = Chest(50, 50, reward_kind="chest_upgrade")
        self.assertEqual(chest.contents, [("coin",)])

        chest.set_reward_kind("stat_shard")

        self.assertEqual(chest.reward_kind, "stat_shard")
        self.assertIn(("loot", "stat_shard"), chest.contents)

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_set_reward_kind_on_looted_chest_is_a_noop(self, _mock_randint, _mock_choices):
        chest = Chest(50, 50, looted=True, reward_kind="chest_upgrade")

        chest.set_reward_kind("stat_shard")

        self.assertEqual(chest.reward_kind, "chest_upgrade")
        self.assertEqual(chest.contents, [])


if __name__ == "__main__":
    unittest.main()