"""HUD: health bar, armor bar, weapon indicator, coin counter, minimap,
consumable quick-bar, compass, game-state screens."""
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_HEALTH_BAR, COLOR_HEALTH_BG,
    COLOR_WHITE, COLOR_BLACK, COLOR_COIN, COLOR_PORTAL,
    COLOR_PLAYER, COLOR_DARK_GRAY, COLOR_GRAY, COLOR_LIGHT_GRAY,
    COLOR_ARMOR_BAR, COLOR_ARMOR_BG,
    COLOR_SPEED_GLOW, COLOR_COMPASS,
    COLOR_DOOR_TWO_WAY, COLOR_DOOR_ONE_WAY, COLOR_DOOR_NONE,
    COLOR_DOOR_SEALED,
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
        # World-anchored overlays first so HUD chrome stays on top.
        self._draw_entity_health_bars(surface, view.entity_health_bars)
        self._draw_damage_numbers(surface, view.damage_numbers)
        self._draw_biome_reward_flashes(surface, view.biome_reward_flashes)
        self._draw_health_bar(surface, view)
        self._draw_armor_bar(surface, view)
        self._draw_weapon(surface, view)
        self._draw_coins(surface, view)
        self._draw_minimap(surface, view.minimap)
        self._draw_quick_bar(surface, view.quick_bar)
        self._draw_active_effects(surface, view)
        self._draw_compass(surface, view.compass)
        self._draw_objective(surface, view.objective, view.compass)
        self._draw_room_identifier(
            surface,
            view.room_identifier,
            view.compass,
            view.objective,
        )
        self._draw_equipped_runes(surface, view.equipped_runes)
        self._draw_rune_meters(surface, view.rune_meters)
        self._draw_dodge_indicator(surface, view.dodge)
        self._draw_ability_indicator(surface, view.ability)
        self._draw_keystone_bonus_banner(surface, view.keystone_bonus_banner)
        self._draw_boss_health_bar(surface, view.boss_health_bar)
        self._draw_boss_intro_banner(surface, view.boss_intro_banner)

    # ── world-space health bars ─────────────────────────
    def _draw_entity_health_bars(self, surface, bar_views):
        if not bar_views:
            return
        bar_w = 28
        bar_h = 4
        for bar in bar_views:
            if bar.max_hp <= 0:
                continue
            ratio = max(0.0, min(1.0, bar.current_hp / bar.max_hp))
            cx = bar.rect.centerx
            top = bar.rect.top - bar_h - 3
            x = cx - bar_w // 2
            pygame.draw.rect(surface, COLOR_HEALTH_BG, (x, top, bar_w, bar_h))
            pygame.draw.rect(
                surface, COLOR_HEALTH_BAR,
                (x, top, int(bar_w * ratio), bar_h),
            )
            pygame.draw.rect(surface, COLOR_BLACK, (x, top, bar_w, bar_h), 1)

    # ── floating damage numbers ─────────────────────────
    def _draw_damage_numbers(self, surface, number_views):
        if not number_views:
            return
        from damage_feedback import DAMAGE_NUMBER_RISE_PIXELS
        font = self._font
        for number in number_views:
            rise = int(DAMAGE_NUMBER_RISE_PIXELS * number.age_fraction)
            cx, cy = number.world_pos
            cy = cy - 18 - rise
            text = number.text
            # Black 1px outline (4-direction blit) for legibility.
            outline = font.render(text, True, COLOR_BLACK)
            ow, oh = outline.get_size()
            ox = cx - ow // 2
            oy = cy - oh // 2
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                surface.blit(outline, (ox + dx, oy + dy))
            fill = font.render(text, True, COLOR_WHITE)
            surface.blit(fill, (ox, oy))

    # ── biome reward spend flashes ──────────────────────
    def _draw_biome_reward_flashes(self, surface, flash_views):
        if not flash_views:
            return
        from damage_feedback import (
            BIOME_REWARD_FLASH_COLORS,
            BIOME_REWARD_FLASH_MAX_RADIUS,
        )
        for flash in flash_views:
            color = BIOME_REWARD_FLASH_COLORS.get(flash.kind)
            if color is None:
                continue
            cx, cy = flash.world_pos
            radius = max(2, int(BIOME_REWARD_FLASH_MAX_RADIUS * flash.age_fraction))
            # Ring thickness shrinks as the flash expands so it fades visually.
            thickness = max(1, int(4 * (1.0 - flash.age_fraction)))
            pygame.draw.circle(surface, color, (cx, cy), radius, thickness)

    # ── keystone starting-coin bonus banner ─────────────
    def _draw_keystone_bonus_banner(self, surface, banner):
        if banner is None:
            return
        # Large fading text near top-center; alpha and slight rise tied to age.
        font = pygame.font.SysFont("consolas", 28, bold=True)
        alpha = max(0, int(255 * (1.0 - banner.age_fraction)))
        rise = int(20 * banner.age_fraction)
        # Pre-render outline + fill, then apply alpha to a composited surface.
        text = banner.text
        outline = font.render(text, True, COLOR_BLACK)
        fill = font.render(text, True, COLOR_COIN)
        ow, oh = fill.get_size()
        composite = pygame.Surface((ow + 2, oh + 2), pygame.SRCALPHA)
        for dx, dy in ((0, 0), (2, 0), (0, 2), (2, 2)):
            composite.blit(outline, (dx, dy))
        composite.blit(fill, (1, 1))
        composite.set_alpha(alpha)
        rect = composite.get_rect(center=(SCREEN_WIDTH // 2, 56 - rise))
        surface.blit(composite, rect)

    # ── boss health bar (top-of-screen, mini-boss only) ─
    def _draw_boss_health_bar(self, surface, bar):
        if bar is None or bar.max_hp <= 0:
            return
        bar_w = min(420, SCREEN_WIDTH - 80)
        bar_h = 16
        x = (SCREEN_WIDTH - bar_w) // 2
        y = 80
        ratio = max(0.0, min(1.0, bar.current_hp / bar.max_hp))
        pygame.draw.rect(surface, COLOR_HEALTH_BG, (x, y, bar_w, bar_h))
        pygame.draw.rect(
            surface, COLOR_HEALTH_BAR,
            (x, y, int(bar_w * ratio), bar_h),
        )
        pygame.draw.rect(surface, COLOR_WHITE, (x, y, bar_w, bar_h), 1)
        if bar.name:
            label_font = pygame.font.SysFont("consolas", 16, bold=True)
            label = bar.name
            if bar.phase >= 2:
                label = f"{label}  \u2014  PHASE 2"
            outline = label_font.render(label, True, COLOR_BLACK)
            fill = label_font.render(label, True, COLOR_WHITE)
            lw, lh = fill.get_size()
            lx = (SCREEN_WIDTH - lw) // 2
            ly = y - lh - 2
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                surface.blit(outline, (lx + dx, ly + dy))
            surface.blit(fill, (lx, ly))

    # ── boss intro banner (mirrors keystone style, red palette) ─
    def _draw_boss_intro_banner(self, surface, banner):
        if banner is None:
            return
        font = pygame.font.SysFont("consolas", 36, bold=True)
        alpha = max(0, int(255 * (1.0 - banner.age_fraction)))
        rise = int(28 * banner.age_fraction)
        text = banner.text.upper()
        outline = font.render(text, True, COLOR_BLACK)
        fill = font.render(text, True, COLOR_HEALTH_BAR)
        ow, oh = fill.get_size()
        composite = pygame.Surface((ow + 2, oh + 2), pygame.SRCALPHA)
        for dx, dy in ((0, 0), (2, 0), (0, 2), (2, 2)):
            composite.blit(outline, (dx, dy))
        composite.blit(fill, (1, 1))
        composite.set_alpha(alpha)
        rect = composite.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3 - rise))
        surface.blit(composite, rect)

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
            self._draw_minimap_objective_marker(
                surface,
                room.objective_marker,
                px,
                py,
                cell,
                getattr(room, "objective_status", None),
            )

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
        if kind == "sealed":
            return COLOR_DOOR_SEALED
        return COLOR_DOOR_NONE

    @staticmethod
    def _draw_minimap_objective_marker(surface, marker, px, py, cell, status=None):
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
        # Status ring (drawn behind the dot so the dot still reads at a glance).
        if status is not None:
            ring_color = HUD._minimap_status_ring_color(kind, status)
            if ring_color is not None:
                pygame.draw.circle(surface, ring_color, center, 3, 1)
        pygame.draw.circle(surface, COLOR_BLACK, center, 2)
        pygame.draw.circle(surface, color, center, 1)

    @staticmethod
    def _minimap_status_ring_color(kind, status):
        # Holdout polish: shrink/migration/anchor each get a distinct halo.
        if kind == "holdout":
            if status == "migrating":
                return (255, 240, 200)
            if status == "anchored":
                return (180, 220, 255)
            if status == "contested":
                return (255, 110, 90)
            if status == "shrinking":
                return (245, 170, 90)
        # Ritual role_chain telegraph: mirror the in-world role glyph color
        # onto the minimap marker so kill order reads at a glance.
        if kind == "altar":
            if status == "summon":
                return (255, 130, 110)
            if status == "pulse":
                return (255, 220, 110)
            if status == "ward":
                return (140, 200, 255)
        return None

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

        # Biome challenge-route trophies (8/9/0). Colors mirror the item icons
        # in item_catalog.py so the badges read as the same trophy.
        shard_label = f"[8] Shard x{quick_bar_view.stat_shard_count}"
        txt = self._small_font.render(shard_label, True, (200, 140, 70))
        surface.blit(txt, (x + 600, y))

        rune_label = f"[9] Rune x{quick_bar_view.tempo_rune_count}"
        txt = self._small_font.render(rune_label, True, (160, 210, 255))
        surface.blit(txt, (x + 720, y))

        charge_label = f"[0] Dash x{quick_bar_view.mobility_charge_count}"
        txt = self._small_font.render(charge_label, True, (90, 230, 200))
        surface.blit(txt, (x + 830, y))

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

    # ── equipped runes strip ────────────────────────────
    def _draw_equipped_runes(self, surface, equipped_runes_view):
        if not equipped_runes_view.runes:
            return
        # Render along the bottom-left, above the quick bar.
        x = 10
        y = SCREEN_HEIGHT - 96
        header = self._small_font.render("Runes", True, COLOR_WHITE)
        surface.blit(header, (x, y))
        y += 16
        for rune_view in equipped_runes_view.runes:
            color = (210, 200, 255) if rune_view.category != "identity" else (255, 215, 130)
            txt = self._small_font.render(rune_view.short_label, True, color)
            surface.blit(txt, (x, y))
            y += 14

    # ── rune meters (time anchor / static charge / glass-soul i-frame) ──
    _RUNE_METER_COLORS = {
        "time_anchor":       (180, 200, 255),
        "static_charge":     (255, 240, 130),
        "glass_soul_iframe": (255, 180, 200),
    }

    def _draw_rune_meters(self, surface, rune_meters_view):
        meters = [
            rune_meters_view.time_anchor,
            rune_meters_view.static_charge,
            rune_meters_view.glass_soul_iframe,
        ]
        visible = [m for m in meters if m.visible]
        if not visible:
            return

        x = 10
        bar_w, bar_h = 120, 6
        spacing = 14
        # Stack upward above the equipped-runes header (which sits at SCREEN_HEIGHT - 96).
        y = SCREEN_HEIGHT - 96 - 4 - spacing * len(visible)

        for meter in visible:
            color = self._RUNE_METER_COLORS.get(meter.kind, COLOR_WHITE)
            pygame.draw.rect(surface, COLOR_HEALTH_BG, (x, y, bar_w, bar_h))
            fill_w = max(0, min(bar_w, int(bar_w * meter.fill_fraction)))
            pygame.draw.rect(surface, color, (x, y, fill_w, bar_h))
            pygame.draw.rect(surface, COLOR_WHITE, (x, y, bar_w, bar_h), 1)
            label = self._small_font.render(meter.label, True, color)
            surface.blit(label, (x + bar_w + 6, y - 4))
            y += spacing

    # ── dodge indicator ─────────────────────────────────
    def _draw_dodge_indicator(self, surface, dodge_view):
        # Small chip at bottom-right showing [Shift] dodge state.
        x = SCREEN_WIDTH - 110
        y = SCREEN_HEIGHT - 24
        if dodge_view.active:
            color = (140, 220, 255)
            label = "[Shift] DODGE"
        elif dodge_view.ready:
            color = (200, 230, 200)
            label = "[Shift] Dodge"
        else:
            color = (140, 140, 140)
            pct = int((1.0 - dodge_view.cooldown_fraction) * 100)
            label = f"[Shift] {pct}%"
        txt = self._small_font.render(label, True, color)
        surface.blit(txt, (x, y))

    # ── active ability indicator ─────────────────────
    def _draw_ability_indicator(self, surface, ability_view):
        x = SCREEN_WIDTH - 230
        y = SCREEN_HEIGHT - 24
        if not ability_view.equipped:
            color = (90, 90, 90)
            label = "[F] —"
        elif ability_view.ready:
            color = (255, 220, 140)
            label = f"[F] {ability_view.label}"
        else:
            color = (140, 130, 100)
            pct = int((1.0 - ability_view.cooldown_fraction) * 100)
            label = f"[F] {ability_view.label} {pct}%"
        txt = self._small_font.render(label, True, color)
        surface.blit(txt, (x, y))

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
        rect = txt.get_rect(center=(SCREEN_WIDTH // 2, y))
        surface.blit(txt, rect)
        if objective_view.extraction_bonus_visible:
            badge = self._small_font.render(
                f"+{objective_view.extraction_bonus_amount} BONUS",
                True,
                COLOR_COIN,
            )
            badge_rect = badge.get_rect(midleft=(rect.right + 10, rect.centery))
            surface.blit(badge, badge_rect)
        if objective_view.carrying_heartstone:
            badge = self._small_font.render("♥ Heartstone", True, (220, 60, 70))
            badge_rect = badge.get_rect(midright=(rect.left - 10, rect.centery))
            surface.blit(badge, badge_rect)

    def _draw_room_identifier(self, surface, room_identifier_view, compass_view, objective_view):
        if not room_identifier_view.visible:
            return

        title = self._small_font.render(room_identifier_view.title, True, COLOR_WHITE)
        detail = self._small_font.render(room_identifier_view.detail, True, COLOR_LIGHT_GRAY)

        padding_x = 10
        padding_y = 6
        line_gap = 3
        width = max(title.get_width(), detail.get_width()) + padding_x * 2
        height = title.get_height() + detail.get_height() + padding_y * 2 + line_gap

        top = 28
        if compass_view.visible:
            top += 24
        if objective_view.visible:
            top += 22

        rect = pygame.Rect((SCREEN_WIDTH - width) // 2, top, width, height)
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 170))
        surface.blit(panel, rect.topleft)
        pygame.draw.rect(surface, COLOR_GRAY, rect, 1)

        surface.blit(title, (rect.x + padding_x, rect.y + padding_y))
        surface.blit(
            detail,
            (rect.x + padding_x, rect.y + padding_y + title.get_height() + line_gap),
        )

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
