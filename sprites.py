"""Colored-rectangle sprite helpers — no external art assets needed."""
import pygame
from settings import TILE_SIZE


def make_rect_surface(width, height, color):
    """Return a Surface filled with *color*."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    surf.fill(color)
    return surf


def make_tile_surface(color):
    """Return a TILE_SIZE square filled with *color*."""
    return make_rect_surface(TILE_SIZE, TILE_SIZE, color)
