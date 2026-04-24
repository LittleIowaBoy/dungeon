import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

import attack_rules
import behavior_runes
import combat_rules
import enemies
import movement_rules
import rune_rules
from items import Coin, LootDrop
from settings import ATTACK_BOOST_MULTIPLIER, INVINCIBILITY_MS, WEAPON_PLUS_MULTIPLIER


class _DummyHitbox:
    def __init__(self, damage):
        self.damage = damage
        self.glow_calls = 0

    def set_glow(self):
        self.glow_calls += 1


class _DummyWeapon:
    def __init__(self, result):
        self._result = result
        self.calls = []

    def attack(self, centerx, centery, facing_dx, facing_dy):
        self.calls.append((centerx, centery, facing_dx, facing_dy))
        return self._result


class _MovementPlayer:
    def __init__(self):
        self.rect = pygame.Rect(20, 20, 24, 24)
        self.facing_dx = 0.0
        self.facing_dy = 1.0
        self.speed_multiplier = 1.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self._on_ice = False

    def _effective_speed_multiplier(self):
        return self.speed_multiplier


class RuntimeRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_attack_returns_none_without_weapon(self):
        player = SimpleNamespace(weapon=None)

        self.assertIsNone(attack_rules.attack(player))

    def test_attack_scales_all_hitboxes_and_applies_glow_when_boosted(self):
        hitboxes = [_DummyHitbox(10), _DummyHitbox(6)]
        weapon = _DummyWeapon(hitboxes)
        player = SimpleNamespace(
            weapon=weapon,
            rect=SimpleNamespace(centerx=64, centery=80),
            facing_dx=1.0,
            facing_dy=0.0,
            is_attack_boosted=True,
            current_weapon_id="axe",
            weapon_upgrade_tier=lambda _weapon_id: 2,
        )

        result = attack_rules.attack(player)

        self.assertIs(result, hitboxes)
        expected_multiplier = ATTACK_BOOST_MULTIPLIER * (WEAPON_PLUS_MULTIPLIER ** 2)
        self.assertEqual(hitboxes[0].damage, int(10 * expected_multiplier))
        self.assertEqual(hitboxes[1].damage, int(6 * expected_multiplier))
        self.assertEqual(hitboxes[0].glow_calls, 1)
        self.assertEqual(hitboxes[1].glow_calls, 1)
        self.assertEqual(weapon.calls, [(64, 80, 1.0, 0.0)])

    def test_attack_with_boomerang_zeroes_outbound_and_queues_return(self):
        hb_rect = pygame.Rect(0, 0, 16, 16)
        hb_rect.center = (100, 50)

        class _Hitbox:
            def __init__(self):
                self.damage = 20
                self.rect = hb_rect

            def set_glow(self):
                pass

        hitbox = _Hitbox()
        weapon = _DummyWeapon(hitbox)
        player = SimpleNamespace(
            weapon=weapon,
            rect=SimpleNamespace(centerx=64, centery=80),
            facing_dx=1.0,
            facing_dy=0.0,
            is_attack_boosted=False,
            current_weapon_id="sword",
            weapon_upgrade_tier=lambda _id: 0,
            equipped_runes=rune_rules.empty_loadout(),
            rune_state={"room": {}},
            statuses={},
        )
        rune_rules.equip_rune(player, "boomerang")

        with patch("pygame.time.get_ticks", return_value=5_000):
            result = attack_rules.attack(player)

        self.assertIs(result, hitbox)
        # Outbound zeroed.
        self.assertEqual(hitbox.damage, 0)
        # Return queued at original (pre-zero) damage.
        pending = player.rune_state["boomerang_pending"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["center"], (100, 50))
        self.assertEqual(pending[0]["damage"], 20)
        self.assertEqual(
            pending[0]["spawn_at"],
            5_000 + behavior_runes.BOOMERANG_RETURN_DELAY_MS,
        )

    def test_reset_runtime_combat_resets_hp_and_invincibility(self):
        player = SimpleNamespace(max_hp=5, current_hp=2, _invincible_until=999)

        combat_rules.reset_runtime_combat(player, 18)

        self.assertEqual(player.max_hp, 18)
        self.assertEqual(player.current_hp, 18)
        self.assertEqual(player._invincible_until, 0)

    def test_take_damage_consumes_armor_then_sets_invincibility(self):
        player = SimpleNamespace(current_hp=20, armor_hp=3, _invincible_until=0)

        combat_rules.take_damage(player, 7, 1000)

        self.assertEqual(player.armor_hp, 0)
        self.assertEqual(player.current_hp, 16)
        self.assertEqual(player._invincible_until, 1000 + INVINCIBILITY_MS)

        combat_rules.take_damage(player, 10, 1000 + INVINCIBILITY_MS - 1)

        self.assertEqual(player.current_hp, 16)

    def test_update_motion_on_ice_preserves_momentum_without_input(self):
        player = _MovementPlayer()

        movement_rules.update_motion(
            player,
            [],
            lambda _x, _y: "ice",
            {pygame.K_RIGHT: True},
        )
        pushed_velocity = player.velocity_x
        pushed_left = player.rect.left

        movement_rules.update_motion(
            player,
            [],
            lambda _x, _y: "ice",
            {},
        )

        self.assertTrue(player._on_ice)
        self.assertGreater(pushed_velocity, 0.0)
        self.assertGreater(player.velocity_x, 0.0)
        self.assertLess(player.velocity_x, pushed_velocity)
        self.assertGreaterEqual(player.rect.left, pushed_left)

    def test_enemy_take_damage_kills_sprite_when_hp_reaches_zero(self):
        enemy = enemies.PatrolEnemy(64, 64)
        group = pygame.sprite.Group(enemy)

        enemy.take_damage(enemy.current_hp)

        self.assertFalse(enemy.alive())
        self.assertNotIn(enemy, group)

    def test_enemy_roll_drop_can_return_coin(self):
        enemy = enemies.RandomEnemy(80, 96)

        with patch("random.random", side_effect=[0.0, 0.0]):
            drop = enemy.roll_drop()

        self.assertIsInstance(drop, Coin)
        self.assertEqual(drop.rect.center, enemy.rect.center)

    def test_enemy_roll_drop_can_return_inventory_loot(self):
        enemy = enemies.ChaserEnemy(96, 112)
        if not enemies.ENEMY_LOOT_IDS:
            self.skipTest("Enemy loot table is empty")

        chosen_item_id = enemies.ENEMY_LOOT_IDS[0]
        with patch("random.random", side_effect=[0.0, 0.75]), patch(
            "random.choices", return_value=[chosen_item_id]
        ):
            drop = enemy.roll_drop()

        self.assertIsInstance(drop, LootDrop)
        self.assertEqual(drop.item_id, chosen_item_id)
        self.assertEqual(drop.rect.center, enemy.rect.center)