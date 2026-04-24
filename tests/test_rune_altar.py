import random
import unittest
from types import SimpleNamespace

import pygame

from objective_entities import RuneAltar
from room import Room
from room_plan import RoomPlan, RoomTemplate
import rune_rules
from rune_catalog import RUNE_DATABASE, RUNE_CATEGORIES
from settings import ROOM_COLS, ROOM_ROWS, TILE_SIZE


def _template():
    return RoomTemplate(
        room_id="rune_altar_chamber",
        display_name="Rune Altar Chamber",
        objective_kind="boon",
        combat_pressure="low",
        decision_complexity="high",
        topology_role="branch",
        min_depth=1,
        max_depth=None,
        branch_preference="branch",
        generation_weight=0,
        enabled=True,
        implementation_status="prototype",
        objective_variant="",
        notes="",
    )


def _plan():
    return RoomPlan(
        position=(0, 0),
        depth=2,
        path_kind="branch",
        is_exit=False,
        template=_template(),
        terrain_type="mud",
        enemy_count_range=(0, 0),
        enemy_type_weights=(50, 35, 15),
        objective_rule="rune_altar",
        objective_duration_ms=None,
        guaranteed_chest=False,
        chest_spawn_chance=None,
        terrain_patch_count_range=(1, 2),
        terrain_patch_size_range=(2, 3),
        clear_center=True,
        reward_tier="standard",
        chest_locked_until_complete=False,
        objective_entity_count=1,
        scripted_wave_sizes=(),
        holdout_zone_radius=0,
        holdout_relief_count=0,
        holdout_relief_delay_ms=0,
        ritual_role_script=(),
        ritual_reinforcement_count=0,
        ritual_link_mode="",
        ritual_payoff_kind="",
        ritual_payoff_label="",
        objective_label="Rune Altar",
        objective_layout_offsets=(),
        objective_spawn_offset=None,
        objective_patrol_offset=None,
        objective_radius=0,
        objective_trigger_padding=0,
        objective_max_hp=0,
        objective_move_speed=0.0,
        objective_guide_radius=0,
        objective_exit_radius=0,
        objective_damage_cooldown_ms=0,
        puzzle_reinforcement_count=0,
        puzzle_stall_duration_ms=0,
    )


def _make_room():
    return Room(
        {"top": False, "bottom": False, "left": True, "right": False},
        is_exit=False,
        room_plan=_plan(),
    )


class _Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(0, 0, 16, 16)
        self.rect.center = (x, y)


class GenerateAltarOfferTests(unittest.TestCase):
    def test_returns_three_distinct_runes_one_per_category(self):
        offer = rune_rules.generate_altar_offer(random.Random(0))
        self.assertEqual(len(offer), 3)
        self.assertEqual(len(set(offer)), 3)
        cats = {RUNE_DATABASE[rid].category for rid in offer}
        self.assertEqual(cats, set(RUNE_CATEGORIES))

    def test_excludes_specified_runes(self):
        first = rune_rules.generate_altar_offer(random.Random(7))
        excluded = first[0]
        again = rune_rules.generate_altar_offer(random.Random(7), exclude_ids=(excluded,))
        self.assertNotIn(excluded, again)

    def test_returns_tuple(self):
        offer = rune_rules.generate_altar_offer(random.Random(0))
        self.assertIsInstance(offer, tuple)


class RoomRuneAltarTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def test_build_rune_altar_configs_produces_one_altar_with_three_runes(self):
        room = _make_room()
        configs = room.objective_entity_configs
        altars = [c for c in configs if c["kind"] == "rune_altar"]
        self.assertEqual(len(altars), 1)
        altar = altars[0]
        self.assertEqual(len(altar["offered_rune_ids"]), 3)
        self.assertEqual(len(set(altar["offered_rune_ids"])), 3)
        self.assertFalse(altar["consumed"])
        cats = {RUNE_DATABASE[rid].category for rid in altar["offered_rune_ids"]}
        self.assertEqual(cats, set(RUNE_CATEGORIES))

    def test_pending_rune_altar_returns_config_when_player_overlaps(self):
        room = _make_room()
        altar = next(c for c in room.objective_entity_configs if c["kind"] == "rune_altar")
        ax, ay = altar["pos"]
        player = _Player(ax, ay)
        self.assertIs(room.pending_rune_altar(player), altar)

    def test_pending_rune_altar_returns_none_when_far(self):
        room = _make_room()
        player = _Player(0, 0)
        self.assertIsNone(room.pending_rune_altar(player))

    def test_consume_rune_altar_marks_consumed_and_blocks_pending(self):
        room = _make_room()
        altar = next(c for c in room.objective_entity_configs if c["kind"] == "rune_altar")
        ax, ay = altar["pos"]
        player = _Player(ax, ay)
        room.consume_rune_altar(altar)
        self.assertTrue(altar["consumed"])
        self.assertIsNone(room.pending_rune_altar(player))

    def test_snooze_clears_when_player_steps_away(self):
        room = _make_room()
        altar = next(c for c in room.objective_entity_configs if c["kind"] == "rune_altar")
        ax, ay = altar["pos"]
        room.snooze_rune_altar(altar)
        # Still snoozed while overlapping → no pick.
        on_top = _Player(ax, ay)
        self.assertIsNone(room.pending_rune_altar(on_top))
        # Step away clears snooze.
        far = _Player(0, 0)
        self.assertIsNone(room.pending_rune_altar(far))
        # Now coming back should pick again.
        self.assertIs(room.pending_rune_altar(on_top), altar)


class EquipAltarPickTests(unittest.TestCase):
    def setUp(self):
        self.player = SimpleNamespace()
        self.progress = SimpleNamespace()

    def test_equip_when_slot_empty(self):
        offer = rune_rules.generate_altar_offer(random.Random(0))
        rune_id = offer[0]
        rune_rules.equip_altar_pick(self.player, self.progress, rune_id)
        loadout = rune_rules.equipped_runes(self.player)
        category = RUNE_DATABASE[rune_id].category
        self.assertIn(rune_id, loadout[category])

    def test_replaces_index_zero_when_full(self):
        category = "stat"
        stat_runes = [rid for rid, r in RUNE_DATABASE.items() if r.category == category]
        from rune_catalog import RUNE_SLOT_CAPACITY
        cap = RUNE_SLOT_CAPACITY[category]
        # Fill stat slots on progress (which equip_altar_pick mutates).
        for rid in stat_runes[:cap]:
            rune_rules.equip_rune(self.progress, rid)
        loadout_before = list(rune_rules.equipped_runes(self.progress)[category])
        new_rune = stat_runes[cap]
        rune_rules.equip_altar_pick(self.player, self.progress, new_rune)
        loadout_after = list(rune_rules.equipped_runes(self.progress)[category])
        self.assertEqual(loadout_after[0], new_rune)
        self.assertEqual(loadout_after[1:], loadout_before[1:])


class RuneAltarSpriteTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def test_draws_without_error(self):
        config = {
            "kind": "rune_altar",
            "pos": (100, 100),
            "offered_rune_ids": ("rune_iron_skin", "rune_quick_step", "rune_lifesteal")[:3],
            "consumed": False,
        }
        # Use a real generated offer to be safe.
        offer = rune_rules.generate_altar_offer(random.Random(0))
        config["offered_rune_ids"] = offer
        altar = RuneAltar(config)
        altar.update(0)
        surface = pygame.Surface((200, 200), pygame.SRCALPHA)
        altar.draw_overlay(surface)


if __name__ == "__main__":
    unittest.main()
