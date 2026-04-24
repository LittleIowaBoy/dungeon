"""Identity rune effect resolution.

Identity runes are run-defining: they replace several systems wholesale
rather than nudge multipliers.  This module exposes pure-function hooks
that other modules call to query identity behaviour.

Per-run state lives at ``player.rune_state`` top level.

Runes covered
-------------
- ``the_pacifist``  — 0 outgoing damage, +100% speed, enemy-vs-enemy x5
- ``glass_soul``    — max HP locked at 1; damage → 2s i-frames; heal →
  attack-speed buff; stunned status = instant death
- ``time_anchor``   — time slows to 20% while standing still; standing
  fills a patience meter; full meter triggers a 3s enemy freeze
- ``necromancer``   — every 3rd kill flagged as ally-spawn (full ally AI
  is out of scope for this slice; flag is exposed for the engine to
  consume / for tests to assert)
- ``the_conduit``   — every hit also damages the nearest other enemy at
  40% (target keeps 60%)
"""

import rune_rules
from settings import TILE_SIZE


# ── helpers ─────────────────────────────────────────────
def _has(player, rune_id):
    return rune_rules.has_rune(player, rune_id)


def _state(player):
    state = getattr(player, "rune_state", None)
    if state is None:
        player.rune_state = {}
        state = player.rune_state
    return state


# ── the_pacifist ────────────────────────────────────────
PACIFIST_SPEED_MULTIPLIER = 2.0
PACIFIST_ENEMY_VS_ENEMY_MULTIPLIER = 5.0


def is_pacifist(player):
    return _has(player, "the_pacifist")


def pacifist_speed_multiplier(player):
    return PACIFIST_SPEED_MULTIPLIER if is_pacifist(player) else 1.0


def pacifist_outgoing_damage(player, base_damage):
    """Return 0 if the Pacifist rune is equipped, else *base_damage*."""
    if is_pacifist(player):
        return 0
    return base_damage


def pacifist_enemy_vs_enemy_multiplier(player):
    """Multiplier to advertise via ``player.rune_state`` for collisions."""
    return PACIFIST_ENEMY_VS_ENEMY_MULTIPLIER if is_pacifist(player) else 0.0


def destroy_pacifist_on_weapon_pickup(player, progress):
    """Remove the Pacifist rune when a new weapon is acquired.

    Returns True if the rune was destroyed.
    """
    if not is_pacifist(player):
        return False
    rune_rules.unequip_rune(player, "the_pacifist")
    if progress is not None:
        rune_rules.unequip_rune(progress, "the_pacifist")
    return True


# ── glass_soul ──────────────────────────────────────────
GLASS_SOUL_MAX_HP = 1
GLASS_SOUL_INVINCIBLE_MS = 2000
GLASS_SOUL_HEAL_ATK_BUFF_MS = 4000


def is_glass_soul(player):
    return _has(player, "glass_soul")


def glass_soul_max_hp(player, base_max_hp):
    return GLASS_SOUL_MAX_HP if is_glass_soul(player) else base_max_hp


def glass_soul_intercept_damage(player, amount, now_ticks):
    """Return ``(absorbed, iframe_until)`` when Glass Soul intercepts.

    ``absorbed`` is True if no HP damage should be applied; the engine
    should set the player's invincibility-until to ``iframe_until``.
    Returns (False, 0) when the rune is not equipped.
    """
    if not is_glass_soul(player) or amount <= 0:
        return (False, 0)
    return (True, now_ticks + GLASS_SOUL_INVINCIBLE_MS)


def glass_soul_intercept_heal(player, heal_amount, now_ticks):
    """Convert a heal into an attack-speed boost.

    Returns the timestamp at which ``attack_boost_until`` should be
    extended to, or 0 when the rune is inert.
    """
    if not is_glass_soul(player) or heal_amount <= 0:
        return 0
    return now_ticks + GLASS_SOUL_HEAL_ATK_BUFF_MS


def glass_soul_stun_kills(player):
    """Stunned applied while Glass Soul equipped → instant death."""
    return is_glass_soul(player)


# ── time_anchor ─────────────────────────────────────────
TIME_ANCHOR_SLOW_SCALE = 0.2
TIME_ANCHOR_METER_FILL_PER_SEC = 1.0 / 4.0      # full in 4s of stillness
TIME_ANCHOR_METER_DRAIN_PER_SEC = 1.0 / 2.0     # empties in 2s of motion
TIME_ANCHOR_FREEZE_DURATION_MS = 3000


def is_time_anchor(player):
    return _has(player, "time_anchor")


def time_anchor_meter(player):
    if not is_time_anchor(player):
        return 0.0
    return float(_state(player).get("time_anchor_meter", 0.0))


def update_time_anchor(player, dt_ms, is_moving):
    """Tick the patience meter and resolve time-scale.

    Returns ``"freeze"`` when the meter just hit full and a freeze
    should be triggered; otherwise ``None``.
    """
    if not is_time_anchor(player):
        return None
    state = _state(player)
    meter = float(state.get("time_anchor_meter", 0.0))
    seconds = dt_ms / 1000.0
    fired = None
    if is_moving:
        meter = max(0.0, meter - TIME_ANCHOR_METER_DRAIN_PER_SEC * seconds)
    else:
        meter = min(1.0, meter + TIME_ANCHOR_METER_FILL_PER_SEC * seconds)
        if meter >= 1.0 and not state.get("time_anchor_full"):
            state["time_anchor_full"] = True
            fired = "freeze"
    if meter < 1.0:
        state["time_anchor_full"] = False
    state["time_anchor_meter"] = meter
    return fired


def time_anchor_time_scale(player, is_moving):
    """Resolve the time scale Time Anchor wants to enforce this frame."""
    if not is_time_anchor(player):
        return None
    return TIME_ANCHOR_SLOW_SCALE if not is_moving else 1.0


def consume_time_anchor_freeze(player):
    """Reset the meter after a freeze fires."""
    if not is_time_anchor(player):
        return
    state = _state(player)
    state["time_anchor_meter"] = 0.0
    state["time_anchor_full"] = False


# ── necromancer ─────────────────────────────────────────
NECROMANCER_KILL_INTERVAL = 3


def is_necromancer(player):
    return _has(player, "necromancer")


def necromancer_register_kill(player):
    """Increment kill counter; return True when an ally should spawn."""
    if not is_necromancer(player):
        return False
    state = _state(player)
    count = int(state.get("necromancer_kill_count", 0)) + 1
    state["necromancer_kill_count"] = count
    if count % NECROMANCER_KILL_INTERVAL == 0:
        state["necromancer_pending_ally"] = True
        return True
    return False


def necromancer_consume_pending(player):
    if not is_necromancer(player):
        return False
    state = _state(player)
    if state.get("necromancer_pending_ally"):
        state["necromancer_pending_ally"] = False
        return True
    return False


# ── the_conduit ─────────────────────────────────────────
CONDUIT_PRIMARY_FRACTION = 0.60
CONDUIT_SPLASH_FRACTION = 0.40
CONDUIT_RADIUS = 5 * TILE_SIZE


def is_conduit(player):
    return _has(player, "the_conduit")


def conduit_split_damage(player, base_damage):
    """Return ``(primary_damage, splash_damage)`` for a hit.

    Splash is 0 when the rune is not equipped (primary keeps 100%).
    """
    if not is_conduit(player):
        return (base_damage, 0)
    primary = max(1, int(base_damage * CONDUIT_PRIMARY_FRACTION))
    splash = max(1, int(base_damage * CONDUIT_SPLASH_FRACTION))
    return (primary, splash)


def conduit_find_splash_target(player, primary, enemies):
    """Closest *other* alive enemy within radius of *primary*, else None."""
    if not is_conduit(player):
        return None
    px, py = primary.rect.center
    best = None
    best_d2 = (CONDUIT_RADIUS + 1) ** 2
    for enemy in enemies:
        if enemy is primary:
            continue
        if getattr(enemy, "current_hp", 0) <= 0:
            continue
        ex, ey = enemy.rect.center
        d2 = (ex - px) ** 2 + (ey - py) ** 2
        if d2 < best_d2:
            best = enemy
            best_d2 = d2
    return best


# ── per-frame passive sync ──────────────────────────────
def passive_update(player):
    """Sync identity-rune passive flags into ``player.rune_state``.

    Called once per frame to keep cross-system observables (e.g.
    `enemy_collision_rules.enemy_vs_enemy_multiplier`) in agreement
    with the equipped-rune set.  Cheap to call when no identity rune
    is equipped (just clears the relevant key).
    """
    state = _state(player)
    if is_pacifist(player):
        state["enemy_vs_enemy_multiplier"] = PACIFIST_ENEMY_VS_ENEMY_MULTIPLIER
    elif state.get("enemy_vs_enemy_multiplier") == PACIFIST_ENEMY_VS_ENEMY_MULTIPLIER:
        # Only clear the value we set; leave any other rune's value intact.
        state["enemy_vs_enemy_multiplier"] = 0.0
