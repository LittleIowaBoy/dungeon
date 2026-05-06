"""Phase B: Frost Witch mini-boss test suite.

Covers:
* FrostWitchShard projectile behaviour
* FrostWitch attack selection + hitbox geometry
* Phase-2 unlock (LUNGE becomes available)
* Cone fan emission (P1 vs P2 shot counts)
* Nova chill delivery via rpg._apply_frost_witch_nova_chill
* Arena terrain polish (THIN_ICE disc + SLIDE ring + door buffer)
* content_db: base template + frozen_depths override present
* rpg boss controller: frost_witch_arena_controller branch
"""

import math
import types
import unittest

import pygame

pygame.init()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_witch(x=400, y=300):
    from enemies import FrostWitch
    return FrostWitch(x, y)


def _make_player_rect(cx, cy):
    r = pygame.Rect(0, 0, 24, 24)
    r.center = (cx, cy)
    return r


# ---------------------------------------------------------------------------
# FrostWitchShard
# ---------------------------------------------------------------------------

class TestFrostWitchShard(unittest.TestCase):
    def test_shard_linear_motion(self):
        from enemies import FrostWitchShard
        s = FrostWitchShard(100, 100, vx=3.5, vy=0)
        old_x = s.rect.centerx
        s.update()
        self.assertGreater(s.rect.centerx, old_x)

    def test_shard_damage_and_type(self):
        from enemies import FrostWitchShard
        from settings import FROST_WITCH_SHARD_DAMAGE
        s = FrostWitchShard(0, 0, vx=1, vy=0)
        self.assertEqual(s.damage, FROST_WITCH_SHARD_DAMAGE)
        self.assertEqual(s.damage_type, "ice")

    def test_shard_collide_walls_kills(self):
        from enemies import FrostWitchShard
        s = FrostWitchShard(100, 100, vx=0, vy=0)
        wall = pygame.Rect(90, 90, 30, 30)
        group = pygame.sprite.Group(s)
        s.collide_walls([wall])
        self.assertFalse(s.alive())


# ---------------------------------------------------------------------------
# FrostWitch attack selection
# ---------------------------------------------------------------------------

class TestFrostWitchAttackSelection(unittest.TestCase):
    def setUp(self):
        from settings import FROST_WITCH_NOVA_RANGE, FROST_WITCH_CONE_RANGE, FROST_WITCH_LUNGE_RANGE
        self.nova_range  = FROST_WITCH_NOVA_RANGE
        self.cone_range  = FROST_WITCH_CONE_RANGE
        self.lunge_range = FROST_WITCH_LUNGE_RANGE

    def test_nova_selected_at_close_range(self):
        witch = _make_witch(400, 300)
        # Put player just inside NOVA range
        player_rect = _make_player_rect(400, 300 + self.nova_range - 2)
        result = witch._can_begin_attack(player_rect)
        self.assertTrue(result)
        self.assertEqual(witch._pending_attack, "nova")

    def test_cone_selected_at_mid_range(self):
        witch = _make_witch(400, 300)
        # Outside nova range, inside cone range
        dist = self.nova_range + 10
        if dist >= self.cone_range:
            self.skipTest("no gap between nova and cone range")
        player_rect = _make_player_rect(400, 300 + dist)
        result = witch._can_begin_attack(player_rect)
        self.assertTrue(result)
        self.assertEqual(witch._pending_attack, "cone")

    def test_lunge_not_available_phase1(self):
        witch = _make_witch(400, 300)
        witch.phase_2 = False
        dist = self.nova_range + 10
        if dist >= self.cone_range:
            self.skipTest("no gap")
        player_rect = _make_player_rect(400, 300 + dist)
        witch._can_begin_attack(player_rect)
        self.assertNotEqual(witch._pending_attack, "lunge")

    def test_lunge_available_phase2(self):
        witch = _make_witch(400, 300)
        witch.phase_2 = True
        # Put player in lunge range but outside nova range
        dist = self.nova_range + 5
        if dist >= self.lunge_range:
            self.skipTest("no lunge gap")
        player_rect = _make_player_rect(400, 300 + dist)
        result = witch._can_begin_attack(player_rect)
        self.assertTrue(result)
        self.assertEqual(witch._pending_attack, "lunge")

    def test_no_attack_outside_all_ranges(self):
        witch = _make_witch(400, 300)
        witch.phase_2 = True
        player_rect = _make_player_rect(400, 300 + max(self.nova_range, self.cone_range, self.lunge_range) + 50)
        result = witch._can_begin_attack(player_rect)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# FrostWitch cone emission
# ---------------------------------------------------------------------------

class TestFrostWitchConeEmission(unittest.TestCase):
    def _force_cone_strike(self, witch, player_rect, now_ticks=1000):
        witch._pending_attack = "cone"
        witch._on_telegraph_start(player_rect, now_ticks)
        witch._on_strike_start(player_rect, now_ticks)

    def test_cone_emits_p1_shot_count(self):
        from settings import FROST_WITCH_CONE_SHOTS_P1
        witch = _make_witch(400, 300)
        witch.phase_2 = False
        pr = _make_player_rect(600, 300)
        self._force_cone_strike(witch, pr)
        shards = witch.consume_emitted_projectiles()
        self.assertEqual(len(shards), FROST_WITCH_CONE_SHOTS_P1)

    def test_cone_emits_p2_shot_count(self):
        from settings import FROST_WITCH_CONE_SHOTS_P2
        witch = _make_witch(400, 300)
        witch.phase_2 = True
        pr = _make_player_rect(600, 300)
        self._force_cone_strike(witch, pr)
        shards = witch.consume_emitted_projectiles()
        self.assertEqual(len(shards), FROST_WITCH_CONE_SHOTS_P2)

    def test_cone_shards_are_FrostWitchShard(self):
        from enemies import FrostWitchShard
        witch = _make_witch(400, 300)
        pr = _make_player_rect(600, 300)
        self._force_cone_strike(witch, pr)
        for s in witch.consume_emitted_projectiles():
            self.assertIsInstance(s, FrostWitchShard)

    def test_consume_clears_list(self):
        witch = _make_witch(400, 300)
        pr = _make_player_rect(600, 300)
        self._force_cone_strike(witch, pr)
        witch.consume_emitted_projectiles()
        self.assertEqual(len(witch.consume_emitted_projectiles()), 0)


# ---------------------------------------------------------------------------
# FrostWitch Nova hitbox
# ---------------------------------------------------------------------------

class TestFrostWitchNova(unittest.TestCase):
    def _force_nova_strike(self, witch, player_rect, now_ticks=1000):
        witch._pending_attack = "nova"
        witch._on_telegraph_start(player_rect, now_ticks)
        witch._on_strike_start(player_rect, now_ticks)

    def test_nova_hitbox_centered_on_witch(self):
        from settings import FROST_WITCH_NOVA_RADIUS, FROST_WITCH_NOVA_DAMAGE
        witch = _make_witch(400, 300)
        pr = _make_player_rect(400, 300)
        self._force_nova_strike(witch, pr)
        rects = witch._hitbox_geometry()
        self.assertEqual(len(rects), 1)
        self.assertEqual(witch.attack_damage, FROST_WITCH_NOVA_DAMAGE)
        self.assertEqual(rects[0].centerx, 400)
        self.assertEqual(rects[0].centery, 300)

    def test_nova_property(self):
        from settings import FROST_WITCH_NOVA_CHILL
        witch = _make_witch()
        self.assertEqual(witch.nova_chill, FROST_WITCH_NOVA_CHILL)


# ---------------------------------------------------------------------------
# FrostWitch lunge hitbox
# ---------------------------------------------------------------------------

class TestFrostWitchLunge(unittest.TestCase):
    def test_lunge_hitbox_is_self_rect(self):
        from settings import FROST_WITCH_LUNGE_DAMAGE
        witch = _make_witch(400, 300)
        witch.phase_2 = True
        witch._pending_attack = "lunge"
        pr = _make_player_rect(500, 300)
        witch._on_telegraph_start(pr, 1000)
        witch._on_strike_start(pr, 1000)
        rects = witch._hitbox_geometry()
        self.assertEqual(len(rects), 1)
        self.assertEqual(witch.attack_damage, FROST_WITCH_LUNGE_DAMAGE)


# ---------------------------------------------------------------------------
# Nova chill via rpg helper  (unit-level, no full game state)
# ---------------------------------------------------------------------------

class TestFrostWitchNovaChill(unittest.TestCase):
    """Verify _apply_frost_witch_nova_chill delivers chill during STRIKE."""

    def _make_rpg_stub(self, player_rect):
        from settings import FROST_WITCH_NOVA_RADIUS
        player = types.SimpleNamespace(rect=player_rect)
        rpg_stub = types.SimpleNamespace(player=player)

        # Attach the method directly from the real Game class
        import rpg as rpg_module
        import types as _types
        rpg_stub._apply_frost_witch_nova_chill = _types.MethodType(
            rpg_module.Game._apply_frost_witch_nova_chill, rpg_stub
        )
        return rpg_stub

    def test_chill_applied_in_strike_nova(self):
        import status_effects as se
        from enemies import FrostWitch
        from settings import FROST_WITCH_NOVA_RADIUS, FROST_WITCH_NOVA_CHILL

        player_rect = _make_player_rect(400, 300)
        stub = self._make_rpg_stub(player_rect)

        witch = FrostWitch(400, 300)
        witch._committed_attack = "nova"
        witch._attack_state = "strike"
        witch.FROST_WITCH_NOVA_RADIUS = FROST_WITCH_NOVA_RADIUS

        # Reset chill
        holder = stub.player
        holder.chill = 0.0
        before = getattr(holder, "chill", 0.0)

        stub._apply_frost_witch_nova_chill(witch, pygame.time.get_ticks())
        after = getattr(stub.player, "chill", 0.0)
        self.assertGreater(after, before)

    def test_chill_not_applied_outside_nova_radius(self):
        import status_effects as se
        from enemies import FrostWitch
        from settings import FROST_WITCH_NOVA_RADIUS, FROST_WITCH_NOVA_CHILL

        # Player far away
        player_rect = _make_player_rect(400 + FROST_WITCH_NOVA_RADIUS + 100, 300)
        stub = self._make_rpg_stub(player_rect)

        witch = FrostWitch(400, 300)
        witch._committed_attack = "nova"
        witch._attack_state = "strike"
        witch.FROST_WITCH_NOVA_RADIUS = FROST_WITCH_NOVA_RADIUS

        holder = stub.player
        holder.chill = 0.0
        before = getattr(holder, "chill", 0.0)

        stub._apply_frost_witch_nova_chill(witch, pygame.time.get_ticks())
        after = getattr(stub.player, "chill", 0.0)
        self.assertEqual(after, before)


# ---------------------------------------------------------------------------
# Arena terrain: THIN_ICE disc + SLIDE ring + door buffer
# ---------------------------------------------------------------------------

class TestFrostWitchArenaPolish(unittest.TestCase):
    def _build_arena_room(self):
        from room import Room
        from room_plan import RoomPlan, RoomTemplate
        tmpl = RoomTemplate(
            room_id="ice_frost_witch_arena",
            display_name="Frost Witch Lair",
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
        rp = RoomPlan(
            position=(0, 0),
            depth=2,
            path_kind="main_path",
            is_exit=True,
            template=tmpl,
            terrain_type="ice",
            enemy_count_range=(0, 0),
            enemy_type_weights=(50, 35, 15),
            objective_rule="clear_enemies",
        )
        return Room(
            {"top": True, "bottom": False, "left": False, "right": False},
            is_exit=True,
            room_plan=rp,
        )

    def test_thin_ice_disc_present(self):
        from room import THIN_ICE
        from settings import FROST_WITCH_ARENA_ICE_RADIUS, TILE_SIZE, ROOM_COLS, ROOM_ROWS
        room = self._build_arena_room()
        cx = ROOM_COLS // 2
        cy = ROOM_ROWS // 2
        # Check a tile at the disc edge (outside portal 3x3 block)
        # ice_r=4 → offset (ice_r, 0) from center should be THIN_ICE
        r = FROST_WITCH_ARENA_ICE_RADIUS
        if r > 1:
            self.assertEqual(room.grid[cy][cx + r], THIN_ICE)

    def test_slide_ring_present(self):
        from room import SLIDE, THIN_ICE
        from settings import FROST_WITCH_ARENA_ICE_RADIUS, FROST_WITCH_ARENA_SLIDE_BAND, ROOM_COLS, ROOM_ROWS
        room = self._build_arena_room()
        cx = ROOM_COLS // 2
        cy = ROOM_ROWS // 2
        # A tile at ice_radius + 1 (within band) should be SLIDE
        outer_col = cx + FROST_WITCH_ARENA_ICE_RADIUS + 1
        if 0 < outer_col < ROOM_COLS - 1:
            self.assertEqual(room.grid[cy][outer_col], SLIDE)

    def test_door_buffer_stays_floor(self):
        from room import FLOOR
        from settings import ROOM_COLS, ROOM_ROWS
        room = self._build_arena_room()
        # Check the tile just inside each door wall stays FLOOR
        for col in range(1, ROOM_COLS - 1):
            # Row 1 (just inside top wall) near top-center door
            if abs(col - ROOM_COLS // 2) <= 3:
                self.assertEqual(room.grid[1][col], FLOOR,
                                 f"Top door buffer at ({col}, 1) should stay FLOOR")
                break

    def test_enemy_config_has_frost_witch(self):
        from enemies import FrostWitch
        room = self._build_arena_room()
        classes = [cls for cls, _pos in room.enemy_configs]
        self.assertIn(FrostWitch, classes)

    def test_objective_entity_configs_present(self):
        room = self._build_arena_room()
        self.assertTrue(len(room.objective_entity_configs) > 0)
        cfg = room.objective_entity_configs[0]
        self.assertEqual(cfg["kind"], "frost_witch_arena_controller")


# ---------------------------------------------------------------------------
# content_db template presence
# ---------------------------------------------------------------------------

class TestFrostWitchArenaTemplate(unittest.TestCase):
    def test_base_template_exists(self):
        from content_db import BASE_ROOM_TEMPLATES
        ids = [t["room_id"] for t in BASE_ROOM_TEMPLATES]
        self.assertIn("ice_frost_witch_arena", ids)

    def test_frozen_depths_override_enabled(self):
        from content_db import DUNGEON_ROOM_TEMPLATE_OVERRIDES
        frozen = DUNGEON_ROOM_TEMPLATE_OVERRIDES.get("frozen_depths", ())
        ids = [t["room_id"] for t in frozen]
        self.assertIn("ice_frost_witch_arena", ids)

    def test_frozen_depths_override_enabled_flag(self):
        from content_db import DUNGEON_ROOM_TEMPLATE_OVERRIDES
        frozen = DUNGEON_ROOM_TEMPLATE_OVERRIDES.get("frozen_depths", ())
        for t in frozen:
            if t["room_id"] == "ice_frost_witch_arena":
                self.assertEqual(t["enabled"], 1)
                return
        self.fail("ice_frost_witch_arena not in frozen_depths")


# ---------------------------------------------------------------------------
# rpg.py boss controller branch
# ---------------------------------------------------------------------------

class TestFrostWitchBossControllerBranch(unittest.TestCase):
    def test_phase_advanced_sets_phase2(self):
        """When the boss controller fires phase_advanced, FrostWitch.phase_2 becomes True."""
        import rpg as rpg_module

        witch_holder = {"phase_2": False}

        class FakeWitch:
            phase_2 = False

        fake_witch = FakeWitch()

        events = types.SimpleNamespace(phase_advanced=True, new_waves=[], defeated=False)
        arena_cfg = {"kind": "frost_witch_arena_controller", "loot_granted": False}

        controller = types.SimpleNamespace(
            boss=fake_witch,
            arena_config=arena_cfg,
            update=lambda: events,
        )
        dungeon = types.SimpleNamespace(boss_controller=controller)
        player = types.SimpleNamespace(progress=None)

        game = types.SimpleNamespace(
            dungeon=dungeon,
            player=player,
        )

        # Call the private method directly via unbound call
        rpg_module.Game._update_boss_controller(game)  # type: ignore[arg-type]
        self.assertTrue(fake_witch.phase_2)

    def test_wave_spawner_dispatches_frost_witch_waves(self):
        """_boss_spawn_waves routes frost_witch_arena_controller to the IceSpirit spawner."""
        import rpg as rpg_module

        spawned = []

        def fake_spawn_ring(cls, count, cx, cy, radius):
            spawned.append((cls, count))

        game = types.SimpleNamespace(
            _spawn_ring_of_enemies=fake_spawn_ring,
            _boss_spawn_frost_witch_waves=lambda *a, **kw: rpg_module.Game._boss_spawn_frost_witch_waves(game, *a, **kw),
            _boss_spawn_golem_waves=lambda *a, **kw: None,
            _boss_spawn_tide_lord_waves=lambda *a, **kw: None,
        )

        arena_cfg = {"wave_spawn_radius": 100, "wave_specs": {0.75: 2}}
        class FakeBoss:
            rect = pygame.Rect(400, 300, 48, 48)

        events = types.SimpleNamespace(new_waves=[0.75])
        rpg_module.Game._boss_spawn_waves(game, arena_cfg, "frost_witch_arena_controller", FakeBoss(), events)  # type: ignore
        self.assertTrue(len(spawned) > 0)
        from enemies import IceSpirit
        self.assertEqual(spawned[0][0], IceSpirit)
        self.assertEqual(spawned[0][1], 2)


if __name__ == "__main__":
    unittest.main()
