"""Projection helpers that turn runtime game state into HUD render data."""

from dataclasses import dataclass

import pygame
from settings import (
    COLOR_COIN, COLOR_HEALTH_BAR, COLOR_PORTAL, COLOR_WHITE,
    CHILL_MAX, COLOR_CHILL_METER, COLOR_CHILL_METER_BG, COLOR_CHILL_METER_PULSE,
)

import consumable_rules
import ability_rules
import behavior_runes
import damage_feedback
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
    objective_status: str | None = None


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
    stat_shard_count: int = 0
    tempo_rune_count: int = 0
    mobility_charge_count: int = 0
    spark_charge_count: int = 0


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
    extraction_bonus_visible: bool = False
    extraction_bonus_amount: int = 0
    carrying_heartstone: bool = False


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
class EntityHealthBarHUDView:
    rect: pygame.Rect
    current_hp: int
    max_hp: int


@dataclass(frozen=True)
class DamageNumberHUDView:
    text: str
    world_pos: tuple[int, int]
    age_fraction: float
    color: tuple = (255, 255, 255)


@dataclass(frozen=True)
class BiomeRewardFlashHUDView:
    kind: str  # "stat_shard" | "tempo_rune" | "mobility_charge"
    world_pos: tuple[int, int]
    age_fraction: float


@dataclass(frozen=True)
class KeystoneBonusBannerHUDView:
    text: str
    age_fraction: float


@dataclass(frozen=True)
class BossHealthBarHUDView:
    name: str
    current_hp: int
    max_hp: int
    phase: int


@dataclass(frozen=True)
class BossIntroBannerHUDView:
    text: str
    age_fraction: float


@dataclass(frozen=True)
class OverlayHUDView:
    title: str
    title_color: tuple[int, int, int]
    detail_text: str | None
    detail_color: tuple[int, int, int]
    prompt_text: str
    prompt_color: tuple[int, int, int]


@dataclass(frozen=True)
class StatusMeterHUDView:
    """A single status-accumulator bar (e.g. the Chill meter)."""
    meter_id: str           # stable identifier, e.g. "chill"
    label: str              # short display label, e.g. "CHILL"
    value: float            # current level 0.0–max
    max_value: float        # 100.0 for chill
    fill_color: tuple       # RGB fill
    bg_color: tuple         # RGB background track
    pulse_color: tuple      # RGB tint when nearly full (≥ 75 %)
    pulsing: bool           # True when fill ≥ 75 % of max


@dataclass(frozen=True)
class StatusMetersHUDView:
    """Collection of all active status-accumulator meters."""
    meters: tuple  # tuple[StatusMeterHUDView, ...]


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
    entity_health_bars: tuple[EntityHealthBarHUDView, ...]
    damage_numbers: tuple[DamageNumberHUDView, ...]
    biome_reward_flashes: tuple[BiomeRewardFlashHUDView, ...]
    keystone_bonus_banner: KeystoneBonusBannerHUDView | None = None
    boss_health_bar: BossHealthBarHUDView | None = None
    boss_intro_banner: BossIntroBannerHUDView | None = None
    status_meters: StatusMetersHUDView | None = None


def build_hud_view(player, dungeon, now_ticks=None, show_room_identifier=False):
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()

    entity_groups = (
        getattr(dungeon, "enemy_group", None),
        getattr(dungeon, "ally_group", None),
        getattr(dungeon, "objective_group", None),
    )
    entity_bar_data = damage_feedback.build_entity_health_bar_views(
        entity_groups, exclude=(player,)
    )
    entity_health_bars = tuple(
        EntityHealthBarHUDView(rect=rect, current_hp=current_hp, max_hp=max_hp)
        for rect, current_hp, max_hp in entity_bar_data
    )
    damage_numbers = tuple(
        DamageNumberHUDView(text=text, world_pos=tuple(world_pos), age_fraction=age, color=color)
        for text, world_pos, age, color in damage_feedback.build_damage_number_views(now_ticks)
    )
    biome_reward_flashes = tuple(
        BiomeRewardFlashHUDView(kind=kind, world_pos=tuple(world_pos), age_fraction=age)
        for kind, world_pos, age in damage_feedback.build_biome_reward_flash_views(now_ticks)
    )
    banner_data = damage_feedback.build_keystone_bonus_banner_view(now_ticks)
    keystone_bonus_banner = (
        KeystoneBonusBannerHUDView(
            text=banner_data[0],
            age_fraction=banner_data[1],
        )
        if banner_data is not None
        else None
    )

    boss_controller = getattr(dungeon, "boss_controller", None)
    boss_health_bar = None
    if boss_controller is not None:
        boss = getattr(boss_controller, "boss", None)
        if boss is not None and not getattr(boss_controller, "defeated", False):
            boss_health_bar = BossHealthBarHUDView(
                name=getattr(boss_controller, "name", "") or "",
                current_hp=int(getattr(boss, "current_hp", 0)),
                max_hp=max(1, int(getattr(boss, "max_hp", 1))),
                phase=int(getattr(boss_controller, "current_phase", 1)),
            )
    boss_intro_data = damage_feedback.build_boss_intro_banner_view(now_ticks)
    boss_intro_banner = (
        BossIntroBannerHUDView(
            text=boss_intro_data[0],
            age_fraction=boss_intro_data[1],
        )
        if boss_intro_data is not None
        else None
    )

    return HUDView(
        current_hp=player.current_hp,
        max_hp=player.max_hp,
        armor_hp=player.armor_hp,
        coins=player.coins,
        weapons=_build_weapon_views(player),
        minimap=_build_minimap_view(dungeon, now_ticks),
        quick_bar=_build_quick_bar_view(player),
        active_effects=_build_active_effects(player, now_ticks),
        compass=_build_compass_view(player, now_ticks),
        objective=_build_objective_view(player, dungeon, now_ticks),
        room_identifier=_build_room_identifier_view(
            dungeon,
            now_ticks,
            show_room_identifier,
        ),
        equipped_runes=_build_equipped_runes_view(player),
        rune_meters=_build_rune_meters_view(player, now_ticks),
        dodge=_build_dodge_view(player, now_ticks),
        ability=_build_ability_view(player, now_ticks),
        entity_health_bars=entity_health_bars,
        damage_numbers=damage_numbers,
        biome_reward_flashes=biome_reward_flashes,
        keystone_bonus_banner=keystone_bonus_banner,
        boss_health_bar=boss_health_bar,
        boss_intro_banner=boss_intro_banner,
        status_meters=_build_status_meters_view(player),
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


def _build_minimap_view(dungeon, now_ticks=None):
    snapshot = dungeon.minimap_snapshot(now_ticks)
    rooms = tuple(
        MinimapRoomHUDView(
            position=room["pos"],
            kind=room["kind"],
            objective_marker=room.get("objective_marker"),
            door_kinds=dict(room["door_kinds"]),
            objective_status=room.get("objective_status"),
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
        stat_shard_count=inventory.get("stat_shard", 0),
        tempo_rune_count=inventory.get("tempo_rune", 0),
        mobility_charge_count=inventory.get("mobility_charge", 0),
        spark_charge_count=inventory.get("spark_charge", 0),
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
    if now_ticks < getattr(player, "spark_until", 0):
        effects.append(
            ActiveEffectHUDView(
                name="Spark Charge",
                seconds_remaining=max(0, player.spark_until - now_ticks) / 1000,
                kind="spark",
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


def _build_objective_view(player, dungeon, now_ticks):
    room = getattr(dungeon, "current_room", None)
    if room is None or not hasattr(room, "objective_hud_state"):
        return ObjectiveHUDView(visible=False, label="")

    state = room.objective_hud_state(now_ticks)
    bonus_visible = False
    bonus_amount = 0
    if hasattr(room, "timed_extraction_bonus_state"):
        bonus = room.timed_extraction_bonus_state()
        if bonus is not None and bonus.get("available"):
            bonus_visible = True
            bonus_amount = int(bonus.get("amount", 0))
    carrying = bool(getattr(player, "carrying_heartstone", False))
    return ObjectiveHUDView(
        visible=bool(state.get("visible")),
        label=state.get("label", ""),
        extraction_bonus_visible=bonus_visible,
        extraction_bonus_amount=bonus_amount,
        carrying_heartstone=carrying,
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


def _build_status_meters_view(player):
    """Build the status-accumulator meters view for the HUD rail.

    Currently only the Chill meter is tracked.  Future accumulators (e.g.
    a Bleed meter, an Exhaustion meter) should add their own
    ``StatusMeterHUDView`` to the *meters* tuple here.

    Returns ``None`` if no meters are active (chill == 0 and nothing else),
    keeping the HUD clean during normal play.
    """
    meters = []

    chill = float(getattr(player, "chill", 0.0))
    if chill > 0.0:
        pulsing = chill >= CHILL_MAX * 0.75
        meters.append(StatusMeterHUDView(
            meter_id="chill",
            label="CHILL",
            value=chill,
            max_value=CHILL_MAX,
            fill_color=COLOR_CHILL_METER,
            bg_color=COLOR_CHILL_METER_BG,
            pulse_color=COLOR_CHILL_METER_PULSE,
            pulsing=pulsing,
        ))

    if not meters:
        return None
    return StatusMetersHUDView(meters=tuple(meters))