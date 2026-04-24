"""Tests for rune_rules: equip/unequip semantics, slot capacity, normalization."""

import unittest

import rune_rules
from rune_catalog import (
    RUNE_CATEGORY_BEHAVIOR,
    RUNE_CATEGORY_IDENTITY,
    RUNE_CATEGORY_STAT,
    RUNE_SLOT_CAPACITY,
    runes_by_category,
)


class _Holder:
    """Minimal duck-typed stand-in for Player or PlayerProgress."""

    def __init__(self):
        self.equipped_runes = rune_rules.empty_loadout()


def _stat_ids(count):
    return [rune.rune_id for rune in runes_by_category(RUNE_CATEGORY_STAT)[:count]]


class EmptyLoadoutTests(unittest.TestCase):
    def test_empty_loadout_has_one_list_per_category(self):
        loadout = rune_rules.empty_loadout()
        self.assertEqual(set(loadout), set(RUNE_SLOT_CAPACITY))
        for runes in loadout.values():
            self.assertEqual(runes, [])

    def test_empty_loadouts_are_independent(self):
        a = rune_rules.empty_loadout()
        b = rune_rules.empty_loadout()
        a[RUNE_CATEGORY_STAT].append("bloodthirst")
        self.assertEqual(b[RUNE_CATEGORY_STAT], [])


class EquipUnequipTests(unittest.TestCase):
    def test_equip_unknown_rune_returns_false(self):
        holder = _Holder()
        self.assertFalse(rune_rules.equip_rune(holder, "not_a_rune"))

    def test_equip_then_query_with_has_rune(self):
        holder = _Holder()
        stat_id = _stat_ids(1)[0]
        self.assertTrue(rune_rules.equip_rune(holder, stat_id))
        self.assertTrue(rune_rules.has_rune(holder, stat_id))

    def test_equip_same_rune_twice_is_rejected(self):
        holder = _Holder()
        stat_id = _stat_ids(1)[0]
        rune_rules.equip_rune(holder, stat_id)
        self.assertFalse(rune_rules.equip_rune(holder, stat_id))

    def test_equip_at_capacity_without_replace_index_fails(self):
        holder = _Holder()
        capacity = RUNE_SLOT_CAPACITY[RUNE_CATEGORY_STAT]
        chosen = _stat_ids(capacity + 1)
        for rune_id in chosen[:capacity]:
            self.assertTrue(rune_rules.equip_rune(holder, rune_id))
        self.assertFalse(rune_rules.equip_rune(holder, chosen[-1]))

    def test_equip_at_capacity_with_replace_index_swaps(self):
        holder = _Holder()
        capacity = RUNE_SLOT_CAPACITY[RUNE_CATEGORY_STAT]
        chosen = _stat_ids(capacity + 1)
        for rune_id in chosen[:capacity]:
            rune_rules.equip_rune(holder, rune_id)
        self.assertTrue(
            rune_rules.equip_rune(holder, chosen[-1], replace_index=0)
        )
        self.assertEqual(
            holder.equipped_runes[RUNE_CATEGORY_STAT][0],
            chosen[-1],
        )

    def test_unequip_removes_rune(self):
        holder = _Holder()
        stat_id = _stat_ids(1)[0]
        rune_rules.equip_rune(holder, stat_id)
        self.assertTrue(rune_rules.unequip_rune(holder, stat_id))
        self.assertFalse(rune_rules.has_rune(holder, stat_id))

    def test_unequip_missing_rune_returns_false(self):
        holder = _Holder()
        self.assertFalse(rune_rules.unequip_rune(holder, "bloodthirst"))

    def test_clear_loadout_empties_every_category(self):
        holder = _Holder()
        rune_rules.equip_rune(holder, _stat_ids(1)[0])
        rune_rules.clear_loadout(holder)
        for runes in holder.equipped_runes.values():
            self.assertEqual(runes, [])


class NormalizeLoadoutTests(unittest.TestCase):
    def test_unknown_ids_are_dropped(self):
        loadout = {RUNE_CATEGORY_STAT: ["not_real", _stat_ids(1)[0]]}
        normalized = rune_rules.normalize_loadout(loadout)
        self.assertEqual(normalized[RUNE_CATEGORY_STAT], [_stat_ids(1)[0]])

    def test_runes_in_wrong_category_are_dropped(self):
        # behavior rune placed in stat slot list should be dropped
        behavior_id = runes_by_category(RUNE_CATEGORY_BEHAVIOR)[0].rune_id
        normalized = rune_rules.normalize_loadout(
            {RUNE_CATEGORY_STAT: [behavior_id]}
        )
        self.assertEqual(normalized[RUNE_CATEGORY_STAT], [])

    def test_excess_entries_are_truncated(self):
        capacity = RUNE_SLOT_CAPACITY[RUNE_CATEGORY_STAT]
        chosen = _stat_ids(capacity + 2)
        normalized = rune_rules.normalize_loadout({RUNE_CATEGORY_STAT: chosen})
        self.assertEqual(len(normalized[RUNE_CATEGORY_STAT]), capacity)

    def test_serialize_returns_plain_lists(self):
        holder = _Holder()
        rune_rules.equip_rune(holder, _stat_ids(1)[0])
        serialized = rune_rules.serialize_loadout(holder.equipped_runes)
        for value in serialized.values():
            self.assertIsInstance(value, list)


class SyncTests(unittest.TestCase):
    def test_sync_runtime_to_progress_copies_loadout(self):
        progress = _Holder()
        player = _Holder()
        stat_id = _stat_ids(1)[0]
        rune_rules.equip_rune(progress, stat_id)
        rune_rules.sync_runtime_to_progress(player, progress)
        self.assertTrue(rune_rules.has_rune(player, stat_id))
        # mutating player should not leak into progress
        rune_rules.unequip_rune(player, stat_id)
        self.assertTrue(rune_rules.has_rune(progress, stat_id))

    def test_sync_progress_to_runtime_copies_back(self):
        progress = _Holder()
        player = _Holder()
        stat_id = _stat_ids(1)[0]
        rune_rules.equip_rune(player, stat_id)
        rune_rules.sync_progress_to_runtime(progress, player)
        self.assertTrue(rune_rules.has_rune(progress, stat_id))


class OnRoomEnterTests(unittest.TestCase):
    def test_on_room_enter_creates_room_state_namespace(self):
        class _P:
            equipped_runes = rune_rules.empty_loadout()
            rune_state: dict = {}
        p = _P()
        rune_rules.on_room_enter(p)
        self.assertIn("room", p.rune_state)
        self.assertEqual(p.rune_state["room"], {})

    def test_on_room_enter_clears_existing_room_state(self):
        class _P:
            equipped_runes = rune_rules.empty_loadout()
            rune_state: dict = {"room": {"berserker_stack": 5}}
        p = _P()
        rune_rules.on_room_enter(p)
        self.assertEqual(p.rune_state["room"], {})


if __name__ == "__main__":
    unittest.main()
