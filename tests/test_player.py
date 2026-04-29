import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

import movement_rules
from player import Player
from progress import PlayerProgress
from settings import ATTACK_BOOST_MULTIPLIER, FLASH_INTERVAL_MS, SPEED_BOOST_MULTIPLIER, WEAPON_PLUS_MULTIPLIER
from settings import COMPASS_DISPLAY_MS
import damage_feedback


class PlayerLoadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_reset_for_dungeon_builds_runtime_weapons_from_progress_loadout(self):
        progress = PlayerProgress()
        progress.equipped_slots["weapon_1"] = "axe"
        progress.equipped_slots["weapon_2"] = "hammer"
        progress.weapon_upgrades["hammer"] = 2

        player = Player(32, 32)
        player.reset_for_dungeon(progress)

        self.assertEqual(player.weapon_ids, ["axe", "hammer"])
        self.assertEqual([weapon.name for weapon in player.weapons], ["Axe", "Hammer"])
        self.assertEqual(player.current_weapon_index, 0)
        self.assertEqual(player.weapon_upgrade_tier("hammer"), 2)

    def test_cycle_and_use_potion_delegate_to_consumable_rules(self):
        progress = PlayerProgress()
        progress.inventory["health_potion_medium"] = 1
        player = Player(32, 32)
        player.reset_for_dungeon(progress)
        player.current_hp = 10

        player.cycle_potion()

        self.assertEqual(player.selected_potion_size, "medium")
        self.assertTrue(player.use_potion())
        self.assertNotIn("health_potion_medium", progress.inventory)
        self.assertGreater(player.current_hp, 10)

    def test_use_boost_consumables_consumes_inventory_and_sets_timers(self):
        progress = PlayerProgress()
        progress.inventory["speed_boost"] = 1
        progress.inventory["attack_boost"] = 1
        player = Player(32, 32)
        player.reset_for_dungeon(progress)

        with patch("pygame.time.get_ticks", side_effect=[1000, 2000]):
            self.assertTrue(player.use_speed_boost())
            self.assertTrue(player.use_attack_boost())

        self.assertEqual(player.speed_boost_until, 21000)
        self.assertEqual(player.attack_boost_until, 22000)
        self.assertNotIn("speed_boost", progress.inventory)
        self.assertNotIn("attack_boost", progress.inventory)

    def test_use_stat_shard_grants_permanent_max_hp_bump(self):
        from settings import STAT_SHARD_MAX_HP_BONUS

        progress = PlayerProgress()
        progress.inventory["stat_shard"] = 2
        player = Player(32, 32)
        player.reset_for_dungeon(progress)
        starting_max = player.max_hp
        player.current_hp = starting_max - 5
        damage_feedback.reset_all()

        with patch("pygame.time.get_ticks", return_value=5000):
            self.assertTrue(player.use_stat_shard())
            self.assertEqual(player.max_hp, starting_max + STAT_SHARD_MAX_HP_BONUS)
            # current_hp is bumped by the same amount, capped at the new max.
            self.assertEqual(
                player.current_hp,
                min(starting_max - 5 + STAT_SHARD_MAX_HP_BONUS, player.max_hp),
            )
            self.assertEqual(progress.inventory["stat_shard"], 1)

            # Spending the second shard stacks the bonus.
            self.assertTrue(player.use_stat_shard())
            self.assertEqual(player.max_hp, starting_max + 2 * STAT_SHARD_MAX_HP_BONUS)
            self.assertNotIn("stat_shard", progress.inventory)

            # No shards left → activation no-ops.
            self.assertFalse(player.use_stat_shard())

        # Each successful spend queued a flash anchored at the player.
        flashes = damage_feedback.build_biome_reward_flash_views(now_ticks=5000)
        self.assertEqual([kind for kind, _pos, _age in flashes], ["stat_shard", "stat_shard"])

    def test_use_tempo_rune_extends_attack_boost_window(self):
        from settings import TEMPO_RUNE_DURATION_MS

        progress = PlayerProgress()
        progress.inventory["tempo_rune"] = 1
        player = Player(32, 32)
        player.reset_for_dungeon(progress)
        damage_feedback.reset_all()

        with patch("pygame.time.get_ticks", return_value=5000):
            self.assertTrue(player.use_tempo_rune())

        self.assertEqual(player.attack_boost_until, 5000 + TEMPO_RUNE_DURATION_MS)
        self.assertNotIn("tempo_rune", progress.inventory)
        self.assertFalse(player.use_tempo_rune())

        flashes = damage_feedback.build_biome_reward_flash_views(now_ticks=5000)
        self.assertEqual([kind for kind, _pos, _age in flashes], ["tempo_rune"])

    def test_use_mobility_charge_triggers_short_speed_burst(self):
        from settings import MOBILITY_CHARGE_DURATION_MS

        progress = PlayerProgress()
        progress.inventory["mobility_charge"] = 1
        player = Player(32, 32)
        player.reset_for_dungeon(progress)
        damage_feedback.reset_all()

        with patch("pygame.time.get_ticks", return_value=5000):
            self.assertTrue(player.use_mobility_charge())

        self.assertEqual(player.speed_boost_until, 5000 + MOBILITY_CHARGE_DURATION_MS)
        self.assertNotIn("mobility_charge", progress.inventory)
        self.assertFalse(player.use_mobility_charge())

        flashes = damage_feedback.build_biome_reward_flash_views(now_ticks=5000)
        self.assertEqual([kind for kind, _pos, _age in flashes], ["mobility_charge"])

    def test_use_compass_delegates_to_tool_rules_and_updates_progress(self):
        progress = PlayerProgress()
        progress.compass_uses = 2
        player = Player(32, 32)
        player.reset_for_dungeon(progress)
        dungeon = SimpleNamespace(current_pos=(0, 0), exit_pos=(2, -1))

        with patch("pygame.time.get_ticks", return_value=1500):
            self.assertTrue(player.use_compass(dungeon))

        self.assertEqual(player.compass_uses, 1)
        self.assertEqual(progress.compass_uses, 1)
        self.assertEqual(player.compass_target_label, "Portal")
        self.assertEqual(player.compass_direction, "NE")
        self.assertEqual(player.compass_arrow, "↗")
        self.assertEqual(player._compass_display_until, 1500 + COMPASS_DISPLAY_MS)

    def test_use_compass_prefers_objective_hint_inside_locked_exit_room(self):
        progress = PlayerProgress()
        progress.compass_uses = 1
        player = Player(32, 32)
        player.reset_for_dungeon(progress)
        dungeon = SimpleNamespace(
            current_pos=(2, -1),
            exit_pos=(2, -1),
            current_room=SimpleNamespace(
                objective_target_info=lambda origin: ("Relic", (origin[0] + 80, origin[1]))
            ),
        )

        with patch("pygame.time.get_ticks", return_value=1500):
            self.assertTrue(player.use_compass(dungeon))

        self.assertEqual(player.compass_target_label, "Relic")
        self.assertEqual(player.compass_direction, "E")
        self.assertEqual(player.compass_arrow, "→")

    def test_compass_showing_uses_tool_timer_state(self):
        progress = PlayerProgress()
        progress.compass_uses = 1
        player = Player(32, 32)
        player.reset_for_dungeon(progress)
        player._compass_display_until = 6000

        with patch("pygame.time.get_ticks", return_value=5500):
            self.assertTrue(player.compass_showing)
        with patch("pygame.time.get_ticks", return_value=6500):
            self.assertFalse(player.compass_showing)

    def test_take_damage_uses_armor_and_invincibility_window(self):
        player = Player(32, 32)
        player.armor_hp = 3

        with patch("pygame.time.get_ticks", return_value=1000):
            player.take_damage(5)

        self.assertEqual(player.armor_hp, 0)
        self.assertEqual(player.current_hp, player.max_hp - 2)
        self.assertEqual(player._invincible_until, 2000)

        with patch("pygame.time.get_ticks", return_value=1500):
            player.take_damage(10)

        self.assertEqual(player.current_hp, player.max_hp - 2)

    def test_attack_applies_boost_and_upgrade_multipliers(self):
        class DummyHitbox:
            def __init__(self, damage):
                self.damage = damage
                self.glow_calls = 0

            def set_glow(self):
                self.glow_calls += 1

        class DummyWeapon:
            def __init__(self, result):
                self.result = result

            def attack(self, *_args):
                return self.result

        player = Player(32, 32)
        hitbox = DummyHitbox(10)
        player.weapons = [DummyWeapon(hitbox)]
        player.weapon_ids = ["axe"]
        player.weapon_upgrade_tiers = {"axe": 2}
        player.attack_boost_until = 1000

        with patch("pygame.time.get_ticks", return_value=0):
            result = player.attack()

        expected_damage = int(10 * ATTACK_BOOST_MULTIPLIER * (WEAPON_PLUS_MULTIPLIER ** 2))
        self.assertIs(result, hitbox)
        self.assertEqual(hitbox.damage, expected_damage)
        self.assertEqual(hitbox.glow_calls, 1)

    def test_update_moves_player_and_updates_facing_from_input(self):
        player = Player(32, 32)
        start_x = player.rect.centerx
        keys = {pygame.K_RIGHT: True}

        with patch("pygame.key.get_pressed", return_value=keys):
            player.update([], lambda _x, _y: "floor")

        self.assertGreater(player.rect.centerx, start_x)
        self.assertGreater(player.velocity_x, 0)
        self.assertEqual(player.facing_dx, 1.0)
        self.assertEqual(player.facing_dy, 0.0)
        self.assertFalse(player._on_ice)

    def test_update_respects_wall_collision(self):
        player = Player(32, 32)
        wall = pygame.Rect(player.rect.right + 2, player.rect.y, 10, player.rect.height)
        keys = {pygame.K_RIGHT: True}

        with patch("pygame.key.get_pressed", return_value=keys):
            player.update([wall], lambda _x, _y: "floor")

        self.assertLessEqual(player.rect.right, wall.left)

    def test_place_resets_velocity_via_movement_rules(self):
        player = Player(32, 32)
        player.velocity_x = 3.5
        player.velocity_y = -2.0

        player.place(100, 120)

        self.assertEqual(player.rect.center, (100, 120))
        self.assertEqual(player.velocity_x, 0.0)
        self.assertEqual(player.velocity_y, 0.0)

    def test_update_applies_speed_boost_glow_and_preserves_center(self):
        player = Player(32, 32)
        original_center = player.rect.center
        player.speed_boost_until = 1000

        with patch("pygame.time.get_ticks", return_value=0), patch(
            "pygame.key.get_pressed", return_value={}
        ):
            player.update([], lambda _x, _y: "floor")

        self.assertGreater(player.image.get_width(), player._base_image.get_width())
        self.assertEqual(player.rect.center, original_center)

    def test_update_applies_invincibility_flash_visibility(self):
        player = Player(32, 32)
        player._invincible_until = FLASH_INTERVAL_MS * 4

        with patch("pygame.time.get_ticks", return_value=FLASH_INTERVAL_MS), patch(
            "pygame.key.get_pressed", return_value={}
        ):
            player.update([], lambda _x, _y: "floor")

        self.assertFalse(player._visible)

    def test_reset_for_dungeon_resets_runtime_visual_state(self):
        progress = PlayerProgress()
        player = Player(32, 32)
        player.speed_boost_until = 1000

        with patch("pygame.time.get_ticks", return_value=0), patch(
            "pygame.key.get_pressed", return_value={}
        ):
            player.update([], lambda _x, _y: "floor")

        self.assertGreater(player.image.get_width(), player._base_image.get_width())

        player.reset_for_dungeon(progress)

        self.assertTrue(player._visible)
        self.assertEqual(player.image.get_size(), player._base_image.get_size())

    def test_boost_state_queries_delegate_to_effect_rules(self):
        player = Player(32, 32)
        player.speed_multiplier = 0.75
        player.speed_boost_until = 600
        player.attack_boost_until = 700

        with patch("pygame.time.get_ticks", return_value=500):
            self.assertTrue(player.is_speed_boosted)
            self.assertTrue(player.is_attack_boosted)
            self.assertEqual(player._effective_speed_multiplier(), SPEED_BOOST_MULTIPLIER)

        with patch("pygame.time.get_ticks", return_value=800):
            self.assertFalse(player.is_speed_boosted)
            self.assertFalse(player.is_attack_boosted)
            self.assertEqual(player._effective_speed_multiplier(), 0.75)


if __name__ == "__main__":
    unittest.main()