"""Universal damage feedback: per-entity health-bar tracking and floating
damage numbers.

Other modules call :func:`report_damage` whenever an entity actually loses
HP/armor.  This module owns two singleton trackers:

* :class:`HealthBarTracker` — remembers which entities have been damaged at
  least once so the HUD knows which world-space health bars to draw.
* :class:`DamageNumberTracker` — collects floating numbers anchored to the
  hit position.  Repeat hits on the same entity within a short coalesce
  window are summed into the existing on-screen number (its position and
  spawn time are reset so the new sum floats afresh).

The HUD reads from these trackers via :func:`build_entity_health_bar_views`
and :func:`build_damage_number_views` to project render data.
"""

import pygame
from settings import DAMAGE_TYPE_COLORS

# Default color for untyped (terrain, status DoT) damage numbers.
_DEFAULT_DAMAGE_COLOR = (255, 255, 255)  # white


def _color_for_type(damage_type):
    if damage_type is None:
        return _DEFAULT_DAMAGE_COLOR
    return DAMAGE_TYPE_COLORS.get(damage_type, _DEFAULT_DAMAGE_COLOR)


# ── tunables ────────────────────────────────────────────
DAMAGE_NUMBER_LIFETIME_MS = 800
DAMAGE_NUMBER_COALESCE_WINDOW_MS = 250
DAMAGE_NUMBER_RISE_PIXELS = 28
BIOME_REWARD_FLASH_LIFETIME_MS = 600
BIOME_REWARD_FLASH_MAX_RADIUS = 48
KEYSTONE_BONUS_BANNER_LIFETIME_MS = 2400
BOSS_INTRO_BANNER_LIFETIME_MS = 2500

# Biome challenge-route reward activation flashes share the icon colors used
# by their item-catalog entries and the HUD quick-bar badges, so the spend
# feedback reads as the same trophy at all three surfaces.
BIOME_REWARD_FLASH_COLORS = {
    "stat_shard": (200, 140, 70),
    "tempo_rune": (160, 210, 255),
    "mobility_charge": (90, 230, 200),
}


# ── trackers ────────────────────────────────────────────
class HealthBarTracker:
    """Set of entity ids that have taken at least one point of damage."""

    def __init__(self):
        self._damaged_ids = set()

    def mark_damaged(self, entity):
        self._damaged_ids.add(id(entity))

    def is_damaged(self, entity):
        return id(entity) in self._damaged_ids

    def reset(self):
        self._damaged_ids.clear()


class _ActiveNumber:
    __slots__ = ("entity_id", "amount", "spawn_ticks", "world_pos", "color")

    def __init__(self, entity_id, amount, spawn_ticks, world_pos, color=None):
        self.entity_id = entity_id
        self.amount = amount
        self.spawn_ticks = spawn_ticks
        self.world_pos = world_pos
        self.color = color if color is not None else _DEFAULT_DAMAGE_COLOR


class DamageNumberTracker:
    """Floating damage numbers; coalesces same-entity hits within a window."""

    def __init__(self):
        self._numbers = []

    def report(self, entity, amount, world_pos, now_ticks, damage_type=None):
        if amount <= 0:
            return
        color = _color_for_type(damage_type)
        entity_id = id(entity)
        for existing in self._numbers:
            if existing.entity_id != entity_id:
                continue
            age = now_ticks - existing.spawn_ticks
            if 0 <= age <= DAMAGE_NUMBER_COALESCE_WINDOW_MS:
                existing.amount += amount
                existing.spawn_ticks = now_ticks
                existing.world_pos = world_pos
                # Keep the most recent hit's color when coalescing.
                existing.color = color
                return
        self._numbers.append(
            _ActiveNumber(entity_id, amount, now_ticks, world_pos, color)
        )

    def active(self, now_ticks):
        """Yield (text, world_pos, age_fraction, color) tuples for live numbers.

        ``age_fraction`` is in ``[0.0, 1.0)`` and grows as the number ages.
        Expired numbers are dropped from the tracker.
        """
        kept = []
        out = []
        for number in self._numbers:
            age = now_ticks - number.spawn_ticks
            if age < 0 or age >= DAMAGE_NUMBER_LIFETIME_MS:
                continue
            kept.append(number)
            out.append(
                (str(number.amount), number.world_pos, age / DAMAGE_NUMBER_LIFETIME_MS, number.color)
            )
        self._numbers = kept
        return out

    def reset(self):
        self._numbers.clear()


# ── module singletons ──────────────────────────────────
_health_bar_tracker = HealthBarTracker()
_damage_number_tracker = DamageNumberTracker()


class _ActiveFlash:
    __slots__ = ("kind", "world_pos", "spawn_ticks")

    def __init__(self, kind, world_pos, spawn_ticks):
        self.kind = kind
        self.world_pos = world_pos
        self.spawn_ticks = spawn_ticks


class BiomeRewardFlashTracker:
    """Brief expanding-ring flashes anchored to the spending entity.

    Used to give the player a short visual confirmation when a biome-themed
    challenge-route trophy (stat_shard / tempo_rune / mobility_charge) is
    spent.  Each flash fades over ``BIOME_REWARD_FLASH_LIFETIME_MS``.
    """

    def __init__(self):
        self._flashes = []

    def report(self, kind, world_pos, now_ticks):
        if kind not in BIOME_REWARD_FLASH_COLORS:
            return
        self._flashes.append(_ActiveFlash(kind, tuple(world_pos), now_ticks))

    def active(self, now_ticks):
        """Yield ``(kind, world_pos, age_fraction)`` triples for live flashes."""
        kept = []
        out = []
        for flash in self._flashes:
            age = now_ticks - flash.spawn_ticks
            if age < 0 or age >= BIOME_REWARD_FLASH_LIFETIME_MS:
                continue
            kept.append(flash)
            out.append((flash.kind, flash.world_pos, age / BIOME_REWARD_FLASH_LIFETIME_MS))
        self._flashes = kept
        return out

    def reset(self):
        self._flashes.clear()


_biome_reward_flash_tracker = BiomeRewardFlashTracker()


class KeystoneBonusBannerTracker:
    """Single-shot HUD banner used for keystone-related notifications:
    the per-run starting-coin bonus and the shop craft toast.  Holds at
    most one active banner at a time — re-reporting replaces it.
    """

    def __init__(self):
        self._spawn_ticks = None
        self._text = ""

    def report(self, text, now_ticks):
        if not text:
            return
        self._text = str(text)
        self._spawn_ticks = now_ticks

    def active(self, now_ticks):
        """Return ``(text, age_fraction)`` or ``None`` if no live banner."""
        if self._spawn_ticks is None:
            return None
        age = now_ticks - self._spawn_ticks
        if age < 0 or age >= KEYSTONE_BONUS_BANNER_LIFETIME_MS:
            self._spawn_ticks = None
            self._text = ""
            return None
        return (self._text, age / KEYSTONE_BONUS_BANNER_LIFETIME_MS)

    def reset(self):
        self._spawn_ticks = None
        self._text = ""


_keystone_bonus_banner_tracker = KeystoneBonusBannerTracker()


def get_keystone_bonus_banner_tracker():
    return _keystone_bonus_banner_tracker


class BossIntroBannerTracker:
    """Single-shot top-screen banner announcing a mini-boss encounter.

    Mirrors :class:`KeystoneBonusBannerTracker`: holds at most one active
    banner; re-reporting replaces it; expires automatically after
    ``BOSS_INTRO_BANNER_LIFETIME_MS``.
    """

    def __init__(self):
        self._spawn_ticks = None
        self._text = ""

    def report(self, text, now_ticks):
        if not text:
            return
        self._text = str(text)
        self._spawn_ticks = now_ticks

    def active(self, now_ticks):
        """Return ``(text, age_fraction)`` or ``None`` if no live banner."""
        if self._spawn_ticks is None:
            return None
        age = now_ticks - self._spawn_ticks
        if age < 0 or age >= BOSS_INTRO_BANNER_LIFETIME_MS:
            self._spawn_ticks = None
            self._text = ""
            return None
        return (self._text, age / BOSS_INTRO_BANNER_LIFETIME_MS)

    def reset(self):
        self._spawn_ticks = None
        self._text = ""


_boss_intro_banner_tracker = BossIntroBannerTracker()


def get_boss_intro_banner_tracker():
    return _boss_intro_banner_tracker


def report_keystone_starting_bonus(amount, now_ticks=None):
    """Queue the once-per-run keystone starting-coin bonus banner."""
    if amount <= 0:
        return
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    _keystone_bonus_banner_tracker.report(
        f"+{int(amount)} keystone coins", now_ticks
    )


def report_keystone_craft_toast(owned, max_owned, next_run_bonus, now_ticks=None):
    """Queue the shop craft confirmation toast.

    Reuses the keystone bonus banner slot — same lifetime, same render —
    so the player gets immediate feedback after spending trophies.  The
    `next_run_bonus` is the *new total* coin bonus the player will earn
    on their next dungeon run (see `PlayerProgress.keystone_starting_coin_bonus`).
    """
    if owned <= 0:
        return
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    text = f"Keystone {int(owned)}/{int(max_owned)} crafted!  Next run: +{int(next_run_bonus)} coins"
    _keystone_bonus_banner_tracker.report(text, now_ticks)


def build_keystone_bonus_banner_view(now_ticks=None):
    """Project the active banner as ``(text, age_fraction)`` or ``None``."""
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    return _keystone_bonus_banner_tracker.active(now_ticks)


def report_hunter_detected(now_ticks=None):
    """Queue the 'HUNTER DETECTED' encounter banner for Danger Mode."""
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    _boss_intro_banner_tracker.report("HUNTER DETECTED", now_ticks)


def report_boss_intro(name, now_ticks=None):
    """Queue the mini-boss intro banner shown on encounter start."""
    if not name:
        return
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    _boss_intro_banner_tracker.report(str(name), now_ticks)


def report_boss_loot(item_name, now_ticks=None):
    """Queue a "{name} acquired" banner after a boss-loot drop.

    Reuses the keystone bonus banner slot (same lifetime + render) so the
    player gets the same prominent toast as keystone awards.  When two
    drops land on the same tick, the second clobbers the first — an
    accepted tradeoff for keeping the single-slot tracker simple.
    """
    if not item_name:
        return
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    _keystone_bonus_banner_tracker.report(f"{item_name} acquired", now_ticks)


def build_boss_intro_banner_view(now_ticks=None):
    """Project the active boss intro as ``(text, age_fraction)`` or ``None``."""
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    return _boss_intro_banner_tracker.active(now_ticks)


def get_biome_reward_flash_tracker():
    return _biome_reward_flash_tracker


def report_biome_reward_flash(entity, kind, now_ticks=None):
    """Queue a spend-feedback flash anchored to *entity*'s rect center."""
    rect = getattr(entity, "rect", None)
    if rect is None:
        return
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    _biome_reward_flash_tracker.report(kind, rect.center, now_ticks)


def build_biome_reward_flash_views(now_ticks=None):
    """Project active biome-reward flashes as ``(kind, world_pos, age_fraction)``."""
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    return tuple(_biome_reward_flash_tracker.active(now_ticks))


def get_health_bar_tracker():
    return _health_bar_tracker


def get_damage_number_tracker():
    return _damage_number_tracker


def reset_all():
    """Clear both trackers (call when starting a new dungeon/room test)."""
    _health_bar_tracker.reset()
    _damage_number_tracker.reset()
    _biome_reward_flash_tracker.reset()
    _keystone_bonus_banner_tracker.reset()
    _boss_intro_banner_tracker.reset()


# ── public API ─────────────────────────────────────────
def report_damage(entity, amount, world_pos=None, now_ticks=None, damage_type=None):
    """Record that *entity* lost *amount* HP/armor this frame.

    Marks the entity as "has been damaged" for health-bar visibility and
    pushes a floating damage number anchored at *world_pos* (defaults to
    ``entity.rect.center``).  *damage_type* tints the floating number by
    the type's color from ``DAMAGE_TYPE_COLORS``.
    """
    if amount is None or amount <= 0:
        return
    if world_pos is None:
        rect = getattr(entity, "rect", None)
        if rect is None:
            return
        world_pos = rect.center
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    if _entity_has_health(entity):
        _health_bar_tracker.mark_damaged(entity)
    _damage_number_tracker.report(entity, int(amount), tuple(world_pos), now_ticks, damage_type)


def _entity_has_health(entity):
    return (
        hasattr(entity, "current_hp")
        and hasattr(entity, "max_hp")
        and getattr(entity, "max_hp", 0) > 0
    )


# ── HUD projection helpers ─────────────────────────────
def build_entity_health_bar_views(entity_groups, exclude=()):
    """Project health-bar render data for damaged entities in *entity_groups*.

    *exclude* may contain entity instances that should never receive a
    world-space bar (e.g. the player, who already has an HUD bar).
    Returns a tuple of ``(rect, current_hp, max_hp)`` triples.
    """
    excluded_ids = {id(e) for e in exclude}
    out = []
    for group in entity_groups:
        if group is None:
            continue
        for entity in group:
            if id(entity) in excluded_ids:
                continue
            if not _entity_has_health(entity):
                continue
            if entity.current_hp <= 0:
                continue
            if not _health_bar_tracker.is_damaged(entity):
                continue
            rect = getattr(entity, "rect", None)
            if rect is None:
                continue
            out.append((rect.copy(), int(entity.current_hp), int(entity.max_hp)))
    return tuple(out)


def build_damage_number_views(now_ticks=None):
    """Project active damage numbers as ``(text, world_pos, age_fraction, color)``."""
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    return tuple(_damage_number_tracker.active(now_ticks))
