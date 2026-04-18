"""Menu screens: MainMenu, DungeonSelect, CharacterCustomize, Shop, Pause, LevelComplete."""
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_BLACK, COLOR_GRAY, COLOR_DARK_GRAY, COLOR_COIN,
    COLOR_PORTAL, COLOR_HEALTH_BAR, COLOR_MUD, COLOR_ICE, COLOR_WATER,
)
from game_states import GameState
from dungeon_config import DUNGEONS
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
#  Character Customize (placeholder)
# ═════════════════════════════════════════════════════════
class CharacterCustomizeScreen:
    def __init__(self):
        self._font = None
        self._title_font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 36)
            self._font = pygame.font.SysFont("consolas", 22)

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    return GameState.MAIN_MENU
        return None

    def draw(self, surface):
        self._ensure_fonts()
        surface.fill(COLOR_BLACK)
        title = self._title_font.render("Character", True, COLOR_WHITE)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 100)))
        msg = self._font.render("Coming Soon", True, COLOR_GRAY)
        surface.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, 250)))
        hint = self._font.render("Press ESC to return", True, COLOR_GRAY)
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 350)))


# ═════════════════════════════════════════════════════════
#  Shop Screen
# ═════════════════════════════════════════════════════════
class ShopScreen:
    def __init__(self, player_progress, shop=None):
        self.progress = player_progress
        self.shop = shop or Shop()
        self.selected = 0
        self._font = None
        self._title_font = None
        self._small_font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._title_font = pygame.font.SysFont("consolas", 36)
            self._font = pygame.font.SysFont("consolas", 22)
            self._small_font = pygame.font.SysFont("consolas", 16)

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
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(items)
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
            y = 120
            for i, item in enumerate(items):
                owned = self.progress.inventory.get(item.id, 0)
                maxed = self.shop.is_maxed(item.id, self.progress)
                can_afford = self.progress.coins >= item.cost

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
                surface.blit(txt, (60, y + i * 50))

                desc = self._small_font.render(item.description, True, COLOR_GRAY)
                surface.blit(desc, (88, y + i * 50 + 24))

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
