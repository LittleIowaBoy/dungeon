"""Projection helpers for menu and overlay screen render state."""

from dataclasses import dataclass

from dungeon_config import DUNGEONS
from rune_catalog import RUNE_DATABASE, RUNE_SLOT_CAPACITY
from settings import (
    BIOME_ATTUNEMENT_MAX_PER_BIOME,
    BIOME_TROPHY_IDS,
    BIOME_TROPHY_EXCHANGE_RATIO,
    BIOME_TROPHY_KEYSTONE_ID,
    KEYSTONE_MAX_OWNED,
    TERRAIN_TROPHY_IDS,
)


@dataclass(frozen=True)
class MainMenuView:
    title: str
    options: tuple[str, ...]
    selected_index: int
    keystone_status_text: str = ""


@dataclass(frozen=True)
class DungeonCardView:
    name: str
    terrain_type: str
    status_text: str
    terrain_label: str
    trophy_label: str = ""
    attunement_label: str = ""


@dataclass(frozen=True)
class DungeonSelectView:
    title: str
    cards: tuple[DungeonCardView, ...]
    selected_index: int
    difficulty_label: str
    back_label: str
    keystone_status_text: str = ""


@dataclass(frozen=True)
class RoomTestRowView:
    line_text: str
    detail_text: str
    selected: bool
    line_color: tuple[int, int, int]


@dataclass(frozen=True)
class RoomTestSelectView:
    title: str
    rows: tuple[RoomTestRowView, ...]
    selected_label: str
    detail_lines: tuple[str, ...]
    empty_message: str
    show_more_above: bool
    show_more_below: bool
    footer_hint: str
    spawn_direction_label: str


@dataclass(frozen=True)
class CharacterSlotView:
    label: str
    value: str
    equipped: bool


@dataclass(frozen=True)
class CharacterItemView:
    label: str
    quantity: int


@dataclass(frozen=True)
class CharacterCustomizeView:
    title: str
    subtitle: str
    slots: tuple[CharacterSlotView, ...]
    selected_slot_index: int
    slot_panel_focused: bool
    panel_title: str
    items: tuple[CharacterItemView, ...]
    selected_item_index: int
    item_panel_focused: bool
    empty_message: str
    help_lines: tuple[str, str]


@dataclass(frozen=True)
class ShopItemView:
    line_text: str
    description: str
    selected: bool
    line_color: tuple[int, int, int]


@dataclass(frozen=True)
class ShopView:
    title: str
    coins_text: str
    items: tuple[ShopItemView, ...]
    empty_message: str
    show_more_above: bool
    show_more_below: bool
    footer_hint: str
    trophy_summary_text: str = ""
    trophy_exchange_hint: str = ""


@dataclass(frozen=True)
class PauseScreenView:
    title: str
    options: tuple[str, ...]
    selected_index: int
    warning_text: str


@dataclass(frozen=True)
class RecordsBiomeRowView:
    """One per-biome row on the Records screen."""
    dungeon_name: str
    terrain_label: str
    completion_label: str       # "Completions: 5" (lifetime, monotonic)
    attunement_label: str       # "Attunements: 2 / 3"  or "Attunements: 3 / 3 (max)"
    next_attunement_label: str  # "Next attunement: 2 / 3"  or ""
    trophy_label: str           # "Stat Shards: 4"
    starting_grant_label: str   # "Run-start trophies: +2" or ""


@dataclass(frozen=True)
class RecordsView:
    title: str
    biome_rows: tuple[RecordsBiomeRowView, ...]
    keystone_summary: str       # "Prismatic Keystones: 2 / 3 (+75 coins/run)" or "(none crafted)"
    totals_summary: str         # "Lifetime completions: 12   |   Trophies in stockpile: 7"
    back_label: str             # "Back"
    footer_hint: str


@dataclass(frozen=True)
class LevelCompleteScreenView:
    dungeon_name: str
    detail_lines: tuple[str, ...]
    options: tuple[str, ...]
    selected_index: int


def build_main_menu_view(screen):
    progress = getattr(screen, "progress", None)
    keystones = getattr(progress, "meta_keystones", 0) if progress is not None else 0
    if keystones > 0:
        keystone_status_text = (
            f"Prismatic Keystones: {keystones} / {KEYSTONE_MAX_OWNED}"
        )
    else:
        keystone_status_text = ""
    return MainMenuView(
        title="Dungeon Crawler",
        options=tuple(screen.OPTIONS),
        selected_index=screen.selected,
        keystone_status_text=keystone_status_text,
    )


def build_dungeon_select_view(screen):
    from dungeon_config import DIFFICULTY_PRESETS
    inventory = getattr(screen.progress, "inventory", {}) or {}
    cards = []
    for dungeon in DUNGEONS:
        progress = screen.progress.get_dungeon(dungeon["id"])
        if progress.completed:
            status_text = "Completed"
        else:
            status_text = "Not started"

        terrain_type = dungeon["terrain_type"]
        trophy_id = TERRAIN_TROPHY_IDS.get(terrain_type)
        if trophy_id is not None:
            count = inventory.get(trophy_id, 0)
            trophy_label = f"{_TROPHY_SHORT_LABELS[trophy_id]} x{count}"
        else:
            trophy_label = ""

        attunement_label = _build_attunement_label(screen.progress, terrain_type)

        cards.append(
            DungeonCardView(
                name=dungeon["name"],
                terrain_type=terrain_type,
                status_text=status_text,
                terrain_label=f"Terrain: {terrain_type.capitalize()}",
                trophy_label=trophy_label,
                attunement_label=attunement_label,
            )
        )

    diff = screen.progress.difficulty_preference
    diff_label = screen.DIFFICULTY_LABELS.get(diff, diff.capitalize())

    keystones = getattr(screen.progress, "meta_keystones", 0)
    if keystones > 0:
        bonus = screen.progress.keystone_starting_coin_bonus()
        keystone_status_text = (
            f"Prismatic Keystones: {keystones}  (+{bonus} coins each run)"
        )
    else:
        keystone_status_text = ""

    return DungeonSelectView(
        title="Select Dungeon",
        cards=tuple(cards),
        selected_index=min(max(screen.selected, 0), len(cards)),
        difficulty_label=diff_label,
        back_label="Back",
        keystone_status_text=keystone_status_text,
    )


def _format_room_test_variant_label(variant_label):
    if not variant_label:
        return "Base rules"
    return variant_label.replace("_", " ").title()


def build_room_test_select_view(screen):
    entries = screen.entries
    if not entries:
        return RoomTestSelectView(
            title="Room Tests",
            rows=(),
            selected_label="No rooms available",
            detail_lines=("Playable rooms are not available yet.",),
            empty_message="No playable room tests available",
            show_more_above=False,
            show_more_below=False,
            footer_hint="Press ESC to return",
            spawn_direction_label="",
        )

    visible_count = screen._visible_entry_count()
    start_index = screen.scroll_offset
    end_index = min(len(entries), start_index + visible_count)
    selected_entry = entries[min(screen.selected, len(entries) - 1)]
    row_views = []

    for index in range(start_index, end_index):
        entry = entries[index]
        selected = index == screen.selected
        line_color = (255, 255, 255) if selected else (160, 160, 160)
        prefix = "> " if selected else "  "
        row_views.append(
            RoomTestRowView(
                line_text=f"{prefix}{entry.display_name}",
                detail_text=f"{entry.context_label} | {entry.objective_kind.replace('_', ' ').title()}",
                selected=selected,
                line_color=line_color,
            )
        )

    if selected_entry.is_biome_variant:
        context_line = f"Context: {selected_entry.context_label}"
    else:
        context_line = (
            f"Context: {selected_entry.context_label}"
            f" (launch profile: {selected_entry.profile_dungeon_name})"
        )
    variant_label = _format_room_test_variant_label(selected_entry.objective_variant)

    return RoomTestSelectView(
        title="Room Tests",
        rows=tuple(row_views),
        selected_label=selected_entry.display_name,
        detail_lines=(
            f"Family: {selected_entry.base_display_name}",
            context_line,
            f"Variant: {variant_label}",
        ),
        empty_message="No playable room tests available",
        show_more_above=start_index > 0,
        show_more_below=end_index < len(entries),
        footer_hint="Enter: start room  ←/→: entry side  Esc: back",
        spawn_direction_label=screen.SPAWN_DIRECTION_LABELS.get(
            screen.spawn_direction, screen.spawn_direction
        ),
    )


def build_character_customize_view(screen):
    slots = tuple(
        CharacterSlotView(
            label=slot_label,
            value=screen._slot_value_label(slot_key),
            equipped=bool(screen.progress.equipped_slots.get(slot_key)),
        )
        for slot_key, slot_label in screen.SLOTS
    )

    compatible_items = []
    for item_id in screen._compatible_items():
        label = screen._item_name(item_id)
        tier = screen.progress.weapon_upgrade_tier(item_id)
        if tier > 0:
            label = f"{label} +{tier}"
        compatible_items.append(
            CharacterItemView(
                label=label,
                quantity=screen.progress.equipment_storage.get(item_id, 0),
            )
        )

    selected_item_index = 0
    if compatible_items:
        selected_item_index = min(screen.selected_item, len(compatible_items) - 1)

    # Equipment-derived stat summary (Phase 0e).  Empty string when no
    # bonus-bearing armor is currently equipped, so the legacy default
    # subtitle stays in place.
    import armor_rules  # local to avoid menu_view top-level cycle
    stats = armor_rules.aggregate_equipped_stats(screen.progress)
    parts = []
    if stats["max_hp_bonus"]:
        parts.append(f"+{int(stats['max_hp_bonus'])} HP")
    if stats["crit_chance"]:
        parts.append(f"+{int(round(stats['crit_chance'] * 100))}% crit")
    if stats["damage_reduction"]:
        parts.append(f"+{int(round(stats['damage_reduction'] * 100))}% DR")
    if stats["speed_bonus"]:
        parts.append(f"+{int(round(stats['speed_bonus'] * 100))}% speed")
    if stats["outgoing_damage_bonus"]:
        parts.append(f"+{int(round(stats['outgoing_damage_bonus'] * 100))}% damage")
    if parts:
        subtitle = "Equipped bonuses: " + ", ".join(parts)
    else:
        subtitle = "Select a slot, then equip from stored compatible gear."

    return CharacterCustomizeView(
        title="Character Loadout",
        subtitle=subtitle,
        slots=slots,
        selected_slot_index=screen.selected_slot,
        slot_panel_focused=screen.focus == "slots",
        panel_title=f"{screen._current_slot_label()} Options",
        items=tuple(compatible_items),
        selected_item_index=selected_item_index,
        item_panel_focused=screen.focus == "items",
        empty_message="No compatible stored items",
        help_lines=(
            "Up/Down: move  Left/Right or Tab: switch panels  Enter: equip or unequip",
            "Backspace/Delete: unequip selected slot  ESC: return to menu",
        ),
    )


def build_shop_view(screen):
    items = screen.shop.items
    trophy_summary, trophy_hint = _build_trophy_strings(screen.progress)
    if not items:
        return ShopView(
            title="Shop",
            coins_text=f"Coins: {screen.progress.coins}",
            items=(),
            empty_message="No items available",
            show_more_above=False,
            show_more_below=False,
            footer_hint="Press ESC to return",
            trophy_summary_text=trophy_summary,
            trophy_exchange_hint=trophy_hint,
        )

    screen._ensure_selection_visible(items)
    start_index = screen.scroll_offset
    visible_count = screen._visible_item_count()
    end_index = min(len(items), start_index + visible_count)
    item_views = []

    for index in range(start_index, end_index):
        item = items[index]
        owned = screen._owned_count(item)
        maxed = screen.shop.is_maxed(item.id, screen.progress)
        can_afford = screen.progress.coins >= item.cost

        if maxed and item.id not in ("armor", "compass"):
            line_color = (60, 60, 60)
        elif index == screen.selected:
            line_color = (255, 255, 255)
        else:
            line_color = (160, 160, 160)

        prefix = "> " if index == screen.selected else "  "
        if item.max_owned > 0:
            badge = f"  [{owned}/{item.max_owned}]"
        else:
            badge = f"  [x{owned}]" if owned else ""

        if maxed and item.id not in ("armor", "compass"):
            suffix = "  MAXED"
        elif not can_afford:
            suffix = "  (not enough coins)"
        else:
            suffix = ""

        item_views.append(
            ShopItemView(
                line_text=f"{prefix}{item.name} - {item.cost} coins{badge}{suffix}",
                description=item.description,
                selected=index == screen.selected,
                line_color=line_color,
            )
        )

    return ShopView(
        title="Shop",
        coins_text=f"Coins: {screen.progress.coins}",
        items=tuple(item_views),
        empty_message="No items available",
        show_more_above=start_index > 0,
        show_more_below=end_index < len(items),
        footer_hint="Press ESC to return",
        trophy_summary_text=trophy_summary,
        trophy_exchange_hint=trophy_hint,
    )


_TROPHY_SHORT_LABELS = {
    "stat_shard": "Shard",
    "tempo_rune": "Rune",
    "mobility_charge": "Dash",
    BIOME_TROPHY_KEYSTONE_ID: "Keystone",
}


def _build_attunement_label(progress, terrain):
    """Format the per-card biome attunement summary, or "" when irrelevant.

    Renders ``Attune N/cap`` (always shown when the biome has any
    completions or attunements).  Below the per-biome cap we also append
    ``(p/threshold next)`` so the player can see exactly how many more
    completions earn the next attunement.
    """
    if terrain is None or terrain not in TERRAIN_TROPHY_IDS:
        return ""
    attunements = getattr(progress, "biome_attunements", {}) or {}
    completions = getattr(progress, "biome_completions", {}) or {}
    owned = attunements.get(terrain, 0)
    completed = completions.get(terrain, 0)
    if owned == 0 and completed == 0:
        return ""
    base = f"Attune {owned}/{BIOME_ATTUNEMENT_MAX_PER_BIOME}"
    if owned >= BIOME_ATTUNEMENT_MAX_PER_BIOME:
        return base + " (max)"
    progress_toward, threshold = progress.biome_attunement_progress(terrain)
    return base + f" ({progress_toward}/{threshold} next)"


def _build_trophy_strings(progress):
    """Return ``(summary, exchange_hint)`` strings for the shop trophy footer.

    Returns ``("", "")`` when the player owns no biome trophies — there's
    nothing to summarise or trade and the screen should stay quiet.
    """
    counts = {
        trophy_id: progress.inventory.get(trophy_id, 0)
        for trophy_id in BIOME_TROPHY_IDS
    }
    keystone_count = getattr(progress, "meta_keystones", 0)
    if not any(counts.values()) and keystone_count == 0:
        return "", ""
    summary_parts = [
        f"{_TROPHY_SHORT_LABELS[trophy_id]} x{counts[trophy_id]}"
        for trophy_id in BIOME_TROPHY_IDS
    ]
    if keystone_count:
        bonus = progress.keystone_starting_coin_bonus()
        summary_parts.append(
            f"{_TROPHY_SHORT_LABELS[BIOME_TROPHY_KEYSTONE_ID]} x{keystone_count}"
            f" (+{bonus} run-start coins)"
        )
    summary = "Trophies: " + "  ".join(summary_parts)
    has_surplus = any(count >= BIOME_TROPHY_EXCHANGE_RATIO for count in counts.values())
    has_each_trophy = all(count >= 1 for count in counts.values())
    at_cap = keystone_count >= KEYSTONE_MAX_OWNED
    hint_parts = []
    if has_surplus:
        ratio = BIOME_TROPHY_EXCHANGE_RATIO
        hint_parts.append(
            f"[1/2/3] Trade {ratio} surplus → Shard / Rune / Dash"
        )
    if at_cap:
        # Cap acknowledgement: there's no further keystone craft available.
        # Replaces the [4] hint entirely so the player isn't prompted to
        # press a key that's now a no-op.
        hint_parts.append(
            f"Keystones complete ({keystone_count}/{KEYSTONE_MAX_OWNED}) — meta route maxed"
        )
    elif has_each_trophy:
        next_tier = progress.next_keystone_tier_bonus()
        if next_tier > 0:
            hint_parts.append(
                f"[4] Craft Keystone (1 of each) — next tier +{next_tier} coins/run"
            )
        else:
            hint_parts.append("[4] Craft Keystone (1 of each)")
    hint = "   ".join(hint_parts)
    return summary, hint


_RECORDS_TROPHY_LONG_LABELS = {
    "stat_shard": "Stat Shards",
    "tempo_rune": "Tempo Runes",
    "mobility_charge": "Mobility Charges",
}


def build_records_view(screen):
    """Project a `RecordsView` summarizing all meta-progression state.

    Reads from `screen.progress` and renders one row per dungeon defined
    in `DUNGEONS`, plus a keystone summary and lifetime totals. Pure
    projection — no pygame, no inputs, no mutation.
    """
    progress = screen.progress
    inventory = getattr(progress, "inventory", {}) or {}
    completions = getattr(progress, "biome_completions", {}) or {}
    attunements = getattr(progress, "biome_attunements", {}) or {}

    rows = []
    for dungeon in DUNGEONS:
        terrain = dungeon["terrain_type"]
        trophy_id = TERRAIN_TROPHY_IDS.get(terrain)
        completion_count = completions.get(terrain, 0)
        attunement_count = attunements.get(terrain, 0)

        if attunement_count >= BIOME_ATTUNEMENT_MAX_PER_BIOME:
            attune_label = (
                f"Attunements: {attunement_count} / "
                f"{BIOME_ATTUNEMENT_MAX_PER_BIOME} (max)"
            )
            next_attune_label = ""
        else:
            attune_label = (
                f"Attunements: {attunement_count} / "
                f"{BIOME_ATTUNEMENT_MAX_PER_BIOME}"
            )
            toward, threshold = progress.biome_attunement_progress(terrain)
            next_attune_label = f"Next attunement: {toward} / {threshold}"

        if trophy_id is not None:
            trophy_long = _RECORDS_TROPHY_LONG_LABELS.get(trophy_id, trophy_id)
            trophy_count = inventory.get(trophy_id, 0)
            trophy_label = f"{trophy_long}: {trophy_count}"
        else:
            trophy_label = ""

        if attunement_count > 0 and trophy_id is not None:
            starting_grant_label = (
                f"Run-start trophies: +{attunement_count}"
            )
        else:
            starting_grant_label = ""

        rows.append(
            RecordsBiomeRowView(
                dungeon_name=dungeon["name"],
                terrain_label=f"Terrain: {terrain.capitalize()}",
                completion_label=f"Completions: {completion_count}",
                attunement_label=attune_label,
                next_attunement_label=next_attune_label,
                trophy_label=trophy_label,
                starting_grant_label=starting_grant_label,
            )
        )

    keystone_count = getattr(progress, "meta_keystones", 0)
    if keystone_count > 0:
        bonus = progress.keystone_starting_coin_bonus()
        keystone_summary = (
            f"Prismatic Keystones: {keystone_count} / "
            f"{KEYSTONE_MAX_OWNED} (+{bonus} coins/run)"
        )
    else:
        keystone_summary = (
            f"Prismatic Keystones: 0 / {KEYSTONE_MAX_OWNED} (none crafted)"
        )

    lifetime = sum(completions.values())
    trophy_total = sum(inventory.get(tid, 0) for tid in TERRAIN_TROPHY_IDS.values())
    totals_summary = (
        f"Lifetime completions: {lifetime}   |   "
        f"Trophies in stockpile: {trophy_total}"
    )

    return RecordsView(
        title="Records",
        biome_rows=tuple(rows),
        keystone_summary=keystone_summary,
        totals_summary=totals_summary,
        back_label="Back",
        footer_hint="Press ESC or Enter to return",
    )


def build_pause_screen_view(screen):
    return PauseScreenView(
        title="Paused",
        options=tuple(screen.option_labels()),
        selected_index=screen.selected,
        warning_text="F3 or the pause menu toggles the room identifier. Quitting loses level progress.",
    )


def build_level_complete_screen_view(screen):
    options = tuple(screen._active_options())
    selected_index = min(screen.selected, max(0, len(options) - 1))
    return LevelCompleteScreenView(
        dungeon_name=screen.dungeon_name,
        detail_lines=tuple(screen.detail_lines),
        options=options,
        selected_index=selected_index,
    )


@dataclass(frozen=True)
class RuneAltarPickCardView:
    name: str
    category_label: str
    slot_status: str
    bonus_text: str
    tradeoff_text: str


@dataclass(frozen=True)
class RuneAltarPickView:
    title: str
    subtitle: str
    cards: tuple[RuneAltarPickCardView, ...]
    selected_index: int
    empty_message: str
    footer_hint: str


def build_rune_altar_pick_view(screen, progress):
    cards = []
    equipped = getattr(progress, "equipped_runes", {}) or {}
    for rune_id in screen.offered_rune_ids:
        rune = RUNE_DATABASE.get(rune_id)
        if rune is None:
            continue
        category_runes = equipped.get(rune.category, [])
        capacity = RUNE_SLOT_CAPACITY.get(rune.category, 0)
        if len(category_runes) >= capacity and category_runes:
            displaced = RUNE_DATABASE.get(category_runes[0])
            displaced_name = displaced.name if displaced else category_runes[0]
            slot_status = f"Slot full — replaces {displaced_name}"
        else:
            slot_status = f"Slot {len(category_runes) + 1}/{capacity}"
        cards.append(
            RuneAltarPickCardView(
                name=rune.name,
                category_label=f"{rune.category.title()} Rune",
                slot_status=slot_status,
                bonus_text=f"+ {rune.bonus_text}",
                tradeoff_text=f"– {rune.tradeoff_text}",
            )
        )
    return RuneAltarPickView(
        title="Rune Altar",
        subtitle="Choose one rune. Picking is permanent for this run.",
        cards=tuple(cards),
        selected_index=min(screen.selected, max(0, len(cards) - 1)),
        empty_message="No runes available.",
        footer_hint="Left/Right: select  Enter: equip  Esc: cancel",
    )