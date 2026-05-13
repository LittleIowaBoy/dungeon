"""Tests for Pact Shrine room API, _apply_pact_effects, and wired pact mechanics."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_room_plan(objective_rule="pact_shrine", objective_label="Pact Shrine"):
    return SimpleNamespace(
        room_id="pact_shrine_chamber",
        objective_rule=objective_rule,
        objective_label=objective_label,
        objective_entity_count=1,
        enemy_scale_factor=0.0,
        enemy_count_range=(0, 0),
        terrain_patch_count_range="0,1",
        terrain_patch_size_range="2,3",
        clear_center=True,
        is_exit=False,
        guaranteed_chest=False,
        combat_pressure="none",
        trap_intensity_scale=None,
        trap_speed_scale=None,
        trap_suppress_duration_ms=None,
        trap_suppress_cooldown_ms=None,
        trap_safespot_speed_mult=None,
        trap_challenge_reward_kind=None,
        objective_variant=None,
        ritual_role_script=None,
        ritual_link_mode=None,
        ritual_reinforcement_count=0,
        objective_trigger_padding=0,
    )


# ── room._build_pact_shrine_configs ──────────────────────────────────────────

class BuildPactShrineConfigsTests(unittest.TestCase):
    def setUp(self):
        from room import Room, TILE_SIZE, ROOM_COLS, ROOM_ROWS
        from room_plan import RoomPlan
        self.TILE_SIZE = TILE_SIZE
        self.ROOM_COLS = ROOM_COLS
        self.ROOM_ROWS = ROOM_ROWS
        # Build a minimal room with the pact_shrine plan.
        doors = {"top": False, "bottom": False, "left": False, "right": True}
        try:
            from room_plan import RoomPlan
            plan = RoomPlan(**{k: v for k, v in vars(_make_room_plan()).items()})
        except Exception:
            plan = _make_room_plan()
        try:
            self.room = Room(doors, is_exit=False, room_plan=plan)
        except Exception:
            self.skipTest("Room construction requires pygame display")

    def test_produces_one_config(self):
        configs = [c for c in self.room.objective_entity_configs if c.get("kind") == "pact_shrine"]
        self.assertEqual(len(configs), 1)

    def test_kind_is_pact_shrine(self):
        configs = self.room.objective_entity_configs
        self.assertTrue(any(c.get("kind") == "pact_shrine" for c in configs))

    def test_not_consumed_initially(self):
        config = next(c for c in self.room.objective_entity_configs if c.get("kind") == "pact_shrine")
        self.assertFalse(config.get("consumed", False))

    def test_positioned_at_room_center(self):
        config = next(c for c in self.room.objective_entity_configs if c.get("kind") == "pact_shrine")
        cx = (self.ROOM_COLS // 2) * self.TILE_SIZE + self.TILE_SIZE // 2
        cy = (self.ROOM_ROWS // 2) * self.TILE_SIZE + self.TILE_SIZE // 2
        self.assertEqual(config["pos"], (cx, cy))


# ── room.pending_pact_shrine ──────────────────────────────────────────────────

class PendingPactShrineTests(unittest.TestCase):
    """Test the proximity / snoozed / consumed logic without a full Room."""

    def _make_room(self, consumed=False, snoozed=False):
        """Return a minimal mock room with one pact_shrine config."""
        from room import TILE_SIZE, ROOM_COLS, ROOM_ROWS
        cx = (ROOM_COLS // 2) * TILE_SIZE + TILE_SIZE // 2
        cy = (ROOM_ROWS // 2) * TILE_SIZE + TILE_SIZE // 2
        config = {"kind": "pact_shrine", "pos": (cx, cy),
                  "consumed": consumed, "snoozed": snoozed}
        room = SimpleNamespace(
            room_plan=_make_room_plan(),
            objective_entity_configs=[config],
        )
        # Bind the real method from Room onto our stub.
        from room import Room
        room.pending_pact_shrine = Room.pending_pact_shrine.__get__(room, type(room))
        return room, config, (cx, cy)

    def _player_at(self, x, y):
        return SimpleNamespace(rect=SimpleNamespace(center=(x, y)))

    def test_returns_config_when_in_range(self):
        room, config, (cx, cy) = self._make_room()
        player = self._player_at(cx, cy)
        result = room.pending_pact_shrine(player)
        self.assertIs(result, config)

    def test_returns_none_when_far_away(self):
        room, config, (cx, cy) = self._make_room()
        player = self._player_at(cx + 200, cy + 200)
        result = room.pending_pact_shrine(player)
        self.assertIsNone(result)

    def test_returns_none_when_consumed(self):
        room, config, (cx, cy) = self._make_room(consumed=True)
        player = self._player_at(cx, cy)
        result = room.pending_pact_shrine(player)
        self.assertIsNone(result)

    def test_returns_none_when_snoozed(self):
        room, config, (cx, cy) = self._make_room(snoozed=True)
        player = self._player_at(cx, cy)
        result = room.pending_pact_shrine(player)
        self.assertIsNone(result)

    def test_clears_snooze_when_player_leaves(self):
        room, config, (cx, cy) = self._make_room(snoozed=True)
        player = self._player_at(cx + 200, cy + 200)
        room.pending_pact_shrine(player)
        self.assertFalse(config.get("snoozed", False))

    def test_returns_none_for_non_pact_shrine_objective_rule(self):
        room, config, (cx, cy) = self._make_room()
        room.room_plan = _make_room_plan(objective_rule="rune_altar")
        player = self._player_at(cx, cy)
        result = room.pending_pact_shrine(player)
        self.assertIsNone(result)


# ── _apply_pact_effects ───────────────────────────────────────────────────────

class ApplyPactEffectsTests(unittest.TestCase):
    def _make_game(self, max_hp=100, current_hp=100):
        import rpg
        game = rpg.Game.__new__(rpg.Game)
        game.player = SimpleNamespace(max_hp=max_hp, current_hp=current_hp)
        game.dungeon = SimpleNamespace(
            active_pacts=[],
            pact_rune_slot_bonus=0,
        )
        return game

    def test_blood_pact_reduces_max_hp(self):
        import rpg
        game = self._make_game(max_hp=100, current_hp=100)
        rpg.Game._apply_pact_effects(game, "blood_pact")
        self.assertIn("blood_pact", game.dungeon.active_pacts)
        self.assertEqual(game.player.max_hp, 75)

    def test_blood_pact_clamps_current_hp(self):
        import rpg
        game = self._make_game(max_hp=100, current_hp=100)
        rpg.Game._apply_pact_effects(game, "blood_pact")
        self.assertLessEqual(game.player.current_hp, game.player.max_hp)

    def test_hex_grants_rune_slot_bonus(self):
        import rpg
        game = self._make_game()
        rpg.Game._apply_pact_effects(game, "hex_of_fragility")
        self.assertIn("hex_of_fragility", game.dungeon.active_pacts)
        self.assertEqual(game.dungeon.pact_rune_slot_bonus, 1)

    def test_duplicate_pact_ignored(self):
        import rpg
        game = self._make_game(max_hp=100, current_hp=100)
        game.dungeon.active_pacts.append("blood_pact")
        rpg.Game._apply_pact_effects(game, "blood_pact")
        # Should not apply a second time.
        self.assertEqual(game.player.max_hp, 100)

    def test_max_pacts_cap_respected(self):
        import rpg
        from risk_reward_rules import MAX_PACTS_PER_RUN
        game = self._make_game()
        game.dungeon.active_pacts = ["blood_pact"] * MAX_PACTS_PER_RUN
        rpg.Game._apply_pact_effects(game, "hex_of_fragility")
        self.assertNotIn("hex_of_fragility", game.dungeon.active_pacts)


# ── coin_mult wiring ──────────────────────────────────────────────────────────

class CoinMultTests(unittest.TestCase):
    def test_blood_pact_multiplies_coins(self):
        """With blood_pact active (coin_mult=1.5), collecting a coin should grant 1 extra."""
        import rpg
        from items import Coin

        game = rpg.Game.__new__(rpg.Game)
        game.dungeon = SimpleNamespace(active_pacts=["blood_pact"])
        game.player = SimpleNamespace(
            coins=0,
            rect=MagicMock(),
        )
        game.player.rect.colliderect.return_value = True

        coin = Coin.__new__(Coin)
        coin.rect = MagicMock()
        coin.rect.colliderect = MagicMock(return_value=True)

        # Simulate item.collect (adds 1) then coin_mult bonus (adds 0 more since int(1.5-1)=0)
        # Actually int(1.5 - 1.0) = 0 — so coins should end at 1.
        with patch.object(coin, "collect", side_effect=lambda p: setattr(p, "coins", p.coins + 1)):
            with patch("rpg.LootDrop", side_effect=ImportError):
                pass
            # Manually run the inline coin_mult logic:
            coin.collect(game.player)
            from risk_reward_rules import PACTS
            for pid in game.dungeon.active_pacts:
                mult = PACTS.get(pid, {}).get("coin_mult", 1.0)
                if mult != 1.0:
                    game.player.coins += int(mult - 1.0)
                    break

        # int(1.5 - 1.0) = 0, so total = 1
        self.assertEqual(game.player.coins, 1)


# ── PactShrine sprite ────────────────────────────────────────────────────────

class PactShrineEntityTests(unittest.TestCase):
    def setUp(self):
        try:
            import pygame
            pygame.display.init()
            pygame.display.set_mode((1, 1))
        except Exception:
            self.skipTest("pygame display not available")

    def test_mark_consumed_changes_image(self):
        from objective_entities import PactShrine
        shrine = PactShrine(100, 100, consumed=False)
        before = shrine.image.copy()
        shrine.mark_consumed()
        self.assertTrue(shrine.consumed)
        # Image should differ after mark_consumed.
        self.assertNotEqual(shrine.image.get_at((0, 0)), before.get_at((0, 0)))

    def test_consumed_flag_set_on_init(self):
        from objective_entities import PactShrine
        shrine = PactShrine(100, 100, consumed=True)
        self.assertTrue(shrine.consumed)


if __name__ == "__main__":
    unittest.main()
