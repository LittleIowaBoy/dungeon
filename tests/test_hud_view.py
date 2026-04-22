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
                }
            ),
            minimap_snapshot=lambda: {
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

        view = build_hud_view(player, dungeon, now_ticks=7000)

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

    def test_overlay_views_project_static_overlay_state(self):
        game_over = build_game_over_overlay_view()
        victory = build_victory_overlay_view(23)

        self.assertEqual(game_over.title, "GAME OVER")
        self.assertIsNone(game_over.detail_text)
        self.assertEqual(game_over.prompt_text, "Press R to return to menu")
        self.assertEqual(victory.title, "DUNGEON CLEARED!")
        self.assertEqual(victory.detail_text, "Coins collected: 23")
        self.assertEqual(victory.prompt_text, "Press R to return to menu")


if __name__ == "__main__":
    unittest.main()