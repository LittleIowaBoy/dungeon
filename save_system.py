"""SQLite-backed save / load system.

Uses Python's built-in sqlite3 module.  The database is stored alongside
the game files as ``save_data.db``.
"""
import os
import sqlite3

from progress import PlayerProgress, DungeonProgress

_DB_PATH = os.path.join(os.path.dirname(__file__), "save_data.db")

# ── schema ──────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS player (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    coins       INTEGER NOT NULL DEFAULT 0,
    max_hp      INTEGER NOT NULL DEFAULT 100,
    speed_cap   REAL    NOT NULL DEFAULT 1.5
);

CREATE TABLE IF NOT EXISTS dungeon_progress (
    dungeon_id    TEXT    PRIMARY KEY,
    current_level INTEGER NOT NULL DEFAULT 0,
    is_alive      INTEGER NOT NULL DEFAULT 1,
    completed     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inventory (
    item_id  TEXT    PRIMARY KEY,
    quantity INTEGER NOT NULL DEFAULT 0
);
"""


def _get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


# ── public API ──────────────────────────────────────────

def save_progress(progress: PlayerProgress):
    """Persist the full PlayerProgress to the database."""
    conn = _get_conn()
    try:
        cur = conn.cursor()

        # player row (upsert)
        cur.execute(
            "INSERT INTO player (id, coins, max_hp, speed_cap) "
            "VALUES (1, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET coins=excluded.coins, "
            "max_hp=excluded.max_hp, speed_cap=excluded.speed_cap",
            (progress.coins, progress.max_hp, progress.speed_cap),
        )

        # dungeon progress (upsert each)
        for dp in progress.dungeons.values():
            cur.execute(
                "INSERT INTO dungeon_progress "
                "(dungeon_id, current_level, is_alive, completed) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(dungeon_id) DO UPDATE SET "
                "current_level=excluded.current_level, "
                "is_alive=excluded.is_alive, completed=excluded.completed",
                (dp.dungeon_id, dp.current_level,
                 int(dp.is_alive), int(dp.completed)),
            )

        # inventory (upsert each)
        for item_id, qty in progress.inventory.items():
            cur.execute(
                "INSERT INTO inventory (item_id, quantity) VALUES (?, ?) "
                "ON CONFLICT(item_id) DO UPDATE SET quantity=excluded.quantity",
                (item_id, qty),
            )

        conn.commit()
    finally:
        conn.close()


def load_progress() -> PlayerProgress:
    """Load player progress from the database.  Returns default if no save."""
    progress = PlayerProgress()
    if not os.path.exists(_DB_PATH):
        return progress

    conn = _get_conn()
    try:
        cur = conn.cursor()

        # player
        cur.execute("SELECT coins, max_hp, speed_cap FROM player WHERE id=1")
        row = cur.fetchone()
        if row:
            progress.coins = row[0]
            progress.max_hp = row[1]
            progress.speed_cap = row[2]

        # dungeon progress
        cur.execute("SELECT dungeon_id, current_level, is_alive, completed "
                    "FROM dungeon_progress")
        for dungeon_id, level, alive, completed in cur.fetchall():
            dp = progress.get_dungeon(dungeon_id)
            dp.current_level = level
            dp.is_alive = bool(alive)
            dp.completed = bool(completed)

        # inventory
        cur.execute("SELECT item_id, quantity FROM inventory")
        for item_id, qty in cur.fetchall():
            progress.inventory[item_id] = qty

    finally:
        conn.close()

    return progress


def delete_save():
    """Delete the save file entirely."""
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)
