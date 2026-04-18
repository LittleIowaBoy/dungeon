"""Dungeon: room graph, boundary enforcement, pre-seeded exit path."""
import random
import pygame
from settings import (
    DEFAULT_PORTAL_DISTANCE, MAX_DUNGEON_RADIUS,
    DIR_OFFSETS, OPPOSITE_DIR,
    TILE_SIZE, ROOM_COLS, ROOM_ROWS,
)
from room import Room
from chest import Chest
from enemies import Enemy


_ALL_DIRS = list(DIR_OFFSETS.keys())


def _in_bounds(x, y, radius=MAX_DUNGEON_RADIUS):
    return abs(x) <= radius and abs(y) <= radius


class Dungeon:
    """Manages the full dungeon graph of Room objects."""

    def __init__(self, dungeon_config=None, level_index=0):
        self.rooms: dict[tuple[int, int], Room] = {}
        self.current_pos = (0, 0)

        # ── extract level config (or use defaults) ──────
        self._config = dungeon_config
        self._level_index = level_index

        if dungeon_config and level_index < len(dungeon_config["levels"]):
            lvl = dungeon_config["levels"][level_index]
            self._path_length = lvl["path_length"]
            self._terrain_type = dungeon_config["terrain_type"]
            self._enemy_count_range = lvl["enemy_count_range"]
            self._enemy_type_weights = lvl["enemy_type_weights"]
        else:
            self._path_length = DEFAULT_PORTAL_DISTANCE
            self._terrain_type = None
            self._enemy_count_range = None
            self._enemy_type_weights = None

        # dynamic radius: ensure the path can always fit
        self._radius = max(MAX_DUNGEON_RADIUS, self._path_length + 2)

        # pre-seed the critical path from (0,0) to exit
        self._exit_path = self._generate_exit_path()
        self._exit_pos = self._exit_path[-1]

        # generate all rooms along the exit path
        for i, pos in enumerate(self._exit_path):
            is_exit = (pos == self._exit_pos)
            doors = self._path_doors(i)
            self._create_room(pos, forced_doors=doors, is_exit=is_exit)

        # track which rooms the player has visited (for minimap fog-of-war)
        self.visited: set[tuple[int, int]] = {(0, 0)}

        # runtime sprite groups (populated when entering a room)
        self.enemy_group: pygame.sprite.Group = pygame.sprite.Group()
        self.item_group: pygame.sprite.Group = pygame.sprite.Group()
        self.chest_group: pygame.sprite.Group = pygame.sprite.Group()
        self.hitbox_group: pygame.sprite.Group = pygame.sprite.Group()

        # load starting room
        self._load_room_sprites()

    # ── public API ──────────────────────────────────────
    @property
    def current_room(self) -> Room:
        return self.rooms[self.current_pos]

    def try_transition(self, player_rect):
        """Check if the player has stepped through a door.

        Returns the direction string if a transition happened, else None.
        """
        room = self.current_room
        px, py = player_rect.centerx, player_rect.centery

        for direction, has_door in room.doors.items():
            if not has_door:
                continue
            if self._at_door(px, py, direction):
                return direction
        return None

    def move_to(self, direction):
        """Transition to the adjacent room in *direction*.

        Generates the room if it doesn't exist. Returns the pixel position
        where the player should spawn in the new room.
        """
        dx, dy = DIR_OFFSETS[direction]
        nx, ny = self.current_pos[0] + dx, self.current_pos[1] + dy

        if not _in_bounds(nx, ny, self._radius):
            return None  # should never happen (door suppressed)

        if (nx, ny) not in self.rooms:
            opp = OPPOSITE_DIR[direction]
            self._generate_room((nx, ny), forced_doors={opp: True})

        # save chest looted state before leaving
        self._save_chest_state()

        self.current_pos = (nx, ny)
        self.visited.add(self.current_pos)
        self._load_room_sprites()

        # player spawn position: opposite door
        opp = OPPOSITE_DIR[direction]
        spawn = self.current_room.door_pixel_pos(opp)
        # nudge inward so the player isn't immediately re-triggering
        inward = DIR_OFFSETS[OPPOSITE_DIR[opp]]
        spawn = (spawn[0] + inward[0] * TILE_SIZE,
                 spawn[1] + inward[1] * TILE_SIZE)
        return spawn

    # ── exit path generation ────────────────────────────
    def _generate_exit_path(self):
        """Random walk of _path_length steps from (0,0), no revisits."""
        path = [(0, 0)]
        visited = {(0, 0)}
        cx, cy = 0, 0
        for _ in range(self._path_length):
            candidates = []
            for d in _ALL_DIRS:
                ox, oy = DIR_OFFSETS[d]
                nx, ny = cx + ox, cy + oy
                if _in_bounds(nx, ny, self._radius) and (nx, ny) not in visited:
                    candidates.append((d, nx, ny))
            if not candidates:
                break
            d, cx, cy = random.choice(candidates)
            path.append((cx, cy))
            visited.add((cx, cy))
        return path

    def _path_doors(self, path_index):
        """Return forced doors dict for the room at exit-path[path_index]."""
        doors = {}
        pos = self._exit_path[path_index]
        # door toward the previous room
        if path_index > 0:
            prev = self._exit_path[path_index - 1]
            for d, (ox, oy) in DIR_OFFSETS.items():
                if (pos[0] + ox, pos[1] + oy) == prev:
                    doors[d] = True
        # door toward the next room
        if path_index < len(self._exit_path) - 1:
            nxt = self._exit_path[path_index + 1]
            for d, (ox, oy) in DIR_OFFSETS.items():
                if (pos[0] + ox, pos[1] + oy) == nxt:
                    doors[d] = True
        return doors

    # ── room creation / generation ──────────────────────
    def _create_room(self, pos, forced_doors=None, is_exit=False):
        doors = self._random_doors(pos, forced_doors)
        room = Room(doors, is_exit=is_exit,
                    terrain_type=self._terrain_type,
                    enemy_count_range=self._enemy_count_range,
                    enemy_type_weights=self._enemy_type_weights)
        self.rooms[pos] = room
        return room

    def _generate_room(self, pos, forced_doors=None):
        """Lazily generate a non-path room at *pos*."""
        # also force doors toward any existing neighbor that has a door toward us
        if forced_doors is None:
            forced_doors = {}
        for d, (ox, oy) in DIR_OFFSETS.items():
            neighbor_pos = (pos[0] + ox, pos[1] + oy)
            if neighbor_pos in self.rooms:
                opp = OPPOSITE_DIR[d]
                if self.rooms[neighbor_pos].doors.get(opp):
                    forced_doors[d] = True
        return self._create_room(pos, forced_doors)

    def _random_doors(self, pos, forced=None):
        """Pick random doors, suppressing any that lead out of bounds."""
        doors = {}
        for d, (ox, oy) in DIR_OFFSETS.items():
            nx, ny = pos[0] + ox, pos[1] + oy
            if not _in_bounds(nx, ny, self._radius):
                doors[d] = False
            elif forced and d in forced:
                doors[d] = True
            else:
                doors[d] = random.random() < 0.5
        # guarantee at least one door (besides forced)
        if not any(doors.values()):
            options = [d for d in _ALL_DIRS
                       if _in_bounds(pos[0] + DIR_OFFSETS[d][0],
                                     pos[1] + DIR_OFFSETS[d][1],
                                     self._radius)]
            if options:
                doors[random.choice(options)] = True
        return doors

    # ── room sprite loading ─────────────────────────────
    def _load_room_sprites(self):
        """Populate sprite groups for the current room (called on every room enter)."""
        self.enemy_group.empty()
        self.item_group.empty()
        self.chest_group.empty()
        self.hitbox_group.empty()

        room = self.current_room

        # enemies: always re-instantiated (respawn)
        for cls, (px, py) in room.enemy_configs:
            enemy = cls(px, py)
            self.enemy_group.add(enemy)

        # chest
        if room.chest_pos:
            chest = Chest(room.chest_pos[0], room.chest_pos[1],
                          looted=room.chest_looted)
            self.chest_group.add(chest)

    def _save_chest_state(self):
        """Persist chest looted flag back to the Room data."""
        room = self.current_room
        for chest in self.chest_group:
            room.chest_looted = chest.looted
            break  # only one chest per room

    # ── door detection ──────────────────────────────────
    @staticmethod
    def _at_door(px, py, direction):
        margin = 4
        if direction == "top" and py <= margin:
            return True
        if direction == "bottom" and py >= ROOM_ROWS * TILE_SIZE - margin:
            return True
        if direction == "left" and px <= margin:
            return True
        if direction == "right" and px >= ROOM_COLS * TILE_SIZE - margin:
            return True
        return False
