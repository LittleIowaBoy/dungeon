"""HUD: health bar, weapon indicator, coin counter, minimap, game-state screens."""
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_HEALTH_BAR, COLOR_HEALTH_BG, COLOR_HUD_TEXT,
    COLOR_WHITE, COLOR_BLACK, COLOR_COIN, COLOR_PORTAL,
    COLOR_PLAYER, COLOR_DARK_GRAY, COLOR_GRAY,
    MAX_DUNGEON_RADIUS,
)


class HUD:
    def __init__(self):
        self._font = None
        self._small_font = None

    def _ensure_fonts(self):
        if self._font is None:
            self._font = pygame.font.SysFont("consolas", 18)
            self._small_font = pygame.font.SysFont("consolas", 13)

    # ── main in-game overlay ────────────────────────────
    def draw(self, surface, player, dungeon):
        self._ensure_fonts()
        self._draw_health_bar(surface, player)
        self._draw_weapon(surface, player)
        self._draw_coins(surface, player)
        self._draw_minimap(surface, dungeon)

    # ── health bar ──────────────────────────────────────
    def _draw_health_bar(self, surface, player):
        x, y, w, h = 10, 10, 180, 18
        pygame.draw.rect(surface, COLOR_HEALTH_BG, (x, y, w, h))
        fill_w = int(w * player.current_hp / player.max_hp)
        pygame.draw.rect(surface, COLOR_HEALTH_BAR, (x, y, fill_w, h))
        pygame.draw.rect(surface, COLOR_WHITE, (x, y, w, h), 1)
        txt = self._font.render(
            f"{player.current_hp}/{player.max_hp}", True, COLOR_WHITE)
        surface.blit(txt, (x + w + 6, y - 1))

    # ── weapon indicator ────────────────────────────────
    def _draw_weapon(self, surface, player):
        y = SCREEN_HEIGHT - 30
        x = 10
        for i, wpn in enumerate(player.weapons):
            prefix = "> " if i == player.current_weapon_index else "  "
            label = f"[{i+1}] {wpn.name}"
            color = COLOR_WHITE if i == player.current_weapon_index else COLOR_GRAY
            txt = self._font.render(prefix + label, True, color)
            surface.blit(txt, (x, y))
            x += txt.get_width() + 12

    # ── coins ───────────────────────────────────────────
    def _draw_coins(self, surface, player):
        txt = self._font.render(f"Coins: {player.coins}", True, COLOR_COIN)
        surface.blit(txt, (SCREEN_WIDTH - txt.get_width() - 10, 10))

    # ── minimap ─────────────────────────────────────────
    def _draw_minimap(self, surface, dungeon):
        cell = 7
        rad = MAX_DUNGEON_RADIUS
        size = (2 * rad + 1) * cell
        ox = SCREEN_WIDTH - size - 10
        oy = SCREEN_HEIGHT - size - 40

        # background
        bg = pygame.Surface((size, size), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        surface.blit(bg, (ox, oy))

        for (rx, ry), _room in dungeon.rooms.items():
            px = (rx + rad) * cell + ox
            py = (ry + rad) * cell + oy
            if (rx, ry) == dungeon._exit_pos:
                color = COLOR_PORTAL
            elif (rx, ry) == dungeon.current_pos:
                color = COLOR_PLAYER
            else:
                color = COLOR_DARK_GRAY
            pygame.draw.rect(surface, color, (px, py, cell - 1, cell - 1))

    # ── game over / victory screens ─────────────────────
    def draw_game_over(self, surface):
        self._ensure_fonts()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        big = pygame.font.SysFont("consolas", 48)
        txt = big.render("GAME OVER", True, COLOR_HEALTH_BAR)
        surface.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2,
                                                SCREEN_HEIGHT // 2 - 20)))
        sub = self._font.render("Press R to restart", True, COLOR_WHITE)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2,
                                                SCREEN_HEIGHT // 2 + 30)))

    def draw_victory(self, surface, player):
        self._ensure_fonts()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        big = pygame.font.SysFont("consolas", 48)
        txt = big.render("DUNGEON CLEARED!", True, COLOR_PORTAL)
        surface.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2,
                                                SCREEN_HEIGHT // 2 - 30)))
        coins = self._font.render(f"Coins collected: {player.coins}",
                                  True, COLOR_COIN)
        surface.blit(coins, coins.get_rect(center=(SCREEN_WIDTH // 2,
                                                    SCREEN_HEIGHT // 2 + 20)))
        sub = self._font.render("Press R to restart", True, COLOR_WHITE)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2,
                                                SCREEN_HEIGHT // 2 + 50)))
