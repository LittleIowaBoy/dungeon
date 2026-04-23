"""Room-test roster helpers and deterministic single-room plan builders."""

from dataclasses import dataclass

from content_db import BASE_ROOM_TEMPLATES, load_room_catalog
from dungeon_config import DUNGEONS, get_dungeon, get_level
from room_plan import RoomTemplate
from room_selector import RoomSelector


_BASE_CONTEXT_LABEL = "Base Layout"


@dataclass(frozen=True, slots=True)
class RoomTestEntry:
    entry_id: str
    room_id: str
    display_name: str
    base_display_name: str
    context_label: str
    profile_dungeon_id: str
    profile_dungeon_name: str
    terrain_type: str
    objective_kind: str
    objective_variant: str
    implementation_status: str
    is_biome_variant: bool
    template_row: dict


def load_room_test_entries():
    """Return a flat roster of base rooms plus distinct biome variants."""
    if not DUNGEONS:
        return ()

    default_dungeon = DUNGEONS[0]
    base_templates = {
        template["room_id"]: dict(template)
        for template in BASE_ROOM_TEMPLATES
        if _is_playable(template)
    }
    dungeon_catalogs = {
        dungeon["id"]: {
            row["room_id"]: dict(row)
            for row in load_room_catalog(dungeon["id"])
            if _is_playable(row)
        }
        for dungeon in DUNGEONS
    }

    entries = []
    for base_template in BASE_ROOM_TEMPLATES:
        room_id = base_template["room_id"]
        if room_id not in base_templates:
            continue

        entries.append(
            _build_entry(
                base_templates[room_id],
                context_label=_BASE_CONTEXT_LABEL,
                profile_dungeon=default_dungeon,
                base_display_name=base_template["display_name"],
                is_biome_variant=False,
                entry_id=f"base:{room_id}",
            )
        )

        for dungeon in DUNGEONS:
            merged = dungeon_catalogs[dungeon["id"]].get(room_id)
            if merged is None or not _is_distinct_variant(base_templates[room_id], merged):
                continue
            entries.append(
                _build_entry(
                    merged,
                    context_label=dungeon["name"],
                    profile_dungeon=dungeon,
                    base_display_name=base_template["display_name"],
                    is_biome_variant=True,
                    entry_id=f"biome:{dungeon['id']}:{room_id}",
                )
            )

    return tuple(entries)


def build_room_test_plan(entry):
    """Build a deterministic single-room RoomPlan for a selected roster entry."""
    dungeon = get_dungeon(entry.profile_dungeon_id)
    if dungeon is None:
        raise ValueError(f"Unknown room-test dungeon profile: {entry.profile_dungeon_id!r}")

    level_index = _representative_level_index(entry.template_row, len(dungeon["levels"]))
    level = get_level(entry.profile_dungeon_id, level_index)
    if level is None:
        raise ValueError(
            f"No level config for room-test profile {entry.profile_dungeon_id!r} at index {level_index}"
        )

    depth = _representative_depth(entry.template_row, len(dungeon["levels"]))
    path_kind = _path_kind(entry.template_row)
    selector = RoomSelector(
        entry.profile_dungeon_id,
        dungeon["terrain_type"],
        level["enemy_count_range"],
        level["enemy_type_weights"],
        catalog=(),
    )
    template = RoomTemplate.from_mapping(entry.template_row)
    return selector.build_room_plan_for_template(
        template,
        pos=(0, 0),
        depth=depth,
        path_kind=path_kind,
        is_exit=True,
        path_id="room_test_main" if path_kind == "main_path" else "room_test_branch",
        path_index=0,
        path_length=1,
        path_progress=1.0,
        difficulty_band=depth,
        is_path_terminal=True,
        reward_tier="finale_bonus" if path_kind == "main_path" else "branch_bonus",
    )


def _build_entry(
    template_row,
    *,
    context_label,
    profile_dungeon,
    base_display_name,
    is_biome_variant,
    entry_id,
):
    return RoomTestEntry(
        entry_id=entry_id,
        room_id=template_row["room_id"],
        display_name=template_row["display_name"],
        base_display_name=base_display_name,
        context_label=context_label,
        profile_dungeon_id=profile_dungeon["id"],
        profile_dungeon_name=profile_dungeon["name"],
        terrain_type=profile_dungeon["terrain_type"],
        objective_kind=template_row["objective_kind"],
        objective_variant=template_row.get("objective_variant", ""),
        implementation_status=template_row.get("implementation_status", "planned"),
        is_biome_variant=is_biome_variant,
        template_row=dict(template_row),
    )


def _is_playable(template_row):
    return bool(template_row.get("enabled")) and template_row.get("implementation_status") != "planned"


def _is_distinct_variant(base_template, merged_template):
    return any(
        merged_template.get(key) != base_template.get(key)
        for key in merged_template
        if key != "room_id"
    )


def _representative_depth(template_row, total_levels):
    max_index = max(0, total_levels - 1)
    min_depth = max(0, int(template_row.get("min_depth") or 0))
    raw_max_depth = template_row.get("max_depth")
    max_depth = max_index if raw_max_depth is None else max(min_depth, int(raw_max_depth))
    target_depth = (min_depth + max_depth) // 2
    return max(0, min(target_depth, max_index))


def _representative_level_index(template_row, total_levels):
    return _representative_depth(template_row, total_levels)


def _path_kind(template_row):
    if template_row.get("branch_preference") == "branch":
        return "branch"
    if template_row.get("topology_role") == "branch":
        return "branch"
    return "main_path"