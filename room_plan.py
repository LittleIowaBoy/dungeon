"""Room templates and concrete room plans for dungeon generation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoomTemplate:
    room_id: str
    display_name: str
    objective_kind: str
    combat_pressure: str
    decision_complexity: str
    topology_role: str
    min_depth: int = 0
    max_depth: int | None = None
    branch_preference: str = "either"
    generation_weight: int = 1
    enabled: bool = True
    implementation_status: str = "planned"
    objective_variant: str = ""
    path_stage_min: int = 0
    path_stage_max: int = 4
    terminal_preference: str = "any"
    repeat_cooldown: int = 0
    reward_affinity: str = "any"
    objective_rule: str = "immediate"
    objective_duration_ms: int | None = None
    enemy_minimum_bonus: int = 0
    enemy_scale_factor: float = 1.0
    guaranteed_chest: bool = False
    chest_spawn_chance: float | None = None
    terrain_patch_count_range: str = ""
    terrain_patch_size_range: str = ""
    clear_center: bool = False
    terminal_chest_lock: bool = False
    objective_entity_count: int = 0
    scripted_wave_sizes: str = ""
    holdout_zone_radius: int = 0
    holdout_zone_min_radius: int = 0
    holdout_zone_shrink_ms: int = 0
    holdout_zone_migrate_ms: int = 0
    holdout_zone_migration_offsets: str = ""
    holdout_relief_count: int = 0
    holdout_relief_delay_ms: int = 0
    holdout_stabilizer_migration_delay_ms: int = 0
    ritual_role_script: str = ""
    ritual_reinforcement_count: int = 0
    ritual_link_mode: str = ""
    ritual_payoff_kind: str = ""
    ritual_payoff_label: str = ""
    ritual_wrong_strike_spawn_count: int = 0
    ritual_tether_regen_ms: int = 0
    ritual_tether_regen_hp: int = 0
    resource_race_rival_label: str = ""
    resource_race_reclaim_window_ms: int = 0
    objective_label: str = ""
    objective_layout_offsets: str = ""
    objective_spawn_offset: str = ""
    objective_patrol_offset: str = ""
    objective_patrol_shape: str = "line"
    objective_radius: int = 0
    objective_trigger_padding: int = 0
    objective_max_hp: int = 0
    objective_move_speed: float = 0.0
    objective_guide_radius: int = 0
    objective_exit_radius: int = 0
    objective_damage_cooldown_ms: int = 0
    escort_checkpoints: str = ""
    escort_blast_points: str = ""
    escort_blast_duration_ms: int = 0
    escort_blast_radius: int = 0
    escort_blast_damage: int = 0
    escort_carrier_stall_interval_ms: int = 0
    escort_carrier_stall_duration_ms: int = 0
    escort_harasser_count: int = 0
    escort_stagger_interval_ms: int = 0
    escort_stagger_duration_ms: int = 0
    escort_hazard_interval_ms: int = 0
    escort_hazard_damage: int = 0
    puzzle_reinforcement_count: int = 0
    puzzle_stall_duration_ms: int = 0
    puzzle_stabilizer_count: int = 0
    puzzle_stabilizer_hp: int = 0
    puzzle_camp_pulse_damage: int = 0
    puzzle_camp_pulse_interval_ms: int = 0
    puzzle_camp_pulse_grace_ms: int = 0
    puzzle_camp_pulse_radius: int = 0
    puzzle_decay_interval_ms: int = 0
    trap_intensity_scale: float = 1.0
    trap_speed_scale: float = 1.0
    trap_challenge_reward_kind: str = "chest_upgrade"
    trap_suppress_duration_ms: int = 2500
    trap_suppress_cooldown_ms: int = 8000
    trap_safespot_speed_mult: float = 1.0
    trap_sweeper_knockback_px: int = 0
    trap_vent_chilled_duration_ms: int = 0
    trap_surge_interval_ms: int = 0
    trap_surge_duration_ms: int = 0
    collapse_terrain_effect: str = ""
    notes: str = ""
    # Terrain layout system (terrain_layouts.py).
    terrain_layout: str = ""
    allow_terrain_accent: bool = True
    min_rows: int = 0
    min_cols: int = 0

    @classmethod
    def from_mapping(cls, row):
        return cls(
            room_id=row["room_id"],
            display_name=row["display_name"],
            objective_kind=row["objective_kind"],
            combat_pressure=row["combat_pressure"],
            decision_complexity=row["decision_complexity"],
            topology_role=row["topology_role"],
            min_depth=row["min_depth"],
            max_depth=row["max_depth"],
            branch_preference=row["branch_preference"],
            generation_weight=row["generation_weight"],
            enabled=bool(row["enabled"]),
            implementation_status=row["implementation_status"],
            objective_variant=row.get("objective_variant", ""),
            path_stage_min=row.get("path_stage_min", 0),
            path_stage_max=row.get("path_stage_max", 4),
            terminal_preference=row.get("terminal_preference", "any"),
            repeat_cooldown=row.get("repeat_cooldown", 0),
            reward_affinity=row.get("reward_affinity", "any"),
            objective_rule=row.get("objective_rule", "immediate"),
            objective_duration_ms=row.get("objective_duration_ms"),
            enemy_minimum_bonus=row.get("enemy_minimum_bonus", 0),
            enemy_scale_factor=row.get("enemy_scale_factor", 1.0),
            guaranteed_chest=bool(row.get("guaranteed_chest", False)),
            chest_spawn_chance=row.get("chest_spawn_chance"),
            terrain_patch_count_range=row.get("terrain_patch_count_range", ""),
            terrain_patch_size_range=row.get("terrain_patch_size_range", ""),
            clear_center=bool(row.get("clear_center", False)),
            terminal_chest_lock=bool(row.get("terminal_chest_lock", False)),
            objective_entity_count=row.get("objective_entity_count", 0),
            scripted_wave_sizes=row.get("scripted_wave_sizes", ""),
            holdout_zone_radius=row.get("holdout_zone_radius", 0),
            holdout_zone_min_radius=row.get("holdout_zone_min_radius", 0),
            holdout_zone_shrink_ms=row.get("holdout_zone_shrink_ms", 0),
            holdout_zone_migrate_ms=row.get("holdout_zone_migrate_ms", 0),
            holdout_zone_migration_offsets=row.get("holdout_zone_migration_offsets", ""),
            holdout_relief_count=row.get("holdout_relief_count", 0),
            holdout_relief_delay_ms=row.get("holdout_relief_delay_ms", 0),
            holdout_stabilizer_migration_delay_ms=row.get("holdout_stabilizer_migration_delay_ms", 0),
            ritual_role_script=row.get("ritual_role_script", ""),
            ritual_reinforcement_count=row.get("ritual_reinforcement_count", 0),
            ritual_link_mode=row.get("ritual_link_mode", ""),
            ritual_payoff_kind=row.get("ritual_payoff_kind", ""),
            ritual_payoff_label=row.get("ritual_payoff_label", ""),
            ritual_wrong_strike_spawn_count=row.get("ritual_wrong_strike_spawn_count", 0),
            ritual_tether_regen_ms=row.get("ritual_tether_regen_ms", 0),
            ritual_tether_regen_hp=row.get("ritual_tether_regen_hp", 0),
            resource_race_rival_label=row.get("resource_race_rival_label", ""),
            resource_race_reclaim_window_ms=row.get("resource_race_reclaim_window_ms", 0),
            objective_label=row.get("objective_label", ""),
            objective_layout_offsets=row.get("objective_layout_offsets", ""),
            objective_spawn_offset=row.get("objective_spawn_offset", ""),
            objective_patrol_offset=row.get("objective_patrol_offset", ""),
            objective_patrol_shape=row.get("objective_patrol_shape", "line") or "line",
            objective_radius=row.get("objective_radius", 0),
            objective_trigger_padding=row.get("objective_trigger_padding", 0),
            objective_max_hp=row.get("objective_max_hp", 0),
            objective_move_speed=row.get("objective_move_speed", 0.0),
            objective_guide_radius=row.get("objective_guide_radius", 0),
            objective_exit_radius=row.get("objective_exit_radius", 0),
            objective_damage_cooldown_ms=row.get("objective_damage_cooldown_ms", 0),
            escort_checkpoints=row.get("escort_checkpoints", "") or "",
            escort_blast_points=row.get("escort_blast_points", "") or "",
            escort_blast_duration_ms=row.get("escort_blast_duration_ms", 0),
            escort_blast_radius=row.get("escort_blast_radius", 0),
            escort_blast_damage=row.get("escort_blast_damage", 0),
            escort_carrier_stall_interval_ms=row.get("escort_carrier_stall_interval_ms", 0),
            escort_carrier_stall_duration_ms=row.get("escort_carrier_stall_duration_ms", 0),
            escort_harasser_count=row.get("escort_harasser_count", 0),
            escort_stagger_interval_ms=row.get("escort_stagger_interval_ms", 0),
            escort_stagger_duration_ms=row.get("escort_stagger_duration_ms", 0),
            escort_hazard_interval_ms=row.get("escort_hazard_interval_ms", 0),
            escort_hazard_damage=row.get("escort_hazard_damage", 0),
            puzzle_reinforcement_count=row.get("puzzle_reinforcement_count", 0),
            puzzle_stall_duration_ms=row.get("puzzle_stall_duration_ms", 0),
            puzzle_stabilizer_count=row.get("puzzle_stabilizer_count", 0),
            puzzle_stabilizer_hp=row.get("puzzle_stabilizer_hp", 0),
            puzzle_camp_pulse_damage=row.get("puzzle_camp_pulse_damage", 0),
            puzzle_camp_pulse_interval_ms=row.get("puzzle_camp_pulse_interval_ms", 0),
            puzzle_camp_pulse_grace_ms=row.get("puzzle_camp_pulse_grace_ms", 0),
            puzzle_camp_pulse_radius=row.get("puzzle_camp_pulse_radius", 0),
            puzzle_decay_interval_ms=row.get("puzzle_decay_interval_ms", 0),
            trap_intensity_scale=row.get("trap_intensity_scale", 1.0),
            trap_speed_scale=row.get("trap_speed_scale", 1.0),
            trap_challenge_reward_kind=row.get("trap_challenge_reward_kind", "chest_upgrade"),
            trap_suppress_duration_ms=row.get("trap_suppress_duration_ms", 2500),
            trap_suppress_cooldown_ms=row.get("trap_suppress_cooldown_ms", 8000),
            trap_safespot_speed_mult=row.get("trap_safespot_speed_mult", 1.0),
            trap_sweeper_knockback_px=row.get("trap_sweeper_knockback_px", 0),
            trap_vent_chilled_duration_ms=row.get("trap_vent_chilled_duration_ms", 0),
            trap_surge_interval_ms=row.get("trap_surge_interval_ms", 0),
            trap_surge_duration_ms=row.get("trap_surge_duration_ms", 0),
            collapse_terrain_effect=row.get("collapse_terrain_effect", "") or "",
            notes=row["notes"],
            terrain_layout=row.get("terrain_layout", "") or "",
            allow_terrain_accent=bool(row.get("allow_terrain_accent", True)),
            min_rows=row.get("min_rows", 0) or 0,
            min_cols=row.get("min_cols", 0) or 0,
        )


@dataclass(frozen=True, slots=True)
class RoomPlan:
    position: tuple[int, int]
    depth: int
    path_kind: str
    is_exit: bool
    template: RoomTemplate
    terrain_type: str | None
    enemy_count_range: tuple[int, int] | None
    enemy_type_weights: tuple[int, ...] | None
    objective_rule: str
    objective_duration_ms: int | None = None
    guaranteed_chest: bool = False
    chest_spawn_chance: float | None = None
    terrain_patch_count_range: tuple[int, int] | None = None
    terrain_patch_size_range: tuple[int, int] | None = None
    clear_center: bool = False
    path_id: str = "main"
    path_index: int = 0
    path_length: int = 1
    path_progress: float = 0.0
    difficulty_band: int = 0
    is_path_terminal: bool = False
    reward_tier: str = "standard"
    chest_locked_until_complete: bool = False
    objective_entity_count: int = 0
    scripted_wave_sizes: tuple[int, ...] = ()
    holdout_zone_radius: int = 0
    holdout_zone_min_radius: int = 0
    holdout_zone_shrink_ms: int = 0
    holdout_zone_migrate_ms: int = 0
    holdout_zone_migration_offsets: tuple[tuple[int, int], ...] = ()
    holdout_relief_count: int = 0
    holdout_relief_delay_ms: int = 0
    holdout_stabilizer_migration_delay_ms: int = 0
    ritual_role_script: tuple[str, ...] = ()
    ritual_reinforcement_count: int = 0
    ritual_link_mode: str = ""
    ritual_payoff_kind: str = ""
    ritual_payoff_label: str = ""
    ritual_wrong_strike_spawn_count: int = 0
    ritual_tether_regen_ms: int = 0
    ritual_tether_regen_hp: int = 0
    resource_race_rival_label: str = ""
    resource_race_reclaim_window_ms: int = 0
    objective_label: str = ""
    objective_layout_offsets: tuple[tuple[int, int], ...] = ()
    objective_spawn_offset: tuple[int, int] | None = None
    objective_patrol_offset: tuple[int, int] | None = None
    objective_patrol_shape: str = "line"
    objective_radius: int = 0
    objective_trigger_padding: int = 0
    objective_max_hp: int = 0
    objective_move_speed: float = 0.0
    objective_guide_radius: int = 0
    objective_exit_radius: int = 0
    objective_damage_cooldown_ms: int = 0
    escort_checkpoints: tuple[tuple[int, int], ...] = ()
    escort_blast_points: tuple[tuple[int, int], ...] = ()
    escort_blast_duration_ms: int = 0
    escort_blast_radius: int = 0
    escort_blast_damage: int = 0
    escort_carrier_stall_interval_ms: int = 0
    escort_carrier_stall_duration_ms: int = 0
    escort_harasser_count: int = 0
    escort_stagger_interval_ms: int = 0
    escort_stagger_duration_ms: int = 0
    escort_hazard_interval_ms: int = 0
    escort_hazard_damage: int = 0
    puzzle_reinforcement_count: int = 0
    puzzle_stall_duration_ms: int = 0
    puzzle_stabilizer_count: int = 0
    puzzle_stabilizer_hp: int = 0
    puzzle_camp_pulse_damage: int = 0
    puzzle_camp_pulse_interval_ms: int = 0
    puzzle_camp_pulse_grace_ms: int = 0
    puzzle_camp_pulse_radius: int = 0
    puzzle_decay_interval_ms: int = 0
    trap_intensity_scale: float = 1.0
    trap_speed_scale: float = 1.0
    trap_challenge_reward_kind: str = "chest_upgrade"
    trap_suppress_duration_ms: int = 2500
    trap_suppress_cooldown_ms: int = 8000
    trap_safespot_speed_mult: float = 1.0
    trap_sweeper_knockback_px: int = 0
    trap_vent_chilled_duration_ms: int = 0
    trap_surge_interval_ms: int = 0
    trap_surge_duration_ms: int = 0
    collapse_terrain_effect: str = ""
    # Danger Mode: True when this room is a flagged danger branch.
    danger_variant: bool = False
    # Terrain layout system (terrain_layouts.py).
    terrain_layout: str = ""
    allow_terrain_accent: bool = True
    min_rows: int = 0
    min_cols: int = 0

    @property
    def room_id(self):
        return self.template.room_id

    @property
    def display_name(self):
        return self.template.display_name

    @property
    def objective_kind(self):
        return self.template.objective_kind

    @property
    def topology_role(self):
        return self.template.topology_role

    @property
    def objective_variant(self):
        return self.template.objective_variant