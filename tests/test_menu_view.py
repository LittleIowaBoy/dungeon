import unittest

import pygame

from dungeon_config import DUNGEONS
from menu import CharacterCustomizeScreen, DungeonSelectScreen, LevelCompleteScreen, MainMenuScreen, PauseScreen, RoomTestSelectScreen, ShopScreen
from menu_view import (
    build_character_customize_view,
    build_dungeon_select_view,
    build_level_complete_screen_view,
    build_main_menu_view,
    build_pause_screen_view,
    build_room_test_select_view,
    build_shop_view,
)
from progress import PlayerProgress
from room_test_catalog import load_room_test_entries


class MenuViewProjectionTests(unittest.TestCase):
    def test_build_main_menu_view_projects_title_and_selection(self):
        screen = MainMenuScreen()
        screen.selected = 2

        view = build_main_menu_view(screen)

        self.assertEqual(view.title, "Dungeon Crawler")
        self.assertEqual(view.options, ("Play", "Room Tests", "Character", "Shop", "Quit"))
        self.assertEqual(view.selected_index, 2)

    def test_build_room_test_select_view_projects_visible_rows_and_selected_details(self):
        screen = RoomTestSelectScreen(
            tuple(
                entry
                for entry in load_room_test_entries()
                if entry.room_id == "ritual_disruption"
            )
        )
        screen.selected = 2

        view = build_room_test_select_view(screen)

        self.assertEqual(view.title, "Room Tests")
        self.assertEqual(len(view.rows), 4)
        self.assertTrue(view.rows[2].selected)
        self.assertTrue(view.rows[2].line_text.startswith("> Frost Obelisk Break"))
        self.assertEqual(view.rows[2].detail_text, "Frozen Depths | Ritual")
        self.assertEqual(view.selected_label, "Frost Obelisk Break")
        self.assertEqual(
            view.detail_lines,
            (
                "Family: Ritual Disruption",
                "Context: Frozen Depths",
                "Variant: Frost Obelisk",
            ),
        )
        self.assertEqual(view.footer_hint, "Enter: start room  Esc: back")

    def test_build_pause_screen_view_projects_selected_option_and_warning(self):
        screen = PauseScreen(room_identifier_enabled=False)
        screen.selected = 1

        view = build_pause_screen_view(screen)

        self.assertEqual(view.title, "Paused")
        self.assertEqual(
            view.options,
            ("Resume", "Room Identifier: Off", "Quit Level"),
        )
        self.assertEqual(view.selected_index, 1)
        self.assertIn("toggles the room identifier", view.warning_text)

    def test_pause_screen_returns_toggle_choice_for_room_identifier_option(self):
        screen = PauseScreen(room_identifier_enabled=True)
        screen.selected = 1

        choice = screen.handle_events(
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
        )

        self.assertEqual(choice, "Toggle Room Identifier")

    def test_build_level_complete_screen_view_clamps_selection_for_final_level(self):
        screen = LevelCompleteScreen("Mud Caves", 5, is_final_level=True)
        screen.selected = 1

        view = build_level_complete_screen_view(screen)

        self.assertEqual(view.heading, "Level 5 Complete!")
        self.assertEqual(view.dungeon_name, "Mud Caves")
        self.assertEqual(view.options, ("Return to Dungeon Select",))
        self.assertEqual(view.selected_index, 0)

    def test_build_dungeon_select_view_projects_cards_and_back_selection(self):
        progress = PlayerProgress()
        progress.get_dungeon(DUNGEONS[0]["id"]).completed = True
        screen = DungeonSelectScreen(progress)
        screen.selected = len(DUNGEONS)

        view = build_dungeon_select_view(screen)

        self.assertEqual(view.title, "Select Dungeon")
        self.assertEqual(len(view.cards), len(DUNGEONS))
        self.assertEqual(view.selected_index, len(DUNGEONS))
        self.assertEqual(view.back_label, "Back")
        self.assertEqual(view.cards[0].name, DUNGEONS[0]["name"])
        self.assertEqual(view.cards[0].status_text, "Completed")
        self.assertEqual(view.cards[0].completed_levels, len(DUNGEONS[0]["levels"]))

    def test_build_character_customize_view_projects_slots_and_item_options(self):
        progress = PlayerProgress()
        progress.equipped_slots["weapon_1"] = "sword"
        progress.equipment_storage["axe"] = 2
        progress.weapon_upgrades["axe"] = 1
        screen = CharacterCustomizeScreen(progress)
        screen.focus = "items"

        view = build_character_customize_view(screen)

        self.assertEqual(view.title, "Character Loadout")
        self.assertEqual(view.selected_slot_index, 0)
        self.assertFalse(view.slot_panel_focused)
        self.assertTrue(view.item_panel_focused)
        self.assertEqual(view.slots[0].label, "Weapon 1")
        self.assertEqual(view.slots[0].value, "Sword")
        self.assertTrue(view.slots[0].equipped)
        self.assertEqual(view.panel_title, "Weapon 1 Options")
        self.assertEqual(view.items[0].label, "Axe +1")
        self.assertEqual(view.items[0].quantity, 2)

    def test_build_shop_view_projects_item_rows_and_scroll_hints(self):
        progress = PlayerProgress()
        progress.coins = 0
        screen = ShopScreen(progress)
        screen.selected = 1
        screen.scroll_offset = 1

        view = build_shop_view(screen)

        self.assertEqual(view.title, "Shop")
        self.assertEqual(view.coins_text, "Coins: 0")
        self.assertTrue(view.show_more_above)
        self.assertGreater(len(view.items), 0)
        self.assertTrue(view.items[0].line_text.startswith("> "))
        self.assertIn("not enough coins", view.items[0].line_text)
        self.assertEqual(view.footer_hint, "Press ESC to return")


if __name__ == "__main__":
    unittest.main()