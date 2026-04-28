"""Tests for the bespoke 'Tuning Test Room' surfaced in the room-test menu."""

import os
import unittest

# Headless pygame for CI / non-interactive runs.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import room as room_module  # noqa: E402
from enemies import (  # noqa: E402
    ChaserEnemy, LauncherEnemy, PatrolEnemy, PulsatorEnemy, RandomEnemy,
    SentryEnemy,
)
from room import (  # noqa: E402
    DOOR,
    FLOOR,
    ICE,
    MUD,
    PORTAL,
    Room,
    TUNING_TEST_ROOM_ID,
    WALL,
    WATER,
)
from room_test_catalog import (  # noqa: E402
    build_room_test_plan,
    load_room_test_entries,
)


def _build_tuning_room():
    entry = load_room_test_entries()[0]
    plan = build_room_test_plan(entry)
    return Room(
        doors={"left": True, "right": False, "top": False, "bottom": False},
        is_exit=True,
        room_plan=plan,
    )


class TuningTestRoomCatalogTests(unittest.TestCase):
    def test_tuning_room_is_first_entry(self):
        entries = load_room_test_entries()
        self.assertGreater(len(entries), 0)
        first = entries[0]
        self.assertEqual(first.room_id, TUNING_TEST_ROOM_ID)
        self.assertEqual(first.display_name, "Tuning Test Room")
        self.assertEqual(first.context_label, "Tuning")
        self.assertEqual(first.implementation_status, "implemented")

    def test_build_room_test_plan_for_tuning_room(self):
        entry = load_room_test_entries()[0]
        plan = build_room_test_plan(entry)
        self.assertEqual(plan.room_id, TUNING_TEST_ROOM_ID)
        self.assertTrue(plan.is_exit)


class TuningTestRoomLayoutTests(unittest.TestCase):
    def test_room_marks_enemies_frozen(self):
        room = _build_tuning_room()
        self.assertTrue(room.frozen_enemies)

    def test_enemy_configs_cover_all_three_classes(self):
        room = _build_tuning_room()
        classes = {cls for cls, _pos in room.enemy_configs}
        self.assertEqual(
            classes,
            {PatrolEnemy, RandomEnemy, ChaserEnemy, PulsatorEnemy, LauncherEnemy, SentryEnemy},
        )
        self.assertEqual(len(room.enemy_configs), 6)

    def test_attacks_disabled_by_default(self):
        room = _build_tuning_room()
        self.assertFalse(room.enemy_attacks_enabled)

    def test_toggle_enemy_attacks_flips_flag_and_propagates(self):
        room = _build_tuning_room()
        e1 = PatrolEnemy(64, 64, is_frozen=True)
        e2 = ChaserEnemy(96, 96, is_frozen=True)
        e1.attacks_disabled = True
        e2.attacks_disabled = True
        group = pygame.sprite.Group(e1, e2)
        room.toggle_enemy_attacks(group)
        self.assertTrue(room.enemy_attacks_enabled)
        self.assertFalse(e1.attacks_disabled)
        self.assertFalse(e2.attacks_disabled)
        room.toggle_enemy_attacks(group)
        self.assertFalse(room.enemy_attacks_enabled)
        self.assertTrue(e1.attacks_disabled)
        self.assertTrue(e2.attacks_disabled)

    def test_grid_contains_every_terrain_type(self):
        room = _build_tuning_room()
        present = {tile for row in room.grid for tile in row}
        for required in (FLOOR, WALL, MUD, ICE, WATER, DOOR, PORTAL):
            self.assertIn(required, present, f"missing terrain: {required!r}")

    def test_chest_and_objective_entities_are_empty(self):
        room = _build_tuning_room()
        self.assertIsNone(room.chest_pos)
        self.assertEqual(room.objective_entity_configs, [])

    def test_labels_include_every_section(self):
        room = _build_tuning_room()
        label_texts = {text for text, _pos in room.tuning_test_labels}
        for required in (
            "MUD", "ICE", "WATER", "WALL", "PORTAL", "FLOOR", "DOOR",
            "PATROL", "RANDOM", "CHASER", "PULSATOR", "LAUNCHER", "SENTRY",
        ):
            self.assertIn(required, label_texts)

    def test_draw_overlay_labels_runs_without_error(self):
        room = _build_tuning_room()
        if not pygame.display.get_init():
            try:
                pygame.display.init()
            except pygame.error:
                self.skipTest("pygame display unavailable")
        surface = pygame.Surface((room_module.ROOM_COLS * room_module.TILE_SIZE,
                                  room_module.ROOM_ROWS * room_module.TILE_SIZE))
        room.draw_overlay_labels(surface)


class TuningTestRoomEnemySpawnTests(unittest.TestCase):
    def test_dungeon_spawns_enemies_with_is_frozen_true(self):
        from dungeon import Dungeon

        room = _build_tuning_room()

        class _StubDungeon:
            def __init__(self, rm):
                import pygame as _pg
                self.current_room = rm
                self.enemy_group = _pg.sprite.Group()
                self.item_group = _pg.sprite.Group()
                self.chest_group = _pg.sprite.Group()
                self.objective_group = _pg.sprite.Group()
                self.hitbox_group = _pg.sprite.Group()
                self.ally_group = _pg.sprite.Group()

        stub = _StubDungeon(room)
        Dungeon._load_room_sprites(stub)
        spawned = list(stub.enemy_group)
        # 6 frozen showcase enemies (5 base + sentry); attacks default OFF.
        self.assertEqual(len(spawned), 6)
        for enemy in spawned:
            self.assertTrue(getattr(enemy, "is_frozen", False))
            self.assertTrue(getattr(enemy, "attacks_disabled", False))
        sentries = [e for e in spawned if isinstance(e, SentryEnemy)]
        self.assertEqual(len(sentries), 1)


if __name__ == "__main__":
    unittest.main()
