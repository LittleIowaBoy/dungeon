"""Phase A ice-mechanic tests.

Covers:
- CHILL accumulator (add, decay, cap → FROZEN)
- SLIDE tile direction-commitment via movement_rules
- TRAIL_FREEZE tile lifecycle (emit → advance → collapse)
- FreezeAuraCrystal immortality and aura-active API
- IceSpirit trail emission and contact chill
- IcePillar HP / damage / destruction
- HUDView status_meters field with chill data
- New room templates present in content_db
"""

import types
import sys
import pygame
import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _dummy_player():
    p = types.SimpleNamespace(
        current_hp=10, max_hp=10, armor_hp=0, coins=0,
        weapons=[], weapon_ids=[], current_weapon_index=0,
        speed_multiplier=1.0, velocity_x=0.0, velocity_y=0.0,
        _on_ice=False, facing_dx=1.0, facing_dy=0.0,
        is_invincible=False,
        _pit_fall_phase=None,
        _pit_fall_shrink_t=0.0,
        _invincible_until=0,
        chill=0.0,
        _on_slide=False,
        _slide_dir=None,
    )
    def take_damage(amount):
        p.current_hp = max(0, p.current_hp - amount)
    p.take_damage = take_damage

    # Stubs required by status_effects
    p.statuses = {}

    # Stubs required by movement_rules
    def _effective_speed_multiplier(): return 1.0
    p._effective_speed_multiplier = _effective_speed_multiplier
    p.speed_boost_until = 0
    p.attack_boost_until = 0
    p.spark_until = 0
    p.time_scale = 1.0
    return p


def _dummy_room(grid=None):
    from settings import ROOM_COLS, ROOM_ROWS
    r = types.SimpleNamespace()
    if grid is None:
        from room import FLOOR
        r.grid = [[FLOOR] * ROOM_COLS for _ in range(ROOM_ROWS)]
    else:
        r.grid = grid

    def tile_at(col, row):
        if 0 <= row < len(r.grid) and 0 <= col < len(r.grid[0]):
            return r.grid[row][col]
        return "wall"
    r.tile_at = tile_at

    def terrain_at_pixel(px, py):
        from settings import TILE_SIZE
        col = int(px) // TILE_SIZE
        row = int(py) // TILE_SIZE
        return tile_at(col, row)
    r.terrain_at_pixel = terrain_at_pixel

    def get_wall_rects(): return []
    r.get_wall_rects = get_wall_rects

    def current_vector_at_pixel(px, py): return None
    r.current_vector_at_pixel = current_vector_at_pixel

    return r


# ── CHILL accumulator tests ───────────────────────────────────────────────────

class TestChillAccumulator:
    def test_add_chill_increases_meter(self):
        import status_effects as se
        p = _dummy_player()
        se.add_chill(p, 30.0, 0)
        assert p.chill == pytest.approx(30.0)

    def test_chill_does_not_exceed_max(self):
        import status_effects as se
        from settings import CHILL_MAX
        p = _dummy_player()
        se.add_chill(p, CHILL_MAX - 1, 0)
        se.add_chill(p, CHILL_MAX, 0)   # cap
        assert p.chill == pytest.approx(0.0)   # reset after freeze

    def test_chill_cap_applies_frozen(self):
        import status_effects as se
        from settings import CHILL_MAX
        p = _dummy_player()
        result = se.add_chill(p, CHILL_MAX, 0)
        assert result is True
        assert se.has_status(p, se.FROZEN, 0)

    def test_chill_cap_resets_meter(self):
        import status_effects as se
        from settings import CHILL_MAX
        p = _dummy_player()
        se.add_chill(p, CHILL_MAX, 0)
        assert p.chill == pytest.approx(0.0)

    def test_chill_decay_reduces_meter(self):
        import status_effects as se
        from settings import CHILL_DECAY_RATE
        p = _dummy_player()
        p.chill = 50.0
        se.decay_chill(p, 1.0)   # 1 second
        assert p.chill == pytest.approx(50.0 - CHILL_DECAY_RATE)

    def test_chill_decay_does_not_go_negative(self):
        import status_effects as se
        p = _dummy_player()
        p.chill = 5.0
        se.decay_chill(p, 100.0)
        assert p.chill == pytest.approx(0.0)

    def test_get_chill_default_zero(self):
        import status_effects as se
        p = _dummy_player()
        del p.chill   # ensure attribute is absent
        assert se.get_chill(p) == pytest.approx(0.0)

    def test_apply_chill_rate_per_frame(self):
        import status_effects as se
        p = _dummy_player()
        se.apply_chill_rate(p, 20.0, 0.5, 0)   # 20/sec for 0.5s → +10
        assert p.chill == pytest.approx(10.0)

    def test_reset_chill(self):
        import status_effects as se
        p = _dummy_player()
        p.chill = 80.0
        se.reset_chill(p)
        assert p.chill == pytest.approx(0.0)


# ── SLIDE tile mechanics ──────────────────────────────────────────────────────

class TestSlideTile:
    def test_slide_tile_in_terrain_colors(self):
        from room import SLIDE, TERRAIN_COLORS
        assert SLIDE in TERRAIN_COLORS

    def test_slide_in_walkable_hazard_tiles(self):
        from room import SLIDE, WALKABLE_HAZARD_TILES
        assert SLIDE in WALKABLE_HAZARD_TILES

    def test_slide_direction_committed_in_terrain_effects(self):
        """Stepping onto SLIDE should set player._on_slide and commit dir."""
        import terrain_effects
        from room import SLIDE, FLOOR
        from settings import TILE_SIZE, ROOM_COLS, ROOM_ROWS
        pygame.init()
        room = _dummy_room()
        # Place SLIDE at tile (2,2)
        room.grid[2][2] = SLIDE
        player = _dummy_player()
        player.rect = pygame.Rect(0, 0, 20, 20)
        # Centre in tile (2,2)
        player.rect.center = (2 * TILE_SIZE + TILE_SIZE // 2,
                               2 * TILE_SIZE + TILE_SIZE // 2)
        player.velocity_x = 1.0
        player.velocity_y = 0.0
        terrain_effects.apply_terrain_effects(player, room, 0, 16)
        assert player._on_slide is True

    def test_leaving_slide_clears_committed_dir(self):
        """Moving back to FLOOR should clear the slide lock."""
        import terrain_effects
        from room import SLIDE, FLOOR
        from settings import TILE_SIZE
        pygame.init()
        room = _dummy_room()
        # tile (2,2) = SLIDE, tile (3,2) = FLOOR (default)
        room.grid[2][2] = SLIDE
        player = _dummy_player()
        player.rect = pygame.Rect(0, 0, 20, 20)
        # First frame: on slide
        player.rect.center = (2 * TILE_SIZE + TILE_SIZE // 2,
                               2 * TILE_SIZE + TILE_SIZE // 2)
        terrain_effects.apply_terrain_effects(player, room, 0, 16)
        assert player._on_slide is True
        # Second frame: moved to floor tile (3,2)
        player.rect.center = (3 * TILE_SIZE + TILE_SIZE // 2,
                               2 * TILE_SIZE + TILE_SIZE // 2)
        terrain_effects.apply_terrain_effects(player, room, 16, 16)
        assert player._on_slide is False
        assert player._slide_dir is None


# ── TRAIL_FREEZE tile lifecycle ───────────────────────────────────────────────

class TestTrailFreeze:
    def test_trail_freeze_in_terrain_colors(self):
        from room import TRAIL_FREEZE, TERRAIN_COLORS
        assert TRAIL_FREEZE in TERRAIN_COLORS

    def test_emit_trail_freeze_tile_sets_grid(self):
        from terrain_effects import emit_trail_freeze_tile
        from room import TRAIL_FREEZE, FLOOR
        room = _dummy_room()
        emit_trail_freeze_tile(room, 3, 3, 0)
        assert room.grid[3][3] == TRAIL_FREEZE

    def test_emit_does_not_overwrite_non_floor(self):
        from terrain_effects import emit_trail_freeze_tile
        from room import TRAIL_FREEZE, WALL
        room = _dummy_room()
        room.grid[3][3] = WALL
        emit_trail_freeze_tile(room, 3, 3, 0)
        assert room.grid[3][3] == WALL

    def test_advance_trail_freeze_collapses_expired_tile(self):
        from terrain_effects import emit_trail_freeze_tile, advance_trail_freeze_tiles
        from settings import TRAIL_FREEZE_DURATION_MS
        from room import PIT_TILE
        room = _dummy_room()
        emit_trail_freeze_tile(room, 3, 3, 0)
        advance_trail_freeze_tiles(room, TRAIL_FREEZE_DURATION_MS + 1)
        assert room.grid[3][3] == PIT_TILE

    def test_advance_does_not_collapse_fresh_tile(self):
        from terrain_effects import emit_trail_freeze_tile, advance_trail_freeze_tiles
        from settings import TRAIL_FREEZE_DURATION_MS
        from room import TRAIL_FREEZE
        room = _dummy_room()
        emit_trail_freeze_tile(room, 3, 3, 0)
        advance_trail_freeze_tiles(room, TRAIL_FREEZE_DURATION_MS // 2)
        assert room.grid[3][3] == TRAIL_FREEZE


# ── FreezeAuraCrystal ─────────────────────────────────────────────────────────

class TestFreezeAuraCrystal:
    def test_immortal_flag(self):
        from enemies import FreezeAuraCrystal
        pygame.init()
        c = FreezeAuraCrystal(100, 100)
        assert c.immortal is True

    def test_take_damage_no_op(self):
        from enemies import FreezeAuraCrystal
        pygame.init()
        c = FreezeAuraCrystal(100, 100)
        initial_hp = c.hp
        c.take_damage(999)
        assert c.hp == initial_hp

    def test_aura_not_active_initially(self):
        from enemies import FreezeAuraCrystal
        pygame.init()
        c = FreezeAuraCrystal(100, 100)
        assert c.is_aura_active() is False

    def test_aura_radius_matches_setting(self):
        from enemies import FreezeAuraCrystal
        from settings import FREEZE_AURA_PULSE_RADIUS
        pygame.init()
        c = FreezeAuraCrystal(100, 100)
        assert c.aura_radius() == FREEZE_AURA_PULSE_RADIUS

    def test_stationary(self):
        from enemies import FreezeAuraCrystal
        pygame.init()
        c = FreezeAuraCrystal(100, 100)
        cx_before, cy_before = c.rect.centerx, c.rect.centery
        c.update_movement(None, [])
        assert c.rect.centerx == cx_before
        assert c.rect.centery == cy_before


# ── IceSpirit ─────────────────────────────────────────────────────────────────

class TestIceSpirit:
    def test_has_expected_hp(self):
        from enemies import IceSpirit
        from settings import ICE_SPIRIT_HP
        pygame.init()
        s = IceSpirit(200, 200)
        assert s.hp == ICE_SPIRIT_HP

    def test_contact_chill_attribute(self):
        from enemies import IceSpirit
        from settings import ICE_SPIRIT_CONTACT_CHILL
        pygame.init()
        s = IceSpirit(200, 200)
        assert s._chill_amount == pytest.approx(ICE_SPIRIT_CONTACT_CHILL)

    def test_apply_contact_chill_adds_to_player(self):
        from enemies import IceSpirit
        from settings import ICE_SPIRIT_CONTACT_CHILL
        pygame.init()
        s = IceSpirit(200, 200)
        p = _dummy_player()
        s.apply_contact_chill(p, 0)
        assert p.chill == pytest.approx(ICE_SPIRIT_CONTACT_CHILL)

    def test_trail_emit_respects_interval(self):
        from enemies import IceSpirit
        from settings import ICE_SPIRIT_TRAIL_INTERVAL_MS
        pygame.init()
        s = IceSpirit(200, 200)
        room = _dummy_room()
        # First call: now = INTERVAL, so interval has elapsed since t=0
        result1 = s.emit_trail(room, ICE_SPIRIT_TRAIL_INTERVAL_MS)
        assert result1 is True
        # Immediate second call (no time elapsed) should not emit
        result2 = s.emit_trail(room, ICE_SPIRIT_TRAIL_INTERVAL_MS)
        assert result2 is False
        # After another full interval, should emit again
        result3 = s.emit_trail(room, ICE_SPIRIT_TRAIL_INTERVAL_MS * 2 + 1)
        assert result3 is True

    def test_not_in_enemy_classes(self):
        """IceSpirit must not be in the random-palette pool."""
        from enemies import ENEMY_CLASSES, IceSpirit
        assert IceSpirit not in ENEMY_CLASSES


# ── IcePillar ─────────────────────────────────────────────────────────────────

class TestIcePillar:
    def test_initial_hp(self):
        from objective_entities import IcePillar
        from settings import ICE_PILLAR_HP
        pygame.init()
        p = IcePillar(100, 100)
        assert p.hp == ICE_PILLAR_HP

    def test_alive_true_initially(self):
        from objective_entities import IcePillar
        pygame.init()
        assert IcePillar(100, 100).alive is True

    def test_take_damage_reduces_hp(self):
        from objective_entities import IcePillar
        from settings import ICE_PILLAR_HP
        pygame.init()
        p = IcePillar(100, 100)
        p.take_damage(10)
        assert p.hp == ICE_PILLAR_HP - 10

    def test_destroyed_when_hp_reaches_zero(self):
        from objective_entities import IcePillar
        from settings import ICE_PILLAR_HP
        pygame.init()
        p = IcePillar(100, 100)
        p.take_damage(ICE_PILLAR_HP)
        assert p.alive is False

    def test_take_damage_returns_true_on_kill(self):
        from objective_entities import IcePillar
        from settings import ICE_PILLAR_HP
        pygame.init()
        p = IcePillar(100, 100)
        result = p.take_damage(ICE_PILLAR_HP)
        assert result is True

    def test_take_damage_returns_false_when_alive(self):
        from objective_entities import IcePillar
        pygame.init()
        p = IcePillar(100, 100)
        result = p.take_damage(1)
        assert result is False

    def test_no_negative_hp(self):
        from objective_entities import IcePillar
        from settings import ICE_PILLAR_HP
        pygame.init()
        p = IcePillar(100, 100)
        p.take_damage(ICE_PILLAR_HP * 10)
        assert p.hp == 0


# ── HUDView status_meters field ───────────────────────────────────────────────

class TestHUDStatusMeters:
    def _make_player(self, chill=0.0):
        import progress
        p = types.SimpleNamespace(
            current_hp=10, max_hp=10, armor_hp=0, coins=0,
            weapons=[], weapon_ids=[], current_weapon_index=0,
            speed_boost_until=0, attack_boost_until=0, spark_until=0,
            compass_uses=0,
            compass_direction=None, compass_arrow=None,
            compass_target_label=None,
            carrying_heartstone=False,
            chill=chill,
            statuses={},
            active_ability_id=None,
        )

        def progress_prop():
            return types.SimpleNamespace(inventory={})
        p.progress = progress_prop()

        # Minimally stub method calls
        p.selected_potion_size = "small"
        return p

    def _make_dungeon(self):
        return types.SimpleNamespace(
            current_room=None,
            minimap_snapshot=lambda *_: {"radius": 0, "rooms": []},
            boss_controller=None,
        )

    def test_status_meters_none_when_no_chill(self):
        from hud_view import _build_status_meters_view
        p = self._make_player(chill=0.0)
        assert _build_status_meters_view(p) is None

    def test_status_meters_present_when_chill_positive(self):
        from hud_view import _build_status_meters_view
        p = self._make_player(chill=30.0)
        result = _build_status_meters_view(p)
        assert result is not None
        assert len(result.meters) == 1
        assert result.meters[0].meter_id == "chill"
        assert result.meters[0].value == pytest.approx(30.0)

    def test_chill_meter_pulsing_at_75_percent(self):
        from hud_view import _build_status_meters_view
        from settings import CHILL_MAX
        p = self._make_player(chill=CHILL_MAX * 0.75)
        result = _build_status_meters_view(p)
        assert result.meters[0].pulsing is True

    def test_chill_meter_not_pulsing_below_75(self):
        from hud_view import _build_status_meters_view
        from settings import CHILL_MAX
        p = self._make_player(chill=CHILL_MAX * 0.5)
        result = _build_status_meters_view(p)
        assert result.meters[0].pulsing is False


# ── content_db new room templates ────────────────────────────────────────────

class TestPhaseARoomTemplates:
    def _catalog(self):
        from content_db import BASE_ROOM_TEMPLATES, DUNGEON_ROOM_TEMPLATE_OVERRIDES
        return BASE_ROOM_TEMPLATES, DUNGEON_ROOM_TEMPLATE_OVERRIDES

    def test_ice_freeze_aura_room_in_base(self):
        templates, _ = self._catalog()
        ids = [t["room_id"] for t in templates]
        assert "ice_freeze_aura_room" in ids

    def test_ice_spirit_swarm_room_in_base(self):
        templates, _ = self._catalog()
        ids = [t["room_id"] for t in templates]
        assert "ice_spirit_swarm_room" in ids

    def test_ice_avalanche_run_in_base(self):
        templates, _ = self._catalog()
        ids = [t["room_id"] for t in templates]
        assert "ice_avalanche_run" in ids

    def test_new_rooms_disabled_by_default(self):
        templates, _ = self._catalog()
        for room_id in ("ice_freeze_aura_room", "ice_spirit_swarm_room", "ice_avalanche_run"):
            t = next(t for t in templates if t["room_id"] == room_id)
            assert t["enabled"] == 0, f"{room_id} should be disabled in BASE_ROOM_TEMPLATES"

    def test_new_rooms_enabled_in_frozen_depths(self):
        _, overrides = self._catalog()
        ice_overrides = overrides.get("frozen_depths", ())
        enabled_ids = [t["room_id"] for t in ice_overrides if t.get("enabled") == 1]
        for room_id in ("ice_freeze_aura_room", "ice_spirit_swarm_room", "ice_avalanche_run"):
            assert room_id in enabled_ids, f"{room_id} not enabled in frozen_depths overrides"
