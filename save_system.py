"""SQLite-backed save / load system.

Uses Python's built-in sqlite3 module.  The database is stored alongside
the game files as ``save_data.db``.
"""
import os
import sqlite3

import rune_rules
from progress import PlayerProgress, DungeonProgress

_DB_PATH = os.path.join(os.path.dirname(__file__), "save_data.db")

# ── schema ──────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS player (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    coins            INTEGER NOT NULL DEFAULT 0,
    max_hp           INTEGER NOT NULL DEFAULT 100,
    speed_cap        REAL    NOT NULL DEFAULT 1.5,
    armor_hp         INTEGER NOT NULL DEFAULT 0,
    compass_uses     INTEGER NOT NULL DEFAULT 0,
    difficulty_preference TEXT NOT NULL DEFAULT 'default',
    meta_keystones   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dungeon_progress (
    dungeon_id TEXT PRIMARY KEY,
    is_alive   INTEGER NOT NULL DEFAULT 1,
    completed  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inventory (
    item_id  TEXT    PRIMARY KEY,
    quantity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS equipment_storage (
    item_id  TEXT    PRIMARY KEY,
    quantity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS equipped_slots (
    slot_name TEXT PRIMARY KEY,
    item_id   TEXT
);

CREATE TABLE IF NOT EXISTS weapon_upgrades (
    weapon_id TEXT PRIMARY KEY,
    tier      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS equipped_runes (
    category   TEXT    NOT NULL,
    slot_index INTEGER NOT NULL,
    rune_id    TEXT    NOT NULL,
    PRIMARY KEY (category, slot_index)
);

CREATE TABLE IF NOT EXISTS biome_meta (
    terrain     TEXT    PRIMARY KEY,
    completions INTEGER NOT NULL DEFAULT 0,
    attunements INTEGER NOT NULL DEFAULT 0
);
"""


def _get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    cur = conn.cursor()

    # Migrate: add columns added after initial release
    cur.execute("PRAGMA table_info(player)")
    player_cols = {row[1] for row in cur.fetchall()}
    if "armor_hp" not in player_cols:
        cur.execute("ALTER TABLE player ADD COLUMN armor_hp INTEGER NOT NULL DEFAULT 0")
    if "compass_uses" not in player_cols:
        cur.execute("ALTER TABLE player ADD COLUMN compass_uses INTEGER NOT NULL DEFAULT 0")

    # Migrate: add difficulty_preference; on first appearance reset dungeon
    # progress so old five-level current_level data does not corrupt new runs.
    if "difficulty_preference" not in player_cols:
        cur.execute(
            "ALTER TABLE player ADD COLUMN "
            "difficulty_preference TEXT NOT NULL DEFAULT 'default'"
        )
        cur.execute("UPDATE dungeon_progress SET is_alive=1, completed=0")

    # Migrate: meta_keystones permanent counter (T11).
    if "meta_keystones" not in player_cols:
        cur.execute(
            "ALTER TABLE player ADD COLUMN "
            "meta_keystones INTEGER NOT NULL DEFAULT 0"
        )

    # Migrate: Danger Mode opt-in toggle.
    if "risk_reward_mode" not in player_cols:
        cur.execute(
            "ALTER TABLE player ADD COLUMN "
            "risk_reward_mode INTEGER NOT NULL DEFAULT 0"
        )

    conn.commit()
    return conn


# ── public API ──────────────────────────────────────────

def save_progress(progress: PlayerProgress):
    """Persist the full PlayerProgress to the database."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        progress.ensure_loadout_state()

        # player row (upsert)
        cur.execute(
            "INSERT INTO player "
            "(id, coins, max_hp, speed_cap, armor_hp, compass_uses, "
            "difficulty_preference, meta_keystones, risk_reward_mode) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET coins=excluded.coins, "
            "max_hp=excluded.max_hp, speed_cap=excluded.speed_cap, "
            "armor_hp=excluded.armor_hp, compass_uses=excluded.compass_uses, "
            "difficulty_preference=excluded.difficulty_preference, "
            "meta_keystones=excluded.meta_keystones, "
            "risk_reward_mode=excluded.risk_reward_mode",
            (progress.coins, progress.max_hp, progress.speed_cap,
             progress.armor_hp, progress.compass_uses,
             progress.difficulty_preference, progress.meta_keystones,
             int(progress.risk_reward_mode)),
        )

        # dungeon progress (upsert each)
        for dp in progress.dungeons.values():
            cur.execute(
                "INSERT INTO dungeon_progress (dungeon_id, is_alive, completed) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(dungeon_id) DO UPDATE SET "
                "is_alive=excluded.is_alive, completed=excluded.completed",
                (dp.dungeon_id, int(dp.is_alive), int(dp.completed)),
            )

        # inventory
        cur.execute("DELETE FROM inventory")
        for item_id, qty in progress.inventory.items():
            cur.execute(
                "INSERT INTO inventory (item_id, quantity) VALUES (?, ?)",
                (item_id, qty),
            )

        # equipment storage
        cur.execute("DELETE FROM equipment_storage")
        for item_id, qty in progress.equipment_storage.items():
            cur.execute(
                "INSERT INTO equipment_storage (item_id, quantity) VALUES (?, ?)",
                (item_id, qty),
            )

        # equipped slots
        cur.execute("DELETE FROM equipped_slots")
        for slot_name, item_id in progress.equipped_slots.items():
            cur.execute(
                "INSERT INTO equipped_slots (slot_name, item_id) VALUES (?, ?)",
                (slot_name, item_id),
            )

        # weapon upgrades
        cur.execute("DELETE FROM weapon_upgrades")
        for weapon_id, tier in progress.weapon_upgrades.items():
            cur.execute(
                "INSERT INTO weapon_upgrades (weapon_id, tier) VALUES (?, ?)",
                (weapon_id, tier),
            )

        # equipped runes
        cur.execute("DELETE FROM equipped_runes")
        rune_loadout = rune_rules.serialize_loadout(progress.equipped_runes)
        for category, rune_ids in rune_loadout.items():
            for slot_index, rune_id in enumerate(rune_ids):
                cur.execute(
                    "INSERT INTO equipped_runes (category, slot_index, rune_id) "
                    "VALUES (?, ?, ?)",
                    (category, slot_index, rune_id),
                )

        # T17: biome meta-progression (completions + attunements per terrain).
        cur.execute("DELETE FROM biome_meta")
        terrains = set(progress.biome_completions) | set(progress.biome_attunements)
        for terrain in terrains:
            cur.execute(
                "INSERT INTO biome_meta (terrain, completions, attunements) "
                "VALUES (?, ?, ?)",
                (
                    terrain,
                    int(progress.biome_completions.get(terrain, 0)),
                    int(progress.biome_attunements.get(terrain, 0)),
                ),
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
        progress.inventory = {}
        progress.equipment_storage = {}
        progress.equipped_slots = {
            slot_name: None for slot_name in progress.equipped_slots
        }
        progress.weapon_upgrades = {
            weapon_id: 0 for weapon_id in progress.weapon_upgrades
        }

        # player
        cur.execute("SELECT coins, max_hp, speed_cap, armor_hp, compass_uses, "
                    "difficulty_preference, meta_keystones, risk_reward_mode "
                    "FROM player WHERE id=1")
        row = cur.fetchone()
        if row:
            progress.coins = row[0]
            progress.max_hp = row[1]
            progress.speed_cap = row[2]
            progress.armor_hp = row[3]
            progress.compass_uses = row[4]
            progress.difficulty_preference = row[5]
            progress.meta_keystones = row[6]
            progress.risk_reward_mode = bool(row[7]) if len(row) > 7 else False

        # dungeon progress
        cur.execute("SELECT dungeon_id, is_alive, completed FROM dungeon_progress")
        for dungeon_id, alive, completed in cur.fetchall():
            dp = progress.get_dungeon(dungeon_id)
            dp.is_alive = bool(alive)
            dp.completed = bool(completed)

        # inventory
        cur.execute("SELECT item_id, quantity FROM inventory")
        for item_id, qty in cur.fetchall():
            progress.inventory[item_id] = qty

        # equipment storage
        cur.execute("SELECT item_id, quantity FROM equipment_storage")
        for item_id, qty in cur.fetchall():
            progress.equipment_storage[item_id] = qty

        # equipped slots
        cur.execute("SELECT slot_name, item_id FROM equipped_slots")
        for slot_name, item_id in cur.fetchall():
            progress.equipped_slots[slot_name] = item_id

        # weapon upgrades
        cur.execute("SELECT weapon_id, tier FROM weapon_upgrades")
        for weapon_id, tier in cur.fetchall():
            progress.weapon_upgrades[weapon_id] = tier

        # equipped runes
        progress.equipped_runes = rune_rules.empty_loadout()
        cur.execute(
            "SELECT category, slot_index, rune_id FROM equipped_runes "
            "ORDER BY category, slot_index"
        )
        rune_rows = cur.fetchall()
        if rune_rows:
            grouped: dict[str, list[str]] = {}
            for category, _slot_index, rune_id in rune_rows:
                grouped.setdefault(category, []).append(rune_id)
            progress.equipped_runes = rune_rules.normalize_loadout(grouped)

        # T17: biome meta-progression.
        progress.biome_completions = {}
        progress.biome_attunements = {}
        cur.execute("SELECT terrain, completions, attunements FROM biome_meta")
        for terrain, completions, attunements in cur.fetchall():
            if int(completions) > 0:
                progress.biome_completions[terrain] = int(completions)
            if int(attunements) > 0:
                progress.biome_attunements[terrain] = int(attunements)

        progress.migrate_legacy_state()

    finally:
        conn.close()

    return progress


def delete_save():
    """Delete the save file entirely."""
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)
