import unittest
from types import SimpleNamespace

import time_rules


class GetSetTests(unittest.TestCase):
    def test_default_when_no_state(self):
        p = SimpleNamespace()
        self.assertEqual(time_rules.get_time_scale(p), 1.0)

    def test_default_when_state_empty(self):
        p = SimpleNamespace(rune_state={})
        self.assertEqual(time_rules.get_time_scale(p), 1.0)

    def test_set_and_get(self):
        p = SimpleNamespace(rune_state={})
        time_rules.set_time_scale(p, 0.2)
        self.assertAlmostEqual(time_rules.get_time_scale(p), 0.2)

    def test_set_clamps_negative_to_zero(self):
        p = SimpleNamespace(rune_state={})
        time_rules.set_time_scale(p, -0.5)
        self.assertEqual(time_rules.get_time_scale(p), 0.0)

    def test_invalid_value_falls_back(self):
        p = SimpleNamespace(rune_state={"time_scale": "broken"})
        self.assertEqual(time_rules.get_time_scale(p), 1.0)

    def test_reset_restores_default(self):
        p = SimpleNamespace(rune_state={"time_scale": 0.0})
        time_rules.reset_time_scale(p)
        self.assertEqual(time_rules.get_time_scale(p), 1.0)

    def test_set_initializes_rune_state_when_missing(self):
        p = SimpleNamespace()
        time_rules.set_time_scale(p, 0.5)
        self.assertEqual(p.rune_state["time_scale"], 0.5)


class IsWorldSlowedTests(unittest.TestCase):
    def test_normal_not_slowed(self):
        p = SimpleNamespace()
        self.assertFalse(time_rules.is_world_slowed(p))

    def test_below_one_is_slowed(self):
        p = SimpleNamespace(rune_state={"time_scale": 0.5})
        self.assertTrue(time_rules.is_world_slowed(p))

    def test_zero_is_slowed(self):
        p = SimpleNamespace(rune_state={"time_scale": 0.0})
        self.assertTrue(time_rules.is_world_slowed(p))


if __name__ == "__main__":
    unittest.main()
