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
        self.assertEqual(view.options, ("Play", "Room Tests", "Character", "Shop", "Records", "Quit"))
        self.assertEqual(view.selected_index, 2)
        # No progress → footer is suppressed.
        self.assertEqual(view.keystone_status_text, "")

    def test_build_main_menu_view_surfaces_keystone_footer_when_owned(self):
        from settings import KEYSTONE_MAX_OWNED
        progress = PlayerProgress()
        progress.meta_keystones = 2
        screen = MainMenuScreen(progress)

        view = build_main_menu_view(screen)

        self.assertIn("Prismatic Keystones: 2", view.keystone_status_text)
        self.assertIn(f"/ {KEYSTONE_MAX_OWNED}", view.keystone_status_text)

    def test_build_main_menu_view_omits_keystone_footer_when_none_owned(self):
        progress = PlayerProgress()
        screen = MainMenuScreen(progress)

        view = build_main_menu_view(screen)

        self.assertEqual(view.keystone_status_text, "")

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
        self.assertEqual(view.footer_hint, "Enter: start room  ←/→: entry side  Esc: back")
        self.assertIn("left", view.spawn_direction_label.lower())

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

    def test_build_level_complete_screen_view_includes_all_options(self):
        screen = LevelCompleteScreen("Mud Caves")
        screen.selected = 0

        view = build_level_complete_screen_view(screen)

        self.assertEqual(view.dungeon_name, "Mud Caves")
        self.assertEqual(view.detail_lines, ())
        self.assertEqual(view.options, ("Play Again", "Return to Dungeon Select"))
        self.assertEqual(view.selected_index, 0)

    def test_build_level_complete_screen_view_projects_reward_details(self):
        screen = LevelCompleteScreen(
            "Mud Caves",
            detail_lines=("Clean extraction bonus: +14 coins",),
        )

        view = build_level_complete_screen_view(screen)

        self.assertEqual(view.detail_lines, ("Clean extraction bonus: +14 coins",))

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
        self.assertIsNotNone(view.difficulty_label)
        # T12: keystone status defaults to empty when no keystones owned.
        self.assertEqual(view.keystone_status_text, "")

    def test_build_dungeon_select_view_surfaces_keystone_status_when_owned(self):
        from settings import KEYSTONE_TIER_COIN_BONUSES
        progress = PlayerProgress()
        progress.meta_keystones = 2
        screen = DungeonSelectScreen(progress)

        view = build_dungeon_select_view(screen)

        self.assertIn("Prismatic Keystones: 2", view.keystone_status_text)
        self.assertIn(
            f"+{sum(KEYSTONE_TIER_COIN_BONUSES[:2])} coins",
            view.keystone_status_text,
        )

    def test_build_dungeon_select_view_card_trophy_labels_reflect_inventory(self):
        from settings import TERRAIN_TROPHY_IDS
        progress = PlayerProgress()
        progress.inventory["stat_shard"] = 2       # mud
        progress.inventory["mobility_charge"] = 1  # water
        # tempo_rune (ice) intentionally absent → expect "x0".
        screen = DungeonSelectScreen(progress)

        view = build_dungeon_select_view(screen)

        labels_by_terrain = {card.terrain_type: card.trophy_label for card in view.cards}
        # Every biome dungeon (mud/ice/water) should surface a trophy label.
        self.assertEqual(labels_by_terrain.get("mud"), "Shard x2")
        self.assertEqual(labels_by_terrain.get("ice"), "Rune x0")
        self.assertEqual(labels_by_terrain.get("water"), "Dash x1")
        # Sanity: the mapping covers every dungeon's terrain in DUNGEONS.
        for card in view.cards:
            self.assertIn(card.terrain_type, TERRAIN_TROPHY_IDS)

    def test_build_dungeon_select_view_card_trophy_labels_default_to_zero(self):
        progress = PlayerProgress()
        screen = DungeonSelectScreen(progress)

        view = build_dungeon_select_view(screen)

        for card in view.cards:
            # Empty inventory → "<Label> x0" (never blank when terrain is mapped).
            self.assertTrue(card.trophy_label.endswith(" x0"))

    def test_build_dungeon_select_view_attunement_label_blank_when_no_progress(self):
        progress = PlayerProgress()
        screen = DungeonSelectScreen(progress)

        view = build_dungeon_select_view(screen)

        for card in view.cards:
            self.assertEqual(card.attunement_label, "")

    def test_build_dungeon_select_view_attunement_label_shows_count_and_progress(self):
        from settings import BIOME_ATTUNEMENT_MAX_PER_BIOME, BIOME_ATTUNEMENT_THRESHOLD
        progress = PlayerProgress()
        progress.biome_attunements["mud"] = 1
        progress.biome_completions["mud"] = BIOME_ATTUNEMENT_THRESHOLD + 1  # 1 over
        screen = DungeonSelectScreen(progress)

        view = build_dungeon_select_view(screen)

        labels = {card.terrain_type: card.attunement_label for card in view.cards}
        self.assertIn(
            f"Attune 1/{BIOME_ATTUNEMENT_MAX_PER_BIOME}", labels.get("mud", "")
        )
        self.assertIn(f"(1/{BIOME_ATTUNEMENT_THRESHOLD} next)", labels.get("mud", ""))

    def test_build_dungeon_select_view_attunement_label_shows_max_at_cap(self):
        from settings import BIOME_ATTUNEMENT_MAX_PER_BIOME
        progress = PlayerProgress()
        progress.biome_attunements["ice"] = BIOME_ATTUNEMENT_MAX_PER_BIOME
        progress.biome_completions["ice"] = 99
        screen = DungeonSelectScreen(progress)

        view = build_dungeon_select_view(screen)

        labels = {card.terrain_type: card.attunement_label for card in view.cards}
        self.assertIn("(max)", labels.get("ice", ""))
        self.assertNotIn("next", labels.get("ice", ""))

    # ── Records (T18) ─────────────────────────────────────
    def test_build_records_view_lists_one_row_per_dungeon(self):
        from menu import RecordsScreen
        from menu_view import build_records_view
        progress = PlayerProgress()
        screen = RecordsScreen(progress)

        view = build_records_view(screen)

        self.assertEqual(view.title, "Records")
        self.assertEqual(len(view.biome_rows), len(DUNGEONS))
        names = [row.dungeon_name for row in view.biome_rows]
        self.assertEqual(names, [d["name"] for d in DUNGEONS])
        # Empty progress → keystone summary indicates none crafted.
        self.assertIn("none crafted", view.keystone_summary)
        self.assertIn("Lifetime completions: 0", view.totals_summary)
        self.assertIn("Trophies in stockpile: 0", view.totals_summary)

    def test_build_records_view_surfaces_completions_and_attunements(self):
        from menu import RecordsScreen
        from menu_view import build_records_view
        from settings import BIOME_ATTUNEMENT_THRESHOLD
        progress = PlayerProgress()
        progress.biome_completions["mud"] = 5
        progress.biome_attunements["mud"] = 1
        progress.inventory["stat_shard"] = 4
        screen = RecordsScreen(progress)

        view = build_records_view(screen)

        mud_row = next(r for r in view.biome_rows if "Mud" in r.terrain_label)
        self.assertEqual(mud_row.completion_label, "Completions: 5")
        self.assertIn("Attunements: 1 / ", mud_row.attunement_label)
        self.assertNotIn("(max)", mud_row.attunement_label)
        self.assertIn(f"/ {BIOME_ATTUNEMENT_THRESHOLD}", mud_row.next_attunement_label)
        self.assertEqual(mud_row.trophy_label, "Stat Shards: 4")
        self.assertEqual(mud_row.starting_grant_label, "Run-start trophies: +1")
        # Lifetime totals reflect aggregate.
        self.assertIn("Lifetime completions: 5", view.totals_summary)
        self.assertIn("Trophies in stockpile: 4", view.totals_summary)

    def test_build_records_view_shows_max_label_at_attunement_cap(self):
        from menu import RecordsScreen
        from menu_view import build_records_view
        from settings import BIOME_ATTUNEMENT_MAX_PER_BIOME
        progress = PlayerProgress()
        progress.biome_attunements["ice"] = BIOME_ATTUNEMENT_MAX_PER_BIOME
        progress.biome_completions["ice"] = 99
        screen = RecordsScreen(progress)

        view = build_records_view(screen)

        ice_row = next(r for r in view.biome_rows if "Ice" in r.terrain_label)
        self.assertIn("(max)", ice_row.attunement_label)
        self.assertEqual(ice_row.next_attunement_label, "")

    def test_build_records_view_shows_keystone_summary_when_owned(self):
        from menu import RecordsScreen
        from menu_view import build_records_view
        from settings import KEYSTONE_MAX_OWNED
        progress = PlayerProgress()
        progress.meta_keystones = 2
        screen = RecordsScreen(progress)

        view = build_records_view(screen)

        self.assertIn("Prismatic Keystones: 2", view.keystone_summary)
        self.assertIn(f"/ {KEYSTONE_MAX_OWNED}", view.keystone_summary)
        self.assertIn("coins/run", view.keystone_summary)

    def test_records_screen_handle_events_returns_main_menu_on_escape(self):
        import pygame as _pg
        from menu import RecordsScreen
        from game_states import GameState
        progress = PlayerProgress()
        screen = RecordsScreen(progress)

        esc_event = _pg.event.Event(_pg.KEYDOWN, {"key": _pg.K_ESCAPE})
        result = screen.handle_events([esc_event])
        self.assertEqual(result, GameState.MAIN_MENU)

        # Unrelated keys do nothing.
        other = _pg.event.Event(_pg.KEYDOWN, {"key": _pg.K_a})
        self.assertIsNone(screen.handle_events([other]))

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
        # No trophies owned → no summary or exchange hint shown.
        self.assertEqual(view.trophy_summary_text, "")
        self.assertEqual(view.trophy_exchange_hint, "")

    def test_build_shop_view_surfaces_trophy_summary_and_exchange_hint(self):
        from settings import BIOME_TROPHY_EXCHANGE_RATIO

        progress = PlayerProgress()
        progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO
        progress.inventory["mobility_charge"] = 1
        screen = ShopScreen(progress)

        view = build_shop_view(screen)

        self.assertIn("Shard x", view.trophy_summary_text)
        self.assertIn("Rune x0", view.trophy_summary_text)
        self.assertIn("Dash x1", view.trophy_summary_text)
        # Surplus exists → exchange hint surfaces.
        self.assertIn("Trade", view.trophy_exchange_hint)
        self.assertIn("[1/2/3]", view.trophy_exchange_hint)

    def test_build_shop_view_hides_exchange_hint_without_surplus(self):
        progress = PlayerProgress()
        progress.inventory["stat_shard"] = 1  # below ratio
        screen = ShopScreen(progress)

        view = build_shop_view(screen)

        self.assertIn("Shard x1", view.trophy_summary_text)
        self.assertEqual(view.trophy_exchange_hint, "")

    def test_build_shop_view_surfaces_keystone_cap_message_when_maxed(self):
        from settings import BIOME_TROPHY_IDS, KEYSTONE_MAX_OWNED
        progress = PlayerProgress()
        progress.meta_keystones = KEYSTONE_MAX_OWNED
        # Even with 1 of each trophy on hand, the [4] craft hint should be
        # replaced by the cap-reached acknowledgement.
        for trophy_id in BIOME_TROPHY_IDS:
            progress.inventory[trophy_id] = 1
        screen = ShopScreen(progress)

        view = build_shop_view(screen)

        self.assertIn(
            f"Keystones complete ({KEYSTONE_MAX_OWNED}/{KEYSTONE_MAX_OWNED})",
            view.trophy_exchange_hint,
        )
        self.assertIn("meta route maxed", view.trophy_exchange_hint)
        self.assertNotIn("[4] Craft Keystone", view.trophy_exchange_hint)

    def test_build_shop_view_keystone_cap_message_appears_alongside_exchange_hint(self):
        from settings import (
            BIOME_TROPHY_IDS,
            BIOME_TROPHY_EXCHANGE_RATIO,
            KEYSTONE_MAX_OWNED,
        )
        progress = PlayerProgress()
        progress.meta_keystones = KEYSTONE_MAX_OWNED
        # Surplus on one trophy → exchange hint should still appear.
        progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO
        screen = ShopScreen(progress)

        view = build_shop_view(screen)

        self.assertIn("[1/2/3]", view.trophy_exchange_hint)
        self.assertIn("Keystones complete", view.trophy_exchange_hint)


if __name__ == "__main__":
    unittest.main()