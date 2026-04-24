"""Menu screens: MainMenu, RoomTestSelect, DungeonSelect, CharacterCustomize, Shop, Pause, LevelComplete."""
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_BLACK, COLOR_GRAY, COLOR_DARK_GRAY, COLOR_COIN,
    COLOR_PORTAL, COLOR_HEALTH_BAR, COLOR_MUD, COLOR_ICE, COLOR_WATER,
)
from game_states import GameState
from dungeon_config import DUNGEONS
from item_catalog import ITEM_DATABASE
from shop import Shop


# ── Terrain-to-colour mapping for dungeon cards ────────
_TERRAIN_CARD_COLORS = {
    "mud":   COLOR_MUD,
    "ice":   COLOR_ICE,
    "water": COLOR_WATER,
}


# ── Helper: draw selectable list items ──────────────────
def _draw_options(surface, font, options, selected, x, y, spacing=40):
    """Draw a vertical list of text options, highlighting *selected*."""
    for i, label in enumerate(options):
        color = COLOR_WHITE if i == selected else COLOR_GRAY
        prefix = "> " if i == selected else "  "
        txt = font.render(prefix + label, True, color)
        surface.blit(txt, (x, y + i * spacing))


# ═════════════════════════════════════════════════════════
#  Main Menu
# ═════════════════════════════════════════════════════════
class MainMenuScreen:
    OPTIONS = ["Play", "Room Tests", "Character", "Shop", "Quit"]

    def __init__(self):
        self.selected = 0
        self._title_font = None
        self._font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 52)
            self._font = pygame.font.SysFont("consolas", 24)

    def handle_events(self, events):
        """Returns the GameState to transition to, or None to stay."""
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.OPTIONS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.OPTIONS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                choice = self.OPTIONS[self.selected]
                if choice == "Play":
                    return GameState.DUNGEON_SELECT
                elif choice == "Room Tests":
                    return GameState.ROOM_TEST_SELECT
                elif choice == "Character":
                    return GameState.CHARACTER_CUSTOMIZE
                elif choice == "Shop":
                    return GameState.SHOP
                elif choice == "Quit":
                    return "QUIT"
        return None

    def draw(self, surface, view):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render(view.title, True, COLOR_PORTAL)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 120)))
        _draw_options(
            surface, self._font, view.options, view.selected_index,
            SCREEN_WIDTH // 2 - 80, 240,
        )


# ═════════════════════════════════════════════════════════
#  Room Test Select
# ═════════════════════════════════════════════════════════
class RoomTestSelectScreen:
    SPAWN_DIRECTIONS = ("left", "right", "top", "bottom")
    SPAWN_DIRECTION_LABELS = {
        "left":   "Left door  (→)",
        "right":  "Right door (←)",
        "top":    "Top door   (↓)",
        "bottom": "Bottom door(↑)",
    }

    def __init__(self, entries=()):
        self.entries = tuple(entries)
        self.selected = 0
        self.scroll_offset = 0
        self.spawn_direction_index = 0  # index into SPAWN_DIRECTIONS
        self._font = None
        self._title_font = None
        self._small_font = None

    @property
    def spawn_direction(self):
        return self.SPAWN_DIRECTIONS[self.spawn_direction_index]

    def set_entries(self, entries):
        self.entries = tuple(entries)
        if not self.entries:
            self.selected = 0
            self.scroll_offset = 0
            return
        self.selected = min(self.selected, len(self.entries) - 1)
        self._ensure_selection_visible()

    @staticmethod
    def _row_height():
        return 46

    def _visible_entry_count(self):
        top_y = 120
        bottom_padding = 190
        available_height = SCREEN_HEIGHT - top_y - bottom_padding
        return max(1, available_height // self._row_height())

    def _ensure_selection_visible(self):
        if not self.entries:
            self.scroll_offset = 0
            return
        visible_count = self._visible_entry_count()
        max_offset = max(0, len(self.entries) - visible_count)
        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        elif self.selected >= self.scroll_offset + visible_count:
            self.scroll_offset = self.selected - visible_count + 1
        self.scroll_offset = max(0, min(self.scroll_offset, max_offset))

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 36)
            self._font = pygame.font.SysFont("consolas", 22)
            self._small_font = pygame.font.SysFont("consolas", 16)

    def handle_events(self, events):
        """Returns (GameState, entry, spawn_direction) or (GameState, None, None) or None."""
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                return (GameState.MAIN_MENU, None, None)
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.spawn_direction_index = (
                    self.spawn_direction_index - 1
                ) % len(self.SPAWN_DIRECTIONS)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.spawn_direction_index = (
                    self.spawn_direction_index + 1
                ) % len(self.SPAWN_DIRECTIONS)
            if not self.entries:
                continue
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.entries)
                self._ensure_selection_visible()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.entries)
                self._ensure_selection_visible()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return (GameState.PLAYING, self.entries[self.selected], self.spawn_direction)
        return None

    def draw(self, surface, view):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)

        title = self._title_font.render(view.title, True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 48)))

        if not view.rows:
            msg = self._font.render(view.empty_message, True, COLOR_GRAY)
            surface.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, 220)))
        else:
            y = 120
            row_height = self._row_height()
            for draw_index, row in enumerate(view.rows):
                row_y = y + draw_index * row_height
                line = self._font.render(row.line_text, True, row.line_color)
                surface.blit(line, (60, row_y))

                detail = self._small_font.render(row.detail_text, True, COLOR_GRAY)
                surface.blit(detail, (88, row_y + 24))

            if view.show_more_above:
                up_hint = self._small_font.render("More above...", True, COLOR_GRAY)
                surface.blit(up_hint, (60, y - 22))
            if view.show_more_below:
                down_hint = self._small_font.render("More below...", True, COLOR_GRAY)
                surface.blit(down_hint, (60, y + len(view.rows) * row_height))

        info_box_y = SCREEN_HEIGHT - 168
        pygame.draw.rect(surface, COLOR_DARK_GRAY, (40, info_box_y, 720, 113))
        pygame.draw.rect(surface, COLOR_GRAY, (40, info_box_y, 720, 113), 1)

        selected_label = self._font.render(view.selected_label, True, COLOR_WHITE)
        surface.blit(selected_label, (54, info_box_y + 10))

        for index, detail_line in enumerate(view.detail_lines):
            detail = self._small_font.render(detail_line, True, COLOR_WHITE)
            surface.blit(detail, (54, info_box_y + 38 + index * 18))

        if view.spawn_direction_label:
            dir_surf = self._small_font.render(
                f"Spawn from: {view.spawn_direction_label}", True, (100, 200, 255)
            )
            surface.blit(dir_surf, (54, info_box_y + 38 + len(view.detail_lines) * 18 + 2))

        hint = self._small_font.render(view.footer_hint, True, COLOR_GRAY)
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 24)))


# ═════════════════════════════════════════════════════════
#  Dungeon Select
# ═════════════════════════════════════════════════════════
class DungeonSelectScreen:
    DIFFICULTIES = ("default", "medium", "hard")
    DIFFICULTY_LABELS = {"default": "Default (5×5)", "medium": "Medium (7×7)", "hard": "Hard (10×10)"}

    def __init__(self, player_progress):
        self.progress = player_progress
        self.selected = 0
        self._font = None
        self._small_font = None
        self._title_font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 36)
            self._font = pygame.font.SysFont("consolas", 22)
            self._small_font = pygame.font.SysFont("consolas", 16)

    def _cycle_difficulty(self, direction):
        """Advance difficulty preference by +1 or -1 and persist immediately."""
        idx = self.DIFFICULTIES.index(
            self.progress.difficulty_preference
            if self.progress.difficulty_preference in self.DIFFICULTIES
            else "default"
        )
        idx = (idx + direction) % len(self.DIFFICULTIES)
        self.progress.difficulty_preference = self.DIFFICULTIES[idx]

    def handle_events(self, events):
        """Returns (GameState, dungeon_id) or (GameState, None) or None."""
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % (len(DUNGEONS) + 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % (len(DUNGEONS) + 1)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self._cycle_difficulty(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._cycle_difficulty(1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.selected == len(DUNGEONS):
                    return (GameState.MAIN_MENU, None)
                d = DUNGEONS[self.selected]
                return (GameState.PLAYING, d["id"])
            elif event.key == pygame.K_ESCAPE:
                return (GameState.MAIN_MENU, None)
        return None

    def draw(self, surface, view):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render(view.title, True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 50)))

        # difficulty row
        diff_label = view.difficulty_label
        diff_y = 85
        diff_txt = self._small_font.render(
            f"Difficulty  ← {diff_label} →", True, COLOR_COIN
        )
        surface.blit(diff_txt, diff_txt.get_rect(center=(SCREEN_WIDTH // 2, diff_y)))

        card_w, card_h = 220, 120
        start_x = (SCREEN_WIDTH - len(view.cards) * (card_w + 20) + 20) // 2
        y = 110

        for i, card in enumerate(view.cards):
            x = start_x + i * (card_w + 20)

            border_color = COLOR_WHITE if i == view.selected_index else COLOR_GRAY
            card_color = _TERRAIN_CARD_COLORS.get(card.terrain_type, COLOR_GRAY)
            pygame.draw.rect(surface, card_color, (x, y, card_w, card_h))
            pygame.draw.rect(surface, border_color, (x, y, card_w, card_h), 3)

            name = self._font.render(card.name, True, COLOR_WHITE)
            surface.blit(name, name.get_rect(center=(x + card_w // 2, y + 28)))

            st = self._small_font.render(card.status_text, True, COLOR_WHITE)
            surface.blit(st, st.get_rect(center=(x + card_w // 2, y + 60)))

            terrain = self._small_font.render(card.terrain_label, True, COLOR_WHITE)
            surface.blit(terrain, terrain.get_rect(center=(x + card_w // 2, y + 88)))

        # "Back" option
        back_y = y + card_h + 40
        back_selected = view.selected_index == len(view.cards)
        back_label = "> Back" if back_selected else f"  {view.back_label}"
        back_color = COLOR_WHITE if back_selected else COLOR_GRAY
        txt = self._font.render(back_label, True, back_color)
        surface.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, back_y)))

        hint = self._small_font.render(
            "Up/Down: select dungeon  Left/Right: change difficulty  Enter: launch",
            True, COLOR_GRAY,
        )
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 24)))


# ═════════════════════════════════════════════════════════
#  Character Customize
# ═════════════════════════════════════════════════════════
class CharacterCustomizeScreen:
    SLOTS = [
        ("weapon_1", "Weapon 1"),
        ("weapon_2", "Weapon 2"),
        ("helmet", "Helmet"),
        ("chest", "Chest"),
        ("arms", "Arms"),
        ("legs", "Legs"),
    ]

    def __init__(self, player_progress):
        self.progress = player_progress
        self.selected_slot = 0
        self.selected_item = 0
        self.focus = "slots"
        self._font = None
        self._small_font = None
        self._title_font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 36)
            self._font = pygame.font.SysFont("consolas", 22)
            self._small_font = pygame.font.SysFont("consolas", 16)

    def _current_slot_key(self):
        return self.SLOTS[self.selected_slot][0]

    def _current_slot_label(self):
        return self.SLOTS[self.selected_slot][1]

    def _item_name(self, item_id):
        if not item_id:
            return "Empty"
        return ITEM_DATABASE.get(item_id, {}).get("name", item_id)

    def _slot_value_label(self, slot_key):
        item_id = self.progress.equipped_slots.get(slot_key)
        if not item_id:
            return "Empty"
        label = self._item_name(item_id)
        if slot_key.startswith("weapon"):
            tier = self.progress.weapon_upgrade_tier(item_id)
            if tier > 0:
                label = f"{label} +{tier}"
        return label

    def _compatible_items(self):
        slot_key = self._current_slot_key()
        compatible = []
        for item_id, qty in self.progress.equipment_storage.items():
            if qty <= 0:
                continue
            if self.progress.can_equip(slot_key, item_id):
                compatible.append(item_id)
        compatible.sort(key=lambda item_id: ITEM_DATABASE[item_id]["name"])
        return compatible

    def _toggle_focus(self):
        self.focus = "items" if self.focus == "slots" else "slots"
        self.selected_item = 0

    def handle_events(self, events):
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                return GameState.MAIN_MENU
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                self._toggle_focus()
                continue
            if event.key in (pygame.K_UP, pygame.K_w):
                if self.focus == "slots":
                    self.selected_slot = (self.selected_slot - 1) % len(self.SLOTS)
                    self.selected_item = 0
                else:
                    compatible = self._compatible_items()
                    if compatible:
                        self.selected_item = (self.selected_item - 1) % len(compatible)
                continue
            if event.key in (pygame.K_DOWN, pygame.K_s):
                if self.focus == "slots":
                    self.selected_slot = (self.selected_slot + 1) % len(self.SLOTS)
                    self.selected_item = 0
                else:
                    compatible = self._compatible_items()
                    if compatible:
                        self.selected_item = (self.selected_item + 1) % len(compatible)
                continue

            slot_key = self._current_slot_key()
            if event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                self.progress.unequip_slot(slot_key)
                continue

            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.focus == "slots":
                    self.progress.unequip_slot(slot_key)
                else:
                    compatible = self._compatible_items()
                    if compatible:
                        chosen_item = compatible[self.selected_item]
                        self.progress.equip_item(slot_key, chosen_item)
                        compatible = self._compatible_items()
                        if compatible:
                            self.selected_item = min(self.selected_item,
                                                     len(compatible) - 1)
                        else:
                            self.selected_item = 0
        return None

    def draw(self, surface, view):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render(view.title, True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 48)))

        subtitle = self._small_font.render(view.subtitle, True, COLOR_GRAY)
        surface.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 80)))

        slot_x, slot_y, slot_w, slot_h = 40, 110, 300, 58
        for index, slot in enumerate(view.slots):
            y = slot_y + index * (slot_h + 10)
            border = COLOR_WHITE if view.slot_panel_focused and index == view.selected_slot_index else COLOR_GRAY
            pygame.draw.rect(surface, COLOR_DARK_GRAY, (slot_x, y, slot_w, slot_h))
            pygame.draw.rect(surface, border, (slot_x, y, slot_w, slot_h), 2)

            header = self._small_font.render(slot.label, True, COLOR_WHITE)
            value = self._font.render(
                slot.value,
                True,
                COLOR_WHITE if slot.equipped else COLOR_GRAY,
            )
            surface.blit(header, (slot_x + 12, y + 8))
            surface.blit(value, (slot_x + 12, y + 26))

        panel_x, panel_y, panel_w, panel_h = 380, 110, 380, 360
        panel_border = COLOR_WHITE if view.item_panel_focused else COLOR_GRAY
        pygame.draw.rect(surface, COLOR_DARK_GRAY, (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(surface, panel_border, (panel_x, panel_y, panel_w, panel_h), 2)

        panel_title = self._font.render(view.panel_title, True, COLOR_WHITE)
        surface.blit(panel_title, (panel_x + 12, panel_y + 12))

        if view.items:
            for index, item in enumerate(view.items):
                item_y = panel_y + 56 + index * 38
                is_selected = view.item_panel_focused and index == view.selected_item_index
                line_color = COLOR_WHITE if is_selected else COLOR_GRAY
                prefix = "> " if is_selected else "  "
                text = self._font.render(
                    f"{prefix}{item.label} x{item.quantity}",
                    True,
                    line_color,
                )
                surface.blit(text, (panel_x + 14, item_y))
        else:
            empty = self._font.render(view.empty_message, True, COLOR_GRAY)
            surface.blit(empty, (panel_x + 14, panel_y + 64))

        help_box_y = SCREEN_HEIGHT - 110
        pygame.draw.rect(surface, COLOR_DARK_GRAY, (40, help_box_y, 720, 70))
        pygame.draw.rect(surface, COLOR_GRAY, (40, help_box_y, 720, 70), 1)
        hint_1 = self._small_font.render(view.help_lines[0], True, COLOR_WHITE)
        hint_2 = self._small_font.render(view.help_lines[1], True, COLOR_WHITE)
        surface.blit(hint_1, (54, help_box_y + 16))
        surface.blit(hint_2, (54, help_box_y + 40))


# ═════════════════════════════════════════════════════════
#  Shop Screen
# ═════════════════════════════════════════════════════════
class ShopScreen:
    def __init__(self, player_progress, shop=None):
        self.progress = player_progress
        self.shop = shop or Shop()
        self.selected = 0
        self.scroll_offset = 0
        self._font = None
        self._title_font = None
        self._small_font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 36)
            self._font = pygame.font.SysFont("consolas", 22)
            self._small_font = pygame.font.SysFont("consolas", 16)

    @staticmethod
    def _row_height():
        return 50

    def _visible_item_count(self):
        top_y = 120
        bottom_padding = 90
        available_height = SCREEN_HEIGHT - top_y - bottom_padding
        return max(1, available_height // self._row_height())

    def _owned_count(self, item):
        data = ITEM_DATABASE[item.id]
        if data.get("category") == "weapon_upgrade":
            return self.progress.weapon_upgrade_tier(data["upgrade_weapon_id"])
        if data.get("storage_bucket") == "equipment":
            return self.progress.total_owned(item.id)
        return self.progress.inventory.get(item.id, 0)

    def _ensure_selection_visible(self, items):
        if not items:
            self.scroll_offset = 0
            return
        visible_count = self._visible_item_count()
        max_offset = max(0, len(items) - visible_count)
        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        elif self.selected >= self.scroll_offset + visible_count:
            self.scroll_offset = self.selected - visible_count + 1
        self.scroll_offset = max(0, min(self.scroll_offset, max_offset))

    def handle_events(self, events):
        items = self.shop.items
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                return GameState.MAIN_MENU
            if not items:
                continue
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(items)
                self._ensure_selection_visible(items)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(items)
                self._ensure_selection_visible(items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                item = items[self.selected]
                if not self.shop.is_maxed(item.id, self.progress):
                    self.shop.buy(item.id, self.progress)
        return None

    def draw(self, surface, view):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render(view.title, True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 50)))

        # coin balance
        coins = self._font.render(view.coins_text, True, COLOR_COIN)
        surface.blit(coins, (SCREEN_WIDTH - coins.get_width() - 20, 20))

        if not view.items:
            msg = self._font.render(view.empty_message, True, COLOR_GRAY)
            surface.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, 250)))
        else:
            y = 120
            row_height = self._row_height()

            for draw_index, item_view in enumerate(view.items):
                row_y = y + draw_index * row_height

                txt = self._font.render(item_view.line_text, True, item_view.line_color)
                surface.blit(txt, (60, row_y))

                desc = self._small_font.render(item_view.description, True, COLOR_GRAY)
                surface.blit(desc, (88, row_y + 24))

            if view.show_more_above:
                up_hint = self._small_font.render("More above...", True, COLOR_GRAY)
                surface.blit(up_hint, (60, y - 22))
            if view.show_more_below:
                down_hint = self._small_font.render("More below...", True, COLOR_GRAY)
                surface.blit(down_hint, (60, y + len(view.items) * row_height))

        hint = self._font.render(view.footer_hint, True, COLOR_GRAY)
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2,
                                                  SCREEN_HEIGHT - 40)))


# ═════════════════════════════════════════════════════════
#  Pause Screen
# ═════════════════════════════════════════════════════════
class PauseScreen:
    def __init__(self, room_identifier_enabled=True):
        self.selected = 0
        self.room_identifier_enabled = room_identifier_enabled
        self._font = None
        self._title_font = None
        self._small_font = None

    def option_labels(self):
        toggle_state = "On" if self.room_identifier_enabled else "Off"
        return (
            "Resume",
            f"Room Identifier: {toggle_state}",
            "Quit Level",
        )

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 40)
            self._font = pygame.font.SysFont("consolas", 22)
            self._small_font = pygame.font.SysFont("consolas", 16)

    def handle_events(self, events):
        """Returns a choice string or None."""
        options = self.option_labels()
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                return "Resume"
            if event.key == pygame.K_F3:
                return "Toggle Room Identifier"
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.selected == 1:
                    return "Toggle Room Identifier"
                return options[self.selected]
        return None

    def draw(self, surface, view):
        self._ensure_fonts()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        title = self._title_font.render(view.title, True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2,
                                                    SCREEN_HEIGHT // 2 - 80)))

        _draw_options(
            surface, self._font, view.options, view.selected_index,
            SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 20,
        )

        warn = self._small_font.render(
            view.warning_text, True, COLOR_GRAY)
        surface.blit(warn, warn.get_rect(center=(SCREEN_WIDTH // 2,
                                                  SCREEN_HEIGHT // 2 + 60)))


# ═════════════════════════════════════════════════════════
#  Level Complete
# ═════════════════════════════════════════════════════════
class LevelCompleteScreen:
    OPTIONS = ["Play Again", "Return to Dungeon Select"]

    def __init__(self, dungeon_name, is_final_level=False, detail_lines=()):
        self.dungeon_name = dungeon_name
        self.is_final_level = is_final_level
        self.detail_lines = tuple(detail_lines)
        self.selected = 0
        self._font = None
        self._title_font = None
        self._small_font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 40)
            self._font = pygame.font.SysFont("consolas", 22)
            self._small_font = pygame.font.SysFont("consolas", 16)

    def handle_events(self, events):
        """Returns a choice string or None."""
        options = self._active_options()
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return options[self.selected]
        return None

    def _active_options(self):
        return list(self.OPTIONS)

    def draw(self, surface, view):
        self._ensure_fonts()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        title = self._title_font.render("Dungeon Complete!", True, COLOR_PORTAL)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2,
                                                    SCREEN_HEIGHT // 2 - 60)))

        sub = self._font.render(view.dungeon_name, True, COLOR_WHITE)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2,
                                                SCREEN_HEIGHT // 2 - 20)))

        detail_y = SCREEN_HEIGHT // 2 + 8
        for index, line in enumerate(view.detail_lines):
            detail = self._small_font.render(line, True, COLOR_COIN)
            surface.blit(detail, detail.get_rect(center=(SCREEN_WIDTH // 2,
                                                         detail_y + index * 18)))

        options_y = SCREEN_HEIGHT // 2 + 30 + len(view.detail_lines) * 18

        _draw_options(
            surface, self._font, view.options, view.selected_index,
            SCREEN_WIDTH // 2 - 160, options_y,
        )
