import unittest
from types import SimpleNamespace

import ability_rules


def _player():
    p = SimpleNamespace()
    ability_rules.reset_runtime_ability(p)
    return p


class _AbilityRegistryFixture(unittest.TestCase):
    """Base class that installs/removes a test ability around each test."""

    def setUp(self):
        self.calls = []
        self.return_value = True

        def activate(player, now_ticks):
            self.calls.append((player, now_ticks))
            return self.return_value

        ability_rules.register_ability("test_blast", activate, cooldown_ms=2000)

    def tearDown(self):
        ability_rules.unregister_ability("test_blast")


class ResetTests(unittest.TestCase):
    def test_reset_initializes_fields(self):
        p = SimpleNamespace()
        ability_rules.reset_runtime_ability(p)
        self.assertIsNone(p.active_ability_id)
        self.assertEqual(p.active_ability_cooldown_ms, 0)
        self.assertEqual(p.ability_cooldown_until, 0)


class EquipTests(_AbilityRegistryFixture):
    def test_equip_known_ability(self):
        p = _player()
        self.assertTrue(ability_rules.equip_ability(p, "test_blast"))
        self.assertEqual(p.active_ability_id, "test_blast")
        self.assertEqual(p.active_ability_cooldown_ms, 2000)
        self.assertTrue(ability_rules.has_ability(p))

    def test_equip_unknown_returns_false(self):
        p = _player()
        self.assertFalse(ability_rules.equip_ability(p, "nope"))
        self.assertIsNone(p.active_ability_id)

    def test_equip_none_clears_slot(self):
        p = _player()
        ability_rules.equip_ability(p, "test_blast")
        self.assertTrue(ability_rules.equip_ability(p, None))
        self.assertIsNone(p.active_ability_id)
        self.assertFalse(ability_rules.has_ability(p))

    def test_equip_resets_cooldown(self):
        p = _player()
        ability_rules.equip_ability(p, "test_blast")
        ability_rules.activate_ability(p, 1000)
        # Re-equip while on cooldown.
        ability_rules.equip_ability(p, "test_blast")
        self.assertEqual(p.ability_cooldown_until, 0)


class ActivateTests(_AbilityRegistryFixture):
    def test_cannot_activate_without_equip(self):
        p = _player()
        self.assertFalse(ability_rules.activate_ability(p, 0))
        self.assertEqual(self.calls, [])

    def test_activate_calls_handler_and_starts_cooldown(self):
        p = _player()
        ability_rules.equip_ability(p, "test_blast")
        self.assertTrue(ability_rules.activate_ability(p, 1000))
        self.assertEqual(self.calls, [(p, 1000)])
        self.assertEqual(p.ability_cooldown_until, 3000)

    def test_cannot_activate_during_cooldown(self):
        p = _player()
        ability_rules.equip_ability(p, "test_blast")
        ability_rules.activate_ability(p, 1000)
        self.assertFalse(ability_rules.activate_ability(p, 2500))
        self.assertEqual(len(self.calls), 1)

    def test_can_activate_again_after_cooldown(self):
        p = _player()
        ability_rules.equip_ability(p, "test_blast")
        ability_rules.activate_ability(p, 1000)
        self.assertTrue(ability_rules.activate_ability(p, 3001))
        self.assertEqual(len(self.calls), 2)

    def test_handler_returning_false_does_not_consume_cooldown(self):
        p = _player()
        ability_rules.equip_ability(p, "test_blast")
        self.return_value = False
        self.assertFalse(ability_rules.activate_ability(p, 1000))
        self.assertEqual(p.ability_cooldown_until, 0)
        self.assertEqual(len(self.calls), 1)


class CooldownFractionTests(_AbilityRegistryFixture):
    def test_zero_when_ready(self):
        p = _player()
        ability_rules.equip_ability(p, "test_blast")
        self.assertEqual(ability_rules.cooldown_fraction_remaining(p, 0), 0.0)

    def test_one_just_after_trigger(self):
        p = _player()
        ability_rules.equip_ability(p, "test_blast")
        ability_rules.activate_ability(p, 0)
        self.assertGreater(ability_rules.cooldown_fraction_remaining(p, 1), 0.99)

    def test_zero_when_no_ability_equipped(self):
        p = _player()
        self.assertEqual(ability_rules.cooldown_fraction_remaining(p, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
