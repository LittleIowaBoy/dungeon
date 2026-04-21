"""Menu screens: MainMenu, DungeonSelect, CharacterCustomize, Shop, Pause, LevelComplete."""
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_BLACK, COLOR_GRAY, COLOR_DARK_GRAY, COLOR_COIN,
    COLOR_PORTAL, COLOR_HEALTH_BAR, COLOR_MUD, COLOR_ICE, COLOR_WATER,
)
from game_states import GameState
from dungeon_config import DUNGEONS
from items import ITEM_DATABASE
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
    OPTIONS = ["Play", "Character", "Shop", "Quit"]

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
                elif choice == "Character":
                    return GameState.CHARACTER_CUSTOMIZE
                elif choice == "Shop":
                    return GameState.SHOP
                elif choice == "Quit":
                    return "QUIT"
        return None

    def draw(self, surface):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render("Dungeon Crawler", True, COLOR_PORTAL)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 120)))
        _draw_options(
            surface, self._font, self.OPTIONS, self.selected,
            SCREEN_WIDTH // 2 - 80, 240,
        )


# ═════════════════════════════════════════════════════════
#  Dungeon Select
# ═════════════════════════════════════════════════════════
class DungeonSelectScreen:
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

    def handle_events(self, events):
        """Returns (GameState, dungeon_id) or (GameState, None) or None."""
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % (len(DUNGEONS) + 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % (len(DUNGEONS) + 1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.selected == len(DUNGEONS):
                    return (GameState.MAIN_MENU, None)
                d = DUNGEONS[self.selected]
                return (GameState.PLAYING, d["id"])
            elif event.key == pygame.K_ESCAPE:
                return (GameState.MAIN_MENU, None)
        return None

    def draw(self, surface):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render("Select Dungeon", True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 50)))

        card_w, card_h = 220, 140
        start_x = (SCREEN_WIDTH - len(DUNGEONS) * (card_w + 20) + 20) // 2
        y = 110

        for i, d in enumerate(DUNGEONS):
            x = start_x + i * (card_w + 20)
            dp = self.progress.get_dungeon(d["id"])

            # card background
            border_color = COLOR_WHITE if i == self.selected else COLOR_GRAY
            card_color = _TERRAIN_CARD_COLORS.get(d["terrain_type"], COLOR_GRAY)
            pygame.draw.rect(surface, card_color, (x, y, card_w, card_h))
            pygame.draw.rect(surface, border_color, (x, y, card_w, card_h), 3)

            # dungeon name
            name = self._font.render(d["name"], True, COLOR_WHITE)
            surface.blit(name, name.get_rect(center=(x + card_w // 2, y + 30)))

            # status line
            if dp.completed:
                status = "Completed"
            elif self.progress.can_resume(d["id"]):
                status = f"Resume Level {dp.current_level + 1}"
            else:
                status = "Level 1"
            st = self._small_font.render(status, True, COLOR_WHITE)
            surface.blit(st, st.get_rect(center=(x + card_w // 2, y + 65)))

            # terrain label
            terrain = self._small_font.render(
                f"Terrain: {d['terrain_type'].capitalize()}", True, COLOR_WHITE)
            surface.blit(terrain,
                         terrain.get_rect(center=(x + card_w // 2, y + 95)))

            # levels bar (filled squares)
            bar_x = x + 30
            bar_y = y + 115
            for lvl in range(len(d["levels"])):
                color = COLOR_WHITE if lvl < dp.current_level or dp.completed else (60, 60, 60)
                pygame.draw.rect(surface, color,
                                 (bar_x + lvl * 34, bar_y, 24, 8))

        # "Back" option
        back_y = y + card_h + 40
        back_label = "> Back" if self.selected == len(DUNGEONS) else "  Back"
        back_color = COLOR_WHITE if self.selected == len(DUNGEONS) else COLOR_GRAY
        txt = self._font.render(back_label, True, back_color)
        surface.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, back_y)))


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

    def draw(self, surface):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render("Character Loadout", True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 48)))

        subtitle = self._small_font.render(
            "Select a slot, then equip from stored compatible gear.",
            True,
            COLOR_GRAY,
        )
        surface.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 80)))

        slot_x, slot_y, slot_w, slot_h = 40, 110, 300, 58
        for index, (slot_key, slot_label) in enumerate(self.SLOTS):
            y = slot_y + index * (slot_h + 10)
            border = COLOR_WHITE if self.focus == "slots" and index == self.selected_slot else COLOR_GRAY
            pygame.draw.rect(surface, COLOR_DARK_GRAY, (slot_x, y, slot_w, slot_h))
            pygame.draw.rect(surface, border, (slot_x, y, slot_w, slot_h), 2)

            header = self._small_font.render(slot_label, True, COLOR_WHITE)
            value = self._font.render(
                self._slot_value_label(slot_key),
                True,
                COLOR_WHITE if self.progress.equipped_slots.get(slot_key) else COLOR_GRAY,
            )
            surface.blit(header, (slot_x + 12, y + 8))
            surface.blit(value, (slot_x + 12, y + 26))

        panel_x, panel_y, panel_w, panel_h = 380, 110, 380, 360
        panel_border = COLOR_WHITE if self.focus == "items" else COLOR_GRAY
        pygame.draw.rect(surface, COLOR_DARK_GRAY, (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(surface, panel_border, (panel_x, panel_y, panel_w, panel_h), 2)

        panel_title = self._font.render(
            f"{self._current_slot_label()} Options",
            True,
            COLOR_WHITE,
        )
        surface.blit(panel_title, (panel_x + 12, panel_y + 12))

        compatible = self._compatible_items()
        if compatible:
            for index, item_id in enumerate(compatible):
                item_y = panel_y + 56 + index * 38
                line_color = COLOR_WHITE if self.focus == "items" and index == self.selected_item else COLOR_GRAY
                prefix = "> " if self.focus == "items" and index == self.selected_item else "  "
                label = self._item_name(item_id)
                tier = self.progress.weapon_upgrade_tier(item_id)
                if tier > 0:
                    label = f"{label} +{tier}"
                qty = self.progress.equipment_storage.get(item_id, 0)
                text = self._font.render(f"{prefix}{label} x{qty}", True, line_color)
                surface.blit(text, (panel_x + 14, item_y))
        else:
            empty = self._font.render("No compatible stored items", True, COLOR_GRAY)
            surface.blit(empty, (panel_x + 14, panel_y + 64))

        help_box_y = SCREEN_HEIGHT - 110
        pygame.draw.rect(surface, COLOR_DARK_GRAY, (40, help_box_y, 720, 70))
        pygame.draw.rect(surface, COLOR_GRAY, (40, help_box_y, 720, 70), 1)
        hint_1 = self._small_font.render(
            "Up/Down: move  Left/Right or Tab: switch panels  Enter: equip or unequip",
            True,
            COLOR_WHITE,
        )
        hint_2 = self._small_font.render(
            "Backspace/Delete: unequip selected slot  ESC: return to menu",
            True,
            COLOR_WHITE,
        )
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

    def draw(self, surface):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render("Shop", True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 50)))

        # coin balance
        coins = self._font.render(f"Coins: {self.progress.coins}", True, COLOR_COIN)
        surface.blit(coins, (SCREEN_WIDTH - coins.get_width() - 20, 20))

        items = self.shop.items
        if not items:
            msg = self._font.render("No items available", True, COLOR_GRAY)
            surface.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, 250)))
        else:
            self._ensure_selection_visible(items)
            start_index = self.scroll_offset
            visible_count = self._visible_item_count()
            end_index = min(len(items), start_index + visible_count)
            y = 120
            row_height = self._row_height()

            for draw_index, i in enumerate(range(start_index, end_index)):
                item = items[i]
                owned = self._owned_count(item)
                maxed = self.shop.is_maxed(item.id, self.progress)
                can_afford = self.progress.coins >= item.cost
                row_y = y + draw_index * row_height

                # Determine line color
                if maxed and item.id not in ("armor", "compass"):
                    line_color = COLOR_DARK_GRAY
                elif i == self.selected:
                    line_color = COLOR_WHITE
                else:
                    line_color = COLOR_GRAY

                prefix = "> " if i == self.selected else "  "

                # Owned badge with max
                if item.max_owned > 0:
                    badge = f"  [{owned}/{item.max_owned}]"
                else:
                    badge = f"  [x{owned}]" if owned else ""

                # Status suffix
                if maxed and item.id not in ("armor", "compass"):
                    suffix = "  MAXED"
                elif not can_afford:
                    suffix = "  (not enough coins)"
                else:
                    suffix = ""

                line = f"{prefix}{item.name} - {item.cost} coins{badge}{suffix}"
                txt = self._font.render(line, True, line_color)
                surface.blit(txt, (60, row_y))

                desc = self._small_font.render(item.description, True, COLOR_GRAY)
                surface.blit(desc, (88, row_y + 24))

            if start_index > 0:
                up_hint = self._small_font.render("More above...", True, COLOR_GRAY)
                surface.blit(up_hint, (60, y - 22))
            if end_index < len(items):
                down_hint = self._small_font.render("More below...", True, COLOR_GRAY)
                surface.blit(down_hint, (60, y + visible_count * row_height))

        hint = self._font.render("Press ESC to return", True, COLOR_GRAY)
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2,
                                                  SCREEN_HEIGHT - 40)))


# ═════════════════════════════════════════════════════════
#  Pause Screen
# ═════════════════════════════════════════════════════════
class PauseScreen:
    OPTIONS = ["Resume", "Quit Level"]

    def __init__(self):
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
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                return "Resume"
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.OPTIONS)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.OPTIONS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return self.OPTIONS[self.selected]
        return None

    def draw(self, surface):
        self._ensure_fonts()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        title = self._title_font.render("Paused", True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2,
                                                    SCREEN_HEIGHT // 2 - 80)))

        _draw_options(
            surface, self._font, self.OPTIONS, self.selected,
            SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 20,
        )

        warn = self._small_font.render(
            "Quitting will lose all progress in this level.", True, COLOR_GRAY)
        surface.blit(warn, warn.get_rect(center=(SCREEN_WIDTH // 2,
                                                  SCREEN_HEIGHT // 2 + 60)))


# ═════════════════════════════════════════════════════════
#  Level Complete
# ═════════════════════════════════════════════════════════
class LevelCompleteScreen:
    OPTIONS = ["Continue to Next Level", "Return to Dungeon Select"]

    def __init__(self, dungeon_name, level_number, is_final_level=False):
        self.dungeon_name = dungeon_name
        self.level_number = level_number
        self.is_final_level = is_final_level
        self.selected = 0
        self._font = None
        self._title_font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 40)
            self._font = pygame.font.SysFont("consolas", 22)

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
        if self.is_final_level:
            return ["Return to Dungeon Select"]
        return list(self.OPTIONS)

    def draw(self, surface):
        self._ensure_fonts()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        heading = f"Level {self.level_number} Complete!"
        title = self._title_font.render(heading, True, COLOR_PORTAL)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2,
                                                    SCREEN_HEIGHT // 2 - 60)))

        sub = self._font.render(self.dungeon_name, True, COLOR_WHITE)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2,
                                                SCREEN_HEIGHT // 2 - 20)))

        options = self._active_options()
        _draw_options(
            surface, self._font, options, self.selected,
            SCREEN_WIDTH // 2 - 160, SCREEN_HEIGHT // 2 + 30,
        )
