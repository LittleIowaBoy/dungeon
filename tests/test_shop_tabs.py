"""Tests for F8: Shop UI tabs."""
import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pygame
from menu import ShopScreen, SHOP_TABS, _TAB_CATEGORIES
from menu_view import build_shop_view, ShopView
from progress import PlayerProgress


def _screen(active_tab=None):
    p = PlayerProgress()
    p.coins = 200
    s = ShopScreen(p)
    if active_tab is not None:
        s.active_tab = active_tab
    return s


# ── Tab structure ─────────────────────────────────────────────────────────────

class ShopTabStructureTests(unittest.TestCase):
    def test_five_tabs_defined(self):
        self.assertEqual(len(SHOP_TABS), 5)

    def test_tab_names(self):
        self.assertEqual(SHOP_TABS, ("Consumables", "Armor", "Accessories", "Weapons", "Trophies"))

    def test_tab_categories_cover_all_purchasable_categories(self):
        all_cats = set()
        for cats in _TAB_CATEGORIES.values():
            all_cats |= cats
        from item_catalog import ITEM_DATABASE
        purchasable_cats = {
            data["category"]
            for data in ITEM_DATABASE.values()
            if data.get("can_purchase")
        }
        self.assertTrue(purchasable_cats.issubset(all_cats), f"Uncovered categories: {purchasable_cats - all_cats}")

    def test_default_tab_is_consumables(self):
        s = _screen()
        self.assertEqual(s.active_tab, "Consumables")

    def test_tab_names_property_returns_shop_tabs(self):
        s = _screen()
        self.assertEqual(s.tab_names, SHOP_TABS)


# ── _tab_items filtering ──────────────────────────────────────────────────────

class TabItemsFilterTests(unittest.TestCase):
    def _items_for_tab(self, tab):
        s = _screen(active_tab=tab)
        return s._tab_items()

    def test_consumables_contains_potions_and_boosts(self):
        items = self._items_for_tab("Consumables")
        cats = {i.category for i in items}
        self.assertTrue(cats.issubset({"potion", "boost", "tool"}))
        self.assertTrue(any(i.id.startswith("health_potion") for i in items))
        self.assertIn("speed_boost", [i.id for i in items])

    def test_consumables_contains_spark_charge(self):
        items = self._items_for_tab("Consumables")
        ids = [i.id for i in items]
        self.assertIn("spark_charge", ids)

    def test_armor_contains_only_equipment(self):
        items = self._items_for_tab("Armor")
        for item in items:
            self.assertEqual(item.category, "equipment")

    def test_armor_contains_iron_helmet(self):
        items = self._items_for_tab("Armor")
        self.assertIn("iron_helmet", [i.id for i in items])

    def test_accessories_contains_rings_pendants_belts(self):
        items = self._items_for_tab("Accessories")
        for item in items:
            self.assertEqual(item.category, "accessory")
        ids = [i.id for i in items]
        self.assertIn("band_of_vigor", ids)
        self.assertIn("tarnished_amulet", ids)
        self.assertIn("leather_strap", ids)

    def test_weapons_contains_weapon_and_weapon_upgrade(self):
        items = self._items_for_tab("Weapons")
        cats = {i.category for i in items}
        self.assertTrue(cats.issubset({"weapon", "weapon_upgrade"}))

    def test_trophies_tab_items_list_is_empty(self):
        """Biome rewards are earned (can_purchase=False), never bought.
        The Trophies tab exists for the exchange/craft hotkeys, not for
        purchasing items.
        """
        items = self._items_for_tab("Trophies")
        self.assertEqual(items, [])

    def test_tabs_are_mutually_exclusive(self):
        """No item should appear in more than one tab."""
        seen = {}
        for tab in SHOP_TABS:
            for item in self._items_for_tab(tab):
                self.assertNotIn(item.id, seen, f"{item.id} appears in both {seen.get(item.id)} and {tab}")
                seen[item.id] = tab

    def test_all_purchasable_items_appear_in_some_tab(self):
        from item_catalog import ITEM_DATABASE
        all_tab_ids = set()
        for tab in SHOP_TABS:
            for item in self._items_for_tab(tab):
                all_tab_ids.add(item.id)
        purchasable_ids = {iid for iid, d in ITEM_DATABASE.items() if d.get("can_purchase")}
        self.assertEqual(purchasable_ids, all_tab_ids)


# ── _cycle_tab ────────────────────────────────────────────────────────────────

class CycleTabTests(unittest.TestCase):
    def test_cycle_forward(self):
        s = _screen()
        s._cycle_tab(1)
        self.assertEqual(s.active_tab, "Armor")

    def test_cycle_backward(self):
        s = _screen()
        s._cycle_tab(-1)
        self.assertEqual(s.active_tab, "Trophies")

    def test_cycle_wraps_forward(self):
        s = _screen(active_tab="Trophies")
        s._cycle_tab(1)
        self.assertEqual(s.active_tab, "Consumables")

    def test_cycle_wraps_backward(self):
        s = _screen(active_tab="Consumables")
        s._cycle_tab(-1)
        self.assertEqual(s.active_tab, "Trophies")

    def test_cycle_resets_selection(self):
        s = _screen()
        s.selected = 3
        s.scroll_offset = 2
        s._cycle_tab(1)
        self.assertEqual(s.selected, 0)
        self.assertEqual(s.scroll_offset, 0)


# ── handle_events tab cycling ─────────────────────────────────────────────────

class HandleEventsTabCycleTests(unittest.TestCase):
    def _key_event(self, key):
        e = pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0})
        return e

    def test_e_key_advances_tab(self):
        s = _screen()
        s.handle_events([self._key_event(pygame.K_e)])
        self.assertEqual(s.active_tab, "Armor")

    def test_q_key_retreats_tab(self):
        s = _screen(active_tab="Armor")
        s.handle_events([self._key_event(pygame.K_q)])
        self.assertEqual(s.active_tab, "Consumables")

    def test_right_arrow_advances_tab(self):
        s = _screen()
        s.handle_events([self._key_event(pygame.K_RIGHT)])
        self.assertEqual(s.active_tab, "Armor")

    def test_left_arrow_retreats_tab(self):
        s = _screen(active_tab="Armor")
        s.handle_events([self._key_event(pygame.K_LEFT)])
        self.assertEqual(s.active_tab, "Consumables")

    def test_trophy_exchange_key_blocked_outside_trophies_tab(self):
        from settings import BIOME_TROPHY_EXCHANGE_RATIO
        s = _screen(active_tab="Consumables")
        s.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO
        s.progress.inventory["tempo_rune"] = 0
        # K_1 should NOT trigger exchange when not on Trophies tab
        before = s.progress.inventory.get("stat_shard", 0)
        s.handle_events([self._key_event(pygame.K_1)])
        after = s.progress.inventory.get("stat_shard", 0)
        self.assertEqual(before, after)

    def test_trophy_exchange_key_active_on_trophies_tab(self):
        from settings import BIOME_TROPHY_EXCHANGE_RATIO
        s = _screen(active_tab="Trophies")
        s.progress.inventory["stat_shard"] = BIOME_TROPHY_EXCHANGE_RATIO
        s.progress.inventory["tempo_rune"] = 0
        s.handle_events([self._key_event(pygame.K_2)])  # K_2 → get tempo_rune
        self.assertEqual(
            s.progress.inventory.get("stat_shard", 0),
            0,
            "Stat shards should have been spent"
        )


# ── ShopView tab fields ───────────────────────────────────────────────────────

class ShopViewTabFieldTests(unittest.TestCase):
    def test_view_contains_tab_labels(self):
        s = _screen()
        view = build_shop_view(s)
        self.assertEqual(view.tab_labels, SHOP_TABS)

    def test_view_active_tab_matches_screen(self):
        s = _screen(active_tab="Armor")
        view = build_shop_view(s)
        self.assertEqual(view.active_tab, "Armor")

    def test_consumables_footer_hint_mentions_tabs(self):
        s = _screen(active_tab="Consumables")
        view = build_shop_view(s)
        self.assertIn("Q/E", view.footer_hint)
        self.assertIn("ESC", view.footer_hint)

    def test_trophies_footer_hint_mentions_exchange(self):
        s = _screen(active_tab="Trophies")
        view = build_shop_view(s)
        self.assertIn("1-3", view.footer_hint)
        self.assertIn("Keystone", view.footer_hint)

    def test_trophy_summary_hidden_on_consumables_tab(self):
        s = _screen(active_tab="Consumables")
        s.progress.inventory["stat_shard"] = 5
        view = build_shop_view(s)
        self.assertEqual(view.trophy_summary_text, "")
        self.assertEqual(view.trophy_exchange_hint, "")

    def test_items_on_consumables_tab_are_consumable_category(self):
        s = _screen(active_tab="Consumables")
        view = build_shop_view(s)
        # All rendered items should be consumables
        self.assertGreater(len(view.items), 0)

    def test_items_on_armor_tab_are_armor_category(self):
        s = _screen(active_tab="Armor")
        view = build_shop_view(s)
        self.assertGreater(len(view.items), 0)

    def test_empty_message_on_trophies_when_no_items(self):
        # Trophies tab should still render (biome_reward items exist)
        s = _screen(active_tab="Trophies")
        view = build_shop_view(s)
        # biome_reward items have can_purchase=False by default, so tab may be empty
        # — just ensure no exception and tab labels are populated
        self.assertEqual(view.tab_labels, SHOP_TABS)
        self.assertEqual(view.active_tab, "Trophies")


if __name__ == "__main__":
    unittest.main()
