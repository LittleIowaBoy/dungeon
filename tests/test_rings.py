"""Tests for Phase F4: Rings — slots, unlock logic, duplicate guard, perks."""
import unittest
from types import SimpleNamespace

import armor_rules
import dodge_rules
import loadout_rules
from item_catalog import (
    EQUIPMENT_SLOTS,
    ITEM_DATABASE,
    RING_EQUIPMENT_SLOTS,
    DEFAULT_EQUIPPED_SLOTS,
)
from armor_rules import (
    aggregate_equipped_stats,
    EQUIPMENT_STAT_BONUSES,
    total_damage_resistance,
)
from loadout_rules import (
    can_equip,
    unlocked_ring_slot_count,
    is_ring_slot_unlocked,
)


# ── helpers ───────────────────────────────────────────────────────────────────
def _progress(equipped=None, keystones=0, storage=None):
    p = SimpleNamespace(
        equipped_slots=dict(DEFAULT_EQUIPPED_SLOTS) if equipped is None else equipped,
        equipment_storage=storage or {},
        meta_keystones=keystones,
        armor_hp=0,
    )
    return p


def _player_with_progress(progress=None, facing=(1.0, 0.0)):
    if progress is None:
        progress = _progress()
    p = SimpleNamespace(
        facing_dx=facing[0],
        facing_dy=facing[1],
        progress=progress,
    )
    dodge_rules.reset_runtime_dodge(p)
    p.bonus_dodges_remaining = 0
    return p


# ── EQUIPMENT_SLOTS contains ring slots ──────────────────────────────────────
class RingSlotRegistrationTests(unittest.TestCase):
    def test_four_ring_slots_in_equipment_slots(self):
        for slot in ("ring_1", "ring_2", "ring_3", "ring_4"):
            self.assertIn(slot, EQUIPMENT_SLOTS)

    def test_ring_equipment_slots_constant(self):
        self.assertEqual(tuple(RING_EQUIPMENT_SLOTS), ("ring_1", "ring_2", "ring_3", "ring_4"))

    def test_default_equipped_slots_has_ring_keys(self):
        for slot in RING_EQUIPMENT_SLOTS:
            self.assertIn(slot, DEFAULT_EQUIPPED_SLOTS)
            self.assertIsNone(DEFAULT_EQUIPPED_SLOTS[slot])


# ── Ring items exist in ITEM_DATABASE ────────────────────────────────────────
class RingItemCatalogTests(unittest.TestCase):
    RING_IDS = (
        "band_of_vigor", "band_of_haste", "band_of_focus",
        "band_of_grit", "ember_signet",
        "frostbound_ring", "viper_loop",
        "stormcoil", "arcane_circlet_ring",
        "bloodstone_ring", "wyrm_seal", "oathbinder",
    )

    def test_all_ring_items_exist(self):
        for ring_id in self.RING_IDS:
            with self.subTest(ring_id=ring_id):
                self.assertIn(ring_id, ITEM_DATABASE)

    def test_all_ring_items_are_equippable(self):
        for ring_id in self.RING_IDS:
            with self.subTest(ring_id=ring_id):
                self.assertTrue(ITEM_DATABASE[ring_id].get("is_equippable"))

    def test_all_ring_items_support_all_ring_slots(self):
        for ring_id in self.RING_IDS:
            with self.subTest(ring_id=ring_id):
                slots = ITEM_DATABASE[ring_id].get("equipment_slots", [])
                for slot in RING_EQUIPMENT_SLOTS:
                    self.assertIn(slot, slots)

    def test_all_ring_items_have_accessory_category(self):
        for ring_id in self.RING_IDS:
            with self.subTest(ring_id=ring_id):
                self.assertEqual(ITEM_DATABASE[ring_id].get("category"), "accessory")

    def test_ring_rarity_ordering(self):
        from settings import (
            RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE, RARITY_SUPERIOR,
            RARITY_EXQUISITE, RARITY_EXOTIC, RARITY_LEGENDARY,
        )
        expected = {
            "band_of_vigor": RARITY_COMMON,
            "band_of_haste": RARITY_COMMON,
            "band_of_focus": RARITY_COMMON,
            "band_of_grit": RARITY_UNCOMMON,
            "ember_signet": RARITY_UNCOMMON,
            "frostbound_ring": RARITY_RARE,
            "viper_loop": RARITY_RARE,
            "stormcoil": RARITY_SUPERIOR,
            "arcane_circlet_ring": RARITY_SUPERIOR,
            "bloodstone_ring": RARITY_EXQUISITE,
            "wyrm_seal": RARITY_EXOTIC,
            "oathbinder": RARITY_LEGENDARY,
        }
        for ring_id, rarity in expected.items():
            with self.subTest(ring_id=ring_id):
                self.assertEqual(ITEM_DATABASE[ring_id].get("rarity"), rarity)


# ── Ring slot unlock count ────────────────────────────────────────────────────
class RingSlotUnlockTests(unittest.TestCase):
    def test_zero_keystones_gives_one_slot(self):
        p = _progress(keystones=0)
        self.assertEqual(unlocked_ring_slot_count(p), 1)

    def test_one_keystone_gives_two_slots(self):
        p = _progress(keystones=1)
        self.assertEqual(unlocked_ring_slot_count(p), 2)

    def test_three_keystones_gives_four_slots(self):
        p = _progress(keystones=3)
        self.assertEqual(unlocked_ring_slot_count(p), 4)

    def test_more_than_three_keystones_capped_at_four(self):
        p = _progress(keystones=10)
        self.assertEqual(unlocked_ring_slot_count(p), 4)

    def test_is_ring_slot_unlocked_ring_1_always_true(self):
        p = _progress(keystones=0)
        self.assertTrue(is_ring_slot_unlocked(p, "ring_1"))

    def test_is_ring_slot_unlocked_ring_2_requires_keystone(self):
        p0 = _progress(keystones=0)
        p1 = _progress(keystones=1)
        self.assertFalse(is_ring_slot_unlocked(p0, "ring_2"))
        self.assertTrue(is_ring_slot_unlocked(p1, "ring_2"))

    def test_non_ring_slots_always_unlocked(self):
        p = _progress(keystones=0)
        for slot in ("helmet", "chest", "weapon_1"):
            self.assertTrue(is_ring_slot_unlocked(p, slot))


# ── can_equip ring guard ──────────────────────────────────────────────────────
class RingEquipGuardTests(unittest.TestCase):
    def _storage_with(self, *item_ids):
        return {iid: 1 for iid in item_ids}

    def test_can_equip_ring_1_with_zero_keystones(self):
        p = _progress(keystones=0, storage=self._storage_with("band_of_vigor"))
        self.assertTrue(can_equip(p, "ring_1", "band_of_vigor"))

    def test_cannot_equip_ring_2_with_zero_keystones(self):
        p = _progress(keystones=0, storage=self._storage_with("band_of_vigor"))
        self.assertFalse(can_equip(p, "ring_2", "band_of_vigor"))

    def test_can_equip_ring_2_with_one_keystone(self):
        p = _progress(keystones=1, storage=self._storage_with("band_of_vigor"))
        self.assertTrue(can_equip(p, "ring_2", "band_of_vigor"))

    def test_duplicate_ring_rejected_across_slots(self):
        slots = dict(DEFAULT_EQUIPPED_SLOTS)
        slots["ring_1"] = "band_of_haste"
        p = _progress(
            equipped=slots,
            keystones=3,
            storage=self._storage_with("band_of_haste"),
        )
        # ring_1 already has band_of_haste; ring_2 should reject same id.
        self.assertFalse(can_equip(p, "ring_2", "band_of_haste"))

    def test_different_rings_allowed_in_different_slots(self):
        slots = dict(DEFAULT_EQUIPPED_SLOTS)
        slots["ring_1"] = "band_of_vigor"
        p = _progress(
            equipped=slots,
            keystones=3,
            storage=self._storage_with("band_of_haste"),
        )
        self.assertTrue(can_equip(p, "ring_2", "band_of_haste"))

    def test_equip_same_item_into_its_own_slot_is_noop(self):
        """Already equipped in ring_1 — re-equipping same id is allowed (no-op)."""
        slots = dict(DEFAULT_EQUIPPED_SLOTS)
        slots["ring_1"] = "band_of_vigor"
        p = _progress(
            equipped=slots,
            keystones=3,
            storage=self._storage_with("band_of_vigor"),
        )
        self.assertTrue(can_equip(p, "ring_1", "band_of_vigor"))


# ── Ring stat bonuses aggregate ───────────────────────────────────────────────
class RingStatBonusAggregateTests(unittest.TestCase):
    def test_band_of_vigor_adds_max_hp(self):
        p = _progress(equipped={"ring_1": "band_of_vigor"})
        stats = aggregate_equipped_stats(p)
        self.assertEqual(stats.get("max_hp_bonus", 0), 5)

    def test_band_of_haste_adds_speed(self):
        p = _progress(equipped={"ring_1": "band_of_haste"})
        stats = aggregate_equipped_stats(p)
        self.assertAlmostEqual(stats.get("speed_bonus", 0.0), 0.03)

    def test_bloodstone_ring_adds_lifesteal(self):
        p = _progress(equipped={"ring_1": "bloodstone_ring"})
        stats = aggregate_equipped_stats(p)
        self.assertEqual(stats.get("lifesteal_on_kill", 0), 5)

    def test_oathbinder_adds_bonus_dodges(self):
        p = _progress(equipped={"ring_1": "oathbinder"})
        stats = aggregate_equipped_stats(p)
        self.assertEqual(stats.get("bonus_dodges_per_room", 0), 1)

    def test_stormcoil_negative_cooldown_mult(self):
        p = _progress(equipped={"ring_1": "stormcoil"})
        stats = aggregate_equipped_stats(p)
        self.assertAlmostEqual(stats.get("dodge_cooldown_mult", 0.0), -0.03)

    def test_wyrm_seal_in_stat_bonuses(self):
        self.assertIn("wyrm_seal", EQUIPMENT_STAT_BONUSES)
        bonuses = EQUIPMENT_STAT_BONUSES["wyrm_seal"]
        self.assertEqual(bonuses.get("max_hp_bonus"), 20)
        resist = bonuses.get("damage_resistance", {})
        for elem in ("fire", "ice", "poison", "lightning", "arcane"):
            with self.subTest(element=elem):
                self.assertAlmostEqual(resist.get(elem, 0.0), 0.15)


# ── wyrm_seal damage resistance ──────────────────────────────────────────────
class WyrmSealResistanceTests(unittest.TestCase):
    def test_wyrm_seal_all_elemental_resist(self):
        p = _progress(equipped={"ring_1": "wyrm_seal"})
        for elem in ("fire", "ice", "poison", "lightning", "arcane"):
            with self.subTest(element=elem):
                r = total_damage_resistance(p, elem)
                self.assertAlmostEqual(r, 0.15)

    def test_wyrm_seal_no_physical_resist(self):
        p = _progress(equipped={"ring_1": "wyrm_seal"})
        self.assertAlmostEqual(total_damage_resistance(p, "physical"), 0.0)


# ── Oathbinder bonus dodge ────────────────────────────────────────────────────
class OathbinderBonusDodgeTests(unittest.TestCase):
    def _oathbinder_progress(self):
        p = _progress(equipped={"ring_1": "oathbinder"})
        return p

    def test_reset_bonus_dodges_sets_one_when_oathbinder_equipped(self):
        prog = self._oathbinder_progress()
        player = _player_with_progress(prog)
        dodge_rules.reset_bonus_dodges(player)
        self.assertEqual(player.bonus_dodges_remaining, 1)

    def test_reset_bonus_dodges_zero_without_oathbinder(self):
        prog = _progress(equipped={})
        player = _player_with_progress(prog)
        dodge_rules.reset_bonus_dodges(player)
        self.assertEqual(player.bonus_dodges_remaining, 0)

    def test_bonus_dodge_fires_while_on_cooldown(self):
        """A bonus dodge should succeed even when the normal cooldown is active."""
        prog = self._oathbinder_progress()
        player = _player_with_progress(prog)
        # Trigger a normal dodge to consume the normal cooldown.
        dodge_rules.trigger_dodge(player, 0)
        # Wait until past the active phase (>DODGE_DURATION_MS) but still on cooldown.
        t_after_active = dodge_rules.DODGE_DURATION_MS + 10
        # Now we're on cooldown.  Give one bonus dodge and fire again.
        player.bonus_dodges_remaining = 1
        result = dodge_rules.trigger_dodge(player, t_after_active)
        self.assertTrue(result)

    def test_bonus_dodge_consumed_on_use(self):
        prog = self._oathbinder_progress()
        player = _player_with_progress(prog)
        dodge_rules.trigger_dodge(player, 0)  # use normal dodge
        # Wait until past the active phase so is_dodging is False.
        t_after_active = dodge_rules.DODGE_DURATION_MS + 10
        player.bonus_dodges_remaining = 1
        dodge_rules.trigger_dodge(player, t_after_active)
        self.assertEqual(player.bonus_dodges_remaining, 0)

    def test_bonus_dodge_does_not_reset_cooldown(self):
        """After a bonus dodge, the existing cooldown_until should not move forward."""
        prog = _progress(equipped={})  # no oathbinder; we set manually
        player = _player_with_progress(prog)
        dodge_rules.trigger_dodge(player, 0)
        cooldown_before = player.dodge_cooldown_until
        player.bonus_dodges_remaining = 1
        # Bonus dodge after active phase ends (still on cooldown).
        t_after_active = dodge_rules.DODGE_DURATION_MS + 10
        dodge_rules.trigger_dodge(player, t_after_active)
        # dodge_cooldown_until should be unchanged (bonus dodge doesn't extend it).
        self.assertEqual(player.dodge_cooldown_until, cooldown_before)


# ── Lifesteal via aggregate stats (unit) ─────────────────────────────────────
class LifestealAggregateTests(unittest.TestCase):
    def test_lifesteal_zero_with_no_ring(self):
        p = _progress(equipped={})
        stats = aggregate_equipped_stats(p)
        self.assertEqual(stats.get("lifesteal_on_kill", 0), 0)

    def test_lifesteal_five_with_bloodstone_ring(self):
        p = _progress(equipped={"ring_1": "bloodstone_ring"})
        stats = aggregate_equipped_stats(p)
        self.assertEqual(stats.get("lifesteal_on_kill", 0), 5)
