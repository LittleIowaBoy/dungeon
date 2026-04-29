import unittest
from types import SimpleNamespace

from hud_view import (
    build_game_over_overlay_view,
    build_hud_view,
    build_victory_overlay_view,
)


class _PlayerStub:
    def __init__(self):
        self.current_hp = 40
        self.max_hp = 100
        self.armor_hp = 5
        self.coins = 17
        self.weapons = [SimpleNamespace(name="Sword"), SimpleNamespace(name="Axe")]
        self.current_weapon_index = 1
        self.weapon_ids = ["sword", "axe"]
        self._weapon_upgrade_tiers = {"sword": 0, "axe": 2}
        self.selected_potion_size = "small"
        self.progress = SimpleNamespace(
            inventory={
                "health_potion_small": 2,
                "speed_boost": 1,
                "attack_boost": 3,
                "stat_shard": 2,
                "tempo_rune": 1,
                "mobility_charge": 4,
            }
        )
        self.compass_uses = 2
        self.compass_target_label = "Relic"
        self.speed_boost_until = 12000
        self.attack_boost_until = 0
        self.compass_direction = "E"
        self.compass_arrow = "→"
        self._compass_display_until = 9000

    def weapon_upgrade_tier(self, weapon_id):
        return self._weapon_upgrade_tiers.get(weapon_id, 0)


class HUDViewProjectionTests(unittest.TestCase):
    def test_build_hud_view_projects_player_and_minimap_state(self):
        player = _PlayerStub()
        dungeon = SimpleNamespace(
            current_room=SimpleNamespace(
                objective_hud_state=lambda _now_ticks: {
                    "visible": True,
                    "label": "Objective: Hold out 2.0s",
                },
                playtest_identifier_state=lambda _now_ticks: {
                    "visible": True,
                    "title": "Room: Survival Holdout",
                    "detail": "Solve: Stay inside the holdout circle until the timer ends.",
                },
            ),
            minimap_snapshot=lambda now_ticks=None: {
                "radius": 3,
                "rooms": [
                    {
                        "pos": (0, 0),
                        "kind": "current",
                        "objective_marker": ("relic", "Cache"),
                        "door_kinds": {
                            "top": "two_way",
                            "bottom": "none",
                            "left": "one_way",
                            "right": "two_way",
                        },
                    },
                    {
                        "pos": (1, 0),
                        "kind": "exit",
                        "objective_marker": None,
                        "door_kinds": {
                            "top": "none",
                            "bottom": "two_way",
                            "left": "two_way",
                            "right": "none",
                        },
                    },
                ],
            }
        )

        view = build_hud_view(player, dungeon, now_ticks=7000, show_room_identifier=True)

        self.assertEqual(view.current_hp, 40)
        self.assertEqual(view.coins, 17)
        self.assertEqual(view.weapons[0].label, "[1] Sword")
        self.assertEqual(view.weapons[1].label, "[2] Axe +2")
        self.assertTrue(view.weapons[1].selected)
        self.assertEqual(view.quick_bar.selected_potion_name, "Small Potion")
        self.assertEqual(view.quick_bar.selected_potion_count, 2)
        self.assertEqual(view.quick_bar.speed_boost_count, 1)
        self.assertEqual(view.quick_bar.attack_boost_count, 3)
        self.assertEqual(view.quick_bar.compass_uses, 2)
        self.assertEqual(view.quick_bar.stat_shard_count, 2)
        self.assertEqual(view.quick_bar.tempo_rune_count, 1)
        self.assertEqual(view.quick_bar.mobility_charge_count, 4)
        self.assertEqual(view.minimap.radius, 3)
        self.assertEqual(view.minimap.rooms[0].kind, "current")
        self.assertEqual(view.minimap.rooms[0].objective_marker, ("relic", "Cache"))
        self.assertEqual(view.minimap.rooms[1].kind, "exit")
        self.assertEqual(len(view.active_effects), 1)
        self.assertEqual(view.active_effects[0].name, "Speed Boost")
        self.assertTrue(view.compass.visible)
        self.assertEqual(view.compass.label, "Relic: E →")
        self.assertTrue(view.objective.visible)
        self.assertEqual(view.objective.label, "Objective: Hold out 2.0s")
        self.assertFalse(view.objective.extraction_bonus_visible)
        self.assertEqual(view.objective.extraction_bonus_amount, 0)
        self.assertTrue(view.room_identifier.visible)
        self.assertEqual(view.room_identifier.title, "Room: Survival Holdout")
        self.assertEqual(
            view.room_identifier.detail,
            "Solve: Stay inside the holdout circle until the timer ends.",
        )

    def test_overlay_views_project_static_overlay_state(self):
        game_over = build_game_over_overlay_view()
        victory = build_victory_overlay_view(23)

        self.assertEqual(game_over.title, "GAME OVER")
        self.assertIsNone(game_over.detail_text)
        self.assertEqual(game_over.prompt_text, "Press R to return to menu")
        self.assertEqual(victory.title, "DUNGEON CLEARED!")
        self.assertEqual(victory.detail_text, "Coins collected: 23")
        self.assertEqual(victory.prompt_text, "Press R to return to menu")

    def test_objective_view_surfaces_extraction_bonus_badge(self):
        player = _PlayerStub()
        dungeon = SimpleNamespace(
            current_room=SimpleNamespace(
                objective_hud_state=lambda _t: {
                    "visible": True,
                    "label": "Objective: Escape under pressure",
                },
                playtest_identifier_state=lambda _t: {"visible": False, "title": "", "detail": ""},
                timed_extraction_bonus_state=lambda: {"available": True, "amount": 14},
            ),
            minimap_snapshot=lambda now_ticks=None: {"radius": 1, "rooms": []},
        )

        view = build_hud_view(player, dungeon, now_ticks=0)

        self.assertTrue(view.objective.extraction_bonus_visible)
        self.assertEqual(view.objective.extraction_bonus_amount, 14)

    def test_objective_view_surfaces_carrying_heartstone_badge(self):
        player = _PlayerStub()
        player.carrying_heartstone = True
        dungeon = SimpleNamespace(
            current_room=SimpleNamespace(
                objective_hud_state=lambda _t: {
                    "visible": True,
                    "label": "Objective: Deliver the heartstone",
                },
                playtest_identifier_state=lambda _t: {"visible": False, "title": "", "detail": ""},
            ),
            minimap_snapshot=lambda now_ticks=None: {"radius": 1, "rooms": []},
        )

        view = build_hud_view(player, dungeon, now_ticks=0)

        self.assertTrue(view.objective.carrying_heartstone)


class RuneMetersHUDViewTests(unittest.TestCase):
    def _build_minimal_dungeon(self):
        return SimpleNamespace(
            current_room=SimpleNamespace(
                objective_hud_state=lambda _t: {"visible": False, "label": ""},
                playtest_identifier_state=lambda _t: {
                    "visible": False, "title": "", "detail": ""
                },
            ),
            minimap_snapshot=lambda now_ticks=None: {"radius": 1, "rooms": []},
        )

    def test_no_runes_equipped_hides_all_meters(self):
        player = _PlayerStub()
        view = build_hud_view(player, self._build_minimal_dungeon(), now_ticks=0)

        self.assertFalse(view.rune_meters.time_anchor.visible)
        self.assertFalse(view.rune_meters.static_charge.visible)
        self.assertFalse(view.rune_meters.glass_soul_iframe.visible)

    def test_time_anchor_meter_reflects_state(self):
        player = _PlayerStub()
        player.equipped_runes = {
            "stat": [], "behavior": [], "identity": ["time_anchor"]
        }
        player.rune_state = {"time_anchor_meter": 0.4}
        view = build_hud_view(player, self._build_minimal_dungeon(), now_ticks=0)

        meter = view.rune_meters.time_anchor
        self.assertTrue(meter.visible)
        self.assertEqual(meter.kind, "time_anchor")
        self.assertAlmostEqual(meter.fill_fraction, 0.4)
        self.assertEqual(meter.label, "Time Anchor")

    def test_time_anchor_full_label(self):
        player = _PlayerStub()
        player.equipped_runes = {
            "stat": [], "behavior": [], "identity": ["time_anchor"]
        }
        player.rune_state = {"time_anchor_meter": 1.0}
        view = build_hud_view(player, self._build_minimal_dungeon(), now_ticks=0)
        self.assertEqual(view.rune_meters.time_anchor.label, "Time Anchor READY")

    def test_static_charge_meter_reflects_state(self):
        player = _PlayerStub()
        player.equipped_runes = {
            "stat": [], "behavior": ["static_charge"], "identity": []
        }
        player.rune_state = {"static_charge": 0.75}
        view = build_hud_view(player, self._build_minimal_dungeon(), now_ticks=0)

        meter = view.rune_meters.static_charge
        self.assertTrue(meter.visible)
        self.assertAlmostEqual(meter.fill_fraction, 0.75)
        self.assertEqual(meter.label, "Static Charge")

    def test_static_charge_full_label(self):
        player = _PlayerStub()
        player.equipped_runes = {
            "stat": [], "behavior": ["static_charge"], "identity": []
        }
        player.rune_state = {"static_charge": 1.0}
        view = build_hud_view(player, self._build_minimal_dungeon(), now_ticks=0)
        self.assertEqual(view.rune_meters.static_charge.label, "Static Charge FULL")

    def test_glass_soul_iframe_active_shows_remaining(self):
        player = _PlayerStub()
        player.equipped_runes = {
            "stat": [], "behavior": [], "identity": ["glass_soul"]
        }
        player._invincible_until = 3000
        view = build_hud_view(player, self._build_minimal_dungeon(), now_ticks=2000)

        meter = view.rune_meters.glass_soul_iframe
        self.assertTrue(meter.visible)
        self.assertAlmostEqual(meter.fill_fraction, 1000 / 2000.0)
        self.assertIn("i-frames", meter.label)

    def test_glass_soul_iframe_idle_shows_zero(self):
        player = _PlayerStub()
        player.equipped_runes = {
            "stat": [], "behavior": [], "identity": ["glass_soul"]
        }
        player._invincible_until = 0
        view = build_hud_view(player, self._build_minimal_dungeon(), now_ticks=5000)

        meter = view.rune_meters.glass_soul_iframe
        self.assertTrue(meter.visible)
        self.assertEqual(meter.fill_fraction, 0.0)
        self.assertEqual(meter.label, "Glass Soul")


if __name__ == "__main__":
    unittest.main()