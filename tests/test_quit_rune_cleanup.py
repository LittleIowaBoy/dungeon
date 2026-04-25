"""Tests for the rune-persistence bug fix (Phase 5).

Two protections combined:
1. ``progress.begin_dungeon_run`` defensively clears ``equipped_runes``
   before snapshotting, so leaked runes from prior sessions are wiped on
   the next run.
2. ``rpg.Game._handle_global_quit`` calls ``abandon_dungeon_run`` (and
   skips ``_sync_player_state_to_progress``) when a dungeon run is active
   so picked-but-uncommitted runes during a live run do not leak to save.
"""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import rune_rules  # noqa: E402
from progress import PlayerProgress  # noqa: E402
from rune_catalog import (  # noqa: E402
    RUNE_CATEGORY_BEHAVIOR,
    runes_by_category,
)


def setUpModule():
    pygame.init()


class BeginDungeonRunRuneClearTests(unittest.TestCase):
    def test_begin_dungeon_run_clears_leaked_equipped_runes(self):
        progress = PlayerProgress()
        rune_id = runes_by_category(RUNE_CATEGORY_BEHAVIOR)[0].rune_id
        # Simulate a leak from a prior session.
        progress.equipped_runes[RUNE_CATEGORY_BEHAVIOR] = [rune_id]

        snapshot = progress.begin_dungeon_run("mud_caverns")

        self.assertEqual(progress.equipped_runes, rune_rules.empty_loadout())
        # Snapshot also reflects the cleansed state, so an abandon will not
        # restore the leaked runes.
        self.assertEqual(
            snapshot["equipped_runes"],
            rune_rules.serialize_loadout(rune_rules.empty_loadout()),
        )

    def test_abandon_after_begin_run_restores_clean_runes(self):
        progress = PlayerProgress()
        rune_id = runes_by_category(RUNE_CATEGORY_BEHAVIOR)[0].rune_id
        progress.equipped_runes[RUNE_CATEGORY_BEHAVIOR] = [rune_id]

        snapshot = progress.begin_dungeon_run("mud_caverns")
        # Player picks another rune mid-run.
        rune_rules.force_equip_rune(progress, rune_id)
        self.assertIn(rune_id, progress.equipped_runes[RUNE_CATEGORY_BEHAVIOR])

        progress.abandon_dungeon_run(snapshot)
        self.assertEqual(progress.equipped_runes, rune_rules.empty_loadout())


class GlobalQuitHandlerTests(unittest.TestCase):
    """Use Game._handle_global_quit directly with stubbed state."""

    def _build_game(self, *, room_test=False, snapshot=None):
        from rpg import Game
        game = Game.__new__(Game)
        game._room_test_entry = SimpleNamespace() if room_test else None
        game._pre_level_progress_snapshot = snapshot
        game._room_test_loadout_snapshot = None
        game.progress = SimpleNamespace(
            abandon_dungeon_run=Mock(),
            equipped_slots={},
            equipment_storage={},
            equipped_runes=rune_rules.empty_loadout(),
        )
        game.player = SimpleNamespace()
        game._sync_player_state_to_progress = Mock()
        game._restore_room_test_loadout = Mock()
        return game

    def test_quit_during_dungeon_run_abandons_before_save(self):
        from rpg import Game
        snapshot = {"coins": 5}
        game = self._build_game(snapshot=snapshot)
        with patch("rpg.save_progress") as save_progress:
            Game._handle_global_quit(game)
        game.progress.abandon_dungeon_run.assert_called_once_with(snapshot)
        game._sync_player_state_to_progress.assert_not_called()
        save_progress.assert_called_once_with(game.progress)

    def test_quit_in_room_test_restores_loadout_before_save(self):
        from rpg import Game
        game = self._build_game(room_test=True)
        with patch("rpg.save_progress") as save_progress:
            Game._handle_global_quit(game)
        game._restore_room_test_loadout.assert_called_once_with()
        game.progress.abandon_dungeon_run.assert_not_called()
        game._sync_player_state_to_progress.assert_not_called()
        save_progress.assert_called_once_with(game.progress)

    def test_quit_in_menu_syncs_player_state_and_saves(self):
        from rpg import Game
        game = self._build_game()  # snapshot=None, no room test
        with patch("rpg.save_progress") as save_progress:
            Game._handle_global_quit(game)
        game._sync_player_state_to_progress.assert_called_once_with()
        game.progress.abandon_dungeon_run.assert_not_called()
        save_progress.assert_called_once_with(game.progress)


if __name__ == "__main__":
    unittest.main()
