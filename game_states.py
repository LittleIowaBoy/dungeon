"""Game state enum used across all modules."""
from enum import Enum, auto


class GameState(Enum):
    MAIN_MENU           = auto()
    DUNGEON_SELECT      = auto()
    CHARACTER_CUSTOMIZE = auto()
    SHOP                = auto()
    PLAYING             = auto()
    PAUSED              = auto()
    LEVEL_COMPLETE      = auto()
    GAME_OVER           = auto()
    GAME_WIN            = auto()  # entire dungeon cleared (all 5 levels)
