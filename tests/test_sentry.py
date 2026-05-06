"""Tests for SentryEnemy patrol → alert → chase → arm → explode."""

import unittest

import pygame

import enemies
import enemy_attack_rules
from settings import (
    SENTRY_ALERT_FLASH_MS, SENTRY_ARM_MS, SENTRY_DETONATE_RADIUS,
    SENTRY_EXPLOSION_DAMAGE, SENTRY_EXPLOSION_RADIUS, SENTRY_SIGHT_RADIUS,
    SENTRY_CONE_ANGLE_DEG,
    TILE_SIZE,
)


pygame.init()
pygame.display.set_mode((1, 1))


class _Player:
    def __init__(self, x, y, hp=100):
        self.rect = pygame.Rect(0, 0, 22, 22)
        self.rect.center = (x, y)
        self.current_hp = hp
        self.is_invincible = False

    def take_damage(self, amount, damage_type=None):
        self.current_hp -= amount


def _player_rect(x, y):
    rect = pygame.Rect(0, 0, 22, 22)
    rect.center = (x, y)
    return rect


class SentryStateMachineTests(unittest.TestCase):
    def test_cone_sight_triggers_alert_when_player_in_front(self):
        # Default facing is (1, 0) — right.  Player directly ahead triggers.
        sentry = enemies.SentryEnemy(200, 200, patrol_points=[(200, 200)])
        self.assertEqual(sentry._facing, (1.0, 0.0))
        in_front = _player_rect(200 + int(SENTRY_SIGHT_RADIUS) - 4, 200)
        sentry.update_movement(in_front, [])
        self.assertEqual(sentry._sentry_state, enemies.SENTRY_ALERT)

    def test_cone_sight_misses_player_directly_behind(self):
        # Player directly behind the sentry (opposite facing) should NOT trigger.
        sentry = enemies.SentryEnemy(200, 200, patrol_points=[(200, 200)])
        self.assertEqual(sentry._facing, (1.0, 0.0))
        behind = _player_rect(200 - int(SENTRY_SIGHT_RADIUS) + 4, 200)
        sentry.update_movement(behind, [])
        self.assertEqual(sentry._sentry_state, enemies.SENTRY_PATROL)

    def test_cone_sight_blocked_by_sentry_blocker(self):
        import pygame
        from objective_entities import SentryBlocker
        sentry = enemies.SentryEnemy(200, 200, patrol_points=[(200, 200)])
        blocker = SentryBlocker(240, 200)
        sentry._blocker_rects = [blocker.rect]
        # Player is in the cone but behind the blocker — should not be seen.
        blocked_player = _player_rect(280, 200)
        result = sentry._player_in_sight(blocked_player)
        self.assertFalse(result)

    def test_cone_sight_detects_player_beside_blocker(self):
        from objective_entities import SentryBlocker
        sentry = enemies.SentryEnemy(200, 200, patrol_points=[(200, 200)])
        # Blocker is below the sight line — player at same distance but offset
        # upward should still be visible.
        blocker = SentryBlocker(240, 230)
        sentry._blocker_rects = [blocker.rect]
        visible_player = _player_rect(260, 170)
        result = sentry._player_in_sight(visible_player)
        self.assertTrue(result)

    def test_draw_overlay_returns_without_error(self):
        sentry = enemies.SentryEnemy(200, 200, patrol_points=[(200, 200)])
        surface = pygame.Surface((640, 480), pygame.SRCALPHA)
        sentry.draw_overlay(surface)  # should not raise

    def test_patrol_step_updates_facing_direction(self):
        sentry = enemies.SentryEnemy(
            200, 200, patrol_points=[(200, 200), (240, 200)]
        )
        sentry._patrol_step([])
        # Moving right → facing should point rightward.
        fx, fy = sentry._facing
        self.assertGreater(fx, 0)
        self.assertAlmostEqual(fy, 0.0, places=5)

    def test_alarm_config_marked_triggered_on_alert(self):
        cfg = {"triggered": False}
        sentry = enemies.SentryEnemy(
            200, 200, patrol_points=[(200, 200)], alarm_config=cfg
        )
        sentry.update_movement(_player_rect(210, 200), [])
        self.assertTrue(cfg["triggered"])
        self.assertTrue(cfg["triggered"])

    def test_arm_explode_kills_sentry_and_damages_player(self):
        sentry = enemies.SentryEnemy(200, 200, patrol_points=[(200, 200)])
        # Drive into chase first.
        sentry.update_movement(_player_rect(210, 200), [])  # alert
        # Skip the alert flash window so it transitions to chase.
        pygame.time.wait(0)
        sentry._alert_until = 0  # force chase next tick
        sentry.update_movement(_player_rect(210, 200), [])
        self.assertEqual(sentry._sentry_state, enemies.SENTRY_CHASE)

        # Now within detonate radius.
        player = _Player(200 + int(SENTRY_DETONATE_RADIUS) - 4, 200, hp=100)
        sentry.update_attack_state(player.rect, 5000)
        self.assertEqual(sentry._attack_state, enemies.ATTACK_TELEGRAPH)
        sentry.update_attack_state(player.rect, 5000 + SENTRY_ARM_MS + 1)
        self.assertEqual(sentry._attack_state, enemies.ATTACK_STRIKE)
        # Hitbox is centred on sentry; player inside it should take damage.
        boxes = sentry.active_hitboxes()
        self.assertEqual(len(boxes), 1)
        self.assertEqual(boxes[0].width, SENTRY_EXPLOSION_RADIUS * 2)

        # Apply via the standard pipeline.
        group = pygame.sprite.Group(sentry)
        enemy_attack_rules.apply_enemy_attacks(group, player, None, 5000 + SENTRY_ARM_MS + 1)
        self.assertEqual(player.current_hp, 100 - SENTRY_EXPLOSION_DAMAGE)

        # Strike ends → sentry dies.
        sentry.update_attack_state(player.rect, 5000 + SENTRY_ARM_MS + 200)
        self.assertFalse(sentry.alive())

    def test_player_outside_explosion_unhurt(self):
        sentry = enemies.SentryEnemy(200, 200)
        sentry._sentry_state = enemies.SENTRY_CHASE
        far_player = _Player(200 + SENTRY_EXPLOSION_RADIUS + TILE_SIZE * 4, 200)
        # Force into strike state directly to inspect hitbox application.
        sentry._attack_state = enemies.ATTACK_STRIKE
        group = pygame.sprite.Group(sentry)
        enemy_attack_rules.apply_enemy_attacks(group, far_player, None, 1000)
        self.assertEqual(far_player.current_hp, 100)


if __name__ == "__main__":
    unittest.main()
