"""Camera: draws current room tiles then all sprite groups."""
import pygame
from settings import (
    TILE_SIZE, ROOM_COLS, ROOM_ROWS,
    COLOR_DOOR_ONE_WAY,
)
from room import TERRAIN_COLORS


class Camera:
    """Renders the current room (room == screen, no scrolling)."""

    def draw(self, surface, room, sprite_groups, dungeon=None):
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
