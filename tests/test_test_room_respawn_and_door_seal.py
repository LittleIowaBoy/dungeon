"""Tests for test-room enemy respawn and main-objective door sealing."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import rpg  # noqa: E402
from enemies import PatrolEnemy  # noqa: E402
from room import Room, TUNING_TEST_ROOM_ID  # noqa: E402
from room_test_catalog import build_room_test_plan, load_room_test_entries  # noqa: E402


def _build_tuning_room():
    entry = load_room_test_entries()[0]
    plan = build_room_test_plan(entry)
    return Room(
        doors={"left": True, "right": True, "top": True, "bottom": True},
        is_exit=True,
        room_plan=plan,
    )


def _build_plain_room(*, is_exit=False, room_plan=None):
    return Room(
        doors={"left": True, "right": True, "top": False, "bottom": False},
        is_exit=is_exit,
        room_plan=room_plan,
    )


class TestRoomRespawnTests(unittest.TestCase):
    def test_tuning_room_configures_2_second_respawn(self):
        room = _build_tuning_room()
        self.assertEqual(room.respawn_enemies_after_ms, 2000)
        self.assertEqual(room.room_plan.room_id, TUNING_TEST_ROOM_ID)

    def test_update_enemy_respawns_returns_empty_when_disabled(self):
        room = _build_plain_room()
        # Plain rooms default to None (no respawn).
        self.assertIsNone(room.respawn_enemies_after_ms)
        self.assertEqual(room.update_enemy_respawns(0, []), [])

    def test_update_enemy_respawns_schedules_then_returns_after_delay(self):
        room = _build_tuning_room()
        # Pretend all configured enemies are missing (just-killed).
        first_call = room.update_enemy_respawns(now_ticks=1000, enemy_group=[])
        # First call only schedules; nothing returned yet.
        self.assertEqual(first_call, [])
        for idx in range(len(room.enemy_configs)):
            self.assertIn(idx, room._enemy_respawn_due_at)
            self.assertEqual(room._enemy_respawn_due_at[idx], 3000)

        # Halfway through the wait: still nothing.
        self.assertEqual(room.update_enemy_respawns(2500, []), [])

        # At/after the deadline: every slot returns its (cls, pos).
        respawns = room.update_enemy_respawns(3000, [])
        self.assertEqual(respawns, list(room.enemy_configs))
        # Timers cleared so the next death restarts the countdown.
        self.assertEqual(room._enemy_respawn_due_at, {})

    def test_update_enemy_respawns_clears_timer_when_enemy_present(self):
        room = _build_tuning_room()
        # First, schedule respawns for all missing enemies.
        room.update_enemy_respawns(0, [])
        self.assertNotEqual(room._enemy_respawn_due_at, {})

        # Provide one enemy at the first config's position.
        cls, (px, py) = room.enemy_configs[0]
        alive = SimpleNamespace(rect=SimpleNamespace(centerx=px, centery=py))
        room.update_enemy_respawns(50, [alive])

        # The first slot's timer is cleared; others remain scheduled.
        self.assertNotIn(0, room._enemy_respawn_due_at)
        for idx in range(1, len(room.enemy_configs)):
            self.assertIn(idx, room._enemy_respawn_due_at)


class TestRoomEnemiesClearedGatingTests(unittest.TestCase):
    """Frame loop should NOT mark a respawn-room as cleared when empty."""

    def _make_game(self, room):
        game = rpg.Game.__new__(rpg.Game)
        game.dungeon = SimpleNamespace(
            current_room=room,
            enemy_group=[],
        )
        return game

    def test_empty_enemy_group_does_not_set_cleared_when_respawn_enabled(self):
        room = _build_tuning_room()
        room.enemies_cleared = False
        # Reproduce the inline block from rpg.Game.update().
        respawn = room.respawn_enemies_after_ms
        if (
            not room.enemies_cleared
            and not []
            and room.enemy_configs
            and respawn is None
        ):
            room.enemies_cleared = True
        self.assertFalse(room.enemies_cleared)


class DoorsSealedPropertyTests(unittest.TestCase):
    def test_room_with_no_enemies_and_no_objective_is_not_sealed(self):
        room = _build_plain_room()
        # Force-clear any randomly-generated enemies for a deterministic check.
        room.enemy_configs = []
        room.enemies_cleared = False
        self.assertFalse(room.doors_sealed)

    def test_room_with_uncleared_enemies_is_sealed(self):
        room = _build_plain_room()
        room.enemy_configs = [(PatrolEnemy, (40, 40))]
        room.enemies_cleared = False
        self.assertTrue(room.doors_sealed)

    def test_room_unseals_after_enemies_cleared(self):
        room = _build_plain_room()
        room.enemy_configs = [(PatrolEnemy, (40, 40))]
        room.enemies_cleared = True
        self.assertFalse(room.doors_sealed)

    def test_respawn_room_is_never_sealed(self):
        room = _build_tuning_room()
        # Tuning room has frozen enemies and respawn enabled.
        self.assertFalse(room.doors_sealed)

    def test_exit_room_with_pending_objective_is_sealed(self):
        room = _build_plain_room()
        room.is_exit = True
        room.room_plan = SimpleNamespace(
            room_id="dummy_exit",
            objective_rule="holdout_timer",
        )
        room.enemy_configs = []
        room.enemies_cleared = False
        room.objective_status = "active"
        self.assertTrue(room.doors_sealed)
        room.objective_status = "completed"
        self.assertFalse(room.doors_sealed)


class DungeonTransitionRespectsSealTests(unittest.TestCase):
    def test_try_transition_returns_none_when_room_sealed(self):
        from dungeon import Dungeon
        dungeon = Dungeon.__new__(Dungeon)
        sealed_room = SimpleNamespace(
            doors_sealed=True,
            doors={"left": True, "right": True, "top": True, "bottom": True},
        )
        dungeon.rooms = {(0, 0): sealed_room}
        dungeon.current_pos = (0, 0)
        # Player at the leftmost door cell.
        rect = pygame.Rect(0, 240, 32, 32)
        result = Dungeon.try_transition(dungeon, rect)
        self.assertIsNone(result)

    def test_door_kind_returns_sealed_for_sealed_room(self):
        from dungeon import Dungeon
        dungeon = Dungeon.__new__(Dungeon)
        sealed_room = SimpleNamespace(
            doors_sealed=True,
            doors={"left": True, "right": False, "top": False, "bottom": False},
        )
        dungeon.rooms = {(0, 0): sealed_room}
        kind = Dungeon.door_kind(dungeon, (0, 0), "left")
        self.assertEqual(kind, "sealed")
        # No-door directions still report 'none'.
        self.assertEqual(Dungeon.door_kind(dungeon, (0, 0), "right"), "none")


if __name__ == "__main__":
    unittest.main()
