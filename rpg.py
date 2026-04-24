"""Top-Down Dungeon Crawler RPG — entry point."""
import os
import sys
import pygame
from chest import Chest
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
    PauseScreen,
    LevelCompleteScreen,
)
from menu_view import (
    build_main_menu_view,
    build_character_customize_view,
    build_dungeon_select_view,
    build_level_complete_screen_view,
    build_pause_screen_view,
    build_room_test_select_view,
    build_shop_view,
)
from room_test_catalog import build_room_test_plan, load_room_test_entries
from shop import Shop


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
        self._main_menu = MainMenuScreen()
        self._room_test_select = RoomTestSelectScreen(load_room_test_entries())
        self._dungeon_select = DungeonSelectScreen(self.progress)
        self._character_screen = CharacterCustomizeScreen(self.progress)
        self._shop_screen = ShopScreen(self.progress, self.shop)
        self._level_complete = None  # created on level complete
        self._pause_screen = PauseScreen(
            room_identifier_enabled=self._show_room_identifier,
        )

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

        room_plan = build_room_test_plan(entry)
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
            for chest in self.dungeon.chest_group:
                chest.set_reward_tier(reward_tier)
        elif update_result.get("kind") == "spawn_reward_chest":
            x, y = update_result.get("position", (None, None))
            if x is not None and y is not None and not self.dungeon.chest_group:
                self.dungeon.chest_group.add(
                    Chest(
                        x,
                        y,
                        looted=False,
                        reward_tier=update_result.get("reward_tier", "standard"),
                    )
                )

    # ── main loop ───────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()

            # global quit
            for event in events:
                if event.type == pygame.QUIT:
                    if not self._is_room_test_active():
                        self._sync_player_state_to_progress()
                    save_progress(self.progress)
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
            elif self.state == GameState.PLAYING:
                self._handle_playing(events)
                self._update_playing()
            elif self.state == GameState.PAUSED:
                self._handle_paused(events)
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

            elif event.key == pygame.K_F3:
                self._toggle_room_identifier()

            # pause menu
            if event.key == pygame.K_ESCAPE:
                self._pause_screen.selected = 0
                self.state = GameState.PAUSED

    def _update_playing(self):
        room = self.dungeon.current_room
        walls = room.get_wall_rects()
        now_ticks = pygame.time.get_ticks()

        # player movement
        self.player.update(walls, room.terrain_at_pixel)

        # door transitions
        direction = self.dungeon.try_transition(self.player.rect)
        if direction:
            spawn = self.dungeon.move_to(direction)
            if spawn:
                self.player.place(*spawn)
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

        enemy_focus_rect = self.player.rect
        for objective in self.dungeon.objective_group:
            if hasattr(objective, "enemy_target_rect"):
                target_rect = objective.enemy_target_rect()
                if target_rect is not None:
                    enemy_focus_rect = target_rect
                    break

        # enemies AI + movement
        for enemy in self.dungeon.enemy_group:
            enemy.update_movement(enemy_focus_rect, walls)

        # attack hitboxes
        self.dungeon.hitbox_group.update()
        for hitbox in self.dungeon.hitbox_group:
            hits = pygame.sprite.spritecollide(hitbox, self.dungeon.enemy_group, False)
            for enemy in hits:
                if hitbox.try_hit(enemy):
                    enemy.take_damage(hitbox.damage)
                    if enemy.current_hp <= 0:
                        drop = enemy.roll_drop()
                        if drop:
                            self.dungeon.item_group.add(drop)

        for hitbox in self.dungeon.hitbox_group:
            hits = pygame.sprite.spritecollide(hitbox, self.dungeon.objective_group, False)
            for objective in hits:
                if hitbox.try_hit(objective):
                    objective.take_damage(hitbox.damage)

        # enemy → player contact damage
        if not self.player.is_invincible:
            hits = pygame.sprite.spritecollide(self.player, self.dungeon.enemy_group, False)
            for enemy in hits:
                self.player.take_damage(enemy.damage)
                break

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
                item.kill()

        # portal check
        objective_update = room.update_objective(
            now_ticks, self.dungeon.enemy_group
        )
        self._apply_room_objective_update(objective_update)
        col = self.player.rect.centerx // TILE_SIZE
        row = self.player.rect.centery // TILE_SIZE
        if room.tile_at(col, row) == PORTAL:
            self._on_level_complete()
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
        elif choice == "Quit Level":
            self._quit_level()

    def _quit_level(self):
        """Quit the current level — revert progress to pre-level snapshot."""
        if self._is_room_test_active():
            self._return_to_room_tests()
            return

        if self._pre_level_progress_snapshot is not None:
            self.progress.abandon_dungeon_run(self._pre_level_progress_snapshot)
        self._return_to_menu(sync_player_state=False)

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

        elif self.state in (GameState.PLAYING, GameState.PAUSED,
                            GameState.LEVEL_COMPLETE,
                            GameState.GAME_OVER, GameState.GAME_WIN):
            # draw the gameplay underneath overlays
            if self.dungeon and self.player:
                self.camera.draw(
                    self.screen,
                    self.dungeon.current_room,
                    [
                        self.dungeon.enemy_group,
                        self.dungeon.item_group,
                        self.dungeon.chest_group,
                        self.dungeon.objective_group,
                        self.player_group,
                        self.dungeon.hitbox_group,
                    ],
                    self.dungeon,
                )
                hud_view = build_hud_view(
                    self.player,
                    self.dungeon,
                    show_room_identifier=self._show_room_identifier,
                )
                self.hud.draw(self.screen, hud_view)

            if self.state == GameState.PAUSED:
                self._pause_screen.draw(self.screen, build_pause_screen_view(self._pause_screen))
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

        pygame.display.flip()


if __name__ == "__main__":
    Game().run()
