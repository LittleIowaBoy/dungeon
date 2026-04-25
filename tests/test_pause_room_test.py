"""Tests for the test-room pause menu (All Items / All Runes) and the
snapshot/restore that wraps a tuning-test-room session."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import loadout_rules  # noqa: E402
import rune_rules  # noqa: E402
from menu import (  # noqa: E402
    AllItemsPauseScreen,
    AllRunesPauseScreen,
    PauseScreen,
)
from progress import PlayerProgress  # noqa: E402
from rune_catalog import (  # noqa: E402
    RUNE_CATEGORY_BEHAVIOR,
    RUNE_CATEGORY_IDENTITY,
    RUNE_CATEGORY_STAT,
    RUNE_DATABASE,
    RUNE_SLOT_CAPACITY,
    runes_by_category,
)


def setUpModule():
    pygame.init()


class _Holder:
    """Minimal duck-typed stand-in matching `progress.equipped_runes`."""

    def __init__(self):
        self.equipped_runes = rune_rules.empty_loadout()


class ForceEquipItemTests(unittest.TestCase):
    def test_force_equip_bypasses_ownership(self):
        progress = PlayerProgress()
        progress.equipment_storage.pop("iron_helmet", None)
        self.assertFalse(loadout_rules.equip_item(progress, "helmet", "iron_helmet"))
        self.assertTrue(loadout_rules.force_equip_item(progress, "helmet", "iron_helmet"))
        self.assertEqual(progress.equipped_slots["helmet"], "iron_helmet")
        # storage was not mutated (still 0/missing)
        self.assertEqual(progress.equipment_storage.get("iron_helmet", 0), 0)

    def test_force_equip_validates_slot_compatibility(self):
        progress = PlayerProgress()
        # iron_helmet only fits "helmet"; trying weapon_1 must fail.
        self.assertFalse(loadout_rules.force_equip_item(progress, "weapon_1", "iron_helmet"))

    def test_force_equip_rejects_unknown_item(self):
        progress = PlayerProgress()
        self.assertFalse(loadout_rules.force_equip_item(progress, "helmet", "nonexistent"))

    def test_force_equip_rejects_dual_weapon(self):
        progress = PlayerProgress()
        loadout_rules.force_equip_item(progress, "weapon_1", "sword")
        self.assertFalse(loadout_rules.force_equip_item(progress, "weapon_2", "sword"))

    def test_force_unequip_clears_slot_without_storage(self):
        progress = PlayerProgress()
        loadout_rules.force_equip_item(progress, "helmet", "iron_helmet")
        before = progress.equipment_storage.get("iron_helmet", 0)
        self.assertTrue(loadout_rules.force_unequip_slot(progress, "helmet"))
        self.assertIsNone(progress.equipped_slots["helmet"])
        self.assertEqual(progress.equipment_storage.get("iron_helmet", 0), before)


class ForceEquipRuneTests(unittest.TestCase):
    def test_force_equip_bypasses_ownership(self):
        holder = _Holder()
        rune_id = runes_by_category(RUNE_CATEGORY_BEHAVIOR)[0].rune_id
        self.assertTrue(rune_rules.force_equip_rune(holder, rune_id))
        self.assertIn(rune_id, holder.equipped_runes[RUNE_CATEGORY_BEHAVIOR])

    def test_force_equip_respects_category_capacity_by_dropping_oldest(self):
        holder = _Holder()
        stat_runes = runes_by_category(RUNE_CATEGORY_STAT)
        capacity = RUNE_SLOT_CAPACITY[RUNE_CATEGORY_STAT]
        # Equip one more than capacity; oldest should be dropped.
        chosen = [r.rune_id for r in stat_runes[: capacity + 1]]
        for rune_id in chosen:
            self.assertTrue(rune_rules.force_equip_rune(holder, rune_id))
        equipped = holder.equipped_runes[RUNE_CATEGORY_STAT]
        self.assertEqual(len(equipped), capacity)
        self.assertNotIn(chosen[0], equipped)
        self.assertIn(chosen[-1], equipped)

    def test_force_equip_idempotent(self):
        holder = _Holder()
        rune_id = runes_by_category(RUNE_CATEGORY_IDENTITY)[0].rune_id
        rune_rules.force_equip_rune(holder, rune_id)
        rune_rules.force_equip_rune(holder, rune_id)
        self.assertEqual(holder.equipped_runes[RUNE_CATEGORY_IDENTITY].count(rune_id), 1)

    def test_force_equip_unknown_rune(self):
        holder = _Holder()
        self.assertFalse(rune_rules.force_equip_rune(holder, "nonexistent_rune"))


class PauseScreenRoomTestModeTests(unittest.TestCase):
    def test_default_mode_omits_all_items_and_runes(self):
        screen = PauseScreen()
        labels = screen.option_labels()
        self.assertNotIn("All Items", labels)
        self.assertNotIn("All Runes", labels)

    def test_room_test_mode_exposes_full_catalog_options(self):
        screen = PauseScreen(room_test_mode=True)
        labels = screen.option_labels()
        self.assertIn("All Items", labels)
        self.assertIn("All Runes", labels)
        # Toggle index aligns with the room-identifier option.
        toggle_label = labels[screen._toggle_index()]
        self.assertTrue(toggle_label.startswith("Room Identifier"))

    def test_select_all_items_returns_choice(self):
        screen = PauseScreen(room_test_mode=True)
        labels = screen.option_labels()
        screen.selected = labels.index("All Items")
        result = screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        )
        self.assertEqual(result, "All Items")

    def test_toggle_room_identifier_choice_at_correct_index(self):
        screen = PauseScreen(room_test_mode=True, room_identifier_enabled=True)
        screen.selected = screen._toggle_index()
        result = screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        )
        self.assertEqual(result, "Toggle Room Identifier")


class AllItemsPauseScreenTests(unittest.TestCase):
    def test_enter_equips_first_compatible_item(self):
        progress = PlayerProgress()
        progress.equipped_slots["helmet"] = None
        screen = AllItemsPauseScreen(progress)
        # Navigate to helmet slot
        helmet_idx = next(i for i, (k, _) in enumerate(screen.SLOTS) if k == "helmet")
        screen.selected_slot = helmet_idx
        screen.focus = "items"
        screen.selected_item = 0
        screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        )
        self.assertIsNotNone(progress.equipped_slots["helmet"])

    def test_backspace_unequips_current_slot(self):
        progress = PlayerProgress()
        loadout_rules.force_equip_item(progress, "helmet", "iron_helmet")
        screen = AllItemsPauseScreen(progress)
        helmet_idx = next(i for i, (k, _) in enumerate(screen.SLOTS) if k == "helmet")
        screen.selected_slot = helmet_idx
        screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE)]
        )
        self.assertIsNone(progress.equipped_slots["helmet"])

    def test_escape_returns_back_signal(self):
        progress = PlayerProgress()
        screen = AllItemsPauseScreen(progress)
        result = screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)]
        )
        self.assertEqual(result, "back")


class AllRunesPauseScreenTests(unittest.TestCase):
    def test_enter_equips_unowned_rune(self):
        progress = PlayerProgress()
        progress.equipped_runes = rune_rules.empty_loadout()
        screen = AllRunesPauseScreen(progress)
        rune_ids = screen._all_rune_ids()
        screen.selected = 0
        screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        )
        first_rune = RUNE_DATABASE[rune_ids[0]]
        self.assertIn(rune_ids[0], progress.equipped_runes[first_rune.category])

    def test_enter_on_equipped_unequips(self):
        progress = PlayerProgress()
        progress.equipped_runes = rune_rules.empty_loadout()
        screen = AllRunesPauseScreen(progress)
        rune_ids = screen._all_rune_ids()
        rune_id = rune_ids[0]
        rune_rules.force_equip_rune(progress, rune_id)
        screen.selected = 0
        screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        )
        first_rune = RUNE_DATABASE[rune_id]
        self.assertNotIn(rune_id, progress.equipped_runes[first_rune.category])

    def test_force_equip_through_screen_respects_capacity(self):
        progress = PlayerProgress()
        progress.equipped_runes = rune_rules.empty_loadout()
        screen = AllRunesPauseScreen(progress)
        rune_ids = screen._all_rune_ids()
        # Equip a few stat runes via the screen
        stat_indices = [
            i for i, rid in enumerate(rune_ids)
            if RUNE_DATABASE[rid].category == RUNE_CATEGORY_STAT
        ]
        for idx in stat_indices[: RUNE_SLOT_CAPACITY[RUNE_CATEGORY_STAT] + 2]:
            screen.selected = idx
            screen.handle_events(
                [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
            )
        equipped = progress.equipped_runes[RUNE_CATEGORY_STAT]
        self.assertLessEqual(len(equipped), RUNE_SLOT_CAPACITY[RUNE_CATEGORY_STAT])

    def test_escape_returns_back_signal(self):
        progress = PlayerProgress()
        screen = AllRunesPauseScreen(progress)
        result = screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)]
        )
        self.assertEqual(result, "back")


class RoomTestSnapshotRestoreTests(unittest.TestCase):
    """Verify that `_snapshot_room_test_loadout` / `_restore_room_test_loadout`
    on the Game class round-trip equipped state without persisting edits."""

    def _build_minimal_game(self):
        from rpg import Game
        # Bypass __init__ side-effects (window creation, dungeon generation):
        game = Game.__new__(Game)
        game.progress = PlayerProgress()
        game._pause_screen = SimpleNamespace(room_test_mode=False, selected=0,
                                              room_identifier_enabled=True)
        game._all_items_screen = None
        game._all_runes_screen = None
        game._room_test_loadout_snapshot = None
        return game

    def test_snapshot_then_restore_round_trips_equipped_slots(self):
        game = self._build_minimal_game()
        original_slots = dict(game.progress.equipped_slots)
        game._room_test_loadout_snapshot = game._snapshot_room_test_loadout()
        # Mutate after snapshot.
        loadout_rules.force_equip_item(game.progress, "helmet", "iron_helmet")
        self.assertEqual(game.progress.equipped_slots["helmet"], "iron_helmet")
        game._restore_room_test_loadout()
        self.assertEqual(game.progress.equipped_slots, original_slots)

    def test_snapshot_then_restore_round_trips_equipped_runes(self):
        game = self._build_minimal_game()
        rune_id = runes_by_category(RUNE_CATEGORY_BEHAVIOR)[0].rune_id
        game._room_test_loadout_snapshot = game._snapshot_room_test_loadout()
        rune_rules.force_equip_rune(game.progress, rune_id)
        self.assertIn(rune_id, game.progress.equipped_runes[RUNE_CATEGORY_BEHAVIOR])
        game._restore_room_test_loadout()
        self.assertNotIn(rune_id, game.progress.equipped_runes[RUNE_CATEGORY_BEHAVIOR])

    def test_restore_clears_snapshot_and_disables_pause_room_test_mode(self):
        game = self._build_minimal_game()
        game._pause_screen.room_test_mode = True
        game._room_test_loadout_snapshot = game._snapshot_room_test_loadout()
        game._all_items_screen = AllItemsPauseScreen(game.progress)
        game._all_runes_screen = AllRunesPauseScreen(game.progress)
        game._restore_room_test_loadout()
        self.assertIsNone(game._room_test_loadout_snapshot)
        self.assertFalse(game._pause_screen.room_test_mode)
        self.assertIsNone(game._all_items_screen)
        self.assertIsNone(game._all_runes_screen)

    def test_restore_with_no_snapshot_is_noop(self):
        game = self._build_minimal_game()
        original_slots = dict(game.progress.equipped_slots)
        game._restore_room_test_loadout()  # snapshot is None
        self.assertEqual(game.progress.equipped_slots, original_slots)


if __name__ == "__main__":
    unittest.main()
