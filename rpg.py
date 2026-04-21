"""Top-Down Dungeon Crawler RPG — entry point."""
import copy
import os
import sys
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    TILE_SIZE, ROOM_COLS, ROOM_ROWS,
    COLOR_BLACK,
)
from player import Player
from dungeon import Dungeon
from camera import Camera
from hud import HUD
from room import PORTAL
from items import LootDrop
from game_states import GameState
from dungeon_config import get_dungeon, DUNGEONS
from progress import PlayerProgress
from save_system import save_progress, load_progress
from menu import (
    MainMenuScreen,
    DungeonSelectScreen,
    CharacterCustomizeScreen,
    ShopScreen,
    PauseScreen,
    LevelCompleteScreen,
)
from shop import Shop


class Game:
    def __init__(self):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
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

        # menu screens
        self._main_menu = MainMenuScreen()
        self._dungeon_select = DungeonSelectScreen(self.progress)
        self._character_screen = CharacterCustomizeScreen(self.progress)
        self._shop_screen = ShopScreen(self.progress, self.shop)
        self._level_complete = None  # created on level complete
        self._pause_screen = PauseScreen()

        # snapshot of progress before entering a level (for quit-revert)
        self._pre_level_progress_snapshot = None

        # start at main menu
        self.state = GameState.MAIN_MENU

    # ── start / resume a dungeon level ──────────────────
    def _start_dungeon(self, dungeon_id):
        """Generate a dungeon level and create the player."""
        self._current_dungeon_id = dungeon_id
        config = get_dungeon(dungeon_id)
        dp = self.progress.get_dungeon(dungeon_id)
        self.progress.start_dungeon(dungeon_id)

        # Snapshot progress before entering the level (for quit-revert)
        self._pre_level_progress_snapshot = {
            "coins": self.progress.coins,
            "inventory": copy.deepcopy(self.progress.inventory),
            "armor_hp": self.progress.armor_hp,
            "compass_uses": self.progress.compass_uses,
        }

        self.dungeon = Dungeon(dungeon_config=config,
                               level_index=dp.current_level)

        start_x = ROOM_COLS // 2 * TILE_SIZE + TILE_SIZE // 2
        start_y = ROOM_ROWS // 2 * TILE_SIZE + TILE_SIZE // 2
        self.player = Player(start_x, start_y)
        self.player.reset_for_dungeon(self.progress)
        self.player_group = pygame.sprite.GroupSingle(self.player)
        self.state = GameState.PLAYING

    def _advance_level(self):
        """Move to the next level in the current dungeon."""
        config = get_dungeon(self._current_dungeon_id)
        dp = self.progress.get_dungeon(self._current_dungeon_id)
        completed = self.progress.advance_in_dungeon(
            self._current_dungeon_id, len(config["levels"])
        )

        if completed:
            # entire dungeon cleared
            self._sync_coins_to_progress()
            save_progress(self.progress)
            self.state = GameState.GAME_WIN
        else:
            # snapshot progress for the new level (for quit-revert)
            self._sync_coins_to_progress()
            self._pre_level_progress_snapshot = {
                "coins": self.progress.coins,
                "inventory": copy.deepcopy(self.progress.inventory),
                "armor_hp": self.progress.armor_hp,
                "compass_uses": self.progress.compass_uses,
            }
            # generate next level, keep player HP/coins as-is
            self.dungeon = Dungeon(dungeon_config=config,
                                   level_index=dp.current_level)
            start_x = ROOM_COLS // 2 * TILE_SIZE + TILE_SIZE // 2
            start_y = ROOM_ROWS // 2 * TILE_SIZE + TILE_SIZE // 2
            self.player.place(start_x, start_y)
            self.state = GameState.PLAYING

    def _sync_coins_to_progress(self):
        """Copy the player's in-game state back to persistent progress."""
        if self.player:
            self.progress.coins = self.player.coins
            self.progress.armor_hp = self.player.armor_hp
            self.progress.compass_uses = self.player.compass_uses

    def _return_to_menu(self):
        """Save and go back to main menu."""
        self._sync_coins_to_progress()
        save_progress(self.progress)
        self._dungeon_select = DungeonSelectScreen(self.progress)
        self._character_screen = CharacterCustomizeScreen(self.progress)
        self._shop_screen = ShopScreen(self.progress, self.shop)
        self.state = GameState.MAIN_MENU

    # ── main loop ───────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()

            # global quit
            for event in events:
                if event.type == pygame.QUIT:
                    self._sync_coins_to_progress()
                    save_progress(self.progress)
                    pygame.quit()
                    sys.exit()

            if self.state == GameState.MAIN_MENU:
                self._handle_main_menu(events)
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
        elif result is not None:
            self.state = result

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
                for chest in self.dungeon.chest_group:
                    chest.try_open(self.player.rect, self.dungeon.item_group)

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

            # pause menu
            if event.key == pygame.K_ESCAPE:
                self._pause_screen.selected = 0
                self.state = GameState.PAUSED

    def _update_playing(self):
        room = self.dungeon.current_room
        walls = room.get_wall_rects()

        # player movement
        self.player.update(walls, room.terrain_at_pixel)

        # door transitions
        direction = self.dungeon.try_transition(self.player.rect)
        if direction:
            spawn = self.dungeon.move_to(direction)
            if spawn:
                self.player.place(*spawn)
            return

        # enemies AI + movement
        for enemy in self.dungeon.enemy_group:
            enemy.update_movement(self.player.rect, walls)

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

        # enemy → player contact damage
        if not self.player.is_invincible:
            hits = pygame.sprite.spritecollide(self.player, self.dungeon.enemy_group, False)
            for enemy in hits:
                self.player.take_damage(enemy.damage)
                break

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
        col = self.player.rect.centerx // TILE_SIZE
        row = self.player.rect.centery // TILE_SIZE
        if room.tile_at(col, row) == PORTAL:
            self._on_level_complete()
            return

        # death check
        if not self.player.alive:
            self._on_death()

    def _on_level_complete(self):
        """Player reached the portal — show level complete screen."""
        config = get_dungeon(self._current_dungeon_id)
        dp = self.progress.get_dungeon(self._current_dungeon_id)
        level_num = dp.current_level + 1  # 1-based for display
        total = len(config["levels"])
        is_final = (dp.current_level >= total - 1)

        self._level_complete = LevelCompleteScreen(
            config["name"], level_num, is_final_level=is_final,
        )
        self._sync_coins_to_progress()
        save_progress(self.progress)
        self.state = GameState.LEVEL_COMPLETE

    def _on_death(self):
        """Player died — reset dungeon progress and save."""
        self._sync_coins_to_progress()
        self.progress.die_in_dungeon(self._current_dungeon_id)
        save_progress(self.progress)
        self.state = GameState.GAME_OVER

    # ── level complete handler ──────────────────────────
    def _handle_level_complete(self, events):
        choice = self._level_complete.handle_events(events)
        if choice == "Continue to Next Level":
            self._advance_level()
        elif choice == "Return to Dungeon Select":
            config = get_dungeon(self._current_dungeon_id)
            dp = self.progress.get_dungeon(self._current_dungeon_id)
            self.progress.advance_in_dungeon(
                self._current_dungeon_id, len(config["levels"])
            )
            save_progress(self.progress)
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
        elif choice == "Quit Level":
            self._quit_level()

    def _quit_level(self):
        """Quit the current level — revert progress to pre-level snapshot."""
        if self._pre_level_progress_snapshot is not None:
            # Restore coins, inventory, armor, compass to pre-level state
            snap = self._pre_level_progress_snapshot
            self.progress.coins = snap["coins"]
            self.progress.inventory = snap["inventory"]
            self.progress.armor_hp = snap["armor_hp"]
            self.progress.compass_uses = snap["compass_uses"]
        save_progress(self.progress)
        self._return_to_menu()

    # ── draw ────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(COLOR_BLACK)

        if self.state == GameState.MAIN_MENU:
            self._main_menu.draw(self.screen)

        elif self.state == GameState.DUNGEON_SELECT:
            self._dungeon_select.draw(self.screen)

        elif self.state == GameState.CHARACTER_CUSTOMIZE:
            self._character_screen.draw(self.screen)

        elif self.state == GameState.SHOP:
            self._shop_screen.draw(self.screen)

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
                        self.player_group,
                        self.dungeon.hitbox_group,
                    ],
                    self.dungeon,
                )
                self.hud.draw(self.screen, self.player, self.dungeon)

            if self.state == GameState.PAUSED:
                self._pause_screen.draw(self.screen)
            elif self.state == GameState.GAME_OVER:
                self.hud.draw_game_over(self.screen)
            elif self.state == GameState.GAME_WIN:
                self.hud.draw_victory(self.screen, self.player)
            elif self.state == GameState.LEVEL_COMPLETE:
                self._level_complete.draw(self.screen)

        pygame.display.flip()


if __name__ == "__main__":
    Game().run()
