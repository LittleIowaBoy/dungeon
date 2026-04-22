"""Topology planning for dungeon room graphs."""

from dataclasses import dataclass
import random

from settings import DIR_OFFSETS, OPPOSITE_DIR


_ALL_DIRS = tuple(DIR_OFFSETS)


def _in_bounds(x, y, radius):
    return abs(x) <= radius and abs(y) <= radius


def _orthogonal_dirs(direction):
    if direction in {"top", "bottom"}:
        return ("left", "right")
    return ("top", "bottom")


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
    path_kind: str
    path_id: str
    path_index: int
    path_length: int
    path_progress: float
    difficulty_band: int
    is_path_terminal: bool
    reward_tier: str
    is_exit: bool
    doors: dict[str, bool]


@dataclass(frozen=True, slots=True)
class TopologyPlan:
    rooms: dict[tuple[int, int], TopologyRoom]
    main_path: tuple[tuple[int, int], ...]
    branch_paths: tuple[tuple[tuple[int, int], ...], ...]
    exit_pos: tuple[int, int]


class TopologyPlanner:
    """Plan a shaped main path with optional branch stubs."""

    def __init__(
        self,
        path_length,
        radius,
        *,
        branch_count_range=None,
        branch_length_range=None,
        pacing_profile="balanced",
        rng=None,
    ):
        self._path_length = path_length
        self._radius = radius
        self._branch_count_range = branch_count_range
        self._branch_length_range = branch_length_range
        self._pacing_profile = pacing_profile
        self._rng = rng or random.Random()

    def build(self):
        main_path = self._build_main_path()
        branch_paths = self._build_branch_paths(main_path)

        room_entries = {}
        connections = {pos: set() for pos in main_path}

        self._link_path(main_path, connections)
        for branch_path in branch_paths:
            for pos in branch_path:
                connections.setdefault(pos, set())
            self._link_path(branch_path, connections)

        main_path_length = len(main_path)
        for depth, pos in enumerate(main_path):
            path_progress = self._path_progress(depth, main_path_length)
            is_path_terminal = depth == main_path_length - 1
            room_entries[pos] = TopologyRoom(
                position=pos,
                depth=depth,
                path_kind="main_path",
                path_id="main",
                path_index=depth,
                path_length=main_path_length,
                path_progress=path_progress,
                difficulty_band=self._difficulty_band(path_progress, is_path_terminal),
                is_path_terminal=is_path_terminal,
                reward_tier=self._reward_tier("main_path", is_path_terminal),
                is_exit=(pos == main_path[-1]),
                doors=self._door_map(pos, connections),
            )

        for branch_index, branch_path in enumerate(branch_paths, start=1):
            anchor_depth = room_entries[branch_path[0]].depth
            branch_path_length = max(1, len(branch_path) - 1)
            for step, pos in enumerate(branch_path[1:], start=1):
                path_index = step - 1
                path_progress = self._path_progress(path_index, branch_path_length)
                is_path_terminal = step == len(branch_path) - 1
                room_entries[pos] = TopologyRoom(
                    position=pos,
                    depth=anchor_depth + step,
                    path_kind="branch",
                    path_id=f"branch_{branch_index}",
                    path_index=path_index,
                    path_length=branch_path_length,
                    path_progress=path_progress,
                    difficulty_band=self._difficulty_band(path_progress, is_path_terminal),
                    is_path_terminal=is_path_terminal,
                    reward_tier=self._reward_tier("branch", is_path_terminal),
                    is_exit=False,
                    doors=self._door_map(pos, connections),
                )

        return TopologyPlan(
            rooms=room_entries,
            main_path=tuple(main_path),
            branch_paths=tuple(tuple(path) for path in branch_paths),
            exit_pos=main_path[-1],
        )

    @staticmethod
    def _path_progress(path_index, path_length):
        if path_length <= 1:
            return 1.0
        return path_index / (path_length - 1)

    @staticmethod
    def _difficulty_band(path_progress, is_path_terminal):
        if is_path_terminal:
            return 4
        return min(3, int(path_progress * 4))

    @staticmethod
    def _reward_tier(path_kind, is_path_terminal):
        if not is_path_terminal:
            return "standard"
        if path_kind == "main_path":
            return "finale_bonus"
        return "branch_bonus"

    def _build_main_path(self):
        if self._path_length <= 0:
            return [(0, 0)]

        segments = self._segment_lengths(self._path_length)
        first_directions = list(_ALL_DIRS)
        self._rng.shuffle(first_directions)

        for first_direction in first_directions:
            second_directions = list(_orthogonal_dirs(first_direction))
            self._rng.shuffle(second_directions)

            if len(segments) == 1:
                path = self._trace_segments(((first_direction, segments[0]),))
                if path:
                    return path
                continue

            for second_direction in second_directions:
                if len(segments) == 2:
                    path = self._trace_segments(
                        (
                            (first_direction, segments[0]),
                            (second_direction, segments[1]),
                        )
                    )
                    if path:
                        return path
                    continue

                third_directions = [first_direction, OPPOSITE_DIR[first_direction]]
                self._rng.shuffle(third_directions)
                for third_direction in third_directions:
                    path = self._trace_segments(
                        (
                            (first_direction, segments[0]),
                            (second_direction, segments[1]),
                            (third_direction, segments[2]),
                        )
                    )
                    if path:
                        return path

        return self._fallback_walk()

    def _trace_segments(self, segments):
        path = [(0, 0)]
        visited = {(0, 0)}
        x, y = 0, 0

        for direction, length in segments:
            ox, oy = DIR_OFFSETS[direction]
            for _ in range(length):
                x += ox
                y += oy
                if not _in_bounds(x, y, self._radius) or (x, y) in visited:
                    return None
                path.append((x, y))
                visited.add((x, y))

        return path

    def _fallback_walk(self):
        path = [(0, 0)]
        visited = {(0, 0)}
        cx, cy = 0, 0
        current_direction = self._rng.choice(_ALL_DIRS)

        for step in range(self._path_length):
            candidates = []
            ordered = [current_direction, *_orthogonal_dirs(current_direction), OPPOSITE_DIR[current_direction]]
            for direction in ordered:
                ox, oy = DIR_OFFSETS[direction]
                nx, ny = cx + ox, cy + oy
                if _in_bounds(nx, ny, self._radius) and (nx, ny) not in visited:
                    score = 2 if direction == current_direction else 1
                    if step in self._turn_depths() and direction != current_direction:
                        score += 1
                    candidates.append((score, direction, nx, ny))
            if not candidates:
                break
            best_score = max(score for score, *_rest in candidates)
            best = [entry for entry in candidates if entry[0] == best_score]
            _, current_direction, cx, cy = self._rng.choice(best)
            path.append((cx, cy))
            visited.add((cx, cy))

        return path

    def _build_branch_paths(self, main_path):
        branch_count = self._choose_branch_count(len(main_path) - 1)
        if branch_count <= 0:
            return []

        visited = set(main_path)
        branch_paths = []
        for anchor_index in self._branch_anchor_indices_for_profile(
            len(main_path),
            branch_count,
            self._pacing_profile,
        ):
            anchor_pos = main_path[anchor_index]
            candidate_dirs = []
            for direction in _ALL_DIRS:
                ox, oy = DIR_OFFSETS[direction]
                neighbor = (anchor_pos[0] + ox, anchor_pos[1] + oy)
                if neighbor in visited or not _in_bounds(neighbor[0], neighbor[1], self._radius):
                    continue
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
            return self._branch_count(path_length)

        low, high = self._branch_count_range
        low = max(0, int(low))
        high = max(low, int(high))
        return self._rng.randint(low, high)

    def _choose_branch_length(self, path_length):
        if self._branch_length_range is None:
            return 2 if path_length >= 8 else 1

        low, high = self._branch_length_range
        low = max(1, int(low))
        high = max(low, int(high))
        return self._rng.randint(low, high)

    @staticmethod
    def _link_path(path, connections):
        for index in range(len(path) - 1):
            start = path[index]
            end = path[index + 1]
            connections[start].add(end)
            connections[end].add(start)

    @staticmethod
    def _door_map(pos, connections):
        doors = {direction: False for direction in DIR_OFFSETS}
        for neighbor in connections[pos]:
            direction = _direction_between(pos, neighbor)
            doors[direction] = True
        return doors

    def _segment_lengths(self, path_length):
        if path_length <= 3:
            return (path_length,)
        if path_length <= 7:
            first = max(2, path_length // 2)
            return first, path_length - first

        first = max(2, path_length // 3)
        second = max(2, (path_length - first) // 2)
        third = path_length - first - second
        if third <= 0:
            return first, path_length - first
        return first, second, third

    def _turn_depths(self):
        if self._path_length < 4:
            return set()
        if self._path_length < 8:
            return {max(1, self._path_length // 2)}
        return {
            max(1, self._path_length // 3),
            max(2, (self._path_length * 2) // 3),
        }

    @staticmethod
    def _branch_count(path_length):
        if path_length < 4:
            return 0
        if path_length < 7:
            return 1
        if path_length < 10:
            return 2
        return 3

    @staticmethod
    def _branch_anchor_indices(main_path_length, branch_count):
        return TopologyPlanner._branch_anchor_indices_for_profile(
            main_path_length,
            branch_count,
            "balanced",
        )

    @staticmethod
    def _branch_anchor_indices_for_profile(main_path_length, branch_count, pacing_profile):
        last_anchor = max(1, main_path_length - 2)
        if branch_count == 1:
            if pacing_profile == "backloaded":
                return (max(1, round(last_anchor * 0.7)),)
            if pacing_profile == "frontloaded":
                return (max(1, round(last_anchor * 0.35)),)
            return (max(1, main_path_length // 2),)

        indices = []
        for branch_index in range(branch_count):
            fraction = (branch_index + 1) / (branch_count + 1)
            if pacing_profile == "frontloaded":
                fraction *= 0.7
            elif pacing_profile == "backloaded":
                fraction = 0.3 + (fraction * 0.7)
            anchor = round(last_anchor * fraction)
            anchor = max(1, min(last_anchor, anchor))
            if anchor not in indices:
                indices.append(anchor)
        return tuple(indices)