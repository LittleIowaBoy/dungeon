"""Tool-use rules for Player runtime state."""

from settings import COMPASS_DISPLAY_MS


_COMPASS_ARROWS = {
    "N": "↑",
    "S": "↓",
    "E": "→",
    "W": "←",
    "NE": "↗",
    "NW": "↖",
    "SE": "↘",
    "SW": "↙",
}


def reset_runtime_tools(player, progress):
    player.compass_uses = getattr(progress, "compass_uses", 0)
    clear_compass_hint(player)


def clear_compass_hint(player):
    player.compass_direction = None
    player.compass_arrow = None
    player._compass_display_until = 0


def compass_showing(player, now_ticks):
    return now_ticks < player._compass_display_until


def use_compass(player, dungeon, now_ticks):
    """Consume a compass use and show the portal direction."""
    if player.compass_uses <= 0:
        return False

    player.compass_uses -= 1
    if player.progress is not None:
        player.progress.compass_uses = player.compass_uses

    direction, arrow = build_compass_hint(dungeon.current_pos, dungeon.exit_pos)
    player.compass_direction = direction
    player.compass_arrow = arrow
    player._compass_display_until = now_ticks + COMPASS_DISPLAY_MS
    return True


def build_compass_hint(current_pos, exit_pos):
    cx, cy = current_pos
    ex, ey = exit_pos
    dx = ex - cx
    dy = ey - cy

    if dx == 0 and dy == 0:
        return "HERE", "●"

    direction = ""
    if dy < 0:
        direction += "N"
    elif dy > 0:
        direction += "S"
    if dx > 0:
        direction += "E"
    elif dx < 0:
        direction += "W"

    return direction, _COMPASS_ARROWS.get(direction, "?")