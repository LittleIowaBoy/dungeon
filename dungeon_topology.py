"""Topology planning for dungeon room graphs.

Grid-based model: rooms are placed on an N×N grid centred at (0,0).
The start room and portal room are chosen at random with a configurable
minimum Manhattan-distance separation.  Every room records its BFS
distance from the start and from the exit so downstream systems can
apply difficulty gradients without relying on linear path position.
"""

from collections import deque
from dataclasses import dataclass
import random

from settings import DIR_OFFSETS, OPPOSITE_DIR


_ALL_DIRS = tuple(DIR_OFFSETS)


def _in_bounds(x, y, radius):
    return abs(x) <= radius and abs(y) <= radius


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _direction_between(start, end):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    for direction, (ox, oy) in DIR_OFFSETS.items():
        if (dx, dy) == (ox, oy):
            return direction
    raise ValueError(f"Positions {start!r} and {end!r} are not adjacent")


@dataclass(frozen=True, slots=True)
class TopologyRoom:
    position: tuple[int, int]
    depth: int
    path_kind: str          # "main_path" | "branch"
    path_id: str
    path_index: int
    path_length: int
    path_progress: float    # 0.0 – 1.0 within its path
    difficulty_band: int    # 0 (easy) – 4 (hardest); derived from distance_from_start
    is_path_terminal: bool
    reward_tier: str
    is_exit: bool
    doors: dict[str, bool]
    distance_from_start: int
    distance_to_exit: int


@dataclass(frozen=True, slots=True)
class TopologyPlan:
    rooms: dict[tuple[int, int], TopologyRoom]
    main_path: tuple[tuple[int, int], ...]
    branch_paths: tuple[tuple[tuple[int, int], ...], ...]
    exit_pos: tuple[int, int]
    start_pos: tuple[int, int]


class TopologyPlanner:
    """Plan a connected room graph on a fixed N×N grid.

    Parameters
    ----------
    grid_size : int
        The N in the N×N grid.  The grid extends from −(N//2) to +(N//2)
        along each axis.
    min_distance : int
        Minimum Manhattan distance required between start and portal rooms.
    branch_count_range, branch_length_range, pacing_profile, rng
        Same semantics as the previous path-based planner.
    """

    def __init__(
        self,
        grid_size=7,
        min_distance=3,
        *,
        branch_count_range=None,
        branch_length_range=None,
        pacing_profile="balanced",
        rng=None,
    ):
        self._grid_size = grid_size
        self._radius = grid_size // 2
        self._min_distance = min_distance
        self._branch_count_range = branch_count_range
        self._branch_length_range = branch_length_range
        self._pacing_profile = pacing_profile
        self._rng = rng or random.Random()

    # ── public entry point ────────────────────────────────────────────────────

    def build(self):
        start_pos, portal_pos = self._pick_endpoints()
        main_path = self._walk_to_portal(start_pos, portal_pos)
        branch_paths = self._build_branch_paths(main_path)

        connections: dict[tuple, set] = {pos: set() for pos in main_path}
        for branch in branch_paths:
            for pos in branch:
                connections.setdefault(pos, set())
        self._link_path(main_path, connections)
        for branch in branch_paths:
            self._link_path(branch, connections)

        dist_start = self._bfs_distances(start_pos, connections)
        dist_exit = self._bfs_distances(portal_pos, connections)
        max_dist = max(dist_start.values()) if len(dist_start) > 1 else 1

        room_entries: dict[tuple, TopologyRoom] = {}
        main_path_length = len(main_path)

        for depth, pos in enumerate(main_path):
            path_progress = self._path_progress(depth, main_path_length)
            is_path_terminal = (depth == main_path_length - 1)
            d_s = dist_start.get(pos, 0)
            d_e = dist_exit.get(pos, 0)
            room_entries[pos] = TopologyRoom(
                position=pos,
                depth=depth,
                path_kind="main_path",
                path_id="main",
                path_index=depth,
                path_length=main_path_length,
                path_progress=path_progress,
                difficulty_band=self._difficulty_band(d_s, max_dist),
                is_path_terminal=is_path_terminal,
                reward_tier=self._reward_tier("main_path", is_path_terminal),
                is_exit=(pos == portal_pos),
                doors=self._door_map(pos, connections),
                distance_from_start=d_s,
                distance_to_exit=d_e,
            )

        for branch_index, branch_path in enumerate(branch_paths, start=1):
            anchor_depth = room_entries[branch_path[0]].depth
            branch_path_length = max(1, len(branch_path) - 1)
            for step, pos in enumerate(branch_path[1:], start=1):
                path_index = step - 1
                path_progress = self._path_progress(path_index, branch_path_length)
                is_path_terminal = (step == len(branch_path) - 1)
                d_s = dist_start.get(pos, 0)
                d_e = dist_exit.get(pos, 0)
                room_entries[pos] = TopologyRoom(
                    position=pos,
                    depth=anchor_depth + step,
                    path_kind="branch",
                    path_id=f"branch_{branch_index}",
                    path_index=path_index,
                    path_length=branch_path_length,
                    path_progress=path_progress,
                    difficulty_band=self._difficulty_band(d_s, max_dist),
                    is_path_terminal=is_path_terminal,
                    reward_tier=self._reward_tier("branch", is_path_terminal),
                    is_exit=False,
                    doors=self._door_map(pos, connections),
                    distance_from_start=d_s,
                    distance_to_exit=d_e,
                )

        return TopologyPlan(
            rooms=room_entries,
            main_path=tuple(main_path),
            branch_paths=tuple(tuple(b) for b in branch_paths),
            exit_pos=portal_pos,
            start_pos=start_pos,
        )

    # ── endpoint selection ────────────────────────────────────────────────────

    def _pick_endpoints(self):
        """Pick start and portal with at least min_distance Manhattan separation."""
        all_cells = [
            (x, y)
            for x in range(-self._radius, self._radius + 1)
            for y in range(-self._radius, self._radius + 1)
        ]
        self._rng.shuffle(all_cells)
        for start in all_cells:
            far_cells = [c for c in all_cells if _manhattan(start, c) >= self._min_distance]
            if far_cells:
                return start, self._rng.choice(far_cells)
        return (-self._radius, -self._radius), (self._radius, self._radius)

    # ── main path generation ──────────────────────────────────────────────────

    def _walk_to_portal(self, start, portal):
        """Biased random walk from start to portal; falls back to BFS."""
        for _ in range(12):
            path = self._attempt_biased_walk(start, portal)
            if path is not None:
                return path
        return self._bfs_path(start, portal)

    def _attempt_biased_walk(self, start, portal):
        """70 % greedy toward portal, 30 % random unvisited neighbour."""
        path = [start]
        visited = {start}
        cx, cy = start
        px, py = portal
        max_steps = (self._radius * 2 + 1) ** 2 * 3

        for _ in range(max_steps):
            if (cx, cy) == (px, py):
                return path
            candidates = []
            for direction in _ALL_DIRS:
                ox, oy = DIR_OFFSETS[direction]
                nx, ny = cx + ox, cy + oy
                if _in_bounds(nx, ny, self._radius) and (nx, ny) not in visited:
                    candidates.append((_manhattan((nx, ny), (px, py)), direction, nx, ny))
            if not candidates:
                return None
            candidates.sort()
            if self._rng.random() < 0.7:
                _, _, cx, cy = candidates[0]
            else:
                _, _, cx, cy = self._rng.choice(candidates)
            path.append((cx, cy))
            visited.add((cx, cy))
        return None

    def _bfs_path(self, start, goal):
        """Guaranteed BFS shortest path with shuffled neighbours for variety."""
        queue: deque[list] = deque([[start]])
        visited = {start}
        while queue:
            path = queue.popleft()
            if path[-1] == goal:
                return path
            cx, cy = path[-1]
            dirs = list(_ALL_DIRS)
            self._rng.shuffle(dirs)
            for direction in dirs:
                ox, oy = DIR_OFFSETS[direction]
                nx, ny = cx + ox, cy + oy
                if _in_bounds(nx, ny, self._radius) and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append(path + [(nx, ny)])
        return [start]

    # ── branch paths ──────────────────────────────────────────────────────────

    def _build_branch_paths(self, main_path):
        branch_count = self._choose_branch_count(len(main_path) - 1)
        if branch_count <= 0:
            return []
        visited = set(main_path)
        branch_paths = []
        for anchor_index in self._branch_anchor_indices_for_profile(
            len(main_path), branch_count, self._pacing_profile,
        ):
            anchor_pos = main_path[anchor_index]
            candidate_dirs = []
            for direction in _ALL_DIRS:
                ox, oy = DIR_OFFSETS[direction]
                neighbor = (anchor_pos[0] + ox, anchor_pos[1] + oy)
                if neighbor not in visited and _in_bounds(neighbor[0], neighbor[1], self._radius):
                    candidate_dirs.append(direction)
            self._rng.shuffle(candidate_dirs)
            for direction in candidate_dirs:
                branch_length = self._choose_branch_length(len(main_path) - 1)
                branch_path = [anchor_pos]
                bx, by = anchor_pos
                ox, oy = DIR_OFFSETS[direction]
                for _ in range(branch_length):
                    bx += ox
                    by += oy
                    if (bx, by) in visited or not _in_bounds(bx, by, self._radius):
                        break
                    branch_path.append((bx, by))
                if len(branch_path) > 1:
                    branch_paths.append(branch_path)
                    visited.update(branch_path[1:])
                    break
        return branch_paths

    def _choose_branch_count(self, path_length):
        if self._branch_count_range is None:
            return self._default_branch_count(path_length)
        low, high = self._branch_count_range
        return self._rng.randint(max(0, int(low)), max(int(low), int(high)))

    def _choose_branch_length(self, path_length):
        if self._branch_length_range is None:
            return 2 if path_length >= 8 else 1
        low, high = self._branch_length_range
        return self._rng.randint(max(1, int(low)), max(int(low), int(high)))

    @staticmethod
    def _default_branch_count(path_length):
        if path_length < 4:
            return 0
        if path_length < 7:
            return 1
        if path_length < 10:
            return 2
        return 3

    # ── metadata helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _path_progress(path_index, path_length):
        if path_length <= 1:
            return 1.0
        return path_index / (path_length - 1)

    @staticmethod
    def _difficulty_band(distance_from_start, max_distance):
        """Map BFS distance → band 0 (easy) … 4 (hardest)."""
        if max_distance == 0:
            return 4
        ratio = distance_from_start / max_distance
        return 4 if ratio >= 1.0 else min(3, int(ratio * 4))

    @staticmethod
    def _reward_tier(path_kind, is_path_terminal):
        if not is_path_terminal:
            return "standard"
        return "finale_bonus" if path_kind == "main_path" else "branch_bonus"

    @staticmethod
    def _bfs_distances(source, connections):
        distances = {source: 0}
        queue = deque([source])
        while queue:
            pos = queue.popleft()
            for neighbor in connections.get(pos, ()):
                if neighbor not in distances:
                    distances[neighbor] = distances[pos] + 1
                    queue.append(neighbor)
        return distances

    @staticmethod
    def _link_path(path, connections):
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            connections[a].add(b)
            connections[b].add(a)

    @staticmethod
    def _door_map(pos, connections):
        doors = {direction: False for direction in DIR_OFFSETS}
        for neighbor in connections.get(pos, ()):
            doors[_direction_between(pos, neighbor)] = True
        return doors

    @staticmethod
    def _branch_anchor_indices_for_profile(main_path_length, branch_count, pacing_profile):
        last_anchor = max(1, main_path_length - 2)
        if branch_count == 1:
            if pacing_profile == "backloaded":
                return (max(1, round(last_anchor * 0.7)),)
            if pacing_profile == "frontloaded":
                return (max(1, round(last_anchor * 0.35)),)
            return (max(1, last_anchor // 2),)
        indices = []
        for i in range(branch_count):
            frac = (i + 1) / (branch_count + 1)
            if pacing_profile == "frontloaded":
                frac *= 0.7
            elif pacing_profile == "backloaded":
                frac = 0.3 + frac * 0.7
            anchor = max(1, min(last_anchor, round(last_anchor * frac)))
            if anchor not in indices:
                indices.append(anchor)
        return tuple(indices)