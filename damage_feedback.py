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


# ── tunables ────────────────────────────────────────────
DAMAGE_NUMBER_LIFETIME_MS = 800
DAMAGE_NUMBER_COALESCE_WINDOW_MS = 250
DAMAGE_NUMBER_RISE_PIXELS = 28


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
    __slots__ = ("entity_id", "amount", "spawn_ticks", "world_pos")

    def __init__(self, entity_id, amount, spawn_ticks, world_pos):
        self.entity_id = entity_id
        self.amount = amount
        self.spawn_ticks = spawn_ticks
        self.world_pos = world_pos


class DamageNumberTracker:
    """Floating damage numbers; coalesces same-entity hits within a window."""

    def __init__(self):
        self._numbers = []

    def report(self, entity, amount, world_pos, now_ticks):
        if amount <= 0:
            return
        entity_id = id(entity)
        for existing in self._numbers:
            if existing.entity_id != entity_id:
                continue
            age = now_ticks - existing.spawn_ticks
            if 0 <= age <= DAMAGE_NUMBER_COALESCE_WINDOW_MS:
                existing.amount += amount
                existing.spawn_ticks = now_ticks
                existing.world_pos = world_pos
                return
        self._numbers.append(
            _ActiveNumber(entity_id, amount, now_ticks, world_pos)
        )

    def active(self, now_ticks):
        """Yield (text, world_pos, age_fraction) tuples for live numbers.

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
                (str(number.amount), number.world_pos, age / DAMAGE_NUMBER_LIFETIME_MS)
            )
        self._numbers = kept
        return out

    def reset(self):
        self._numbers.clear()


# ── module singletons ──────────────────────────────────
_health_bar_tracker = HealthBarTracker()
_damage_number_tracker = DamageNumberTracker()


def get_health_bar_tracker():
    return _health_bar_tracker


def get_damage_number_tracker():
    return _damage_number_tracker


def reset_all():
    """Clear both trackers (call when starting a new dungeon/room test)."""
    _health_bar_tracker.reset()
    _damage_number_tracker.reset()


# ── public API ─────────────────────────────────────────
def report_damage(entity, amount, world_pos=None, now_ticks=None):
    """Record that *entity* lost *amount* HP/armor this frame.

    Marks the entity as "has been damaged" for health-bar visibility and
    pushes a floating damage number anchored at *world_pos* (defaults to
    ``entity.rect.center``).
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
    _damage_number_tracker.report(entity, int(amount), tuple(world_pos), now_ticks)


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
    """Project active damage numbers as ``(text, world_pos, age_fraction)``."""
    if now_ticks is None:
        now_ticks = pygame.time.get_ticks()
    return tuple(_damage_number_tracker.active(now_ticks))
