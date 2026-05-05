"""Tests for Phase F5: Pendants — slot, catalog, stat bonuses, cleanse."""
import unittest
from types import SimpleNamespace

import armor_rules
import loadout_rules
import status_effects
from item_catalog import (
    EQUIPMENT_SLOTS,
    ITEM_DATABASE,
    DEFAULT_EQUIPPED_SLOTS,
)
from armor_rules import (
    aggregate_equipped_stats,
    total_damage_resistance,
    EQUIPMENT_STAT_BONUSES,
)
from loadout_rules import can_equip, equip_item


# ── helpers ───────────────────────────────────────────────────────────────────
def _progress(equipped=None, storage=None):
    p = SimpleNamespace(
        equipped_slots=dict(DEFAULT_EQUIPPED_SLOTS) if equipped is None else equipped,
        equipment_storage=storage or {},
        meta_keystones=0,
        armor_hp=0,
    )

    def add_to_equipment_storage(iid):
        p.equipment_storage[iid] = p.equipment_storage.get(iid, 0) + 1

    def remove_from_equipment_storage(iid):
        if p.equipment_storage.get(iid, 0) > 0:
            p.equipment_storage[iid] -= 1

    p.add_to_equipment_storage = add_to_equipment_storage
    p.remove_from_equipment_storage = remove_from_equipment_storage
    return p


def _player_with_poison():
    p = SimpleNamespace(statuses={})
    status_effects.apply_status(p, status_effects.POISONED, 0)
    return p


# ── Pendant slot registration ─────────────────────────────────────────────────
class PendantSlotTests(unittest.TestCase):
    def test_pendant_in_equipment_slots(self):
        self.assertIn("pendant", EQUIPMENT_SLOTS)

    def test_pendant_in_default_equipped_slots(self):
        self.assertIn("pendant", DEFAULT_EQUIPPED_SLOTS)
        self.assertIsNone(DEFAULT_EQUIPPED_SLOTS["pendant"])


# ── Pendant items in ITEM_DATABASE ───────────────────────────────────────────
class PendantCatalogTests(unittest.TestCase):
    PENDANT_IDS = (
        "tarnished_amulet", "cinder_pendant", "glacial_locket",
        "serpent_charm", "stormcaller_pendant", "wardstone",
        "aegis_of_the_deep", "prismatic_pendant",
    )

    def test_all_pendant_items_exist(self):
        for pid in self.PENDANT_IDS:
            with self.subTest(pid=pid):
                self.assertIn(pid, ITEM_DATABASE)

    def test_all_pendants_equippable(self):
        for pid in self.PENDANT_IDS:
            with self.subTest(pid=pid):
                self.assertTrue(ITEM_DATABASE[pid].get("is_equippable"))

    def test_all_pendants_slot_is_pendant(self):
        for pid in self.PENDANT_IDS:
            with self.subTest(pid=pid):
                slots = ITEM_DATABASE[pid].get("equipment_slots", [])
                self.assertIn("pendant", slots)
                self.assertEqual(len(slots), 1, msg=f"{pid} should only fit pendant slot")

    def test_all_pendants_accessory_category(self):
        for pid in self.PENDANT_IDS:
            with self.subTest(pid=pid):
                self.assertEqual(ITEM_DATABASE[pid].get("category"), "accessory")

    def test_pendant_rarity_spread(self):
        from settings import (
            RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE,
            RARITY_SUPERIOR, RARITY_EXQUISITE, RARITY_LEGENDARY,
        )
        expected = {
            "tarnished_amulet": RARITY_COMMON,
            "cinder_pendant": RARITY_UNCOMMON,
            "glacial_locket": RARITY_UNCOMMON,
            "serpent_charm": RARITY_RARE,
            "stormcaller_pendant": RARITY_RARE,
            "wardstone": RARITY_SUPERIOR,
            "aegis_of_the_deep": RARITY_EXQUISITE,
            "prismatic_pendant": RARITY_LEGENDARY,
        }
        for pid, rarity in expected.items():
            with self.subTest(pid=pid):
                self.assertEqual(ITEM_DATABASE[pid].get("rarity"), rarity)


# ── Pendant can_equip ─────────────────────────────────────────────────────────
class PendantEquipTests(unittest.TestCase):
    def test_can_equip_tarnished_amulet_to_pendant_slot(self):
        p = _progress(storage={"tarnished_amulet": 1})
        self.assertTrue(can_equip(p, "pendant", "tarnished_amulet"))

    def test_cannot_equip_pendant_to_wrong_slot(self):
        p = _progress(storage={"tarnished_amulet": 1})
        self.assertFalse(can_equip(p, "helmet", "tarnished_amulet"))

    def test_cannot_equip_without_storage(self):
        p = _progress(storage={})
        self.assertFalse(can_equip(p, "pendant", "tarnished_amulet"))


# ── Pendant stat bonus aggregation ───────────────────────────────────────────
class PendantResistTests(unittest.TestCase):
    def test_tarnished_amulet_physical_resist(self):
        p = SimpleNamespace(equipped_slots={"pendant": "tarnished_amulet"})
        r = total_damage_resistance(p, "physical")
        self.assertAlmostEqual(r, 0.05)

    def test_cinder_pendant_fire_resist(self):
        p = SimpleNamespace(equipped_slots={"pendant": "cinder_pendant"})
        self.assertAlmostEqual(total_damage_resistance(p, "fire"), 0.15)

    def test_glacial_locket_ice_resist(self):
        p = SimpleNamespace(equipped_slots={"pendant": "glacial_locket"})
        self.assertAlmostEqual(total_damage_resistance(p, "ice"), 0.15)

    def test_serpent_charm_poison_resist(self):
        p = SimpleNamespace(equipped_slots={"pendant": "serpent_charm"})
        self.assertAlmostEqual(total_damage_resistance(p, "poison"), 0.20)

    def test_stormcaller_lightning_resist(self):
        p = SimpleNamespace(equipped_slots={"pendant": "stormcaller_pendant"})
        self.assertAlmostEqual(total_damage_resistance(p, "lightning"), 0.20)

    def test_wardstone_arcane_resist(self):
        p = SimpleNamespace(equipped_slots={"pendant": "wardstone"})
        self.assertAlmostEqual(total_damage_resistance(p, "arcane"), 0.25)

    def test_wardstone_all_type_bonus(self):
        p = SimpleNamespace(equipped_slots={"pendant": "wardstone"})
        for dtype in ("physical", "fire", "ice", "poison", "lightning", "blunt", "pierce"):
            with self.subTest(dtype=dtype):
                r = total_damage_resistance(p, dtype)
                self.assertGreater(r, 0.0)

    def test_aegis_physical_resist_and_hp(self):
        p = SimpleNamespace(equipped_slots={"pendant": "aegis_of_the_deep"})
        self.assertAlmostEqual(total_damage_resistance(p, "physical"), 0.30)
        stats = aggregate_equipped_stats(p)
        self.assertEqual(stats.get("max_hp_bonus", 0), 15)

    def test_prismatic_pendant_all_types(self):
        p = SimpleNamespace(equipped_slots={"pendant": "prismatic_pendant"})
        for dtype in ("physical", "fire", "ice", "poison", "lightning", "arcane", "blunt", "pierce"):
            with self.subTest(dtype=dtype):
                self.assertAlmostEqual(total_damage_resistance(p, dtype), 0.20)

    def test_resistance_stacks_with_ring(self):
        """glacier_locket + frostbound_ring should combine ice resist."""
        p = SimpleNamespace(equipped_slots={
            "pendant": "glacial_locket",   # +15% ice
            "ring_1": "frostbound_ring",   # +15% ice
        })
        r = total_damage_resistance(p, "ice")
        self.assertAlmostEqual(r, 0.30)

    def test_resistance_caps_at_85_percent(self):
        """Stacking lots of resist should not exceed 85%."""
        p = SimpleNamespace(equipped_slots={
            "pendant": "prismatic_pendant",  # +20%
            "ring_1": "wyrm_seal",           # +15%
            "ring_2": "frostbound_ring",     # +15% ice only
        })
        r = total_damage_resistance(p, "ice")
        self.assertLessEqual(r, 0.85)


# ── serpent_charm cleanse on equip ───────────────────────────────────────────
class SerpentCharmCleanseTests(unittest.TestCase):
    def test_equip_cleanses_poison_on_player(self):
        prog = _progress(storage={"serpent_charm": 1})
        player = _player_with_poison()
        self.assertTrue(status_effects.has_status(player, status_effects.POISONED))
        equip_item(prog, "pendant", "serpent_charm", player=player)
        self.assertFalse(status_effects.has_status(player, status_effects.POISONED))

    def test_equip_without_player_arg_still_succeeds(self):
        """No player kwarg — cleanse hook silently skipped."""
        prog = _progress(storage={"serpent_charm": 1})
        result = equip_item(prog, "pendant", "serpent_charm")
        self.assertTrue(result)
        self.assertEqual(prog.equipped_slots.get("pendant"), "serpent_charm")

    def test_equip_serpent_charm_when_no_poison_is_harmless(self):
        prog = _progress(storage={"serpent_charm": 1})
        player = SimpleNamespace(statuses={})  # no poison
        result = equip_item(prog, "pendant", "serpent_charm", player=player)
        self.assertTrue(result)

    def test_other_pendants_do_not_cleanse(self):
        """Equipping glacial_locket should NOT clear poison even with player arg."""
        prog = _progress(storage={"glacial_locket": 1})
        player = _player_with_poison()
        equip_item(prog, "pendant", "glacial_locket", player=player)
        self.assertTrue(status_effects.has_status(player, status_effects.POISONED))
