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


if __name__ == "__main__":
    unittest.main()