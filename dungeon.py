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
from dungeon_topology import TopologyPlan, TopologyPlanner, TopologyRoom
from dungeon_config import get_difficulty_preset
from objective_entities import (
    AltarAnchor,
    EscortNPC,
    HoldoutStabilizer,
    HoldoutZone,
    PressurePlate,
    PuzzleStabilizer,
    RuneAltar,
    TrapCrusher,
    TrapLaneSwitch,
    TrapSafeSpot,
    TrapSweeper,
    TrapVentLane,
    TremorEmitter,
    VeinCrystal,
    SporeMushroom,
    CollapseEmitter,
    MiningCart,
    BurrowSpawner,
    Boulder,
    BoulderRunSpawner,
    ShrineGlyph,
    BossController,
)
from room_selector import RoomSelector


_ALL_DIRS = list(DIR_OFFSETS.keys())


def _in_bounds(x, y, radius=MAX_DUNGEON_RADIUS):
    return abs(x) <= radius and abs(y) <= radius


class Dungeon:
    """Manages the full dungeon graph of Room objects."""

    def __init__(self, dungeon_config=None, difficulty="default"):
        self.rooms: dict[tuple[int, int], Room] = {}
        self.room_plans = {}
        self.current_pos = (0, 0)

        # ── extract run config ──────────────────────────
        self._config = dungeon_config
        self._dungeon_id = dungeon_config["id"] if dungeon_config else None

        # Difficulty preset drives grid size and min distance (used in Phase 6 topology rewrite)
        preset = get_difficulty_preset(difficulty)
        self._grid_size = preset["grid_size"]        # future use: Phase 6 topology planner
        self._min_distance = preset["min_distance"]  # future use: Phase 6 topology planner
        # For now, derive path_length and radius using the existing planner conventions
        self._path_length = max(DEFAULT_PORTAL_DISTANCE, int(self._grid_size * 1.5))
        self._radius = max(MAX_DUNGEON_RADIUS, self._path_length + 2)

        if dungeon_config and "run_profile" in dungeon_config:
            profile = dungeon_config["run_profile"]
            self._terrain_type = dungeon_config["terrain_type"]
            self._enemy_count_range = profile["enemy_count_range"]
            self._enemy_type_weights = profile["enemy_type_weights"]
            self._branch_count_range = profile.get("branch_count_range")
            self._branch_length_range = profile.get("branch_length_range")
            self._pacing_profile = profile.get("pacing_profile", "balanced")
        else:
            self._terrain_type = None
            self._enemy_count_range = None
            self._enemy_type_weights = None
            self._branch_count_range = None
            self._branch_length_range = None
            self._pacing_profile = "balanced"
        self._room_depths: dict[tuple[int, int], int] = {}
        self._room_selector = RoomSelector(
            self._dungeon_id,
            self._terrain_type,
            self._enemy_count_range,
            self._enemy_type_weights,
        )
        self._topology_plan = TopologyPlanner(
            self._grid_size,
            self._min_distance,
            branch_count_range=self._branch_count_range,
            branch_length_range=self._branch_length_range,
            pacing_profile=self._pacing_profile,
        ).build()

        # pre-seed the planned topology
        self._exit_path = self._topology_plan.main_path
        self._exit_pos = self._topology_plan.exit_pos
        self.spawn_pos: tuple[int, int] = self._topology_plan.start_pos
        self.current_pos = self._topology_plan.start_pos

        for room_node in self._ordered_topology_rooms():
            self._room_depths[room_node.position] = room_node.depth
            self._create_room(
                room_node.position,
                fixed_doors=room_node.doors,
                is_exit=room_node.is_exit,
                depth=room_node.depth,
                path_kind=room_node.path_kind,
            )

        # track which rooms the player has visited (for minimap fog-of-war)
        self.visited: set[tuple[int, int]] = {self._topology_plan.start_pos}

        # runtime sprite groups (populated when entering a room)
        self._initialize_runtime_groups()

        # load starting room
        self._load_room_sprites()

    @classmethod
    def from_room_plan(cls, dungeon_id, room_plan, *, entry_direction=None):
        """Build a deterministic single-room dungeon for room-test mode.

        *entry_direction* ("left", "right", "top", or "bottom") opens a door
        on that wall so the room geometry is generated as if the player arrived
        from that direction in a real dungeon run.
        """
        dungeon = cls.__new__(cls)
        dungeon.rooms = {}
        dungeon.room_plans = {}
        dungeon.current_pos = (0, 0)

        dungeon._config = None
        dungeon._dungeon_id = dungeon_id
        dungeon._path_length = 1
        dungeon._terrain_type = room_plan.terrain_type
        dungeon._enemy_count_range = room_plan.enemy_count_range
        dungeon._enemy_type_weights = room_plan.enemy_type_weights
        dungeon._branch_count_range = None
        dungeon._branch_length_range = None
        dungeon._pacing_profile = "room_test"
        dungeon._radius = 1
        dungeon._room_depths = {(0, 0): room_plan.depth}
        dungeon._room_selector = None

        doors = {direction: False for direction in _ALL_DIRS}
        if entry_direction in doors:
            doors[entry_direction] = True

        topology_room = TopologyRoom(
            position=(0, 0),
            depth=room_plan.depth,
            path_kind=room_plan.path_kind,
            path_id=room_plan.path_id,
            path_index=room_plan.path_index,
            path_length=room_plan.path_length,
            path_progress=room_plan.path_progress,
            difficulty_band=room_plan.difficulty_band,
            is_path_terminal=room_plan.is_path_terminal,
            reward_tier=room_plan.reward_tier,
            is_exit=room_plan.is_exit,
            doors=doors,
            distance_from_start=0,
            distance_to_exit=0,
        )
        dungeon._topology_plan = TopologyPlan(
            rooms={(0, 0): topology_room},
            main_path=((0, 0),),
            branch_paths=(),
            exit_pos=(0, 0),
            start_pos=(0, 0),
        )
        dungeon._exit_path = dungeon._topology_plan.main_path
        dungeon._exit_pos = dungeon._topology_plan.exit_pos

        dungeon.rooms[(0, 0)] = Room(
            doors,
            is_exit=room_plan.is_exit,
            terrain_type=room_plan.terrain_type,
            enemy_count_range=room_plan.enemy_count_range,
            enemy_type_weights=room_plan.enemy_type_weights,
            room_plan=room_plan,
        )
        dungeon.room_plans[(0, 0)] = room_plan
        dungeon.visited = {(0, 0)}
        dungeon._initialize_runtime_groups()
        dungeon._load_room_sprites()
        return dungeon

    def _initialize_runtime_groups(self):
        self.enemy_group: pygame.sprite.Group = pygame.sprite.Group()
        self.item_group: pygame.sprite.Group = pygame.sprite.Group()
        self.chest_group: pygame.sprite.Group = pygame.sprite.Group()
        self.objective_group: pygame.sprite.Group = pygame.sprite.Group()
        self.hitbox_group: pygame.sprite.Group = pygame.sprite.Group()
        self.ally_group: pygame.sprite.Group = pygame.sprite.Group()
        # Telegraphed-attack secondary entities (rings + projectiles).
        self.enemy_projectile_group: pygame.sprite.Group = pygame.sprite.Group()
        self.pulsator_ring_group: pygame.sprite.Group = pygame.sprite.Group()
        # Mini-boss orchestrator for the current room. Populated by room
        # builders (e.g. earth_golem_arena) when a boss is present, then
        # cleared on room exit. Read by hud_view to surface the boss bar.
        self.boss_controller = None

    # ── public API ──────────────────────────────────────
    @property
    def current_room(self) -> Room:
        return self.rooms[self.current_pos]

    @property
    def exit_pos(self):
        return self._exit_pos

    def minimap_snapshot(self, now_ticks=None):
        """Return minimap-ready room state for HUD projection."""
        rooms = []
        for pos in sorted(self.visited):
            room = self.rooms[pos]
            if pos == self._exit_pos and not room._portal_active:
                kind = "objective"
            elif pos == self.current_pos:
                kind = "current"
            elif pos == self._exit_pos:
                kind = "exit"
            else:
                kind = "visited"

            objective_marker = None
            objective_status = None
            if pos == self.current_pos and hasattr(room, "minimap_objective_marker"):
                objective_marker = room.minimap_objective_marker()
                if objective_marker is not None and hasattr(room, "minimap_objective_status"):
                    objective_status = room.minimap_objective_status(now_ticks)
            rooms.append(
                {
                    "pos": pos,
                    "kind": kind,
                    "path_kind": self._topology_plan.rooms[pos].path_kind,
                    "objective_marker": objective_marker,
                    "objective_status": objective_status,
                    "door_kinds": {
                        direction: self.door_kind(pos, direction)
                        for direction in _ALL_DIRS
                    },
                }
            )
        return {"radius": self._radius, "rooms": rooms}

    def door_kind(self, pos, direction):
        """Return door kind on a room wall: 'none', 'sealed', 'two_way', or 'one_way'."""
        room = self.rooms.get(pos)
        if room is None or not room.doors.get(direction):
            return "none"
        if getattr(room, "doors_sealed", False):
            return "sealed"

        ox, oy = DIR_OFFSETS[direction]
        neighbor_pos = (pos[0] + ox, pos[1] + oy)
        neighbor = self.rooms.get(neighbor_pos)
        if neighbor is None:
            # Unknown room will be generated with reciprocal door on entry.
            return "two_way"

        opposite = OPPOSITE_DIR[direction]
        if neighbor.doors.get(opposite):
            return "two_way"
        return "one_way"

    def current_room_door_kinds(self):
        """Return {direction: kind} for the current room."""
        return {
            direction: self.door_kind(self.current_pos, direction)
            for direction in _ALL_DIRS
        }

    def try_transition(self, player_rect):
        """Check if the player has stepped through a door.

        Returns the direction string if a transition happened, else None.
        """
        room = self.current_room
        if getattr(room, "doors_sealed", False):
            return None
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
            planned_room = self._topology_plan.rooms.get((nx, ny))
            if planned_room is None:
                return None
            self._room_depths[(nx, ny)] = planned_room.depth
            self._create_room(
                planned_room.position,
                fixed_doors=planned_room.doors,
                is_exit=planned_room.is_exit,
                depth=planned_room.depth,
                path_kind=planned_room.path_kind,
            )

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

    def _ordered_topology_rooms(self):
        return sorted(
            self._topology_plan.rooms.values(),
            key=lambda room: (
                room.depth,
                0 if room.path_kind == "main_path" else 1,
                room.position[1],
                room.position[0],
            ),
        )

    # ── room creation / generation ──────────────────────
    def _create_room(
        self,
        pos,
        forced_doors=None,
        fixed_doors=None,
        is_exit=False,
        depth=0,
        path_kind="main_path",
    ):
        if fixed_doors is not None:
            doors = dict(fixed_doors)
        else:
            doors = self._random_doors(pos, forced_doors)
        topology_room = self._topology_plan.rooms.get(pos)
        if (
            topology_room is not None
            and topology_room.is_boss_slot
            and self._room_selector is not None
        ):
            # Second-to-last main-path position: always use a boss template.
            # build_boss_room_plan picks randomly from all enabled "boss"
            # topology-role templates so future bosses can be added without
            # changing this wiring.
            room_plan = self._room_selector.build_boss_room_plan(
                pos,
                depth,
                path_kind,
                path_id=topology_room.path_id,
                path_index=topology_room.path_index,
                path_length=topology_room.path_length,
                path_progress=topology_room.path_progress,
                difficulty_band=topology_room.difficulty_band,
            )
        else:
            room_plan = self._room_selector.build_room_plan(
                pos,
                depth,
                path_kind,
                is_exit=is_exit,
                path_id=topology_room.path_id if topology_room is not None else None,
                path_index=topology_room.path_index if topology_room is not None else None,
                path_length=topology_room.path_length if topology_room is not None else None,
                path_progress=topology_room.path_progress if topology_room is not None else None,
                difficulty_band=topology_room.difficulty_band if topology_room is not None else None,
                is_path_terminal=topology_room.is_path_terminal if topology_room is not None else False,
                reward_tier=topology_room.reward_tier if topology_room is not None else "standard",
            )
        room = Room(
            doors,
            is_exit=is_exit,
            terrain_type=self._terrain_type,
            enemy_count_range=self._enemy_count_range,
            enemy_type_weights=self._enemy_type_weights,
            room_plan=room_plan,
        )
        self.rooms[pos] = room
        self.room_plans[pos] = room_plan
        return room

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
        self.objective_group.empty()
        self.hitbox_group.empty()
        self.ally_group.empty()
        if hasattr(self, "enemy_projectile_group"):
            self.enemy_projectile_group.empty()
        if hasattr(self, "pulsator_ring_group"):
            self.pulsator_ring_group.empty()
        self.boss_controller = None

        room = self.current_room
        # Phase 1 biome-room infra: per-room buffs / hazard timers do not
        # persist across room transitions.
        if hasattr(room, "reset_room_buffs"):
            room.reset_room_buffs()

        # enemies: skip if already cleared this run
        if not room.enemies_cleared:
            frozen = bool(getattr(room, "frozen_enemies", False))
            attacks_enabled = bool(getattr(room, "enemy_attacks_enabled", True))
            for cls, (px, py) in room.enemy_configs:
                enemy = cls(px, py, is_frozen=frozen)
                enemy.attacks_disabled = not attacks_enabled
                self.enemy_group.add(enemy)

        # chest
        if room.chest_pos:
            chest = Chest(room.chest_pos[0], room.chest_pos[1],
                          looted=room.chest_looted,
                          reward_tier=room.chest_reward_tier() if hasattr(room, "chest_reward_tier") else (room.room_plan.reward_tier if room.room_plan else "standard"),
                          reward_kind=room.chest_reward_kind() if hasattr(room, "chest_reward_kind") else "chest_upgrade")
            self.chest_group.add(chest)

        for config in room.objective_entity_configs:
            if config["kind"] == "altar" and not config["destroyed"]:
                self.objective_group.add(AltarAnchor(config))
            elif config["kind"] == "holdout_zone":
                self.objective_group.add(HoldoutZone(config))
            elif config["kind"] == "holdout_stabilizer":
                self.objective_group.add(HoldoutStabilizer(config))
            elif config["kind"] == "pressure_plate":
                self.objective_group.add(PressurePlate(config))
            elif config["kind"] == "puzzle_stabilizer" and not config.get("destroyed"):
                self.objective_group.add(PuzzleStabilizer(config))
            elif config["kind"] == "alarm_beacon":
                from enemies import SentryEnemy
                pos = config["pos"]
                self.enemy_group.add(SentryEnemy(
                    pos[0], pos[1],
                    patrol_points=config.get("patrol_points"),
                    alarm_config=config,
                ))
            elif config["kind"] == "sentry_blocker":
                from objective_entities import SentryBlocker
                pos = config["pos"]
                self.objective_group.add(SentryBlocker(pos[0], pos[1]))
            elif config["kind"] == "escort_npc" and not config["destroyed"]:
                self.objective_group.add(EscortNPC(config))
            elif config["kind"] == "trap_lane_switch":
                self.objective_group.add(TrapLaneSwitch(config))
            elif config["kind"] == "trap_sweeper":
                self.objective_group.add(TrapSweeper(config))
            elif config["kind"] == "trap_vent_lane":
                self.objective_group.add(TrapVentLane(config))
            elif config["kind"] == "trap_crusher":
                self.objective_group.add(TrapCrusher(config))
            elif config["kind"] == "trap_safe_spot":
                self.objective_group.add(TrapSafeSpot(config))
            elif config["kind"] == "rune_altar" and not config.get("consumed"):
                self.objective_group.add(RuneAltar(config))
            elif config["kind"] == "vein_crystal" and not config.get("destroyed"):
                self.objective_group.add(VeinCrystal(config))
            elif config["kind"] == "tremor_emitter":
                self.objective_group.add(TremorEmitter(config))
            elif config["kind"] == "spore_mushroom" and not config.get("destroyed"):
                self.objective_group.add(SporeMushroom(config))
            elif config["kind"] == "collapse_emitter":
                self.objective_group.add(CollapseEmitter(config))
            elif config["kind"] == "mining_cart":
                self.objective_group.add(MiningCart(config))
            elif config["kind"] == "burrow_spawner":
                self.objective_group.add(BurrowSpawner(config))
            elif config["kind"] == "boulder":
                self.objective_group.add(Boulder(config))
            elif config["kind"] == "boulder_run_spawner":
                spawner = BoulderRunSpawner(config)
                # Spawner needs a live group reference so it can drop
                # freshly spawned boulders straight into the scene.
                spawner.objective_group = self.objective_group
                self.objective_group.add(spawner)
            elif config["kind"] == "shrine_glyph":
                self.objective_group.add(ShrineGlyph(config))
            elif config["kind"] == "ice_pillar":
                from objective_entities import IcePillar
                self.objective_group.add(IcePillar(config["x"], config["y"]))
            elif config["kind"] == "golem_arena_controller":
                # Locate the Golem we just spawned via enemy_configs and
                # wrap it in a BossController.  Wave thresholds default
                # to 0.75 / 0.5 / 0.25 — the same keys as wave_specs so
                # rpg.py can map ``new_waves`` straight to shard counts.
                from enemies import Golem
                boss = next(
                    (e for e in self.enemy_group if isinstance(e, Golem)),
                    None,
                )
                if boss is not None:
                    self.boss_controller = BossController(
                        boss, name="Stone Golem",
                    )
                    # Stash the room's golem-arena config so rpg.py can
                    # read wave_specs / shard_spawn_radius / loot_granted.
                    self.boss_controller.arena_config = config
                    # Seal the exit portal until the boss falls; the
                    # ``clear_enemies`` rule will unseal it once the
                    # Golem and all spawned shards are dead.
                    if hasattr(self.current_room, "_set_portal_active"):
                        self.current_room._set_portal_active(False)
                    # Fire the one-shot intro banner so the player gets
                    # the same encounter-start cue as keystone bonuses.
                    import damage_feedback
                    damage_feedback.report_boss_intro(self.boss_controller.name)
            elif config["kind"] == "tide_lord_arena_controller":
                from enemies import TideLord
                boss = next(
                    (e for e in self.enemy_group if isinstance(e, TideLord)),
                    None,
                )
                if boss is not None:
                    self.boss_controller = BossController(
                        boss, name="Tide Lord",
                    )
                    self.boss_controller.arena_config = config
                    if hasattr(self.current_room, "_set_portal_active"):
                        self.current_room._set_portal_active(False)
                    import damage_feedback
                    damage_feedback.report_boss_intro(self.boss_controller.name)
            elif config["kind"] == "frost_witch_arena_controller":
                from enemies import FrostWitch
                boss = next(
                    (e for e in self.enemy_group if isinstance(e, FrostWitch)),
                    None,
                )
                if boss is not None:
                    self.boss_controller = BossController(
                        boss, name="Frost Witch",
                    )
                    self.boss_controller.arena_config = config
                    if hasattr(self.current_room, "_set_portal_active"):
                        self.current_room._set_portal_active(False)
                    import damage_feedback
                    damage_feedback.report_boss_intro(self.boss_controller.name)

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
