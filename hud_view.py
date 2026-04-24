"""Projection helpers that turn runtime game state into HUD render data."""

from dataclasses import dataclass

import pygame
from settings import COLOR_COIN, COLOR_HEALTH_BAR, COLOR_PORTAL, COLOR_WHITE

import consumable_rules
import ability_rules
import behavior_runes
import dodge_rules
import identity_runes
import rune_rules
import tool_rules
from rune_catalog import RUNE_CATEGORIES, RUNE_DATABASE


@dataclass(frozen=True)
class WeaponHUDView:
    label: str
    selected: bool


@dataclass(frozen=True)
class MinimapRoomHUDView:
    position: tuple[int, int]
    kind: str
    objective_marker: tuple[str, str] | None
    door_kinds: dict[str, str]


@dataclass(frozen=True)
class MinimapHUDView:
    radius: int
    rooms: tuple[MinimapRoomHUDView, ...]


@dataclass(frozen=True)
class QuickBarHUDView:
    selected_potion_name: str
    selected_potion_count: int
    speed_boost_count: int
    attack_boost_count: int
    compass_uses: int


@dataclass(frozen=True)
class ActiveEffectHUDView:
    name: str
    seconds_remaining: float
    kind: str


@dataclass(frozen=True)
class CompassHUDView:
    visible: bool
    label: str


@dataclass(frozen=True)
class ObjectiveHUDView:
    visible: bool
    label: str


@dataclass(frozen=True)
class RoomIdentifierHUDView:
    visible: bool
    title: str
    detail: str


@dataclass(frozen=True)
class EquippedRuneHUDView:
    name: str
    category: str
    short_label: str


@dataclass(frozen=True)
class EquippedRunesHUDView:
    runes: tuple[EquippedRuneHUDView, ...]


@dataclass(frozen=True)
class RuneMeterHUDView:
    visible: bool
    label: str
    fill_fraction: float
    kind: str  # "time_anchor" | "static_charge" | "glass_soul_iframe"


@dataclass(frozen=True)
class RuneMetersHUDView:
    time_anchor: RuneMeterHUDView
    static_charge: RuneMeterHUDView
    glass_soul_iframe: RuneMeterHUDView


@dataclass(frozen=True)
class DodgeHUDView:
    ready: bool
    active: bool
    cooldown_fraction: float  # 0.0 ready → 1.0 just triggered


@dataclass(frozen=True)
class AbilityHUDView:
    equipped: bool
    label: str
    ready: bool
    cooldown_fraction: float


@dataclass(frozen=True)
class OverlayHUDView:
    title: str
    title_color: tuple[int, int, int]
    detail_text: str | None
    detail_color: tuple[int, int, int]
    prompt_text: str
    prompt_color: tuple[int, int, int]


@dataclass(frozen=True)
class HUDView:
    current_hp: int
    max_hp: int
    armor_hp: int
    coins: int
    weapons: tuple[WeaponHUDView, ...]
    minimap: MinimapHUDView
    quick_bar: QuickBarHUDView
    active_effects: tuple[ActiveEffectHUDView, ...]
    compass: CompassHUDView
    objective: ObjectiveHUDView
    room_identifier: RoomIdentifierHUDView
    equipped_runes: EquippedRunesHUDView
    rune_meters: RuneMetersHUDView
    dodge: DodgeHUDView
    ability: AbilityHUDView


def build_hud_view(player, dungeon, now_ticks=None, show_room_identifier=False):
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()

    return HUDView(
        current_hp=player.current_hp,
        max_hp=player.max_hp,
        armor_hp=player.armor_hp,
        coins=player.coins,
        weapons=_build_weapon_views(player),
        minimap=_build_minimap_view(dungeon),
        quick_bar=_build_quick_bar_view(player),
        active_effects=_build_active_effects(player, now_ticks),
        compass=_build_compass_view(player, now_ticks),
        objective=_build_objective_view(dungeon, now_ticks),
        room_identifier=_build_room_identifier_view(
            dungeon,
            now_ticks,
            show_room_identifier,
        ),
        equipped_runes=_build_equipped_runes_view(player),
        rune_meters=_build_rune_meters_view(player, now_ticks),
        dodge=_build_dodge_view(player, now_ticks),
        ability=_build_ability_view(player, now_ticks),
    )


def build_game_over_overlay_view():
    return OverlayHUDView(
        title="GAME OVER",
        title_color=COLOR_HEALTH_BAR,
        detail_text=None,
        detail_color=COLOR_WHITE,
        prompt_text="Press R to return to menu",
        prompt_color=COLOR_WHITE,
    )


def build_victory_overlay_view(coins_collected):
    return OverlayHUDView(
        title="DUNGEON CLEARED!",
        title_color=COLOR_PORTAL,
        detail_text=f"Coins collected: {coins_collected}",
        detail_color=COLOR_COIN,
        prompt_text="Press R to return to menu",
        prompt_color=COLOR_WHITE,
    )


def _build_weapon_views(player):
    if not player.weapons:
        return ()

    views = []
    for index, weapon in enumerate(player.weapons):
        label = f"[{index + 1}] {weapon.name}"
        weapon_id = player.weapon_ids[index] if index < len(player.weapon_ids) else None
        tier = player.weapon_upgrade_tier(weapon_id)
        if tier > 0:
            label += f" +{tier}"
        views.append(WeaponHUDView(label=label, selected=index == player.current_weapon_index))
    return tuple(views)


def _build_minimap_view(dungeon):
    snapshot = dungeon.minimap_snapshot()
    rooms = tuple(
        MinimapRoomHUDView(
            position=room["pos"],
            kind=room["kind"],
            objective_marker=room.get("objective_marker"),
            door_kinds=dict(room["door_kinds"]),
        )
        for room in snapshot["rooms"]
    )
    return MinimapHUDView(radius=snapshot["radius"], rooms=rooms)


def _build_quick_bar_view(player):
    inventory = player.progress.inventory if player.progress else {}
    selected_size = player.selected_potion_size
    potion_id = consumable_rules.POTION_ITEM_IDS[selected_size]
    return QuickBarHUDView(
        selected_potion_name=f"{selected_size.capitalize()} Potion",
        selected_potion_count=inventory.get(potion_id, 0),
        speed_boost_count=inventory.get("speed_boost", 0),
        attack_boost_count=inventory.get("attack_boost", 0),
        compass_uses=player.compass_uses,
    )


def _build_active_effects(player, now_ticks):
    effects = []
    if now_ticks < player.speed_boost_until:
        effects.append(
            ActiveEffectHUDView(
                name="Speed Boost",
                seconds_remaining=max(0, player.speed_boost_until - now_ticks) / 1000,
                kind="speed",
            )
        )
    if now_ticks < player.attack_boost_until:
        effects.append(
            ActiveEffectHUDView(
                name="Attack Boost",
                seconds_remaining=max(0, player.attack_boost_until - now_ticks) / 1000,
                kind="attack",
            )
        )
    return tuple(effects)


def _build_compass_view(player, now_ticks):
    visible = tool_rules.compass_showing(player, now_ticks)
    if not visible:
        return CompassHUDView(visible=False, label="")

    prefix = getattr(player, "compass_target_label", "Portal")
    label_suffix = " ".join(
        part for part in (player.compass_direction or "", player.compass_arrow or "") if part
    )
    return CompassHUDView(visible=True, label=f"{prefix}: {label_suffix}".strip())


def _build_objective_view(dungeon, now_ticks):
    room = getattr(dungeon, "current_room", None)
    if room is None or not hasattr(room, "objective_hud_state"):
        return ObjectiveHUDView(visible=False, label="")

    state = room.objective_hud_state(now_ticks)
    return ObjectiveHUDView(
        visible=bool(state.get("visible")),
        label=state.get("label", ""),
    )


def _build_room_identifier_view(dungeon, now_ticks, show_room_identifier):
    if not show_room_identifier:
        return RoomIdentifierHUDView(visible=False, title="", detail="")

    room = getattr(dungeon, "current_room", None)
    if room is None or not hasattr(room, "playtest_identifier_state"):
        return RoomIdentifierHUDView(visible=False, title="", detail="")

    state = room.playtest_identifier_state(now_ticks)
    return RoomIdentifierHUDView(
        visible=bool(state.get("visible")),
        title=state.get("title", ""),
        detail=state.get("detail", ""),
    )


_RUNE_CATEGORY_SHORT = {
    "stat":     "S",
    "behavior": "B",
    "identity": "I",
}


def _build_equipped_runes_view(player):
    loadout = rune_rules.equipped_runes(player)
    runes = []
    for category in RUNE_CATEGORIES:
        for rune_id in loadout.get(category, ()):
            rune = RUNE_DATABASE.get(rune_id)
            if rune is None:
                continue
            short = _RUNE_CATEGORY_SHORT.get(category, "?")
            runes.append(
                EquippedRuneHUDView(
                    name=rune.name,
                    category=category,
                    short_label=f"[{short}] {rune.name}",
                )
            )
    return EquippedRunesHUDView(runes=tuple(runes))


_HIDDEN_RUNE_METER = RuneMeterHUDView(
    visible=False, label="", fill_fraction=0.0, kind=""
)


def _build_rune_meters_view(player, now_ticks):
    # Time Anchor patience meter
    if rune_rules.has_rune(player, "time_anchor"):
        meter = max(0.0, min(1.0, identity_runes.time_anchor_meter(player)))
        time_anchor = RuneMeterHUDView(
            visible=True,
            label=("Time Anchor READY" if meter >= 1.0 else "Time Anchor"),
            fill_fraction=meter,
            kind="time_anchor",
        )
    else:
        time_anchor = _HIDDEN_RUNE_METER

    # Static Charge meter
    if rune_rules.has_rune(player, "static_charge"):
        charge = max(0.0, min(1.0, behavior_runes.static_charge_value(player)))
        static_charge = RuneMeterHUDView(
            visible=True,
            label=("Static Charge FULL" if charge >= 1.0 else "Static Charge"),
            fill_fraction=charge,
            kind="static_charge",
        )
    else:
        static_charge = _HIDDEN_RUNE_METER

    # Glass Soul i-frame countdown
    if rune_rules.has_rune(player, "glass_soul"):
        until = int(getattr(player, "_invincible_until", 0) or 0)
        remaining_ms = max(0, until - int(now_ticks))
        if remaining_ms > 0:
            fraction = min(
                1.0, remaining_ms / float(identity_runes.GLASS_SOUL_INVINCIBLE_MS)
            )
            glass_soul = RuneMeterHUDView(
                visible=True,
                label=f"i-frames {remaining_ms / 1000:.1f}s",
                fill_fraction=fraction,
                kind="glass_soul_iframe",
            )
        else:
            glass_soul = RuneMeterHUDView(
                visible=True,
                label="Glass Soul",
                fill_fraction=0.0,
                kind="glass_soul_iframe",
            )
    else:
        glass_soul = _HIDDEN_RUNE_METER

    return RuneMetersHUDView(
        time_anchor=time_anchor,
        static_charge=static_charge,
        glass_soul_iframe=glass_soul,
    )


def _build_dodge_view(player, now_ticks):
    return DodgeHUDView(
        ready=dodge_rules.can_dodge(player, now_ticks),
        active=dodge_rules.is_dodging(player, now_ticks),
        cooldown_fraction=dodge_rules.cooldown_fraction_remaining(player, now_ticks),
    )


def _build_ability_view(player, now_ticks):
    ability_id = getattr(player, "active_ability_id", None)
    return AbilityHUDView(
        equipped=ability_rules.has_ability(player),
        label=ability_id or "",
        ready=ability_rules.can_activate(player, now_ticks),
        cooldown_fraction=ability_rules.cooldown_fraction_remaining(player, now_ticks),
    )