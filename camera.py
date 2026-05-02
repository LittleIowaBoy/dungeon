"""Camera: draws current room tiles then all sprite groups."""
import pygame
from settings import (
    TILE_SIZE, ROOM_COLS, ROOM_ROWS,
    COLOR_DOOR_ONE_WAY,
    THIN_ICE_CRACK_COLORS,
)
from room import TERRAIN_COLORS, THIN_ICE
from terrain_effects import thin_ice_crack_stage


# Biome-themed seal door palettes.  Keys match Room.biome_terrain
# ("mud"/"ice"/"water") with ``None`` as the fallback for biome-less
# rooms (e.g. the tuning test room).
SEAL_DOOR_THEMES = {
    "mud": {
        # Earthy oak planks held by iron bands.
        "base":  (118, 78, 42),
        "band":  (74, 44, 22),
        "frame": (40, 28, 18),
    },
    "ice": {
        # Frosted blue crystal slab with pale veins.
        "base":  (110, 170, 220),
        "band":  (210, 235, 250),
        "frame": (40, 80, 130),
    },
    "water": {
        # Coral-and-kelp barricade with bronze fittings.
        "base":  (45, 110, 110),
        "band":  (180, 140, 70),
        "frame": (20, 60, 65),
    },
    None: {
        # Stone-and-iron default for biome-less rooms.
        "base":  (110, 110, 115),
        "band":  (170, 165, 150),
        "frame": (50, 50, 55),
    },
}


class Camera:
    """Renders the current room (room == screen, no scrolling)."""

    def draw(self, surface, room, sprite_groups, dungeon=None, player=None):
        """
        Parameters
        ----------
        surface : pygame.Surface
        room : Room
        sprite_groups : list[pygame.sprite.Group]
            Groups to draw in order (enemies, items, chests, player, hitboxes…).
        """
        # tiles
        for r in range(ROOM_ROWS):
            for c in range(ROOM_COLS):
                tile = room.grid[r][c]
                color = TERRAIN_COLORS.get(tile, TERRAIN_COLORS["floor"])
                pygame.draw.rect(
                    surface, color,
                    (c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE),
                )
                # ── Thin-ice crack overlay ───────────────────────────────────
                # Draw progressively darker crack lines over THIN_ICE tiles
                # based on how many times the player has stepped on each one.
                if tile == THIN_ICE:
                    stage = thin_ice_crack_stage(room, c, r)
                    if 0 < stage <= len(THIN_ICE_CRACK_COLORS):
                        crack_color = THIN_ICE_CRACK_COLORS[stage - 1]
                        self._draw_thin_ice_cracks(
                            surface, c, r, stage, crack_color
                        )

        # sprites
        overlay_sprites = []
        for group in sprite_groups:
            group.draw(surface)
            overlay_sprites.extend(
                sprite for sprite in group if hasattr(sprite, "draw_overlay")
            )

        for sprite in overlay_sprites:
            sprite.draw_overlay(surface)

        # one-way door overlays (drawn on top so they are clearly visible)
        if dungeon is not None:
            self._draw_one_way_door_markers(surface, dungeon)
            self._draw_sealed_door_markers(surface, dungeon)
            self._draw_enemy_attack_hitboxes(surface, dungeon)
            # Fog-of-war pass for vision-radius rooms (echo cavern, blizzard,
            # anglerfish lure).  Drawn after gameplay sprites so it occludes
            # them, but before world-space text labels so HUD text stays
            # readable.
            self._draw_fog_of_war(surface, room, player)

        # bespoke world-space overlays (e.g., tuning test room section labels)
        if hasattr(room, "draw_overlay_labels"):
            room.draw_overlay_labels(surface)

    def _draw_enemy_attack_hitboxes(self, surface, dungeon):
        """Outline enemy attack hitboxes for designer visibility.

        Yellow outline during TELEGRAPH (incoming swing preview); red
        translucent fill + outline during STRIKE (active damage frame).
        Pulsator rings and launcher projectiles are visible as their own
        sprites so they need no extra overlay here.
        """
        enemy_group = getattr(dungeon, "enemy_group", None)
        if enemy_group is None:
            return
        telegraph_color = (255, 220, 0)
        strike_color = (255, 40, 40)
        strike_fill = (255, 40, 40, 90)
        for enemy in enemy_group:
            if not enemy.alive():
                continue
            for rect in getattr(enemy, "telegraph_hitboxes", lambda: ())():
                pygame.draw.rect(surface, telegraph_color, rect, width=2)
            strike_rects = getattr(enemy, "active_hitboxes", lambda: ())()
            for rect in strike_rects:
                fill = pygame.Surface(rect.size, pygame.SRCALPHA)
                fill.fill(strike_fill)
                surface.blit(fill, rect.topleft)
                pygame.draw.rect(surface, strike_color, rect, width=2)

    def _draw_fog_of_war(self, surface, room, player):
        """Hard-circle fog-of-war for ``Room.vision_radius`` rooms.

        Renders a near-opaque dark overlay with a transparent hole around
        the player.  Soft falloff is intentionally deferred to a polish
        pass; a hard circle is cheap and reads clearly to designers.
        """
        radius = getattr(room, "vision_radius", None)
        if not radius or radius <= 0:
            return
        if player is None or not hasattr(player, "rect"):
            return
        w, h = surface.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 215))
        pygame.draw.circle(
            overlay, (0, 0, 0, 0),
            player.rect.center, int(radius),
        )
        surface.blit(overlay, (0, 0))

    def _draw_one_way_door_markers(self, surface, dungeon):
        marker_margin = 2
        marker_thickness = 5
        current_kinds = dungeon.current_room_door_kinds()

        if current_kinds.get("top") == "one_way":
            y = marker_margin
            rect = pygame.Rect(0, y, ROOM_COLS * TILE_SIZE, marker_thickness)
            pygame.draw.rect(surface, COLOR_DOOR_ONE_WAY, rect)

        if current_kinds.get("bottom") == "one_way":
            y = ROOM_ROWS * TILE_SIZE - marker_margin - marker_thickness
            rect = pygame.Rect(0, y, ROOM_COLS * TILE_SIZE, marker_thickness)
            pygame.draw.rect(surface, COLOR_DOOR_ONE_WAY, rect)

        if current_kinds.get("left") == "one_way":
            x = marker_margin
            rect = pygame.Rect(x, 0, marker_thickness, ROOM_ROWS * TILE_SIZE)
            pygame.draw.rect(surface, COLOR_DOOR_ONE_WAY, rect)

        if current_kinds.get("right") == "one_way":
            x = ROOM_COLS * TILE_SIZE - marker_margin - marker_thickness
            rect = pygame.Rect(x, 0, marker_thickness, ROOM_ROWS * TILE_SIZE)
            pygame.draw.rect(surface, COLOR_DOOR_ONE_WAY, rect)

    def _draw_sealed_door_markers(self, surface, dungeon):
        """Render biome-themed seal doors over each closed entrance/exit."""
        room = dungeon.current_room
        if not getattr(room, "doors_sealed", False):
            return
        biome = getattr(room, "biome_terrain", None)
        theme = SEAL_DOOR_THEMES.get(biome, SEAL_DOOR_THEMES[None])
        for direction, rect in room.get_seal_door_rects():
            self._draw_seal_door(surface, rect, direction, theme)

    @staticmethod
    def _draw_seal_door(surface, rect, direction, theme):
        """Paint a single themed seal door at *rect*.

        The door is a base panel with two contrasting bands (planks for
        wood, frost cracks for ice, kelp ribs for water, stone joints by
        default).  Bands run perpendicular to the wall so the door reads
        as a closed barrier no matter which side of the room it's on.
        """
        base, band, frame = theme["base"], theme["band"], theme["frame"]
        pygame.draw.rect(surface, base, rect)
        # Frame border.
        pygame.draw.rect(surface, frame, rect, width=2)
        # Two cross-bands perpendicular to the wall.
        if direction in ("top", "bottom"):
            band_h = 4
            for i in (1, 2):
                y = rect.y + (rect.h * i) // 3 - band_h // 2
                pygame.draw.rect(
                    surface, band,
                    pygame.Rect(rect.x + 2, y, rect.w - 4, band_h),
                )
        else:
            band_w = 4
            for i in (1, 2):
                x = rect.x + (rect.w * i) // 3 - band_w // 2
                pygame.draw.rect(
                    surface, band,
                    pygame.Rect(x, rect.y + 2, band_w, rect.h - 4),
                )
        # Center stud / lock so the door reads as closed.
        cx, cy = rect.center
        pygame.draw.rect(
            surface, frame,
            pygame.Rect(cx - 3, cy - 3, 6, 6),
        )

    # ------------------------------------------------------------------
    def _draw_thin_ice_cracks(self, surface, col, row, stage, crack_color):
        """Draw crack lines on a THIN_ICE tile proportional to *stage*.

        Stage 1: two crossing primary cracks with a couple of short branches.
        Stage 2: the stage-1 lines remain, additional secondary cracks radiate
        outward from the crossing point, and the tile edge begins to show
        stress marks — giving a heavily fractured look just before collapse.
        """
        x0 = col * TILE_SIZE
        y0 = row * TILE_SIZE
        ts = TILE_SIZE

        overlay = pygame.Surface((ts, ts), pygame.SRCALPHA)

        r, g, b, a = crack_color
        line_color = (r, g, b, a)
        branch_color = (r, g, b, max(0, a - 30))
        thin_color   = (r, g, b, max(0, a - 60))

        # ── Stage 1: two primary crossing cracks + 3 branches ──────────────
        # Primary crack: top-left quadrant → bottom-right quadrant
        pygame.draw.line(overlay, line_color,
                         (ts // 5,      ts // 4),
                         (ts * 4 // 5,  ts * 3 // 4), 2)
        # Second primary: top-right → bottom-left
        pygame.draw.line(overlay, line_color,
                         (ts * 3 // 4,  ts // 5),
                         (ts // 5,      ts * 4 // 5), 2)

        mid_x, mid_y = ts // 2, ts // 2

        # Branches sprouting from the crossing centre
        pygame.draw.line(overlay, branch_color,
                         (mid_x, mid_y), (mid_x - ts // 4, mid_y - ts // 8), 1)
        pygame.draw.line(overlay, branch_color,
                         (mid_x, mid_y), (mid_x + ts // 4, mid_y + ts // 8), 1)
        pygame.draw.line(overlay, branch_color,
                         (mid_x, mid_y), (mid_x + ts // 8, mid_y - ts // 4), 1)

        if stage >= 2:
            # ── Stage 2: extra radiating cracks + edge stress lines ─────────
            # Additional diagonal splinters from the centre
            pygame.draw.line(overlay, branch_color,
                             (mid_x, mid_y), (mid_x - ts // 5, mid_y + ts // 3), 1)
            pygame.draw.line(overlay, branch_color,
                             (mid_x, mid_y), (mid_x + ts // 3, mid_y - ts // 5), 1)
            pygame.draw.line(overlay, branch_color,
                             (mid_x, mid_y), (ts - 2, mid_y + ts // 6), 1)
            pygame.draw.line(overlay, branch_color,
                             (mid_x, mid_y), (ts // 6, 2), 1)

            # Hairline stress cracks near tile edges (makes the ice look
            # like it is about to shatter at the seams)
            pygame.draw.line(overlay, thin_color,
                             (1, ts // 3),       (ts // 4, ts // 2), 1)
            pygame.draw.line(overlay, thin_color,
                             (ts - 2, ts * 2 // 3), (ts * 3 // 4, ts // 2), 1)
            pygame.draw.line(overlay, thin_color,
                             (ts // 3, 1),       (ts // 2, ts // 4), 1)
            pygame.draw.line(overlay, thin_color,
                             (ts * 2 // 3, ts - 2), (ts // 2, ts * 3 // 4), 1)

            # Small corner chips
            pygame.draw.line(overlay, thin_color,
                             (2, 2), (ts // 6, ts // 7), 1)
            pygame.draw.line(overlay, thin_color,
                             (ts - 2, ts - 2), (ts * 5 // 6, ts * 6 // 7), 1)

        surface.blit(overlay, (x0, y0))


