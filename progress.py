"""Player and dungeon progress tracking.

PlayerProgress is the single source of truth for persistent state.
It is loaded from / saved to the SQLite database via save_system.
"""
from dungeon_config import DUNGEONS


class DungeonProgress:
    """Tracks a single dungeon's run state."""

    def __init__(self, dungeon_id, current_level=0, is_alive=True, completed=False):
        self.dungeon_id = dungeon_id
        self.current_level = current_level
        self.is_alive = is_alive
        self.completed = completed

    def advance_level(self, total_levels=5):
        """Move to the next level. Returns True if dungeon is now complete."""
        if self.current_level >= total_levels - 1:
            self.completed = True
            return True
        self.current_level += 1
        return False

    def reset(self):
        """Reset dungeon to the beginning (used on death)."""
        self.current_level = 0
        self.is_alive = True
        self.completed = False

    def die(self):
        """Mark the player as dead in this dungeon and reset to level 0."""
        self.is_alive = False
        self.current_level = 0


class PlayerProgress:
    """Aggregates all persistent player state."""

    def __init__(self):
        self.coins = 0
        self.max_hp = 100
        self.speed_cap = 1.5
        self.dungeons: dict[str, DungeonProgress] = {}
        self.inventory: dict[str, int] = {}  # item_id -> quantity

        # create an entry for every defined dungeon
        for d in DUNGEONS:
            self.dungeons[d["id"]] = DungeonProgress(d["id"])

    def get_dungeon(self, dungeon_id) -> DungeonProgress:
        if dungeon_id not in self.dungeons:
            self.dungeons[dungeon_id] = DungeonProgress(dungeon_id)
        return self.dungeons[dungeon_id]

    def can_resume(self, dungeon_id) -> bool:
        dp = self.get_dungeon(dungeon_id)
        return dp.is_alive and dp.current_level > 0 and not dp.completed

    def die_in_dungeon(self, dungeon_id):
        self.get_dungeon(dungeon_id).die()

    def advance_in_dungeon(self, dungeon_id, total_levels=5):
        return self.get_dungeon(dungeon_id).advance_level(total_levels)

    def start_dungeon(self, dungeon_id):
        """Prepare a dungeon for a fresh start (or resume)."""
        dp = self.get_dungeon(dungeon_id)
        dp.is_alive = True
