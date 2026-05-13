import unittest
import random
from unittest.mock import patch, MagicMock

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


class GambleStateTests(unittest.TestCase):
    """Tests for Chest.try_gamble / cancel_gamble / confirm_gamble."""

    def _make_chest_at(self, cx=100, cy=100, **kw):
        return Chest(cx, cy, **kw)

    def _near_rect(self, cx=100, cy=100):
        rect = MagicMock()
        rect.centerx = cx
        rect.centery = cy
        return rect

    def _far_rect(self):
        rect = MagicMock()
        rect.centerx = 9999
        rect.centery = 9999
        return rect

    # ── try_gamble ───────────────────────────────────────

    def test_try_gamble_enters_pending_when_near(self):
        chest = self._make_chest_at()
        result = chest.try_gamble(self._near_rect())
        self.assertTrue(result)
        self.assertTrue(chest.gamble_pending)

    def test_try_gamble_returns_false_when_far(self):
        chest = self._make_chest_at()
        result = chest.try_gamble(self._far_rect())
        self.assertFalse(result)
        self.assertFalse(chest.gamble_pending)

    def test_try_gamble_noop_on_looted_chest(self):
        chest = self._make_chest_at(looted=True)
        result = chest.try_gamble(self._near_rect())
        self.assertFalse(result)
        self.assertFalse(chest.gamble_pending)

    def test_try_gamble_noop_when_already_pending(self):
        chest = self._make_chest_at()
        chest.try_gamble(self._near_rect())
        result = chest.try_gamble(self._near_rect())
        self.assertFalse(result)
        self.assertTrue(chest.gamble_pending)

    # ── cancel_gamble ────────────────────────────────────

    def test_cancel_gamble_clears_pending(self):
        chest = self._make_chest_at()
        chest.try_gamble(self._near_rect())
        chest.cancel_gamble()
        self.assertFalse(chest.gamble_pending)
        self.assertFalse(chest.looted)

    def test_cancel_gamble_noop_when_not_pending(self):
        chest = self._make_chest_at()
        chest.cancel_gamble()  # Should not raise.
        self.assertFalse(chest.gamble_pending)

    # ── confirm_gamble ───────────────────────────────────

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_confirm_gamble_win_elevates_tier(self, _ri, _rc):
        chest = self._make_chest_at(reward_tier="standard")
        chest.try_gamble(self._near_rect())
        rng = MagicMock()
        rng.random.return_value = 0.0   # always win
        result = chest.confirm_gamble(rng)
        self.assertEqual(result, "win")
        self.assertEqual(chest.reward_tier, "branch_bonus")
        self.assertFalse(chest.gamble_pending)

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_confirm_gamble_lose_marks_looted(self, _ri, _rc):
        chest = self._make_chest_at()
        chest.try_gamble(self._near_rect())
        rng = MagicMock()
        rng.random.return_value = 1.0   # always lose
        result = chest.confirm_gamble(rng)
        self.assertEqual(result, "lose")
        self.assertTrue(chest.looted)
        self.assertFalse(chest.gamble_pending)

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_confirm_gamble_idle_when_not_pending(self, _ri, _rc):
        chest = self._make_chest_at()
        result = chest.confirm_gamble(MagicMock())
        self.assertEqual(result, "idle")

    # ── try_elevate_tier ─────────────────────────────────

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_try_elevate_tier_standard_to_branch(self, _ri, _rc):
        chest = self._make_chest_at(reward_tier="standard")
        elevated = chest.try_elevate_tier()
        self.assertTrue(elevated)
        self.assertEqual(chest.reward_tier, "branch_bonus")

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_try_elevate_tier_branch_to_finale(self, _ri, _rc):
        chest = self._make_chest_at(reward_tier="branch_bonus")
        elevated = chest.try_elevate_tier()
        self.assertTrue(elevated)
        self.assertEqual(chest.reward_tier, "finale_bonus")

    @patch("chest.random.choices", return_value=[("coin",)])
    @patch("chest.random.randint", return_value=1)
    def test_try_elevate_tier_returns_false_at_max(self, _ri, _rc):
        chest = self._make_chest_at(reward_tier="finale_bonus")
        elevated = chest.try_elevate_tier()
        self.assertFalse(elevated)
        self.assertEqual(chest.reward_tier, "finale_bonus")


if __name__ == "__main__":
    unittest.main()