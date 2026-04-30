"""Phase 4 — earth_golem_arena mini-boss orchestration.

Covers the BossController/wave-spec/loot pipeline directly (without
booting the full Game) by instantiating the Room, the Golem, the
controller, and a stub player.progress, then driving controller events
through the same logic ``rpg.RPGGame._update_boss_controller`` runs.
"""
import math
import os
import random
import unittest
from types import SimpleNamespace

import pygame

import armor_rules
from enemies import Golem, GolemShard
from objective_entities import BossController
from progress import PlayerProgress
from room import ROOM_COLS, ROOM_ROWS, Room
from room_plan import RoomPlan, RoomTemplate
from settings import TILE_SIZE


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.init()
pygame.display.set_mode((1, 1))


def _plan():
    tmpl = RoomTemplate(
        room_id="earth_golem_arena",
        display_name="Stone Golem",
        objective_kind="combat",
        combat_pressure="high",
        decision_complexity="mid",
        topology_role="finale",
        min_depth=2,
        max_depth=None,
        branch_preference="either",
        generation_weight=1,
        enabled=True,
        implementation_status="prototype",
        objective_variant="",
        notes="",
    )
    return RoomPlan(
        position=(0, 0),
        depth=2,
        path_kind="main_path",
        is_exit=True,
        template=tmpl,
        terrain_type="mud",
        enemy_count_range=(0, 0),
        enemy_type_weights=(50, 35, 15),
        objective_rule="clear_enemies",
    )


def _make_room():
    return Room(
        {"top": True, "bottom": False, "left": False, "right": False},
        is_exit=True,
        room_plan=_plan(),
    )


class GolemArenaBuilderTests(unittest.TestCase):
    """Builder + enemy_configs handoff is the integration handshake."""

    def test_objective_config_carries_wave_specs_and_loot_flag(self):
        room = _make_room()
        configs = [
            cfg for cfg in room.objective_entity_configs
            if cfg["kind"] == "golem_arena_controller"
        ]
        self.assertEqual(len(configs), 1)
        cfg = configs[0]
        self.assertEqual(cfg["wave_specs"], {0.75: 2, 0.5: 4, 0.25: 6})
        self.assertGreater(cfg["shard_spawn_radius"], 0)
        self.assertFalse(cfg["loot_granted"])
        cx, cy = cfg["boss_pos"]
        self.assertEqual(cx, (ROOM_COLS // 2) * TILE_SIZE + TILE_SIZE // 2)
        self.assertEqual(cy, (ROOM_ROWS // 2) * TILE_SIZE + TILE_SIZE // 2)

    def test_room_only_seeds_a_single_golem_via_enemy_configs(self):
        room = _make_room()
        self.assertEqual(len(room.enemy_configs), 1)
        cls, _pos = room.enemy_configs[0]
        self.assertIs(cls, Golem)


def _spawn_wave_shards(controller, arena_cfg, enemy_group, *, rng):
    """Mirror of rpg.py wave-spawning logic, isolated for test."""
    events = controller.update()
    if events.new_waves:
        wave_specs = arena_cfg["wave_specs"]
        radius = arena_cfg["shard_spawn_radius"]
        boss = controller.boss
        cx, cy = boss.rect.centerx, boss.rect.centery
        for thr in events.new_waves:
            count = wave_specs.get(thr, 0)
            for i in range(count):
                angle = (2 * math.pi * i / count) + rng.uniform(-0.2, 0.2)
                sx = int(cx + radius * math.cos(angle))
                sy = int(cy + radius * math.sin(angle))
                enemy_group.add(GolemShard(sx, sy))
    return events


class GolemArenaWaveTests(unittest.TestCase):
    def setUp(self):
        self.room = _make_room()
        cfg = next(
            c for c in self.room.objective_entity_configs
            if c["kind"] == "golem_arena_controller"
        )
        self.cfg = cfg
        cx, cy = cfg["boss_pos"]
        self.golem = Golem(cx, cy)
        self.controller = BossController(self.golem, name="Stone Golem")
        self.enemy_group = pygame.sprite.Group(self.golem)
        self.rng = random.Random(1234)

    def test_first_wave_spawns_two_shards_at_75_percent_hp(self):
        # Drop boss to 70% — first threshold (0.75) fires.
        self.golem.current_hp = int(self.golem.max_hp * 0.7)
        events = _spawn_wave_shards(
            self.controller, self.cfg, self.enemy_group, rng=self.rng
        )
        self.assertEqual(events.new_waves, (0.75,))
        shards = [e for e in self.enemy_group if isinstance(e, GolemShard)]
        self.assertEqual(len(shards), 2)

    def test_each_threshold_only_fires_once(self):
        self.golem.current_hp = int(self.golem.max_hp * 0.4)
        events = _spawn_wave_shards(
            self.controller, self.cfg, self.enemy_group, rng=self.rng
        )
        # Two thresholds crossed in one tick: 0.75 and 0.5.
        self.assertEqual(set(events.new_waves), {0.75, 0.5})
        shards = [e for e in self.enemy_group if isinstance(e, GolemShard)]
        self.assertEqual(len(shards), 2 + 4)

        # Re-tick at the same HP — no thresholds re-fire.
        events2 = _spawn_wave_shards(
            self.controller, self.cfg, self.enemy_group, rng=self.rng
        )
        self.assertEqual(events2.new_waves, ())
        shards = [e for e in self.enemy_group if isinstance(e, GolemShard)]
        self.assertEqual(len(shards), 6)


class GolemArenaDefeatLootTests(unittest.TestCase):
    def setUp(self):
        self.room = _make_room()
        self.cfg = next(
            c for c in self.room.objective_entity_configs
            if c["kind"] == "golem_arena_controller"
        )
        cx, cy = self.cfg["boss_pos"]
        self.golem = Golem(cx, cy)
        self.controller = BossController(self.golem, name="Stone Golem")

    def _grant_once(self, progress):
        events = self.controller.update()
        if events.defeated and not self.cfg.get("loot_granted"):
            self.cfg["loot_granted"] = True
            drops = armor_rules.roll_boss_loot(progress, rng=random.Random(0))
            armor_rules.grant_boss_loot(progress, drops)
            return drops
        return None

    def test_defeat_grants_loot_exactly_once_and_flips_flag(self):
        progress = PlayerProgress()
        self.golem.current_hp = 0
        self.golem.kill()
        drops = self._grant_once(progress)
        self.assertIsNotNone(drops)
        self.assertTrue(self.cfg["loot_granted"])
        # Second tick: even though defeat-condition still holds, no new
        # loot is rolled because loot_granted is True.
        again = self._grant_once(progress)
        self.assertIsNone(again)


class GolemArenaHUDFeedbackTests(unittest.TestCase):
    """Boss intro banner + per-drop loot banner integration smoke tests."""

    def test_boss_intro_banner_helper_queues_text(self):
        import damage_feedback
        damage_feedback.get_boss_intro_banner_tracker().reset()
        now = pygame.time.get_ticks()
        damage_feedback.report_boss_intro("Stone Golem", now_ticks=now)
        view = damage_feedback.build_boss_intro_banner_view(now_ticks=now)
        self.assertIsNotNone(view)
        text, age = view
        self.assertEqual(text, "Stone Golem")
        self.assertGreaterEqual(age, 0.0)

    def test_loot_banner_helper_queues_acquired_text(self):
        import damage_feedback
        # The loot banner reuses the keystone bonus banner slot.
        damage_feedback._keystone_bonus_banner_tracker.reset()
        now = pygame.time.get_ticks()
        damage_feedback.report_boss_loot("Golem Crown", now_ticks=now)
        view = damage_feedback.build_keystone_bonus_banner_view(now_ticks=now)
        self.assertIsNotNone(view)
        text, _age = view
        self.assertEqual(text, "Golem Crown acquired")


if __name__ == "__main__":
    unittest.main()
