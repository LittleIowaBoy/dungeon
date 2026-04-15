"""Camera: draws current room tiles then all sprite groups."""
import pygame
from settings import TILE_SIZE, ROOM_COLS, ROOM_ROWS
from room import TERRAIN_COLORS


class Camera:
    """Renders the current room (room == screen, no scrolling)."""

    def draw(self, surface, room, sprite_groups):
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
        for group in sprite_groups:
            group.draw(surface)
