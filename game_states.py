"""Game state enum used across all modules."""
from enum import Enum, auto


class GameState(Enum):
    MAIN_MENU           = auto()
    ROOM_TEST_SELECT    = auto()
    ROOM_TEST_CATEGORY  = auto()
    DUNGEON_SELECT      = auto()
    CHARACTER_CUSTOMIZE = auto()
    SHOP                = auto()
    RECORDS             = auto()
    PLAYING             = auto()
    PAUSED              = auto()
    PAUSE_ALL_ITEMS     = auto()  # test-room only: pause sub-screen for force-equip items
    PAUSE_ALL_RUNES     = auto()  # test-room only: pause sub-screen for force-equip runes
    RUNE_ALTAR_PICK     = auto()
    LEVEL_COMPLETE      = auto()
    GAME_OVER           = auto()
    GAME_WIN            = auto()  # entire dungeon cleared (all 5 levels)
