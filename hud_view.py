"""Projection helpers that turn runtime game state into HUD render data."""

from dataclasses import dataclass

import pygame
from settings import COLOR_COIN, COLOR_HEALTH_BAR, COLOR_PORTAL, COLOR_WHITE

import consumable_rules
import tool_rules


@dataclass(frozen=True)
class WeaponHUDView:
    label: str
    selected: bool


@dataclass(frozen=True)
class MinimapRoomHUDView:
    position: tuple[int, int]
    kind: str
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


def build_hud_view(player, dungeon, now_ticks=None):
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

    label_suffix = " ".join(
        part for part in (player.compass_direction or "", player.compass_arrow or "") if part
    )
    return CompassHUDView(visible=True, label=f"Portal: {label_suffix}".strip())