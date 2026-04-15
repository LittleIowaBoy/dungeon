"""Top-Down Dungeon Crawler RPG — entry point."""
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

# ── Game states ─────────────────────────────────────────
PLAYING   = "playing"
GAME_OVER = "game_over"
GAME_WIN  = "game_win"


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Dungeon Crawler")
        self.clock = pygame.time.Clock()
        self.camera = Camera()
        self.hud = HUD()
        self._new_game()

    # ── init / restart ──────────────────────────────────
    def _new_game(self):
        self.state = PLAYING
        self.dungeon = Dungeon()
        start_x = ROOM_COLS // 2 * TILE_SIZE + TILE_SIZE // 2
        start_y = ROOM_ROWS // 2 * TILE_SIZE + TILE_SIZE // 2
        self.player = Player(start_x, start_y)
        self.player_group = pygame.sprite.GroupSingle(self.player)

    # ── main loop ───────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(FPS)
            self._handle_events()
            if self.state == PLAYING:
                self._update()
            self._draw()

    # ── events ──────────────────────────────────────────
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                # restart from end screens
                if self.state in (GAME_OVER, GAME_WIN) and event.key == pygame.K_r:
                    self._new_game()
                    return

                if self.state != PLAYING:
                    continue

                # weapon switching
                if event.key == pygame.K_1:
                    self.player.switch_weapon(0)
                elif event.key == pygame.K_2:
                    self.player.switch_weapon(1)
                elif event.key == pygame.K_3:
                    self.player.switch_weapon(2)

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

    # ── update ──────────────────────────────────────────
    def _update(self):
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
            return  # skip rest of frame on transition

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
                break  # only take damage from one enemy per frame

        # item pickup
        collected = pygame.sprite.spritecollide(self.player, self.dungeon.item_group, True)
        for item in collected:
            item.collect(self.player)

        # portal check
        col = self.player.rect.centerx // TILE_SIZE
        row = self.player.rect.centery // TILE_SIZE
        if room.tile_at(col, row) == PORTAL:
            self.state = GAME_WIN

        # death check
        if not self.player.alive:
            self.state = GAME_OVER

    # ── draw ────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(COLOR_BLACK)
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
        )
        self.hud.draw(self.screen, self.player, self.dungeon)

        if self.state == GAME_OVER:
            self.hud.draw_game_over(self.screen)
        elif self.state == GAME_WIN:
            self.hud.draw_victory(self.screen, self.player)

        pygame.display.flip()


if __name__ == "__main__":
    Game().run()
