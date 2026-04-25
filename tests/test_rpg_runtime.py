import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import rpg


class _DummyGroup(list):
    def add(self, item):
        self.append(item)


class _DummyChest:
    def __init__(self):
        self.looted = False
        self.reward_tiers = []
        self.restore_calls = 0

    def mark_looted(self):
        self.looted = True

    def restore_for_reclaim(self):
        self.looted = False
        self.restore_calls += 1

    def set_reward_tier(self, reward_tier):
        self.reward_tiers.append(reward_tier)


class _DummyEnemy:
    def __init__(self, x, y):
        self.pos = (x, y)


class _SpawnedChest:
    def __init__(self, x, y, looted=False, reward_tier="standard"):
        self.pos = (x, y)
        self.looted = looted
        self.reward_tier = reward_tier


class GameRuntimeTests(unittest.TestCase):
    def test_toggle_room_identifier_updates_pause_screen_state(self):
        game = rpg.Game.__new__(rpg.Game)
        game._show_room_identifier = True
        game._pause_screen = SimpleNamespace(room_identifier_enabled=True)

        rpg.Game._toggle_room_identifier(game)

        self.assertFalse(game._show_room_identifier)
        self.assertFalse(game._pause_screen.room_identifier_enabled)

    def test_apply_room_objective_update_spawns_enemy_instances(self):
        game = rpg.Game.__new__(rpg.Game)
        game.dungeon = SimpleNamespace(
            enemy_group=_DummyGroup(),
            chest_group=_DummyGroup(),
            current_room=SimpleNamespace(enemies_cleared=False, enemy_configs=[(_DummyEnemy, (0, 0))]),
        )

        rpg.Game._apply_room_objective_update(
            game,
            {
                "kind": "spawn_enemies",
                "enemy_configs": [(_DummyEnemy, (10, 20)), (_DummyEnemy, (30, 40))],
            },
        )

        self.assertEqual([enemy.pos for enemy in game.dungeon.enemy_group], [(10, 20), (30, 40)])

    def test_apply_room_objective_update_marks_looted_and_upgrades_existing_chests(self):
        chest_a = _DummyChest()
        chest_b = _DummyChest()
        game = rpg.Game.__new__(rpg.Game)
        game.dungeon = SimpleNamespace(
            enemy_group=_DummyGroup(),
            chest_group=_DummyGroup([chest_a, chest_b]),
            current_room=SimpleNamespace(enemies_cleared=False, enemy_configs=[]),
        )

        rpg.Game._apply_room_objective_update(game, {"kind": "forfeit_chest"})
        rpg.Game._apply_room_objective_update(
            game,
            {"kind": "upgrade_reward_chest", "reward_tier": "finale_bonus"},
        )

        self.assertTrue(chest_a.looted)
        self.assertTrue(chest_b.looted)
        self.assertEqual(chest_a.reward_tiers, ["finale_bonus"])
        self.assertEqual(chest_b.reward_tiers, ["finale_bonus"])

    def test_apply_room_objective_update_restores_reclaimable_chests(self):
        chest = _DummyChest()
        chest.looted = True
        game = rpg.Game.__new__(rpg.Game)
        game.dungeon = SimpleNamespace(
            enemy_group=_DummyGroup(),
            chest_group=_DummyGroup([chest]),
            current_room=SimpleNamespace(enemies_cleared=False, enemy_configs=[]),
        )

        rpg.Game._apply_room_objective_update(game, {"kind": "restore_chest"})

        self.assertFalse(chest.looted)
        self.assertEqual(chest.restore_calls, 1)

    def test_apply_room_objective_update_spawns_reward_chest_only_when_group_empty(self):
        game = rpg.Game.__new__(rpg.Game)
        game.dungeon = SimpleNamespace(
            enemy_group=_DummyGroup(),
            chest_group=_DummyGroup(),
            current_room=SimpleNamespace(enemies_cleared=False, enemy_configs=[]),
        )

        with patch("rpg.Chest", _SpawnedChest):
            rpg.Game._apply_room_objective_update(
                game,
                {
                    "kind": "spawn_reward_chest",
                    "position": (50, 60),
                    "reward_tier": "branch_bonus",
                },
            )
            rpg.Game._apply_room_objective_update(
                game,
                {
                    "kind": "spawn_reward_chest",
                    "position": (70, 80),
                    "reward_tier": "finale_bonus",
                },
            )

        self.assertEqual(len(game.dungeon.chest_group), 1)
        chest = game.dungeon.chest_group[0]
        self.assertEqual(chest.pos, (50, 60))
        self.assertFalse(chest.looted)
        self.assertEqual(chest.reward_tier, "branch_bonus")

    def test_start_room_test_builds_single_room_dungeon_without_beginning_campaign_run(self):
        entry = SimpleNamespace(profile_dungeon_id="mud_caverns")
        room_plan = SimpleNamespace()
        dungeon = object()
        game = rpg.Game.__new__(rpg.Game)
        game.progress = SimpleNamespace(
            begin_dungeon_run=Mock(),
            equipped_slots={"weapon_1": "sword", "helmet": None},
            equipment_storage={"sword": 1},
            equipped_runes={"stat": [], "behavior": [], "identity": []},
        )
        game._pause_screen = SimpleNamespace(room_test_mode=False, room_identifier_enabled=True)
        game._all_items_screen = None
        game._all_runes_screen = None
        game._room_test_loadout_snapshot = None
        game._pre_level_progress_snapshot = {"coins": 10}

        with patch("rpg.build_room_test_plan", return_value=room_plan) as build_room_test_plan:
            with patch("rpg.Dungeon.from_room_plan", return_value=dungeon) as from_room_plan:
                with patch("rpg.Player") as player_cls:
                    player = player_cls.return_value
                    player.reset_for_dungeon = Mock()
                    with patch.object(rpg.Game, "_room_test_spawn_position", return_value=(123, 456)) as room_test_spawn_position:
                        with patch("rpg.pygame.sprite.GroupSingle", return_value="player-group"):
                            with patch.object(rpg.Game, "_enter_current_room") as enter_room:
                                rpg.Game._start_room_test(game, entry, "top")

        build_room_test_plan.assert_called_once_with(entry)
        from_room_plan.assert_called_once_with("mud_caverns", room_plan, entry_direction="top")
        game.progress.begin_dungeon_run.assert_not_called()
        room_test_spawn_position.assert_called_once_with("top")
        player_cls.assert_called_once_with(123, 456)
        player.reset_for_dungeon.assert_called_once_with(game.progress)
        enter_room.assert_called_once_with(entry_direction="top")
        self.assertIs(game.dungeon, dungeon)
        self.assertIs(game.player, player)
        self.assertEqual(game.player_group, "player-group")
        self.assertIsNone(game._pre_level_progress_snapshot)
        self.assertIs(game._room_test_entry, entry)
        self.assertEqual(game.state, rpg.GameState.PLAYING)

    def test_on_death_returns_to_room_tests_without_persisting_campaign_progress(self):
        game = rpg.Game.__new__(rpg.Game)
        game._room_test_entry = SimpleNamespace(entry_id="ritual")
        game.progress = SimpleNamespace(resolve_dungeon_death=Mock())
        game._return_to_room_tests = Mock()
        game.player = object()
        game._current_dungeon_id = "mud_caverns"

        rpg.Game._on_death(game)

        game.progress.resolve_dungeon_death.assert_not_called()
        game._return_to_room_tests.assert_called_once_with()

    def test_on_level_complete_returns_to_room_tests_immediately(self):
        game = rpg.Game.__new__(rpg.Game)
        game._room_test_entry = SimpleNamespace(entry_id="holdout")
        game._return_to_room_tests = Mock()

        with patch("rpg.save_progress") as save_progress:
            rpg.Game._on_level_complete(game)

        save_progress.assert_not_called()
        game._return_to_room_tests.assert_called_once_with()

    def test_on_level_complete_applies_timed_extraction_bonus_before_completing_dungeon(self):
        room = SimpleNamespace(
            claim_timed_extraction_completion_bonus=Mock(return_value=14),
            room_plan=SimpleNamespace(objective_rule="loot_then_timer"),
            objective_status="escape",
        )
        player = SimpleNamespace(coins=20)
        progress = SimpleNamespace(
            complete_dungeon_from_runtime=Mock(),
        )
        game = rpg.Game.__new__(rpg.Game)
        game._room_test_entry = None
        game._current_dungeon_id = "mud_caverns"
        game.progress = progress
        game.player = player
        game.dungeon = SimpleNamespace(current_room=room)

        with patch("rpg.get_dungeon", return_value={"name": "Mud Caverns"}) as get_dungeon:
            with patch("rpg.LevelCompleteScreen", return_value="level-complete") as level_complete_cls:
                with patch("rpg.save_progress") as save_progress:
                    rpg.Game._on_level_complete(game)

        get_dungeon.assert_called_once_with("mud_caverns")
        room.claim_timed_extraction_completion_bonus.assert_called_once_with()
        self.assertEqual(player.coins, 34)
        progress.complete_dungeon_from_runtime.assert_called_once_with("mud_caverns", player)
        level_complete_cls.assert_called_once_with(
            "Mud Caverns",
            detail_lines=("Clean extraction bonus: +14 coins",),
        )
        save_progress.assert_called_once_with(progress)
        self.assertEqual(game._level_complete, "level-complete")
        self.assertEqual(game.state, rpg.GameState.LEVEL_COMPLETE)

    def test_on_level_complete_marks_overtime_bonus_lost_in_screen_details(self):
        room = SimpleNamespace(
            claim_timed_extraction_completion_bonus=Mock(return_value=0),
            room_plan=SimpleNamespace(objective_rule="loot_then_timer"),
            objective_status="overtime",
        )
        player = SimpleNamespace(coins=20)
        progress = SimpleNamespace(
            complete_dungeon_from_runtime=Mock(),
        )
        game = rpg.Game.__new__(rpg.Game)
        game._room_test_entry = None
        game._current_dungeon_id = "mud_caverns"
        game.progress = progress
        game.player = player
        game.dungeon = SimpleNamespace(current_room=room)

        with patch("rpg.get_dungeon", return_value={"name": "Mud Caverns"}) as get_dungeon:
            with patch("rpg.LevelCompleteScreen", return_value="level-complete") as level_complete_cls:
                with patch("rpg.save_progress") as save_progress:
                    rpg.Game._on_level_complete(game)

        get_dungeon.assert_called_once_with("mud_caverns")
        room.claim_timed_extraction_completion_bonus.assert_called_once_with()
        self.assertEqual(player.coins, 20)
        progress.complete_dungeon_from_runtime.assert_called_once_with("mud_caverns", player)
        level_complete_cls.assert_called_once_with(
            "Mud Caverns",
            detail_lines=("Overtime escape: clean extraction bonus lost",),
        )
        save_progress.assert_called_once_with(progress)

    def test_quit_level_returns_to_room_tests_without_abandoning_snapshot(self):
        game = rpg.Game.__new__(rpg.Game)
        game._room_test_entry = SimpleNamespace(entry_id="stealth")
        game.progress = SimpleNamespace(abandon_dungeon_run=Mock())
        game._pre_level_progress_snapshot = {"coins": 99}
        game._return_to_room_tests = Mock()

        rpg.Game._quit_level(game)

        game.progress.abandon_dungeon_run.assert_not_called()
        game._return_to_room_tests.assert_called_once_with()

    def test_return_to_room_tests_clears_runtime_state(self):
        game = rpg.Game.__new__(rpg.Game)
        game.dungeon = object()
        game.player = object()
        game.player_group = object()
        game._current_dungeon_id = "mud_caverns"
        game._pre_level_progress_snapshot = {"coins": 5}
        game._level_complete = object()
        game._room_test_entry = SimpleNamespace(entry_id="resource")
        game._room_test_loadout_snapshot = None
        game._pause_screen = SimpleNamespace(room_test_mode=False, room_identifier_enabled=True)
        game._all_items_screen = None
        game._all_runes_screen = None

        rpg.Game._return_to_room_tests(game)

        self.assertIsNone(game.dungeon)
        self.assertIsNone(game.player)
        self.assertIsNone(game.player_group)
        self.assertIsNone(game._current_dungeon_id)
        self.assertIsNone(game._pre_level_progress_snapshot)
        self.assertIsNone(game._level_complete)
        self.assertIsNone(game._room_test_entry)
        self.assertEqual(game.state, rpg.GameState.ROOM_TEST_SELECT)

    def test_room_test_spawn_position_places_player_one_tile_inside_entry_door(self):
        # Left door: door_pixel_pos returns x at col 0, inward = right (+1, 0)
        mid_row = rpg.ROOM_ROWS // 2
        door_px = rpg.TILE_SIZE // 2
        door_py = mid_row * rpg.TILE_SIZE + rpg.TILE_SIZE // 2
        expected_x = door_px + rpg.TILE_SIZE   # one tile inward (rightward)
        expected_y = door_py

        room = SimpleNamespace(
            door_pixel_pos=lambda direction: (door_px, door_py),
        )
        game = rpg.Game.__new__(rpg.Game)
        game.dungeon = SimpleNamespace(current_room=room)

        spawn_x, spawn_y = rpg.Game._room_test_spawn_position(game, "left")

        self.assertEqual(spawn_x, expected_x)
        self.assertEqual(spawn_y, expected_y)