"""Colored-rectangle sprite helpers — no external art assets needed."""
import pygame


def make_rect_surface(width, height, color):
    """Return a Surface filled with *color*."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    surf.fill(color)
    return surf
