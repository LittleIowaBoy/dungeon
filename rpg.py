"""Top-Down Dungeon Crawler RPG — entry point."""
import os
import sys
import pygame
from chest import Chest
from objective_entities import EscortNPC, Heartstone
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    TILE_SIZE, ROOM_COLS, ROOM_ROWS,
    DIR_OFFSETS, OPPOSITE_DIR,
    COLOR_BLACK,
    PLAYTEST_ROOM_IDENTIFIER_ENABLED,
)
from hud_view import (
    build_game_over_overlay_view,
    build_hud_view,
    build_victory_overlay_view,
)
from player import Player
from dungeon import Dungeon
from camera import Camera
from hud import HUD
from room import DOOR, PORTAL, WALL
from items import LootDrop
from item_catalog import ITEM_DATABASE
from game_states import GameState
from content_db import ensure_room_content_db
from dungeon_config import get_dungeon, get_difficulty_preset, DUNGEONS
from progress import PlayerProgress
from save_system import save_progress, load_progress
from menu import (
    MainMenuScreen,
    RoomTestSelectScreen,
    DungeonSelectScreen,
    CharacterCustomizeScreen,
    ShopScreen,
    RecordsScreen,
    PauseScreen,
    LevelCompleteScreen,
    RuneAltarPickScreen,
    AllItemsPauseScreen,
    AllRunesPauseScreen,
)
from menu_view import (
    build_main_menu_view,
    build_character_customize_view,
    build_dungeon_select_view,
    build_level_complete_screen_view,
    build_pause_screen_view,
    build_records_view,
    build_room_test_select_view,
    build_rune_altar_pick_view,
    build_shop_view,
)
from room_test_catalog import build_room_test_plan, load_room_test_entries
from shop import Shop
import ability_rules
import allies
import behavior_runes
import damage_feedback
import dodge_rules
import enemy_collision_rules
import enemy_attack_rules
import armor_rules
import identity_runes
import rune_rules
import stat_runes
import status_effects
import time_rules
import terrain_effects
from settings import BIOME_TROPHY_IDS, BIOME_TROPHY_KEYSTONE_ID


# Display labels for biome trophies on the level-complete summary.
_BIOME_TROPHY_DISPLAY = {
    "stat_shard": "Boulder Stat Shards",
    "tempo_rune": "Storm Tempo Runes",
    "mobility_charge": "Tide Mobility Charges",
    BIOME_TROPHY_KEYSTONE_ID: "Prismatic Keystones",
}


def _build_trophy_tally_lines(progress):
    """Return tuple of "Label: count" strings for biome trophies in inventory."""
    inventory = getattr(progress, "inventory", None)
    if inventory is None:
        return ()
    lines = []
    for trophy_id in BIOME_TROPHY_IDS:
        count = inventory.get(trophy_id, 0)
        if count > 0:
            lines.append(f"{_BIOME_TROPHY_DISPLAY[trophy_id]}: {count}")
    keystone_count = getattr(progress, "meta_keystones", 0)
    if keystone_count > 0:
        lines.append(
            f"{_BIOME_TROPHY_DISPLAY[BIOME_TROPHY_KEYSTONE_ID]}: {keystone_count}"
        )
    return tuple(lines)


class Game:
    def __init__(self):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
        ensure_room_content_db()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Dungeon Crawler")
        self.clock = pygame.time.Clock()
        self.camera = Camera()
        self.hud = HUD()
        self.shop = Shop()

        # persistent progress (loaded from SQLite)
        self.progress = load_progress()

        # current dungeon run state
        self.dungeon = None
        self.player = None
        self.player_group = None
        self._current_dungeon_id = None
        self._show_room_identifier = PLAYTEST_ROOM_IDENTIFIER_ENABLED
        self._room_test_entry = None
        self._room_test_spawn_direction = "left"

        # menu screens
        self._main_menu = MainMenuScreen(self.progress)
        self._room_test_select = RoomTestSelectScreen(load_room_test_entries())
        self._dungeon_select = DungeonSelectScreen(self.progress)
        self._character_screen = CharacterCustomizeScreen(self.progress)
        self._shop_screen = ShopScreen(self.progress, self.shop)
        self._level_complete = None  # created on level complete
        self._pause_screen = PauseScreen(
            room_identifier_enabled=self._show_room_identifier,
        )
        self._rune_altar_pick = RuneAltarPickScreen()
        self._pending_rune_altar = None  # config dict of altar awaiting pick

        # Test-room pause sub-screens (lazy-built when entering a room test).
        self._all_items_screen = None
        self._all_runes_screen = None
        # Snapshot of (equipped_slots, equipment_storage, equipped_runes) taken
        # when entering a room test.  Restored on exit so test-room edits do
        # not persist.  None when no room test is active.
        self._room_test_loadout_snapshot = None

        # snapshot of progress before entering a level (for quit-revert)
        self._pre_level_progress_snapshot = None

        # start at main menu
        self.state = GameState.MAIN_MENU

    # ── start / resume a dungeon level ──────────────────
    def _start_dungeon(self, dungeon_id):
        """Generate a dungeon and create the player."""
        self._room_test_entry = None
        self._current_dungeon_id = dungeon_id
        config = get_dungeon(dungeon_id)
        self._pre_level_progress_snapshot = self.progress.begin_dungeon_run(dungeon_id)

        difficulty = self.progress.difficulty_preference
        damage_feedback.reset_all()
        # Surface the keystone starting-coin bonus (T11) as a brief HUD banner
        # immediately after the reset so the new run's feedback channel is clean.
        bonus = self.progress.keystone_starting_coin_bonus()
        if bonus:
            damage_feedback.report_keystone_starting_bonus(bonus)
        self.dungeon = Dungeon(dungeon_config=config, difficulty=difficulty)

        start_x = ROOM_COLS // 2 * TILE_SIZE + TILE_SIZE // 2
        start_y = ROOM_ROWS // 2 * TILE_SIZE + TILE_SIZE // 2
        self.player = Player(start_x, start_y)
        self.player.reset_for_dungeon(self.progress)
        self.player_group = pygame.sprite.GroupSingle(self.player)
        self._enter_current_room()
        self.state = GameState.PLAYING

    def _start_room_test(self, entry, spawn_direction="left"):
        """Build a single-room test run without mutating persistent progress."""
        self._room_test_entry = entry
        self._room_test_spawn_direction = spawn_direction
        self._current_dungeon_id = entry.profile_dungeon_id
        self._pre_level_progress_snapshot = None

        # Snapshot loadout state before any test-room edits.  The pause
        # menu in test-room mode lets the player force-equip any item or
        # rune; on exit (death, quit, or returning to the selector) we
        # restore from this snapshot so persistent progress is unchanged.
        self._room_test_loadout_snapshot = self._snapshot_room_test_loadout()
        self._pause_screen.room_test_mode = True
        self._all_items_screen = AllItemsPauseScreen(self.progress)
        self._all_runes_screen = AllRunesPauseScreen(self.progress)

        room_plan = build_room_test_plan(entry)
        damage_feedback.reset_all()
        self.dungeon = Dungeon.from_room_plan(
            entry.profile_dungeon_id, room_plan, entry_direction=spawn_direction
        )

        start_x, start_y = self._room_test_spawn_position(spawn_direction)
        self.player = Player(start_x, start_y)
        self.player.reset_for_dungeon(self.progress)
        self.player_group = pygame.sprite.GroupSingle(self.player)
        self._level_complete = None
        self._enter_current_room(entry_direction=spawn_direction)
        self.state = GameState.PLAYING

    def _snapshot_room_test_loadout(self):
        """Capture equipped slots/storage/runes before test-room entry."""
        return {
            "equipped_slots": dict(self.progress.equipped_slots),
            "equipment_storage": dict(self.progress.equipment_storage),
            "equipped_runes": rune_rules.serialize_loadout(self.progress.equipped_runes),
        }

    def _restore_room_test_loadout(self):
        """Revert progress loadout to the pre-test snapshot, if any."""
        snapshot = self._room_test_loadout_snapshot
        if snapshot is None:
            return
        self.progress.equipped_slots = dict(snapshot["equipped_slots"])
        self.progress.equipment_storage = dict(snapshot["equipment_storage"])
        self.progress.equipped_runes = rune_rules.normalize_loadout(
            snapshot["equipped_runes"]
        )
        self._room_test_loadout_snapshot = None
        self._pause_screen.room_test_mode = False
        self._all_items_screen = None
        self._all_runes_screen = None

    def _room_test_spawn_position(self, spawn_direction="left"):
        """Return the spawn point just inside the entry door for room-test mode."""
        if self.dungeon is None:
            center_col = ROOM_COLS // 2
            center_row = ROOM_ROWS // 2
            return (
                center_col * TILE_SIZE + TILE_SIZE // 2,
                center_row * TILE_SIZE + TILE_SIZE // 2,
            )

        room = self.dungeon.current_room
        # Spawn at the entry door and step one tile inward.
        door_px, door_py = room.door_pixel_pos(spawn_direction)
        inward_dx, inward_dy = DIR_OFFSETS[OPPOSITE_DIR[spawn_direction]]
        return (
            door_px + inward_dx * TILE_SIZE,
            door_py + inward_dy * TILE_SIZE,
        )

    def _sync_player_state_to_progress(self):
        """Copy the player's in-game state back to persistent progress."""
        if self.player:
            self.progress.sync_runtime_state(self.player)

    def _reset_runtime_state(self):
        self.dungeon = None
        self.player = None
        self.player_group = None
        self._current_dungeon_id = None
        self._pre_level_progress_snapshot = None
        self._level_complete = None
        self._room_test_entry = None

    def _is_room_test_active(self):
        return self._room_test_entry is not None

    def _return_to_menu(self, sync_player_state=True):
        """Save and go back to main menu."""
        if sync_player_state:
            self._sync_player_state_to_progress()
        save_progress(self.progress)
        self._reset_runtime_state()
        self._dungeon_select = DungeonSelectScreen(self.progress)
        self._character_screen = CharacterCustomizeScreen(self.progress)
        self._shop_screen = ShopScreen(self.progress, self.shop)
        self.state = GameState.MAIN_MENU

    def _return_to_room_tests(self):
        """Drop the current room-test runtime and reopen the selector."""
        self._restore_room_test_loadout()
        self._reset_runtime_state()
        self.state = GameState.ROOM_TEST_SELECT

    def _enter_current_room(self, entry_direction=None):
        if self.dungeon is not None:
            player_position = None
            if self.player is not None:
                player_position = self.player.rect.center
            self.dungeon.current_room.on_enter(
                pygame.time.get_ticks(),
                entry_direction=entry_direction,
                player_position=player_position,
                room_test=self._is_room_test_active(),
            )

    def _toggle_room_identifier(self):
        self._show_room_identifier = not self._show_room_identifier
        self._pause_screen.room_identifier_enabled = self._show_room_identifier

    def _apply_room_objective_update(self, update_result):
        if not update_result:
            return
        room = self.dungeon.current_room
        if update_result.get("kind") in {"spawn_reinforcements", "spawn_enemies"}:
            if not room.enemies_cleared:
                for cls, (px, py) in update_result.get("enemy_configs", ()):
                    self.dungeon.enemy_group.add(cls(px, py))
        elif update_result.get("kind") == "forfeit_chest":
            for chest in self.dungeon.chest_group:
                chest.mark_looted()
        elif update_result.get("kind") == "restore_chest":
            for chest in self.dungeon.chest_group:
                chest.restore_for_reclaim()
        elif update_result.get("kind") == "upgrade_reward_chest":
            reward_tier = update_result.get("reward_tier", "standard")
            reward_kind = update_result.get("reward_kind", "chest_upgrade")
            for chest in self.dungeon.chest_group:
                chest.set_reward_tier(reward_tier)
                chest.set_reward_kind(reward_kind)
        elif update_result.get("kind") == "spawn_reward_chest":
            x, y = update_result.get("position", (None, None))
            if x is not None and y is not None and not self.dungeon.chest_group:
                self.dungeon.chest_group.add(
                    Chest(
                        x,
                        y,
                        looted=False,
                        reward_tier=update_result.get("reward_tier", "standard"),
                        reward_kind=update_result.get("reward_kind", "chest_upgrade"),
                    )
                )
        elif update_result.get("kind") == "despawn_escort":
            for objective in list(self.dungeon.objective_group):
                if isinstance(objective, EscortNPC):
                    objective.kill()
        elif update_result.get("kind") == "spawn_heartstone":
            x, y = update_result.get("position", (None, None))
            if x is not None and y is not None:
                room = self.dungeon.current_room
                config = room._heartstone_config
                if config is not None:
                    self.dungeon.objective_group.add(Heartstone(config))

    def _update_boss_controller(self):
        """Drive the active room's BossController and react to its events.

        Currently the only boss is the Stone Golem (``earth_golem_arena``).
        Wave thresholds spawn :class:`~enemies.GolemShard` reinforcements
        around the Golem; the defeat event rolls + grants armor loot via
        :mod:`armor_rules` exactly once.
        """
        controller = getattr(self.dungeon, "boss_controller", None)
        if controller is None:
            return
        events = controller.update()
        arena_cfg = getattr(controller, "arena_config", None)
        if arena_cfg is None:
            return

        # Wave triggers — spawn GolemShard adds for each new threshold.
        if events.new_waves:
            from enemies import GolemShard
            wave_specs = arena_cfg.get("wave_specs", {})
            radius = int(arena_cfg.get("shard_spawn_radius", 0))
            boss = controller.boss
            cx = boss.rect.centerx if boss is not None else 0
            cy = boss.rect.centery if boss is not None else 0
            import math
            import random as _random
            for threshold in events.new_waves:
                count = int(wave_specs.get(threshold, 0))
                if count <= 0:
                    continue
                for i in range(count):
                    # Distribute shards evenly around the Golem with a
                    # small random jitter so successive waves don't pile
                    # onto the same exact pixels.
                    angle = (2 * math.pi * i / count) + _random.uniform(-0.2, 0.2)
                    sx = int(cx + radius * math.cos(angle))
                    sy = int(cy + radius * math.sin(angle))
                    shard = GolemShard(sx, sy)
                    self.dungeon.enemy_group.add(shard)

        # Defeat: roll + grant loot once.
        if events.defeated and not arena_cfg.get("loot_granted"):
            arena_cfg["loot_granted"] = True
            drops = armor_rules.roll_boss_loot(self.player.progress)
            if drops:
                armor_rules.grant_boss_loot(self.player.progress, drops)
                # HUD banner per drop so the player sees what dropped.
                import damage_feedback
                from item_catalog import ITEM_DATABASE
                for item_id in drops:
                    name = ITEM_DATABASE.get(item_id, {}).get("name", item_id)
                    damage_feedback.report_boss_loot(name)

    def _update_heartstone(self, room, hp_at_frame_start):
        """Pickup / carry-sync / damage-drop / portal-delivery for the Heartstone."""
        state = room.heartstone_state() if hasattr(room, "heartstone_state") else None
        if state is None or state["delivered"]:
            return

        heartstone_sprite = None
        for objective in self.dungeon.objective_group:
            if isinstance(objective, Heartstone):
                heartstone_sprite = objective
                break
        if heartstone_sprite is None:
            return

        if not state["carried"]:
            # Pickup on overlap.
            if self.player.rect.colliderect(heartstone_sprite.rect):
                room.notify_heartstone_picked_up()
                self.player.carrying_heartstone = True
                room.notify_heartstone_position(self.player.rect.center)
            return

        # Carrying: drop if damaged this frame.
        if self.player.current_hp < hp_at_frame_start:
            room.notify_heartstone_dropped(self.player.rect.center)
            self.player.carrying_heartstone = False
            return

        # Carrying: keep heartstone glued to the player.
        room.notify_heartstone_position(self.player.rect.center)

        # Delivery: player overlaps any portal cell.
        col = self.player.rect.centerx // TILE_SIZE
        row = self.player.rect.centery // TILE_SIZE
        if room.tile_at(col, row) == PORTAL or self._player_over_portal_cell(room):
            room.notify_heartstone_delivered()
            self.player.carrying_heartstone = False
            heartstone_sprite.kill()

    def _player_over_portal_cell(self, room):
        # Heartstone delivery: the portal cells live in room._portal_cells; check
        # whether the player's center is on any of them even when the tile has
        # been temporarily set to FLOOR (portal inactive while sealed).
        cells = getattr(room, "_portal_cells", ())
        if not cells:
            return False
        col = self.player.rect.centerx // TILE_SIZE
        row = self.player.rect.centery // TILE_SIZE
        return (row, col) in cells

    # ── main loop ───────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()

            # global quit
            for event in events:
                if event.type == pygame.QUIT:
                    self._handle_global_quit()
                    pygame.quit()
                    sys.exit()

            if self.state == GameState.MAIN_MENU:
                self._handle_main_menu(events)
            elif self.state == GameState.ROOM_TEST_SELECT:
                self._handle_room_test_select(events)
            elif self.state == GameState.DUNGEON_SELECT:
                self._handle_dungeon_select(events)
            elif self.state == GameState.CHARACTER_CUSTOMIZE:
                self._handle_character(events)
            elif self.state == GameState.SHOP:
                self._handle_shop(events)
            elif self.state == GameState.RECORDS:
                self._handle_records(events)
            elif self.state == GameState.PLAYING:
                self._handle_playing(events)
                self._update_playing()
            elif self.state == GameState.PAUSED:
                self._handle_paused(events)
            elif self.state == GameState.PAUSE_ALL_ITEMS:
                self._handle_pause_all_items(events)
            elif self.state == GameState.PAUSE_ALL_RUNES:
                self._handle_pause_all_runes(events)
            elif self.state == GameState.RUNE_ALTAR_PICK:
                self._handle_rune_altar_pick(events)
            elif self.state == GameState.LEVEL_COMPLETE:
                self._handle_level_complete(events)
            elif self.state == GameState.GAME_OVER:
                self._handle_game_over(events)
            elif self.state == GameState.GAME_WIN:
                self._handle_game_win(events)

            self._draw()

    # ── menu handlers ───────────────────────────────────
    def _handle_main_menu(self, events):
        result = self._main_menu.handle_events(events)
        if result == "QUIT":
            save_progress(self.progress)
            pygame.quit()
            sys.exit()
        elif result == GameState.ROOM_TEST_SELECT:
            self._room_test_select.set_entries(load_room_test_entries())
            self.state = result
        elif result is not None:
            self.state = result

    def _handle_room_test_select(self, events):
        result = self._room_test_select.handle_events(events)
        if result is None:
            return
        next_state, entry, spawn_direction = result
        if next_state == GameState.PLAYING and entry is not None:
            self._start_room_test(entry, spawn_direction)
        else:
            self.state = next_state

    def _handle_dungeon_select(self, events):
        result = self._dungeon_select.handle_events(events)
        if result is None:
            return
        next_state, dungeon_id = result
        if next_state == GameState.PLAYING and dungeon_id:
            self._start_dungeon(dungeon_id)
        else:
            self.state = next_state

    def _handle_character(self, events):
        result = self._character_screen.handle_events(events)
        if result is not None:
            save_progress(self.progress)
            self.state = result

    def _handle_records(self, events):
        result = self._records_screen.handle_events(events)
        if result is not None:
            self.state = result

    def _handle_shop(self, events):
        result = self._shop_screen.handle_events(events)
        if result is not None:
            save_progress(self.progress)
            self.state = result

    # ── playing handlers ────────────────────────────────
    def _handle_playing(self, events):
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            # weapon switching
            if event.key == pygame.K_1:
                self.player.switch_weapon(0)
            elif event.key == pygame.K_2:
                self.player.switch_weapon(1)

            # attack
            if event.key == pygame.K_SPACE:
                result = self.player.attack()
                if result:
                    if isinstance(result, list):
                        for hb in result:
                            self.dungeon.hitbox_group.add(hb)
                    else:
                        self.dungeon.hitbox_group.add(result)

            # dodge (i-frames + burst of motion)
            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                pre_center = self.player.rect.center
                if dodge_rules.trigger_dodge(self.player, pygame.time.get_ticks()):
                    if behavior_runes.spawns_afterimage(self.player):
                        decoy = behavior_runes.make_afterimage_hitbox(pre_center)
                        self.dungeon.hitbox_group.add(decoy)

            # active ability (rune-supplied)
            if event.key == pygame.K_f:
                ability_rules.activate_ability(self.player, pygame.time.get_ticks())

            # chest interaction
            if event.key == pygame.K_e:
                now_ticks = pygame.time.get_ticks()
                for chest in self.dungeon.chest_group:
                    if not self.dungeon.current_room.allows_chest_open(now_ticks):
                        continue
                    if chest.try_open(self.player.rect, self.dungeon.item_group):
                        self.dungeon.current_room.notify_chest_opened(
                            now_ticks
                        )

            # consumables
            if event.key == pygame.K_q:
                self.player.cycle_potion()
            elif event.key == pygame.K_4:
                self.player.use_potion()
            elif event.key == pygame.K_5:
                self.player.use_speed_boost()
            elif event.key == pygame.K_6:
                self.player.use_attack_boost()
            elif event.key == pygame.K_7:
                self.player.use_compass(self.dungeon)
            elif event.key == pygame.K_8:
                self.player.use_stat_shard()
            elif event.key == pygame.K_9:
                self.player.use_tempo_rune()
            elif event.key == pygame.K_0:
                self.player.use_mobility_charge()

            elif event.key == pygame.K_F3:
                self._toggle_room_identifier()

            elif event.key == pygame.K_F2:
                # Test-room utility: toggle whether enemies in the current
                # room may attack.  Movement (frozen) state is unaffected.
                room = self.dungeon.current_room
                if room is not None and hasattr(room, "toggle_enemy_attacks"):
                    room.toggle_enemy_attacks(self.dungeon.enemy_group)

            # pause menu
            if event.key == pygame.K_ESCAPE:
                self._pause_screen.selected = 0
                self.state = GameState.PAUSED

    def _apply_player_hit(self, hitbox, enemy):
        """Apply a single player→enemy hit through all rune pipelines."""
        scaled = stat_runes.modify_outgoing_damage(
            self.player, enemy, hitbox.damage
        )
        # Equipment-derived flat outgoing-damage bonus (e.g. Golem Fists).
        scaled = armor_rules.apply_outgoing_damage_multiplier(self.player, scaled)
        # Equipment-derived crit chance (e.g. Golem Crown).  Applied after
        # all multiplicative scaling so the crit boosts the final number.
        crit_mult = armor_rules.roll_crit_multiplier(self.player)
        if crit_mult != 1.0:
            scaled = max(0, int(round(scaled * crit_mult)))
        # Crystal Vein room buff: each shattered crystal grants +N% damage
        # for the rest of the room.  No-op when no buffs are registered.
        room = self.dungeon.current_room if self.dungeon is not None else None
        if room is not None and hasattr(room, "active_room_buff_total"):
            damage_buff = room.active_room_buff_total(
                "damage", pygame.time.get_ticks()
            )
            if damage_buff:
                scaled = int(round(scaled * (1.0 + damage_buff)))
        # The Conduit: split damage across primary + nearest other enemy.
        primary_damage, splash_damage = identity_runes.conduit_split_damage(
            self.player, scaled
        )
        enemy.take_damage(primary_damage)
        if splash_damage > 0:
            splash_target = identity_runes.conduit_find_splash_target(
                self.player, enemy, self.dungeon.enemy_group
            )
            if splash_target is not None:
                splash_target.take_damage(splash_damage)
        killed = enemy.current_hp <= 0
        stat_runes.on_player_hit_landed(self.player, enemy, primary_damage, killed)
        if not killed:
            return
        # Vampiric Strike heal
        heal = behavior_runes.vampiric_kill_heal_amount(self.player)
        if heal > 0:
            self.player.current_hp = min(
                self.player.max_hp, self.player.current_hp + heal
            )
        # Necromancer: register the kill (ally spawn handled by caller).
        identity_runes.necromancer_register_kill(self.player)
        # Shrapnel Burst AOE
        targets = behavior_runes.shrapnel_burst_targets(
            self.player, enemy.rect, self.dungeon.enemy_group
        )
        if targets:
            blast = behavior_runes.shrapnel_burst_damage(self.player, scaled)
            for other in targets:
                if other is enemy:
                    continue
                other.take_damage(blast)
        if behavior_runes.player_in_shrapnel_blast(self.player, enemy.rect):
            self_dmg = behavior_runes.shrapnel_burst_self_damage(self.player, scaled)
            if self_dmg > 0:
                self.player.take_damage(self_dmg)
        # Loot drop
        drop = enemy.roll_drop()
        if drop:
            self.dungeon.item_group.add(drop)

    def _update_playing(self):
        room = self.dungeon.current_room
        walls = room.get_wall_rects()
        now_ticks = pygame.time.get_ticks()

        # Track HP at the start of the frame so we can detect any damage source
        # (enemy contact, traps, altars, etc.) and drop the heartstone if hit.
        hp_at_frame_start = self.player.current_hp

        # player movement
        prev_center = self.player.rect.center
        self.player.update(walls, room.terrain_at_pixel)
        # Biome-room hazard tile effects (spike tick, quicksand drown,
        # current push, pit lethal-on-step).  Runs after movement so the
        # tile under the player's new position is what triggers the effect.
        terrain_effects.apply_terrain_effects(
            self.player, room, now_ticks, self.clock.get_time(),
        )
        room.prune_expired_room_buffs(now_ticks)
        is_moving = self.player.rect.center != prev_center
        stat_runes.update_movement_state(
            self.player, now_ticks, self.clock.get_time(), is_moving
        )
        behavior_runes.update_static_charge(
            self.player, self.clock.get_time(), is_moving
        )
        behavior_runes.update_boomerang_returns(
            self.player, self.dungeon.hitbox_group, now_ticks
        )
        # Identity rune passives + time anchor patience meter
        identity_runes.passive_update(self.player)
        anchor_event = identity_runes.update_time_anchor(
            self.player, self.clock.get_time(), is_moving
        )
        anchor_scale = identity_runes.time_anchor_time_scale(self.player, is_moving)
        if anchor_scale is not None:
            time_rules.set_time_scale(self.player, anchor_scale)
        if anchor_event == "freeze":
            for enemy in self.dungeon.enemy_group:
                status_effects.apply_status(
                    enemy, status_effects.STUNNED, now_ticks,
                    duration_ms=identity_runes.TIME_ANCHOR_FREEZE_DURATION_MS,
                )
            identity_runes.consume_time_anchor_freeze(self.player)

        # dodge — clear pass-through once active phase ends
        dodge_rules.update_dodge_state(self.player, now_ticks)

        # status effect ticks (DOT + expiry) for player and enemies
        status_effects.tick_statuses(
            self.player, now_ticks,
            lambda holder, amount: holder.take_damage(amount),
        )
        for enemy in list(self.dungeon.enemy_group):
            status_effects.tick_statuses(
                enemy, now_ticks,
                lambda holder, amount: holder.take_damage(amount),
            )

        # door transitions
        direction = self.dungeon.try_transition(self.player.rect)
        if direction:
            spawn = self.dungeon.move_to(direction)
            if spawn:
                self.player.place(*spawn)
                rune_rules.on_room_enter(self.player)
                self.dungeon.current_room.on_enter(
                    pygame.time.get_ticks(),
                    entry_direction=OPPOSITE_DIR[direction],
                    player_position=self.player.rect.center,
                    room_test=self._is_room_test_active(),
                )
            return

        for objective in self.dungeon.objective_group:
            objective.update(now_ticks)
            if hasattr(objective, "update_behavior"):
                objective.update_behavior(
                    player=self.player,
                    wall_rects=walls,
                    portal_pos=room.portal_center_pixel(),
                    allow_advance=room.escort_allows_advance(self.dungeon.enemy_group),
                )
            if hasattr(objective, "sync_player_overlap"):
                objective.sync_player_overlap(self.player)
            if hasattr(objective, "apply_player_pressure"):
                objective.apply_player_pressure(self.player)
            if hasattr(objective, "apply_room_pressure"):
                objective.apply_room_pressure(self.player, self.dungeon.enemy_group)

        enemy_focus_rect = self.player.rect
        for objective in self.dungeon.objective_group:
            if hasattr(objective, "enemy_target_rect"):
                target_rect = objective.enemy_target_rect()
                if target_rect is not None:
                    enemy_focus_rect = target_rect
                    break

        # enemies AI + movement
        time_scale = time_rules.get_time_scale(self.player)
        for enemy in self.dungeon.enemy_group:
            # Drive telegraphed-attack state machine first so movement-blocked
            # enemies (TELEGRAPH/STRIKE) properly halt this tick.  Frozen
            # enemies still tick their attack machine when ``attacks_disabled``
            # is False — this is what powers the test-room attack toggle.
            if hasattr(enemy, "update_attack_state"):
                enemy.update_attack_state(enemy_focus_rect, now_ticks)
            if getattr(enemy, "is_frozen", False):
                # Drain any rings/projectiles emitted while frozen attacks fire,
                # but skip movement entirely.
                if hasattr(enemy, "consume_emitted_rings"):
                    for ring in enemy.consume_emitted_rings():
                        self.dungeon.pulsator_ring_group.add(ring)
                if hasattr(enemy, "consume_emitted_projectiles"):
                    for proj in enemy.consume_emitted_projectiles():
                        self.dungeon.enemy_projectile_group.add(proj)
                continue
            if status_effects.is_immobilized(enemy, now_ticks):
                continue
            if time_scale != 1.0:
                original_speed = enemy.speed
                enemy.speed = original_speed * time_scale
                try:
                    enemy.update_movement(enemy_focus_rect, walls)
                finally:
                    enemy.speed = original_speed
            else:
                enemy.update_movement(enemy_focus_rect, walls)
            # Drain any rings/projectiles emitted by this enemy's strike.
            if hasattr(enemy, "consume_emitted_rings"):
                for ring in enemy.consume_emitted_rings():
                    self.dungeon.pulsator_ring_group.add(ring)
            if hasattr(enemy, "consume_emitted_projectiles"):
                for proj in enemy.consume_emitted_projectiles():
                    self.dungeon.enemy_projectile_group.add(proj)

        # Necromancer: spawn a SkeletonAlly when a kill milestone is pending.
        if identity_runes.necromancer_consume_pending(self.player):
            allies.spawn_skeleton_near(
                self.player, self.dungeon.ally_group, now_ticks,
            )
        # Allies: chase nearest enemy and melee.
        allies.update_allies(
            self.dungeon.ally_group,
            self.dungeon.enemy_group,
            self.player,
            walls,
            now_ticks,
        )

        # enemy-vs-enemy collisions (Pacifist rune)
        enemy_collision_rules.apply_enemy_collisions(
            self.dungeon.enemy_group,
            enemy_collision_rules.enemy_vs_enemy_multiplier(self.player),
            now_ticks,
        )

        # attack hitboxes
        self.dungeon.hitbox_group.update()
        for hitbox in self.dungeon.hitbox_group:
            hits = pygame.sprite.spritecollide(hitbox, self.dungeon.enemy_group, False)
            for enemy in hits:
                if hitbox.try_hit(enemy):
                    self._apply_player_hit(hitbox, enemy)
            # Ricochet: pick a second target near the first primary hit
            if hits:
                ricochet_target = behavior_runes.find_ricochet_target(
                    self.player, hitbox, hits[0], self.dungeon.enemy_group
                )
                if ricochet_target is not None and hitbox.try_hit(ricochet_target):
                    self._apply_player_hit(hitbox, ricochet_target)

        for hitbox in self.dungeon.hitbox_group:
            hits = pygame.sprite.spritecollide(hitbox, self.dungeon.objective_group, False)
            for objective in hits:
                if hitbox.try_hit(objective):
                    objective.take_damage(hitbox.damage)

        # enemy → player/ally damage via telegraphed attacks (no contact damage)
        enemy_attack_rules.apply_enemy_attacks(
            self.dungeon.enemy_group,
            self.player,
            self.dungeon.ally_group,
            now_ticks,
        )
        # Pulsator rings expand and tick once per target.
        self.dungeon.pulsator_ring_group.update()
        enemy_attack_rules.apply_pulsator_rings(
            self.dungeon.pulsator_ring_group,
            self.player,
            self.dungeon.ally_group,
        )
        # Launcher projectiles travel, hit, or despawn on walls.
        self.dungeon.enemy_projectile_group.update()
        enemy_attack_rules.apply_launcher_projectiles(
            self.dungeon.enemy_projectile_group,
            self.player,
            self.dungeon.ally_group,
            walls,
        )

        for objective in self.dungeon.objective_group:
            if hasattr(objective, "apply_enemy_contact"):
                objective.apply_enemy_contact(self.dungeon.enemy_group, now_ticks)

        # item pickup
        for item in list(self.dungeon.item_group):
            if self.player.rect.colliderect(item.rect):
                if isinstance(item, LootDrop):
                    # Check max before collecting
                    inv = self.player.progress.inventory
                    current = inv.get(item.item_id, 0)
                    if current >= item.max_owned:
                        continue  # leave on ground
                item.collect(self.player)
                # Pacifist rune: destroyed when a weapon item is picked up.
                if isinstance(item, LootDrop):
                    item_data = ITEM_DATABASE.get(item.item_id, {})
                    if item_data.get("category") == "weapon":
                        identity_runes.destroy_pacifist_on_weapon_pickup(
                            self.player, self.player.progress,
                        )
                item.kill()

        # Heartstone Claim: pickup, carry-sync, drop on damage, deliver on portal.
        self._update_heartstone(room, hp_at_frame_start)

        # portal check
        objective_update = room.update_objective(
            now_ticks, self.dungeon.enemy_group
        )
        self._apply_room_objective_update(objective_update)
        # Boss orchestration: drive the per-room BossController and react
        # to the events it emits (wave triggers, defeat loot drop).  No-op
        # when the current room has no boss.
        self._update_boss_controller()
        # Test rooms with respawn enabled re-spawn slain configured enemies
        # after their per-room delay so designers can keep testing damage.
        if room.respawn_enemies_after_ms is not None:
            frozen = bool(getattr(room, "frozen_enemies", False))
            attacks_enabled = bool(getattr(room, "enemy_attacks_enabled", True))
            for cls, (px, py) in room.update_enemy_respawns(
                now_ticks, self.dungeon.enemy_group
            ):
                enemy = cls(px, py, is_frozen=frozen)
                enemy.attacks_disabled = not attacks_enabled
                self.dungeon.enemy_group.add(enemy)
        col = self.player.rect.centerx // TILE_SIZE
        row = self.player.rect.centery // TILE_SIZE
        if room.tile_at(col, row) == PORTAL:
            self._on_level_complete()
            return

        # rune altar pickup prompt
        altar_config = room.pending_rune_altar(self.player)
        if altar_config is not None:
            self._pending_rune_altar = altar_config
            self._rune_altar_pick.open(altar_config["offered_rune_ids"])
            self.state = GameState.RUNE_ALTAR_PICK
            return

        # death check
        if not self.player.alive:
            self._on_death()

        # mark room cleared when all enemies are gone after combat started
        room = self.dungeon.current_room
        if (
            not room.enemies_cleared
            and not self.dungeon.enemy_group
            and room.enemy_configs
            and room.respawn_enemies_after_ms is None
        ):
            room.enemies_cleared = True

    def _on_level_complete(self):
        """Player reached the portal — dungeon complete."""
        if self._is_room_test_active():
            self._return_to_room_tests()
            return

        config = get_dungeon(self._current_dungeon_id)
        detail_lines = ()

        if self.dungeon is not None and self.player is not None:
            room = self.dungeon.current_room
            bonus_coins = room.claim_timed_extraction_completion_bonus()
            if bonus_coins:
                self.player.coins += bonus_coins
                detail_lines = (f"Clean extraction bonus: +{bonus_coins} coins",)
            elif (
                room.room_plan is not None
                and room.room_plan.objective_rule == "loot_then_timer"
                and room.objective_status == "overtime"
            ):
                detail_lines = ("Overtime escape: clean extraction bonus lost",)

        self.progress.complete_dungeon_from_runtime(self._current_dungeon_id, self.player)
        detail_lines = detail_lines + _build_trophy_tally_lines(self.progress)
        self._level_complete = LevelCompleteScreen(
            config["name"],
            detail_lines=detail_lines,
        )
        save_progress(self.progress)
        self.state = GameState.LEVEL_COMPLETE

    def _on_death(self):
        """Player died — reset dungeon progress and save."""
        if self._is_room_test_active():
            self._return_to_room_tests()
            return

        self.progress.resolve_dungeon_death(self._current_dungeon_id, self.player)
        save_progress(self.progress)
        self.state = GameState.GAME_OVER

    # ── level complete handler ──────────────────────────
    def _handle_level_complete(self, events):
        choice = self._level_complete.handle_events(events)
        if choice == "Play Again":
            self._start_dungeon(self._current_dungeon_id)
        elif choice == "Return to Dungeon Select":
            self._return_to_menu()

    # ── game over / win handlers ────────────────────────
    def _handle_game_over(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self._return_to_menu()

    def _handle_game_win(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self._return_to_menu()

    # ── pause handler ───────────────────────────────────
    def _handle_paused(self, events):
        choice = self._pause_screen.handle_events(events)
        if choice == "Resume":
            self.state = GameState.PLAYING
        elif choice == "Toggle Room Identifier":
            self._toggle_room_identifier()
        elif choice == "All Items":
            if self._all_items_screen is not None:
                self.state = GameState.PAUSE_ALL_ITEMS
        elif choice == "All Runes":
            if self._all_runes_screen is not None:
                self.state = GameState.PAUSE_ALL_RUNES
        elif choice == "Quit Level":
            self._quit_level()

    def _handle_pause_all_items(self, events):
        if self._all_items_screen is None:
            self.state = GameState.PAUSED
            return
        result = self._all_items_screen.handle_events(events)
        if result == "back":
            self._pause_screen.selected = 0
            self.state = GameState.PAUSED

    def _handle_pause_all_runes(self, events):
        if self._all_runes_screen is None:
            self.state = GameState.PAUSED
            return
        result = self._all_runes_screen.handle_events(events)
        if result == "back":
            self._pause_screen.selected = 0
            self.state = GameState.PAUSED

    # ── rune altar pick handler ─────────────────────────
    def _handle_rune_altar_pick(self, events):
        result = self._rune_altar_pick.handle_events(events)
        if result is None:
            return
        action, rune_id = result
        room = self.dungeon.current_room
        if action == "pick" and rune_id is not None:
            if rune_rules.equip_altar_pick(self.player, self.progress, rune_id):
                if self._pending_rune_altar is not None:
                    room.consume_rune_altar(self._pending_rune_altar)
        elif action == "cancel" and self._pending_rune_altar is not None:
            room.snooze_rune_altar(self._pending_rune_altar)
        self._pending_rune_altar = None
        self.state = GameState.PLAYING
        # Reload sprites so a consumed altar disappears immediately
        self.dungeon._load_room_sprites()

    def _quit_level(self):
        """Quit the current level — revert progress to pre-level snapshot."""
        if self._is_room_test_active():
            self._return_to_room_tests()
            return

        if self._pre_level_progress_snapshot is not None:
            self.progress.abandon_dungeon_run(self._pre_level_progress_snapshot)
        self._return_to_menu(sync_player_state=False)

    def _handle_global_quit(self):
        """Persist progress on window close.

        Mid-dungeon-run handling:
        - Room test active → restore the loadout snapshot, then save without
          syncing the live player (test-room edits never persist).
        - Live dungeon run with a pre-level snapshot → abandon the run by
          reverting to the snapshot before saving.  This prevents picked-
          but-uncommitted runes from leaking into save state when the
          player closes the window mid-run.
        - No active run → sync player state and save normally.
        """
        if self._is_room_test_active():
            self._restore_room_test_loadout()
            save_progress(self.progress)
            return
        if self._pre_level_progress_snapshot is not None:
            self.progress.abandon_dungeon_run(self._pre_level_progress_snapshot)
            save_progress(self.progress)
            return
        self._sync_player_state_to_progress()
        save_progress(self.progress)

    # ── draw ────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(COLOR_BLACK)

        if self.state == GameState.MAIN_MENU:
            self._main_menu.draw(self.screen, build_main_menu_view(self._main_menu))

        elif self.state == GameState.ROOM_TEST_SELECT:
            self._room_test_select.draw(
                self.screen,
                build_room_test_select_view(self._room_test_select),
            )

        elif self.state == GameState.DUNGEON_SELECT:
            self._dungeon_select.draw(
                self.screen,
                build_dungeon_select_view(self._dungeon_select),
            )

        elif self.state == GameState.CHARACTER_CUSTOMIZE:
            self._character_screen.draw(
                self.screen,
                build_character_customize_view(self._character_screen),
            )

        elif self.state == GameState.SHOP:
            self._shop_screen.draw(self.screen, build_shop_view(self._shop_screen))

        elif self.state == GameState.RECORDS:
            self._records_screen.draw(
                self.screen, build_records_view(self._records_screen)
            )

        elif self.state in (GameState.PLAYING, GameState.PAUSED,
                            GameState.PAUSE_ALL_ITEMS, GameState.PAUSE_ALL_RUNES,
                            GameState.LEVEL_COMPLETE,
                            GameState.GAME_OVER, GameState.GAME_WIN,
                            GameState.RUNE_ALTAR_PICK):
            # draw the gameplay underneath overlays
            if self.dungeon and self.player:
                self.camera.draw(
                    self.screen,
                    self.dungeon.current_room,
                    [
                        self.dungeon.enemy_group,
                        self.dungeon.ally_group,
                        self.dungeon.item_group,
                        self.dungeon.chest_group,
                        self.dungeon.objective_group,
                        self.dungeon.pulsator_ring_group,
                        self.dungeon.enemy_projectile_group,
                        self.player_group,
                        self.dungeon.hitbox_group,
                    ],
                    self.dungeon,
                    player=self.player,
                )
                hud_view = build_hud_view(
                    self.player,
                    self.dungeon,
                    show_room_identifier=self._show_room_identifier,
                )
                self.hud.draw(self.screen, hud_view)

            if self.state == GameState.PAUSED:
                self._pause_screen.draw(self.screen, build_pause_screen_view(self._pause_screen))
            elif self.state == GameState.PAUSE_ALL_ITEMS:
                if self._all_items_screen is not None:
                    self._all_items_screen.draw(self.screen)
            elif self.state == GameState.PAUSE_ALL_RUNES:
                if self._all_runes_screen is not None:
                    self._all_runes_screen.draw(self.screen)
            elif self.state == GameState.GAME_OVER:
                self.hud.draw_game_over(self.screen, build_game_over_overlay_view())
            elif self.state == GameState.GAME_WIN:
                self.hud.draw_victory(
                    self.screen,
                    build_victory_overlay_view(self.player.coins),
                )
            elif self.state == GameState.LEVEL_COMPLETE:
                self._level_complete.draw(
                    self.screen,
                    build_level_complete_screen_view(self._level_complete),
                )
            elif self.state == GameState.RUNE_ALTAR_PICK:
                self._rune_altar_pick.draw(
                    self.screen,
                    build_rune_altar_pick_view(self._rune_altar_pick, self.progress),
                )

        pygame.display.flip()


if __name__ == "__main__":
    Game().run()
