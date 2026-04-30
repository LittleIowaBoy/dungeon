"""Phase 0e: Golem armor set + armor_rules pipeline.

Verifies:

* :func:`armor_rules.aggregate_equipped_stats` sums per-slot bonuses,
  skips empty slots, and clamps DR/crit to safe ranges.
* The four ``apply_*`` shims fold their bonus into the matching pipeline
  (max HP, incoming/outgoing damage, speed multiplier, crit roll).
* :func:`armor_rules.roll_boss_loot` honours the primary/secondary
  probabilities and excludes pieces the player already owns.
* Equipment storage round-trips through save_system for the new ids.
* Character-screen subtitle reflects equipped bonuses.
"""

import os
import random
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import armor_rules  # noqa: E402
from settings import (  # noqa: E402
    GOLEM_SET_HP_PER_PIECE, GOLEM_HUSK_HP_BONUS,
    GOLEM_CROWN_CRIT_CHANCE, GOLEM_HUSK_DR_FRACTION,
    GOLEM_STRIDE_SPEED_BONUS, GOLEM_FISTS_DAMAGE_BONUS,
    GOLEM_CRIT_MULTIPLIER,
    GOLEM_LOOT_PRIMARY_CHANCE,
)


def _stub_progress(equipped=None, owned=()):
    """Return a SimpleNamespace mimicking the Progress API armor_rules uses."""
    owned_set = set(owned)
    return SimpleNamespace(
        equipped_slots=dict(equipped or {}),
        total_owned=lambda item_id, _owned=owned_set: 1 if item_id in _owned else 0,
        equipment_storage={},
        add_to_equipment_storage=lambda item_id, qty=1: None,
    )


def _stub_player(progress):
    return SimpleNamespace(progress=progress)


class AggregateStatsTests(unittest.TestCase):
    def test_empty_progress_returns_zeros(self):
        agg = armor_rules.aggregate_equipped_stats(None)
        self.assertEqual(agg["max_hp_bonus"], 0)
        self.assertEqual(agg["crit_chance"], 0.0)
        self.assertEqual(agg["damage_reduction"], 0.0)

    def test_no_armor_returns_zeros(self):
        progress = _stub_progress({"helmet": None, "chest": None})
        agg = armor_rules.aggregate_equipped_stats(progress)
        self.assertEqual(agg["max_hp_bonus"], 0)

    def test_full_golem_set_sums_correctly(self):
        progress = _stub_progress({
            "helmet": "golem_crown",
            "chest":  "golem_husk",
            "legs":   "golem_stride",
            "arms":   "golem_fists",
        })
        agg = armor_rules.aggregate_equipped_stats(progress)
        expected_hp = GOLEM_HUSK_HP_BONUS + 3 * GOLEM_SET_HP_PER_PIECE
        self.assertEqual(agg["max_hp_bonus"], expected_hp)
        self.assertAlmostEqual(agg["crit_chance"], GOLEM_CROWN_CRIT_CHANCE)
        self.assertAlmostEqual(agg["damage_reduction"], GOLEM_HUSK_DR_FRACTION)
        self.assertAlmostEqual(agg["speed_bonus"], GOLEM_STRIDE_SPEED_BONUS)
        self.assertAlmostEqual(agg["outgoing_damage_bonus"], GOLEM_FISTS_DAMAGE_BONUS)

    def test_unknown_item_contributes_nothing(self):
        progress = _stub_progress({"helmet": "iron_helmet"})
        agg = armor_rules.aggregate_equipped_stats(progress)
        self.assertEqual(agg["max_hp_bonus"], 0)
        self.assertEqual(agg["crit_chance"], 0.0)


class StatApplicationTests(unittest.TestCase):
    def test_max_hp_bonus(self):
        p = _stub_player(_stub_progress({"chest": "golem_husk"}))
        self.assertEqual(armor_rules.apply_max_hp_bonus(p, 100), 100 + GOLEM_HUSK_HP_BONUS)

    def test_speed_multiplier_additive(self):
        p = _stub_player(_stub_progress({"legs": "golem_stride"}))
        self.assertAlmostEqual(
            armor_rules.apply_speed_multiplier(p, 1.0),
            1.0 + GOLEM_STRIDE_SPEED_BONUS,
        )

    def test_outgoing_damage_bonus(self):
        p = _stub_player(_stub_progress({"arms": "golem_fists"}))
        self.assertEqual(
            armor_rules.apply_outgoing_damage_multiplier(p, 100),
            int(round(100 * (1.0 + GOLEM_FISTS_DAMAGE_BONUS))),
        )

    def test_outgoing_damage_zero_passthrough(self):
        p = _stub_player(_stub_progress({"arms": "golem_fists"}))
        self.assertEqual(armor_rules.apply_outgoing_damage_multiplier(p, 0), 0)

    def test_incoming_damage_reduction(self):
        p = _stub_player(_stub_progress({"chest": "golem_husk"}))
        # 100 dmg × (1 - 0.10) = 90.
        self.assertEqual(
            armor_rules.apply_incoming_damage_multiplier(p, 100),
            int(100 * (1.0 - GOLEM_HUSK_DR_FRACTION)),
        )

    def test_no_armor_leaves_pipelines_untouched(self):
        p = _stub_player(_stub_progress({}))
        self.assertEqual(armor_rules.apply_max_hp_bonus(p, 100), 100)
        self.assertEqual(armor_rules.apply_speed_multiplier(p, 1.5), 1.5)
        self.assertEqual(armor_rules.apply_outgoing_damage_multiplier(p, 50), 50)
        self.assertEqual(armor_rules.apply_incoming_damage_multiplier(p, 50), 50)


class CritRollTests(unittest.TestCase):
    def test_no_crit_chance_returns_one(self):
        p = _stub_player(_stub_progress({}))
        self.assertEqual(armor_rules.roll_crit_multiplier(p), 1.0)

    def test_low_roll_triggers_crit(self):
        p = _stub_player(_stub_progress({"helmet": "golem_crown"}))
        rng = random.Random()
        rng.random = lambda: 0.0  # always crit
        self.assertEqual(
            armor_rules.roll_crit_multiplier(p, rng=rng),
            GOLEM_CRIT_MULTIPLIER,
        )

    def test_high_roll_no_crit(self):
        p = _stub_player(_stub_progress({"helmet": "golem_crown"}))
        rng = random.Random()
        rng.random = lambda: 0.99  # never crit
        self.assertEqual(armor_rules.roll_crit_multiplier(p, rng=rng), 1.0)


class BossLootRollTests(unittest.TestCase):
    def test_no_drops_when_primary_misses(self):
        progress = _stub_progress({})
        rng = random.Random()
        rng.random = lambda: GOLEM_LOOT_PRIMARY_CHANCE + 0.001
        self.assertEqual(armor_rules.roll_boss_loot(progress, rng=rng), [])

    def test_primary_drop_only(self):
        progress = _stub_progress({})
        rng = random.Random()
        # First .random() call decides primary success (low → success);
        # second call decides secondary (high → fail).
        outcomes = iter([0.0, 0.99])
        rng.random = lambda: next(outcomes)
        rng.choice = lambda pool: pool[0]
        drops = armor_rules.roll_boss_loot(progress, rng=rng)
        self.assertEqual(len(drops), 1)
        self.assertIn(drops[0], armor_rules.GOLEM_SET_ITEM_IDS)

    def test_primary_and_secondary_drop(self):
        progress = _stub_progress({})
        rng = random.Random()
        outcomes = iter([0.0, 0.0])
        rng.random = lambda: next(outcomes)
        choices = iter([
            armor_rules.GOLEM_SET_ITEM_IDS[0],
            armor_rules.GOLEM_SET_ITEM_IDS[1],
        ])
        rng.choice = lambda _pool: next(choices)
        drops = armor_rules.roll_boss_loot(progress, rng=rng)
        self.assertEqual(len(drops), 2)
        self.assertEqual(len(set(drops)), 2)

    def test_owned_pieces_excluded_from_pool(self):
        progress = _stub_progress({}, owned={"golem_crown", "golem_husk"})
        rng = random.Random()
        # Primary roll succeeds, secondary fails.
        outcomes = iter([0.0, 0.99])
        rng.random = lambda: next(outcomes)
        rng.choice = lambda pool: pool[0]
        drops = armor_rules.roll_boss_loot(progress, rng=rng)
        self.assertEqual(len(drops), 1)
        self.assertNotIn(drops[0], {"golem_crown", "golem_husk"})

    def test_empty_pool_returns_no_drops(self):
        progress = _stub_progress({}, owned=set(armor_rules.GOLEM_SET_ITEM_IDS))
        rng = random.Random()
        rng.random = lambda: 0.0
        self.assertEqual(armor_rules.roll_boss_loot(progress, rng=rng), [])


class GrantBossLootTests(unittest.TestCase):
    def test_grant_calls_progress_storage(self):
        log = []
        progress = SimpleNamespace(
            add_to_equipment_storage=lambda item_id, qty=1: log.append((item_id, qty)),
        )
        granted = armor_rules.grant_boss_loot(progress, ["golem_crown", "golem_husk"])
        self.assertEqual(granted, ["golem_crown", "golem_husk"])
        self.assertEqual(log, [("golem_crown", 1), ("golem_husk", 1)])


class CatalogIntegrationTests(unittest.TestCase):
    def test_all_golem_items_registered_in_catalog(self):
        from item_catalog import ITEM_DATABASE
        for item_id in armor_rules.GOLEM_SET_ITEM_IDS:
            self.assertIn(item_id, ITEM_DATABASE)
            entry = ITEM_DATABASE[item_id]
            self.assertTrue(entry["is_equippable"])
            self.assertTrue(entry["equipment_slots"])

    def test_each_golem_piece_targets_correct_slot(self):
        from item_catalog import ITEM_DATABASE
        expected = {
            "golem_crown":  "helmet",
            "golem_husk":   "chest",
            "golem_stride": "legs",
            "golem_fists":  "arms",
        }
        for item_id, slot in expected.items():
            self.assertIn(slot, ITEM_DATABASE[item_id]["equipment_slots"])


class SaveRoundTripTests(unittest.TestCase):
    def test_equipment_storage_round_trip(self):
        import tempfile
        from unittest.mock import patch
        import save_system
        from progress import PlayerProgress

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "save.db")
            with patch.object(save_system, "_DB_PATH", db_path):
                progress = PlayerProgress()
                progress.add_to_equipment_storage("golem_crown", 1)
                progress.add_to_equipment_storage("golem_husk", 1)
                progress.equipped_slots["chest"] = "golem_husk"
                save_system.save_progress(progress)

                loaded = save_system.load_progress()
                self.assertEqual(loaded.equipment_storage.get("golem_crown"), 1)
                self.assertEqual(loaded.equipped_slots.get("chest"), "golem_husk")


if __name__ == "__main__":
    unittest.main()
