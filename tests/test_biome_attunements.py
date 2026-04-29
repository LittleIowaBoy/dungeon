"""Tests for the T17 biome attunement meta-progression token.

Covers:
- `record_biome_completion` ticks counters and grants attunements at the
  configured threshold, capped per biome.
- `complete_dungeon_from_runtime` triggers the per-biome counter via the
  dungeon's terrain.
- `begin_dungeon_run` grants +1 of the matching biome trophy per
  attunement, after the snapshot (so abandon reverts the bonus).
- Save/load round-trips the new biome_meta state without mutation.
- Helper introspection (`biome_attunement_progress`,
  `biome_attunement_starting_trophies`).
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from progress import PlayerProgress
from settings import (
    BIOME_ATTUNEMENT_MAX_PER_BIOME,
    BIOME_ATTUNEMENT_THRESHOLD,
    TERRAIN_TROPHY_IDS,
)


def _player_stub():
    """Minimal player stub for `complete_dungeon_from_runtime` paths."""
    player = MagicMock()
    player.coins = 0
    player.armor_hp = 0
    player.compass_uses = 0
    return player


class BiomeAttunementCounterTests(unittest.TestCase):
    def test_record_first_completion_does_not_grant_attunement(self):
        progress = PlayerProgress()
        granted = progress.record_biome_completion("mud")
        self.assertEqual(granted, 0)
        self.assertEqual(progress.biome_completions["mud"], 1)
        self.assertEqual(progress.biome_attunements.get("mud", 0), 0)

    def test_threshold_completions_grant_one_attunement(self):
        progress = PlayerProgress()
        for _ in range(BIOME_ATTUNEMENT_THRESHOLD - 1):
            progress.record_biome_completion("ice")
        self.assertEqual(progress.biome_attunements.get("ice", 0), 0)
        granted = progress.record_biome_completion("ice")
        self.assertEqual(granted, 1)
        self.assertEqual(progress.biome_attunements["ice"], 1)

    def test_attunement_caps_per_biome(self):
        progress = PlayerProgress()
        # Drive completions well past the cap-worth of thresholds.
        total = (BIOME_ATTUNEMENT_MAX_PER_BIOME + 2) * BIOME_ATTUNEMENT_THRESHOLD
        for _ in range(total):
            progress.record_biome_completion("water")
        self.assertEqual(
            progress.biome_attunements["water"], BIOME_ATTUNEMENT_MAX_PER_BIOME
        )
        # Counter keeps ticking even after cap so dossier UIs can show
        # lifetime completions, but no further attunements are granted.
        self.assertEqual(progress.biome_completions["water"], total)

    def test_unknown_terrain_is_ignored(self):
        progress = PlayerProgress()
        granted = progress.record_biome_completion("lava")
        self.assertEqual(granted, 0)
        self.assertEqual(progress.biome_completions, {})
        self.assertEqual(progress.biome_attunements, {})

    def test_attunement_progress_reports_completions_toward_next(self):
        progress = PlayerProgress()
        progress.record_biome_completion("mud")
        toward, threshold = progress.biome_attunement_progress("mud")
        self.assertEqual(toward, 1)
        self.assertEqual(threshold, BIOME_ATTUNEMENT_THRESHOLD)

    def test_attunement_progress_reports_zero_at_cap(self):
        progress = PlayerProgress()
        progress.biome_attunements["mud"] = BIOME_ATTUNEMENT_MAX_PER_BIOME
        toward, threshold = progress.biome_attunement_progress("mud")
        self.assertEqual(toward, 0)
        self.assertEqual(threshold, BIOME_ATTUNEMENT_THRESHOLD)


class CompleteDungeonAdvancesAttunementsTests(unittest.TestCase):
    def test_complete_dungeon_ticks_terrain_counter(self):
        progress = PlayerProgress()
        progress.complete_dungeon_from_runtime("mud_caverns", _player_stub())
        # mud_caverns has terrain_type "mud" in dungeon_config.DUNGEONS.
        self.assertEqual(progress.biome_completions.get("mud"), 1)


class StartingTrophyGrantTests(unittest.TestCase):
    def test_attunement_grants_trophy_at_run_start(self):
        progress = PlayerProgress()
        progress.biome_attunements["mud"] = 2  # → +2 stat_shards per run
        before = progress.inventory.get("stat_shard", 0)
        progress.begin_dungeon_run("mud_caverns")
        self.assertEqual(progress.inventory["stat_shard"], before + 2)

    def test_no_attunement_grants_no_trophy(self):
        progress = PlayerProgress()
        progress.begin_dungeon_run("mud_caverns")
        self.assertEqual(progress.inventory.get("stat_shard", 0), 0)

    def test_abandon_reverts_attunement_grant(self):
        progress = PlayerProgress()
        progress.biome_attunements["ice"] = 1
        snapshot = progress.begin_dungeon_run("frozen_depths")
        # Live inventory holds the bonus trophy.
        self.assertEqual(progress.inventory.get("tempo_rune", 0), 1)
        # Snapshot was taken pre-grant, so abandon strips the trophy.
        progress.abandon_dungeon_run(snapshot)
        self.assertEqual(progress.inventory.get("tempo_rune", 0), 0)

    def test_starting_trophy_count_helper(self):
        progress = PlayerProgress()
        progress.biome_attunements["water"] = 3
        self.assertEqual(
            progress.biome_attunement_starting_trophies("sunken_ruins"), 3
        )
        self.assertEqual(
            progress.biome_attunement_starting_trophies("mud_caverns"), 0
        )


class BiomeMetaPersistenceTests(unittest.TestCase):
    def setUp(self):
        # Isolated DB per test using a temp dir.
        import save_system
        self._save_system = save_system
        self._tmp = tempfile.TemporaryDirectory()
        self._original_db = save_system._DB_PATH
        save_system._DB_PATH = os.path.join(self._tmp.name, "save.db")

    def tearDown(self):
        self._save_system._DB_PATH = self._original_db
        self._tmp.cleanup()

    def test_save_and_load_roundtrips_biome_meta(self):
        progress = PlayerProgress()
        progress.biome_completions = {"mud": 4, "ice": 2, "water": 9}
        progress.biome_attunements = {"mud": 1, "water": 3}
        self._save_system.save_progress(progress)

        loaded = self._save_system.load_progress()
        self.assertEqual(loaded.biome_completions["mud"], 4)
        self.assertEqual(loaded.biome_completions["ice"], 2)
        self.assertEqual(loaded.biome_completions["water"], 9)
        self.assertEqual(loaded.biome_attunements["mud"], 1)
        self.assertEqual(loaded.biome_attunements["water"], 3)
        self.assertNotIn("ice", loaded.biome_attunements)

    def test_fresh_save_load_yields_empty_dicts(self):
        progress = PlayerProgress()
        self._save_system.save_progress(progress)
        loaded = self._save_system.load_progress()
        self.assertEqual(loaded.biome_completions, {})
        self.assertEqual(loaded.biome_attunements, {})


if __name__ == "__main__":
    unittest.main()
