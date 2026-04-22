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
    COLOR_DOOR_TWO_WAY, COLOR_DOOR_ONE_WAY, COLOR_DOOR_NONE,
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
    def draw(self, surface, view):
        self._ensure_fonts()
        self._draw_health_bar(surface, view)
        self._draw_armor_bar(surface, view)
        self._draw_weapon(surface, view)
        self._draw_coins(surface, view)
        self._draw_minimap(surface, view.minimap)
        self._draw_quick_bar(surface, view.quick_bar)
        self._draw_active_effects(surface, view)
        self._draw_compass(surface, view.compass)
        self._draw_objective(surface, view.objective, view.compass)

    # ── health bar ──────────────────────────────────────
    def _draw_health_bar(self, surface, view):
        x, y, w, h = 10, 10, 180, 18
        pygame.draw.rect(surface, COLOR_HEALTH_BG, (x, y, w, h))
        fill_w = int(w * view.current_hp / view.max_hp)
        pygame.draw.rect(surface, COLOR_HEALTH_BAR, (x, y, fill_w, h))
        pygame.draw.rect(surface, COLOR_WHITE, (x, y, w, h), 1)
        txt = self._font.render(
            f"{view.current_hp}/{view.max_hp}", True, COLOR_WHITE)
        surface.blit(txt, (x + w + 6, y - 1))

    # ── armor bar ───────────────────────────────────────
    def _draw_armor_bar(self, surface, view):
        if view.armor_hp <= 0:
            return
        x, y, w, h = 10, 32, 180, 12
        pygame.draw.rect(surface, COLOR_ARMOR_BG, (x, y, w, h))
        fill_w = int(w * view.armor_hp / ARMOR_HP)
        pygame.draw.rect(surface, COLOR_ARMOR_BAR, (x, y, fill_w, h))
        pygame.draw.rect(surface, COLOR_WHITE, (x, y, w, h), 1)
        txt = self._small_font.render(
            f"Armor: {view.armor_hp}/{ARMOR_HP}", True, COLOR_WHITE)
        surface.blit(txt, (x + w + 6, y - 1))

    # ── weapon indicator ────────────────────────────────
    def _draw_weapon(self, surface, view):
        y = SCREEN_HEIGHT - 30
        x = 10
        if not view.weapons:
            txt = self._font.render("No weapons equipped", True, COLOR_GRAY)
            surface.blit(txt, (x, y))
            return

        for weapon in view.weapons:
            prefix = "> " if weapon.selected else "  "
            color = COLOR_WHITE if weapon.selected else COLOR_GRAY
            txt = self._font.render(prefix + weapon.label, True, color)
            surface.blit(txt, (x, y))
            x += txt.get_width() + 12

    # ── coins ───────────────────────────────────────────
    def _draw_coins(self, surface, view):
        txt = self._font.render(f"Coins: {view.coins}", True, COLOR_COIN)
        surface.blit(txt, (SCREEN_WIDTH - txt.get_width() - 10, 10))

    # ── minimap ─────────────────────────────────────────
    def _draw_minimap(self, surface, minimap_view):
        cell = 7
        rad = minimap_view.radius
        size = (2 * rad + 1) * cell
        ox = SCREEN_WIDTH - size - 10
        oy = SCREEN_HEIGHT - size - 40

        # background
        bg = pygame.Surface((size, size), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        surface.blit(bg, (ox, oy))

        for room in minimap_view.rooms:
            rx, ry = room.position
            px = (rx + rad) * cell + ox
            py = (ry + rad) * cell + oy
            color = self._minimap_room_color(room.kind)
            pygame.draw.rect(surface, color, (px, py, cell - 1, cell - 1))
            self._draw_minimap_wall_indicators(surface, room, px, py, cell)
            self._draw_minimap_objective_marker(surface, room.objective_marker, px, py, cell)

    @staticmethod
    def _minimap_room_color(kind):
        if kind == "current":
            return COLOR_PLAYER
        if kind == "objective":
            return COLOR_COMPASS
        if kind == "exit":
            return COLOR_PORTAL
        return COLOR_DARK_GRAY

    def _draw_minimap_wall_indicators(self, surface, room_view, px, py, cell):
        top = pygame.Rect(px, py, cell - 1, 1)
        bottom = pygame.Rect(px, py + cell - 2, cell - 1, 1)
        left = pygame.Rect(px, py, 1, cell - 1)
        right = pygame.Rect(px + cell - 2, py, 1, cell - 1)

        pygame.draw.rect(
            surface,
            self._door_kind_color(room_view.door_kinds.get("top", "none")),
            top,
        )
        pygame.draw.rect(
            surface,
            self._door_kind_color(room_view.door_kinds.get("bottom", "none")),
            bottom,
        )
        pygame.draw.rect(
            surface,
            self._door_kind_color(room_view.door_kinds.get("left", "none")),
            left,
        )
        pygame.draw.rect(
            surface,
            self._door_kind_color(room_view.door_kinds.get("right", "none")),
            right,
        )

    @staticmethod
    def _door_kind_color(kind):
        if kind == "two_way":
            return COLOR_DOOR_TWO_WAY
        if kind == "one_way":
            return COLOR_DOOR_ONE_WAY
        return COLOR_DOOR_NONE

    @staticmethod
    def _draw_minimap_objective_marker(surface, marker, px, py, cell):
        if marker is None:
            return

        kind, _label = marker
        if kind == "altar":
            color = (230, 110, 240)
        elif kind == "holdout":
            color = (245, 210, 120)
        elif kind == "relic":
            color = COLOR_COIN
        elif kind == "puzzle":
            color = (120, 220, 255)
        elif kind == "escort":
            color = (245, 220, 140)
        else:
            color = COLOR_PORTAL

        center = (px + (cell - 1) // 2, py + (cell - 1) // 2)
        pygame.draw.circle(surface, COLOR_BLACK, center, 2)
        pygame.draw.circle(surface, color, center, 1)

    # ── consumable quick-bar ────────────────────────────
    def _draw_quick_bar(self, surface, quick_bar_view):
        """Draw inventory quick-bar: Q=cycle potion, 4-7=use items."""
        y = SCREEN_HEIGHT - 58
        x = 10

        # Potion selector (Q to cycle, 4 to use)
        potion_label = (
            f"[Q/{4}] {quick_bar_view.selected_potion_name} "
            f"x{quick_bar_view.selected_potion_count}"
        )
        txt = self._small_font.render(potion_label, True, COLOR_WHITE)
        surface.blit(txt, (x, y))

        # Speed boost (5)
        sp_label = f"[5] Speed x{quick_bar_view.speed_boost_count}"
        txt = self._small_font.render(sp_label, True, COLOR_SPEED_GLOW)
        surface.blit(txt, (x + 200, y))

        # Attack boost (6)
        atk_label = f"[6] Attack x{quick_bar_view.attack_boost_count}"
        txt = self._small_font.render(atk_label, True, (255, 80, 80))
        surface.blit(txt, (x + 330, y))

        # Compass (7)
        comp_label = f"[7] Compass x{quick_bar_view.compass_uses}"
        txt = self._small_font.render(comp_label, True, COLOR_COMPASS)
        surface.blit(txt, (x + 470, y))

    # ── active effect timers ────────────────────────────
    def _draw_active_effects(self, surface, view):
        """Show remaining time for active boosts."""
        y = 50
        if view.armor_hp > 0:
            y = 50  # shift down if armor bar is showing

        for effect in view.active_effects:
            color = COLOR_SPEED_GLOW if effect.kind == "speed" else (255, 80, 80)
            txt = self._small_font.render(
                f"{effect.name}: {effect.seconds_remaining:.1f}s", True, color)
            surface.blit(txt, (10, y))
            y += 16

    # ── compass direction display ───────────────────────
    def _draw_compass(self, surface, compass_view):
        """Show compass direction arrow + text after use."""
        if not compass_view.visible:
            return
        txt = self._font.render(compass_view.label, True, COLOR_COMPASS)
        surface.blit(txt, txt.get_rect(
            center=(SCREEN_WIDTH // 2, 30)))

    def _draw_objective(self, surface, objective_view, compass_view):
        if not objective_view.visible:
            return
        y = 54 if compass_view.visible else 30
        txt = self._small_font.render(objective_view.label, True, COLOR_WHITE)
        surface.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, y)))

    # ── game over / victory screens ─────────────────────
    def draw_game_over(self, surface, overlay_view):
        self._ensure_fonts()
        self._draw_overlay(surface, overlay_view)

    def draw_victory(self, surface, overlay_view):
        self._ensure_fonts()
        self._draw_overlay(surface, overlay_view)

    def _draw_overlay(self, surface, overlay_view):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        big = pygame.font.SysFont("consolas", 48)
        txt = big.render(overlay_view.title, True, overlay_view.title_color)
        surface.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2,
                                                SCREEN_HEIGHT // 2 - 20)))
        if overlay_view.detail_text:
            detail = self._font.render(
                overlay_view.detail_text,
                True,
                overlay_view.detail_color,
            )
            surface.blit(detail, detail.get_rect(center=(SCREEN_WIDTH // 2,
                                                         SCREEN_HEIGHT // 2 + 20)))
            prompt_y = SCREEN_HEIGHT // 2 + 50
        else:
            prompt_y = SCREEN_HEIGHT // 2 + 30
        sub = self._font.render(
            overlay_view.prompt_text,
            True,
            overlay_view.prompt_color,
        )
        surface.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, prompt_y)))
