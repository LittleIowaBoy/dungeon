"""HUD: health bar, armor bar, weapon indicator, coin counter, minimap,
consumable quick-bar, compass, game-state screens."""
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_HEALTH_BAR, COLOR_HEALTH_BG, COLOR_HUD_TEXT,
    COLOR_WHITE, COLOR_BLACK, COLOR_COIN, COLOR_PORTAL,
    COLOR_PLAYER, COLOR_DARK_GRAY, COLOR_GRAY,
    COLOR_ARMOR_BAR, COLOR_ARMOR_BG,
    COLOR_SPEED_GLOW, COLOR_COMPASS,
    ARMOR_HP,
    SPEED_BOOST_DURATION_MS, ATTACK_BOOST_DURATION_MS,
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
        self._draw_armor_bar(surface, player)
        self._draw_weapon(surface, player)
        self._draw_coins(surface, player)
        self._draw_minimap(surface, dungeon)
        self._draw_quick_bar(surface, player)
        self._draw_active_effects(surface, player)
        self._draw_compass(surface, player)

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

    # ── armor bar ───────────────────────────────────────
    def _draw_armor_bar(self, surface, player):
        if player.armor_hp <= 0:
            return
        x, y, w, h = 10, 32, 180, 12
        pygame.draw.rect(surface, COLOR_ARMOR_BG, (x, y, w, h))
        fill_w = int(w * player.armor_hp / ARMOR_HP)
        pygame.draw.rect(surface, COLOR_ARMOR_BAR, (x, y, fill_w, h))
        pygame.draw.rect(surface, COLOR_WHITE, (x, y, w, h), 1)
        txt = self._small_font.render(
            f"Armor: {player.armor_hp}/{ARMOR_HP}", True, COLOR_WHITE)
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
        rad = getattr(dungeon, '_radius', 7)
        size = (2 * rad + 1) * cell
        ox = SCREEN_WIDTH - size - 10
        oy = SCREEN_HEIGHT - size - 40

        # background
        bg = pygame.Surface((size, size), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        surface.blit(bg, (ox, oy))

        for (rx, ry) in dungeon.visited:
            px = (rx + rad) * cell + ox
            py = (ry + rad) * cell + oy
            if (rx, ry) == dungeon.current_pos:
                color = COLOR_PLAYER
            elif (rx, ry) == dungeon._exit_pos:
                color = COLOR_PORTAL
            else:
                color = COLOR_DARK_GRAY
            pygame.draw.rect(surface, color, (px, py, cell - 1, cell - 1))

    # ── consumable quick-bar ────────────────────────────
    def _draw_quick_bar(self, surface, player):
        """Draw inventory quick-bar: Q=cycle potion, 4-7=use items."""
        inv = player.progress.inventory if player.progress else {}
        y = SCREEN_HEIGHT - 58
        x = 10

        # Potion selector (Q to cycle, 4 to use)
        size = player.selected_potion_size
        potion_id = f"health_potion_{size}"
        count = inv.get(potion_id, 0)
        potion_label = f"[Q/{4}] {size.capitalize()} Potion x{count}"
        txt = self._small_font.render(potion_label, True, COLOR_WHITE)
        surface.blit(txt, (x, y))

        # Speed boost (5)
        sp_count = inv.get("speed_boost", 0)
        sp_label = f"[5] Speed x{sp_count}"
        txt = self._small_font.render(sp_label, True, COLOR_SPEED_GLOW)
        surface.blit(txt, (x + 200, y))

        # Attack boost (6)
        atk_count = inv.get("attack_boost", 0)
        atk_label = f"[6] Attack x{atk_count}"
        txt = self._small_font.render(atk_label, True, (255, 80, 80))
        surface.blit(txt, (x + 330, y))

        # Compass (7)
        comp_uses = player.compass_uses
        comp_label = f"[7] Compass x{comp_uses}"
        txt = self._small_font.render(comp_label, True, COLOR_COMPASS)
        surface.blit(txt, (x + 470, y))

    # ── active effect timers ────────────────────────────
    def _draw_active_effects(self, surface, player):
        """Show remaining time for active boosts."""
        now = pygame.time.get_ticks()
        y = 50
        if player.armor_hp > 0:
            y = 50  # shift down if armor bar is showing

        if player.is_speed_boosted:
            remaining = max(0, player.speed_boost_until - now)
            secs = remaining / 1000
            txt = self._small_font.render(
                f"Speed Boost: {secs:.1f}s", True, COLOR_SPEED_GLOW)
            surface.blit(txt, (10, y))
            y += 16

        if player.is_attack_boosted:
            remaining = max(0, player.attack_boost_until - now)
            secs = remaining / 1000
            txt = self._small_font.render(
                f"Attack Boost: {secs:.1f}s", True, (255, 80, 80))
            surface.blit(txt, (10, y))

    # ── compass direction display ───────────────────────
    def _draw_compass(self, surface, player):
        """Show compass direction arrow + text after use."""
        if not player.compass_showing:
            return
        direction = player.compass_direction or ""
        arrow = player.compass_arrow or ""
        label = f"Portal: {direction} {arrow}"
        txt = self._font.render(label, True, COLOR_COMPASS)
        surface.blit(txt, txt.get_rect(
            center=(SCREEN_WIDTH // 2, 30)))

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
        sub = self._font.render("Press R to return to menu", True, COLOR_WHITE)
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
        sub = self._font.render("Press R to return to menu", True, COLOR_WHITE)
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2,
                                                SCREEN_HEIGHT // 2 + 50)))
