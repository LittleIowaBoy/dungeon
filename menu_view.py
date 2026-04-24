"""Projection helpers for menu and overlay screen render state."""

from dataclasses import dataclass

from dungeon_config import DUNGEONS
from rune_catalog import RUNE_DATABASE, RUNE_SLOT_CAPACITY


@dataclass(frozen=True)
class MainMenuView:
    title: str
    options: tuple[str, ...]
    selected_index: int


@dataclass(frozen=True)
class DungeonCardView:
    name: str
    terrain_type: str
    status_text: str
    terrain_label: str


@dataclass(frozen=True)
class DungeonSelectView:
    title: str
    cards: tuple[DungeonCardView, ...]
    selected_index: int
    difficulty_label: str
    back_label: str


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


@dataclass(frozen=True)
class PauseScreenView:
    title: str
    options: tuple[str, ...]
    selected_index: int
    warning_text: str


@dataclass(frozen=True)
class LevelCompleteScreenView:
    dungeon_name: str
    detail_lines: tuple[str, ...]
    options: tuple[str, ...]
    selected_index: int


def build_main_menu_view(screen):
    return MainMenuView(
        title="Dungeon Crawler",
        options=tuple(screen.OPTIONS),
        selected_index=screen.selected,
    )


def build_dungeon_select_view(screen):
    from dungeon_config import DIFFICULTY_PRESETS
    cards = []
    for dungeon in DUNGEONS:
        progress = screen.progress.get_dungeon(dungeon["id"])
        if progress.completed:
            status_text = "Completed"
        else:
            status_text = "Not started"

        cards.append(
            DungeonCardView(
                name=dungeon["name"],
                terrain_type=dungeon["terrain_type"],
                status_text=status_text,
                terrain_label=f"Terrain: {dungeon['terrain_type'].capitalize()}",
            )
        )

    diff = screen.progress.difficulty_preference
    diff_label = screen.DIFFICULTY_LABELS.get(diff, diff.capitalize())

    return DungeonSelectView(
        title="Select Dungeon",
        cards=tuple(cards),
        selected_index=min(max(screen.selected, 0), len(cards)),
        difficulty_label=diff_label,
        back_label="Back",
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

    return CharacterCustomizeView(
        title="Character Loadout",
        subtitle="Select a slot, then equip from stored compatible gear.",
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
    if not items:
        return ShopView(
            title="Shop",
            coins_text=f"Coins: {screen.progress.coins}",
            items=(),
            empty_message="No items available",
            show_more_above=False,
            show_more_below=False,
            footer_hint="Press ESC to return",
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