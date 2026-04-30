"""Phase 0c: BossController + boss HP bar + intro banner tests.

Covers the biome-agnostic mini-boss orchestration introduced for the
Stone Golem encounter (and reusable by any future boss):

* :class:`BossController` — wave thresholds fire in HP order, fire at
  most once, phase-2 transitions on threshold cross, ``defeated`` fires
  exactly once.
* :class:`BossIntroBannerTracker` — single-slot 2.5s banner.
* :class:`HUDView` projection wires both surfaces from
  ``dungeon.boss_controller`` and the banner tracker.
"""

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import damage_feedback  # noqa: E402
from objective_entities import BossController  # noqa: E402


class _FakeBoss:
    """Minimal sprite-shaped stub: HP attrs + alive() flag."""

    def __init__(self, max_hp=100, current_hp=None):
        self.max_hp = max_hp
        self.current_hp = max_hp if current_hp is None else current_hp
        self._alive = True

    def alive(self):
        return self._alive

    def kill(self):
        self._alive = False


class BossControllerTests(unittest.TestCase):
    def test_no_events_at_full_hp(self):
        ctrl = BossController(_FakeBoss(100, 100))
        ev = ctrl.update()
        self.assertEqual(ev.new_waves, ())
        self.assertFalse(ev.phase_advanced)
        self.assertFalse(ev.defeated)
        self.assertEqual(ctrl.current_phase, 1)

    def test_wave_thresholds_fire_in_order_and_only_once(self):
        boss = _FakeBoss(100, 100)
        ctrl = BossController(boss, wave_thresholds=(0.75, 0.5, 0.25))
        boss.current_hp = 80  # above first threshold
        self.assertEqual(ctrl.update().new_waves, ())
        boss.current_hp = 70  # crosses 0.75
        self.assertEqual(ctrl.update().new_waves, (0.75,))
        # Next tick at same HP should NOT re-fire.
        self.assertEqual(ctrl.update().new_waves, ())
        boss.current_hp = 20  # crosses both 0.5 AND 0.25 in one drop
        ev = ctrl.update()
        self.assertEqual(ev.new_waves, (0.5, 0.25))

    def test_thresholds_normalised_descending_regardless_of_input_order(self):
        ctrl = BossController(
            _FakeBoss(100, 50),
            wave_thresholds=(0.25, 0.75, 0.5),
        )
        self.assertEqual(ctrl.wave_thresholds, (0.75, 0.5, 0.25))

    def test_phase_advances_once_on_threshold_cross(self):
        boss = _FakeBoss(200, 200)
        ctrl = BossController(boss, phase_threshold=0.5)
        boss.current_hp = 120
        ev = ctrl.update()
        self.assertFalse(ev.phase_advanced)
        self.assertEqual(ctrl.current_phase, 1)
        boss.current_hp = 100  # exactly threshold
        ev = ctrl.update()
        self.assertTrue(ev.phase_advanced)
        self.assertEqual(ctrl.current_phase, 2)
        # Next tick: no re-trigger.
        boss.current_hp = 50
        self.assertFalse(ctrl.update().phase_advanced)

    def test_defeated_fires_once_when_hp_hits_zero(self):
        boss = _FakeBoss(100, 1)
        ctrl = BossController(boss)
        self.assertFalse(ctrl.update().defeated)
        boss.current_hp = 0
        ev = ctrl.update()
        self.assertTrue(ev.defeated)
        self.assertTrue(ctrl.defeated)
        # Subsequent ticks do NOT re-fire defeated.
        self.assertFalse(ctrl.update().defeated)

    def test_defeated_also_fires_when_sprite_killed_externally(self):
        boss = _FakeBoss(100, 50)
        ctrl = BossController(boss)
        boss.kill()
        ev = ctrl.update()
        self.assertTrue(ev.defeated)

    def test_hp_ratio_clamps_negative_and_handles_zero_max(self):
        boss = _FakeBoss(100, -5)
        ctrl = BossController(boss)
        self.assertEqual(ctrl.hp_ratio, 0.0)
        boss.max_hp = 0
        boss.current_hp = 0
        # Avoids zero division.
        self.assertEqual(ctrl.hp_ratio, 0.0)


class BossIntroBannerTrackerTests(unittest.TestCase):
    def setUp(self):
        damage_feedback.reset_all()

    def test_report_queues_active_banner(self):
        damage_feedback.report_boss_intro("Stone Golem", now_ticks=1000)
        view = damage_feedback.build_boss_intro_banner_view(now_ticks=1000)
        self.assertIsNotNone(view)
        text, age = view
        self.assertEqual(text, "Stone Golem")
        self.assertAlmostEqual(age, 0.0)

    def test_empty_name_does_not_queue(self):
        damage_feedback.report_boss_intro("", now_ticks=1000)
        damage_feedback.report_boss_intro(None, now_ticks=1000)
        self.assertIsNone(
            damage_feedback.build_boss_intro_banner_view(now_ticks=1000)
        )

    def test_banner_expires_after_lifetime(self):
        damage_feedback.report_boss_intro("Boss", now_ticks=1000)
        expired = 1000 + damage_feedback.BOSS_INTRO_BANNER_LIFETIME_MS
        self.assertIsNone(
            damage_feedback.build_boss_intro_banner_view(now_ticks=expired)
        )

    def test_re_report_replaces_active_banner(self):
        damage_feedback.report_boss_intro("First", now_ticks=1000)
        damage_feedback.report_boss_intro("Second", now_ticks=1500)
        text, _ = damage_feedback.build_boss_intro_banner_view(now_ticks=1500)
        self.assertEqual(text, "Second")

    def test_reset_all_clears_boss_intro(self):
        damage_feedback.report_boss_intro("Boss", now_ticks=1000)
        damage_feedback.reset_all()
        self.assertIsNone(
            damage_feedback.build_boss_intro_banner_view(now_ticks=1000)
        )

    def test_intro_and_keystone_banners_are_independent_slots(self):
        damage_feedback.report_keystone_starting_bonus(50, now_ticks=1000)
        damage_feedback.report_boss_intro("Boss", now_ticks=1000)
        self.assertIsNotNone(
            damage_feedback.build_keystone_bonus_banner_view(now_ticks=1000)
        )
        self.assertIsNotNone(
            damage_feedback.build_boss_intro_banner_view(now_ticks=1000)
        )


class HUDViewBossWiringTests(unittest.TestCase):
    """build_hud_view surfaces the boss bar + intro banner from dungeon state."""

    def setUp(self):
        damage_feedback.reset_all()

    def _make_player(self):
        player = SimpleNamespace(
            current_hp=40,
            max_hp=100,
            armor_hp=0,
            coins=0,
            weapons=[],
            current_weapon_index=0,
            weapon_ids=[],
            weapon_upgrade_tier=lambda _wid: 0,
            selected_potion_size="small",
            progress=SimpleNamespace(inventory={}),
            compass_uses=0,
            compass_target_label="",
            speed_boost_until=0,
            attack_boost_until=0,
            compass_direction="",
            compass_arrow="",
            _compass_display_until=0,
        )
        return player

    def _make_dungeon(self, boss_controller=None):
        return SimpleNamespace(
            current_room=SimpleNamespace(
                objective_hud_state=lambda _now_ticks: {"visible": False, "label": ""},
                playtest_identifier_state=lambda _now_ticks: {
                    "visible": False, "title": "", "detail": ""
                },
            ),
            minimap_snapshot=lambda now_ticks=None: {"radius": 1, "rooms": []},
            boss_controller=boss_controller,
        )

    def test_no_boss_controller_means_no_boss_bar_or_banner(self):
        from hud_view import build_hud_view
        view = build_hud_view(self._make_player(), self._make_dungeon(), now_ticks=1000)
        self.assertIsNone(view.boss_health_bar)
        self.assertIsNone(view.boss_intro_banner)

    def test_active_controller_surfaces_boss_health_bar(self):
        from hud_view import build_hud_view
        boss = _FakeBoss(800, 600)
        ctrl = BossController(boss, name="Stone Golem")
        view = build_hud_view(
            self._make_player(),
            self._make_dungeon(boss_controller=ctrl),
            now_ticks=1000,
        )
        self.assertIsNotNone(view.boss_health_bar)
        self.assertEqual(view.boss_health_bar.name, "Stone Golem")
        self.assertEqual(view.boss_health_bar.current_hp, 600)
        self.assertEqual(view.boss_health_bar.max_hp, 800)
        self.assertEqual(view.boss_health_bar.phase, 1)

    def test_defeated_controller_hides_boss_health_bar(self):
        from hud_view import build_hud_view
        boss = _FakeBoss(800, 0)
        ctrl = BossController(boss, name="Stone Golem")
        ctrl.update()  # marks defeated
        view = build_hud_view(
            self._make_player(),
            self._make_dungeon(boss_controller=ctrl),
            now_ticks=1000,
        )
        self.assertIsNone(view.boss_health_bar)

    def test_intro_banner_surfaces_when_reported(self):
        from hud_view import build_hud_view
        damage_feedback.report_boss_intro("Stone Golem", now_ticks=1000)
        view = build_hud_view(
            self._make_player(), self._make_dungeon(), now_ticks=1000
        )
        self.assertIsNotNone(view.boss_intro_banner)
        self.assertEqual(view.boss_intro_banner.text, "Stone Golem")


if __name__ == "__main__":
    unittest.main()
