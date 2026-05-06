"""Select concrete room plans from the room-content catalog."""

import random

from content_db import load_room_catalog
from room_plan import RoomPlan, RoomTemplate


def _scale_enemy_count_range(base_range, minimum_bonus=0, factor=1.0):
    if base_range is None:
        return None
    low, high = base_range
    scaled_low = max(0, int(round(low * factor)) + minimum_bonus)
    scaled_high = max(scaled_low, int(round(high * factor)) + minimum_bonus)
    return scaled_low, scaled_high


def _path_progress(path_index, path_length):
    if path_length <= 1:
        return 1.0
    return path_index / (path_length - 1)


def _scale_enemy_count_for_difficulty_band(base_range, difficulty_band):
    if base_range is None or base_range == (0, 0):
        return base_range

    # Bonus enemies added per difficulty tier so rooms grow harder as the
    # player goes deeper.  Three steps spread the scaling more evenly than
    # the old two-step (band≥2 / band≥4) curve:
    #   band 0        → +0  (opener rooms, full dodge window)
    #   band 1        → +1  (early mid-run)
    #   band 2–3      → +2  (mid-run pressure ramp)
    #   band 4+       → +3  (late / finale rooms)
    # NOTE: These thresholds assume the base ranges in dungeon_config.py and
    # the per-type caps in settings.py are the primary difficulty levers.  If
    # enemy HP, damage, or cooldowns are rebalanced, revisit this curve so the
    # combined effect stays in the intended challenge window.
    low, high = base_range
    bonus = 0
    if difficulty_band >= 1:
        bonus += 1
    if difficulty_band >= 2:
        bonus += 1
    if difficulty_band >= 4:
        bonus += 1
    return low + bonus, high + bonus


def _parse_range_script(value):
    if not value:
        return None
    if isinstance(value, (tuple, list)) and len(value) == 2:
        low, high = value
        low = int(low)
        high = int(high)
        return low, max(low, high)

    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    if len(parts) != 2:
        return None
    low = int(parts[0])
    high = int(parts[1])
    return low, max(low, high)


def _parse_int_script(value):
    if not value:
        return ()
    if isinstance(value, (tuple, list)):
        return tuple(int(part) for part in value)
    return tuple(int(part.strip()) for part in str(value).split(",") if part.strip())


def _parse_text_script(value):
    if not value:
        return ()
    if isinstance(value, (tuple, list)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return tuple(part.strip() for part in str(value).split(",") if part.strip())


def _parse_offset_script(value):
    if not value:
        return ()
    if isinstance(value, (tuple, list)):
        offsets = []
        for item in value:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                offsets.append((int(item[0]), int(item[1])))
        return tuple(offsets)

    offsets = []
    for chunk in str(value).split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [part.strip() for part in chunk.split(",")]
        if len(parts) != 2:
            continue
        offsets.append((int(parts[0]), int(parts[1])))
    return tuple(offsets)


def _parse_optional_offset(value):
    offsets = _parse_offset_script(value)
    return offsets[0] if offsets else None


class RoomSelector:
    """Build room plans from content templates and dungeon pacing intent."""

    def __init__(
        self,
        dungeon_id,
        terrain_type,
        enemy_count_range,
        enemy_type_weights,
        *,
        catalog=None,
        rng=None,
    ):
        if catalog is None:
            catalog = load_room_catalog(dungeon_id)
        self._templates = tuple(self._coerce_template(row) for row in catalog)
        self._terrain_type = terrain_type
        self._enemy_count_range = enemy_count_range
        self._enemy_type_weights = tuple(enemy_type_weights or ())
        self._rng = rng or random.Random()
        self._path_recent_room_ids = {}

    @staticmethod
    def _coerce_template(row):
        if isinstance(row, RoomTemplate):
            return row
        return RoomTemplate.from_mapping(row)

    def build_room_plan_for_template(
        self,
        template,
        *,
        pos=(0, 0),
        depth=0,
        path_kind="main_path",
        is_exit=True,
        path_id=None,
        path_index=0,
        path_length=1,
        path_progress=1.0,
        difficulty_band=None,
        is_path_terminal=True,
        reward_tier=None,
    ):
        template = self._coerce_template(template)
        if path_id is None:
            path_id = "main" if path_kind == "main_path" else "branch"
        if difficulty_band is None:
            difficulty_band = depth
        if reward_tier is None:
            reward_tier = "finale_bonus" if path_kind == "main_path" else "branch_bonus"
        return self._build_plan_from_template(
            template,
            pos=pos,
            depth=depth,
            path_kind=path_kind,
            is_exit=is_exit,
            path_id=path_id,
            path_index=path_index,
            path_length=path_length,
            path_progress=path_progress,
            difficulty_band=difficulty_band,
            is_path_terminal=is_path_terminal,
            reward_tier=reward_tier,
        )

    def build_boss_room_plan(
        self,
        pos,
        depth,
        path_kind,
        *,
        path_id=None,
        path_index=None,
        path_length=None,
        path_progress=None,
        difficulty_band=None,
    ):
        """Select a boss-slot room for the second-to-last main-path position.

        Picks randomly from enabled templates with ``topology_role == "boss"``.
        If no such templates exist the call falls back to a normal
        ``build_room_plan`` call so generation never hard-fails.

        The boss slot always receives ``reward_tier="finale_bonus"`` and
        ``is_path_terminal=False`` (the exit room is still the terminal).
        """
        boss_templates = [
            t for t in self._templates
            if t.enabled and t.topology_role == "boss"
        ]
        if not boss_templates:
            return self.build_room_plan(
                pos, depth, path_kind,
                is_exit=False,
                path_id=path_id,
                path_index=path_index,
                path_length=path_length,
                path_progress=path_progress,
                difficulty_band=difficulty_band,
                is_path_terminal=False,
            )

        template = self._rng.choice(boss_templates)
        if path_id is None:
            path_id = "main"
        if path_index is None:
            path_index = 0
        if path_length is None:
            path_length = 1
        if path_progress is None:
            path_progress = 0.0
        if difficulty_band is None:
            difficulty_band = depth

        return self._build_plan_from_template(
            template,
            pos=pos,
            depth=depth,
            path_kind=path_kind,
            is_exit=False,
            path_id=path_id,
            path_index=path_index,
            path_length=path_length,
            path_progress=path_progress,
            difficulty_band=difficulty_band,
            is_path_terminal=False,
            reward_tier="finale_bonus",
        )

    def build_room_plan(
        self,
        pos,
        depth,
        path_kind,
        *,
        is_exit=False,
        path_id=None,
        path_index=None,
        path_length=None,
        path_progress=None,
        difficulty_band=None,
        is_path_terminal=False,
        reward_tier="standard",
    ):
        path_context_provided = any(
            value is not None
            for value in (path_id, path_index, path_length, path_progress, difficulty_band)
        ) or is_path_terminal
        if path_id is None:
            path_id = "main" if path_kind == "main_path" else "branch"
        if path_index is None:
            path_index = 0
        if path_length is None:
            path_length = 1
        if path_progress is None:
            path_progress = 0.0
        if difficulty_band is None:
            difficulty_band = 0
        if reward_tier == "standard" and is_path_terminal:
            reward_tier = "finale_bonus" if is_exit or path_kind == "main_path" else "branch_bonus"

        template = self._select_template(
            depth,
            path_kind,
            is_exit,
            path_id=path_id,
            difficulty_band=difficulty_band,
            is_path_terminal=is_path_terminal,
            reward_tier=reward_tier,
            use_path_rules=path_context_provided,
        )
        if path_context_provided:
            history = self._path_recent_room_ids.setdefault(path_id, [])
            history.append(template.room_id)
            del history[:-5]
        return self._build_plan_from_template(
            template,
            pos=pos,
            depth=depth,
            path_kind=path_kind,
            is_exit=is_exit,
            path_id=path_id,
            path_index=path_index,
            path_length=path_length,
            path_progress=path_progress,
            difficulty_band=difficulty_band,
            is_path_terminal=is_path_terminal,
            reward_tier=reward_tier,
        )

    def _select_template(
        self,
        depth,
        path_kind,
        is_exit,
        *,
        path_id,
        difficulty_band,
        is_path_terminal,
        reward_tier,
        use_path_rules,
    ):
        if depth == 0 and path_kind != "branch":
            for template in self._templates:
                if template.room_id == "standard_combat" and template.enabled:
                    return template

        candidates = [
            template
            for template in self._templates
            if template.enabled and self._matches_depth(template, depth)
            and self._matches_branch_preference(template, path_kind)
        ]

        preferred = self._preferred_candidates(candidates, path_kind, is_exit)
        if preferred:
            candidates = preferred

        if use_path_rules:
            stage_candidates = [
                template
                for template in candidates
                if template.path_stage_min <= difficulty_band <= template.path_stage_max
            ]
            if stage_candidates:
                candidates = stage_candidates

            terminal_candidates = self._terminal_candidates(candidates, is_path_terminal)
            if terminal_candidates:
                candidates = terminal_candidates

            history = self._path_recent_room_ids.get(path_id, [])
            non_repeat = [
                template
                for template in candidates
                if template.repeat_cooldown <= 0
                or template.room_id not in history[-template.repeat_cooldown :]
            ]
            if non_repeat:
                candidates = non_repeat

        if not candidates:
            for template in self._templates:
                if template.room_id == "standard_combat":
                    return template
            raise ValueError("No room templates are available for selection")

        weights = [
            max(
                1,
                int(
                    round(
                        template.generation_weight
                        * self._reward_affinity_weight(template, reward_tier, is_path_terminal)
                    )
                ),
            )
            for template in candidates
        ]
        return self._rng.choices(candidates, weights=weights, k=1)[0]

    @staticmethod
    def _terminal_candidates(candidates, is_path_terminal):
        if is_path_terminal:
            return [
                template for template in candidates if template.terminal_preference != "avoid"
            ]
        return [
            template for template in candidates if template.terminal_preference != "prefer"
        ]

    @staticmethod
    def _reward_affinity_weight(template, reward_tier, is_path_terminal):
        if not is_path_terminal:
            return 1.0
        if reward_tier == "branch_bonus" and template.reward_affinity == "branch":
            return 1.8
        if reward_tier == "finale_bonus" and template.reward_affinity == "finale":
            return 1.8
        return 1.0

    @staticmethod
    def _matches_depth(template, depth):
        if depth < template.min_depth:
            return False
        if template.max_depth is not None and depth > template.max_depth:
            return False
        return True

    @staticmethod
    def _matches_branch_preference(template, path_kind):
        if path_kind == "branch":
            return template.branch_preference in {"branch", "either"}
        return template.branch_preference in {"main_path", "either"}

    @staticmethod
    def _preferred_candidates(candidates, path_kind, is_exit):
        if is_exit:
            preferred_roles = {"finale", "mid_run", "wildcard"}
        elif path_kind == "branch":
            preferred_roles = {"branch"}
        else:
            preferred_roles = {"mid_run", "opener", "wildcard"}

        preferred = [
            template for template in candidates if template.topology_role in preferred_roles
        ]
        if preferred:
            return preferred

        if is_exit:
            return [
                template for template in candidates if template.topology_role in {"mid_run", "wildcard"}
            ]

        if path_kind == "branch":
            return [
                template for template in candidates if template.topology_role in {"wildcard", "mid_run"}
            ]

        return []

    def _build_plan_from_template(
        self,
        template,
        *,
        pos,
        depth,
        path_kind,
        is_exit,
        path_id,
        path_index,
        path_length,
        path_progress,
        difficulty_band,
        is_path_terminal,
        reward_tier,
    ):
        enemy_count_range = self._enemy_count_range
        objective_rule = template.objective_rule or "immediate"
        objective_duration_ms = template.objective_duration_ms
        guaranteed_chest = bool(template.guaranteed_chest)
        chest_spawn_chance = template.chest_spawn_chance
        terrain_patch_count_range = _parse_range_script(template.terrain_patch_count_range)
        terrain_patch_size_range = _parse_range_script(template.terrain_patch_size_range)
        clear_center = bool(template.clear_center)
        chest_locked_until_complete = False
        objective_entity_count = max(0, int(template.objective_entity_count or 0))
        scripted_wave_sizes = _parse_int_script(template.scripted_wave_sizes)
        holdout_zone_radius = max(0, int(template.holdout_zone_radius or 0))
        holdout_zone_min_radius = max(0, int(template.holdout_zone_min_radius or 0))
        holdout_zone_shrink_ms = max(0, int(template.holdout_zone_shrink_ms or 0))
        holdout_zone_migrate_ms = max(0, int(template.holdout_zone_migrate_ms or 0))
        holdout_zone_migration_offsets = _parse_offset_script(template.holdout_zone_migration_offsets)
        holdout_relief_count = max(0, int(template.holdout_relief_count or 0))
        holdout_relief_delay_ms = max(0, int(template.holdout_relief_delay_ms or 0))
        holdout_stabilizer_migration_delay_ms = max(0, int(template.holdout_stabilizer_migration_delay_ms or 0))
        ritual_role_script = _parse_text_script(template.ritual_role_script)
        ritual_reinforcement_count = max(0, int(template.ritual_reinforcement_count or 0))
        ritual_link_mode = template.ritual_link_mode or ""
        ritual_payoff_kind = template.ritual_payoff_kind or ""
        ritual_payoff_label = template.ritual_payoff_label or ""
        ritual_wrong_strike_spawn_count = max(0, int(template.ritual_wrong_strike_spawn_count or 0))
        objective_label = template.objective_label or ""
        objective_layout_offsets = _parse_offset_script(template.objective_layout_offsets)
        objective_spawn_offset = _parse_optional_offset(template.objective_spawn_offset)
        objective_patrol_offset = _parse_optional_offset(template.objective_patrol_offset)
        objective_patrol_shape = (template.objective_patrol_shape or "line").strip().lower() or "line"
        objective_radius = max(0, int(template.objective_radius or 0))
        objective_trigger_padding = max(0, int(template.objective_trigger_padding or 0))
        objective_max_hp = max(0, int(template.objective_max_hp or 0))
        objective_move_speed = float(template.objective_move_speed or 0.0)
        objective_guide_radius = max(0, int(template.objective_guide_radius or 0))
        objective_exit_radius = max(0, int(template.objective_exit_radius or 0))
        objective_damage_cooldown_ms = max(0, int(template.objective_damage_cooldown_ms or 0))
        puzzle_reinforcement_count = max(0, int(template.puzzle_reinforcement_count or 0))
        puzzle_stall_duration_ms = max(0, int(template.puzzle_stall_duration_ms or 0))
        puzzle_stabilizer_count = max(0, int(template.puzzle_stabilizer_count or 0))
        puzzle_stabilizer_hp = max(0, int(template.puzzle_stabilizer_hp or 0))
        puzzle_camp_pulse_damage = max(0, int(template.puzzle_camp_pulse_damage or 0))
        puzzle_camp_pulse_interval_ms = max(0, int(template.puzzle_camp_pulse_interval_ms or 0))
        puzzle_camp_pulse_grace_ms = max(0, int(template.puzzle_camp_pulse_grace_ms or 0))
        puzzle_camp_pulse_radius = max(0, int(template.puzzle_camp_pulse_radius or 0))
        trap_intensity_scale = max(0.0, float(template.trap_intensity_scale or 1.0))
        trap_speed_scale = max(0.0, float(template.trap_speed_scale or 1.0))
        trap_challenge_reward_kind = str(template.trap_challenge_reward_kind or "chest_upgrade")

        if objective_rule == "charge_plates":
            if puzzle_reinforcement_count <= 0:
                puzzle_reinforcement_count = 1
            if puzzle_stall_duration_ms <= 0:
                puzzle_stall_duration_ms = 2500

        if self._enemy_count_range is not None and (
            template.enemy_minimum_bonus or template.enemy_scale_factor != 1.0
        ):
            enemy_count_range = _scale_enemy_count_range(
                self._enemy_count_range,
                minimum_bonus=template.enemy_minimum_bonus,
                factor=template.enemy_scale_factor,
            )

        if objective_rule == "holdout_timer":
            if not scripted_wave_sizes:
                scripted_wave_sizes = (1, 2)
            if difficulty_band >= 4 or is_path_terminal:
                scripted_wave_sizes = scripted_wave_sizes + (scripted_wave_sizes[-1] + 1,)
            if holdout_zone_radius <= 0:
                holdout_zone_radius = 96
            if holdout_zone_shrink_ms > 0:
                if holdout_zone_min_radius <= 0:
                    holdout_zone_min_radius = max(40, int(holdout_zone_radius * 0.6))
                holdout_zone_min_radius = min(holdout_zone_min_radius, holdout_zone_radius)
            else:
                holdout_zone_min_radius = 0
            if not holdout_zone_migration_offsets:
                holdout_zone_migrate_ms = 0
            if holdout_zone_migrate_ms <= 0:
                holdout_stabilizer_migration_delay_ms = 0
            elif holdout_stabilizer_migration_delay_ms <= 0:
                holdout_stabilizer_migration_delay_ms = holdout_zone_migrate_ms
            if holdout_relief_count <= 0:
                holdout_relief_count = 1
            if holdout_relief_delay_ms <= 0:
                holdout_relief_delay_ms = 1500
        elif objective_rule == "destroy_altars":
            if objective_entity_count <= 0:
                objective_entity_count = max(3, len(ritual_role_script) or 3)
            if difficulty_band >= 4 or is_path_terminal:
                objective_entity_count += 1
                if ritual_role_script:
                    ritual_role_script = ritual_role_script + (ritual_role_script[-1],)

        enemy_count_range = _scale_enemy_count_for_difficulty_band(
            enemy_count_range,
            difficulty_band,
        )
        if is_path_terminal:
            guaranteed_chest = True
            chest_spawn_chance = 1.0
        if is_exit and is_path_terminal and template.terminal_chest_lock:
            chest_locked_until_complete = True

        return RoomPlan(
            position=pos,
            depth=depth,
            path_kind=path_kind,
            is_exit=is_exit,
            template=template,
            terrain_type=self._terrain_type,
            enemy_count_range=enemy_count_range,
            enemy_type_weights=self._enemy_type_weights,
            objective_rule=objective_rule,
            objective_duration_ms=objective_duration_ms,
            guaranteed_chest=guaranteed_chest,
            chest_spawn_chance=chest_spawn_chance,
            terrain_patch_count_range=terrain_patch_count_range,
            terrain_patch_size_range=terrain_patch_size_range,
            clear_center=clear_center,
            path_id=path_id,
            path_index=path_index,
            path_length=path_length,
            path_progress=path_progress,
            difficulty_band=difficulty_band,
            is_path_terminal=is_path_terminal,
            reward_tier=reward_tier,
            chest_locked_until_complete=chest_locked_until_complete,
            objective_entity_count=objective_entity_count,
            scripted_wave_sizes=scripted_wave_sizes,
            holdout_zone_radius=holdout_zone_radius,
            holdout_zone_min_radius=holdout_zone_min_radius,
            holdout_zone_shrink_ms=holdout_zone_shrink_ms,
            holdout_zone_migrate_ms=holdout_zone_migrate_ms,
            holdout_zone_migration_offsets=holdout_zone_migration_offsets,
            holdout_relief_count=holdout_relief_count,
            holdout_relief_delay_ms=holdout_relief_delay_ms,
            holdout_stabilizer_migration_delay_ms=holdout_stabilizer_migration_delay_ms,
            ritual_role_script=ritual_role_script,
            ritual_reinforcement_count=ritual_reinforcement_count,
            ritual_link_mode=ritual_link_mode,
            ritual_payoff_kind=ritual_payoff_kind,
            ritual_payoff_label=ritual_payoff_label,
            ritual_wrong_strike_spawn_count=ritual_wrong_strike_spawn_count,
            objective_label=objective_label,
            objective_layout_offsets=objective_layout_offsets,
            objective_spawn_offset=objective_spawn_offset,
            objective_patrol_offset=objective_patrol_offset,
            objective_patrol_shape=objective_patrol_shape,
            objective_radius=objective_radius,
            objective_trigger_padding=objective_trigger_padding,
            objective_max_hp=objective_max_hp,
            objective_move_speed=objective_move_speed,
            objective_guide_radius=objective_guide_radius,
            objective_exit_radius=objective_exit_radius,
            objective_damage_cooldown_ms=objective_damage_cooldown_ms,
            puzzle_reinforcement_count=puzzle_reinforcement_count,
            puzzle_stall_duration_ms=puzzle_stall_duration_ms,
            puzzle_stabilizer_count=puzzle_stabilizer_count,
            puzzle_stabilizer_hp=puzzle_stabilizer_hp,
            puzzle_camp_pulse_damage=puzzle_camp_pulse_damage,
            puzzle_camp_pulse_interval_ms=puzzle_camp_pulse_interval_ms,
            puzzle_camp_pulse_grace_ms=puzzle_camp_pulse_grace_ms,
            puzzle_camp_pulse_radius=puzzle_camp_pulse_radius,
            trap_intensity_scale=trap_intensity_scale,
            trap_speed_scale=trap_speed_scale,
            trap_challenge_reward_kind=trap_challenge_reward_kind,
        )