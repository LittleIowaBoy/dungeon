"""Player: 8-dir movement, ice momentum, health, inventory, weapon slot, consumables."""
import pygame
import attack_rules
import combat_rules
import consumable_rules
import ability_rules
import dodge_rules
import effect_state_rules
import loadout_rules
import movement_rules
import player_visual_rules
import rune_rules
import status_effects
import time_rules
import tool_rules
from sprites import make_rect_surface
from settings import (
    PLAYER_MAX_HP, PLAYER_SIZE,
    COLOR_PLAYER,
)
from weapons import create_weapon


class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = make_rect_surface(PLAYER_SIZE, PLAYER_SIZE, COLOR_PLAYER)
        self._base_image = self.image.copy()
        self.rect = self.image.get_rect(center=(x, y))

        # stats
        self.max_hp = PLAYER_MAX_HP
        self.current_hp = PLAYER_MAX_HP
        self.speed_multiplier = 1.0
        self.coins = 0

        # progress reference (set in reset_for_dungeon)
        self.progress = None

        # armor
        self.armor_hp = 0

        # movement
        self.facing_dx = 0.0
        self.facing_dy = 1.0  # face down initially
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self._on_ice = False

        # weapons
        self.weapon_ids = ["sword", "spear"]
        self.weapons = [create_weapon(weapon_id) for weapon_id in self.weapon_ids]
        self.current_weapon_index = 0
        self.weapon_upgrade_tiers = {weapon_id: 0 for weapon_id in self.weapon_ids}

        # invincibility
        self._invincible_until = 0
        self._visible = True

        # consumable state
        self.selected_potion_size = "small"  # cycles: small → medium → large
        self.speed_boost_until = 0   # ticks timestamp; 0 = inactive
        self.attack_boost_until = 0  # ticks timestamp; 0 = inactive

        # compass
        self.compass_uses = 0
        self.compass_direction = None       # e.g. "NE"
        self.compass_arrow = None           # e.g. "↗"
        self._compass_display_until = 0     # ticks timestamp

        # heartstone carry state (Heartstone Claim room)
        self.carrying_heartstone = False

        # pit fall animation state
        # _pit_fall_phase cycles: None → "falling" → "shrinking" → "pause" → None
        self._pit_fall_phase = None
        self._pit_fall_started_at = 0
        self._pit_fall_pit_col = 0
        self._pit_fall_pit_row = 0
        self._pit_fall_start_x = 0   # player pixel-x when the fall began
        self._pit_fall_start_y = 0   # player pixel-y when the fall began
        self._pit_entry_col = 0      # tile col the player stepped from (respawn target)
        self._pit_entry_row = 0      # tile row the player stepped from (respawn target)
        self._pit_fall_shrink_t = 0.0  # 0.0→1.0 progress through shrink phase

        # runes (per-dungeon loadout + scratch state)
        self.equipped_runes = rune_rules.empty_loadout()
        self.rune_state = {}

        # dodge
        dodge_rules.reset_runtime_dodge(self)

        # active ability slot (rune-supplied)
        ability_rules.reset_runtime_ability(self)

        # status effects (burning/frozen/etc.) — inert until applied
        status_effects.reset_statuses(self)

        # time scale — 1.0 normal, runes may slow
        time_rules.reset_time_scale(self)

    # ── properties ──────────────────────────────────────
    @property
    def weapon(self):
        if not self.weapons:
            return None
        return self.weapons[self.current_weapon_index]

    @property
    def current_weapon_id(self):
        if not self.weapon_ids:
            return None
        return self.weapon_ids[self.current_weapon_index]

    @property
    def is_invincible(self):
        return combat_rules.is_invincible(self, pygame.time.get_ticks())

    @property
    def alive(self):
        return combat_rules.is_alive(self)

    def weapon_upgrade_tier(self, weapon_id):
        if weapon_id is None:
            return 0
        return self.weapon_upgrade_tiers.get(weapon_id, 0)

    # ── damage ──────────────────────────────────────────
    def take_damage(self, amount):
        combat_rules.take_damage(self, amount, pygame.time.get_ticks())

    # ── weapon switching ────────────────────────────────
    def switch_weapon(self, index):
        if 0 <= index < len(self.weapons):
            self.current_weapon_index = index

    def attack(self):
        return attack_rules.attack(self)

    # ── movement / update ───────────────────────────────
    def update(self, wall_rects, terrain_at):
        """Called every frame. *wall_rects* is a list of pygame.Rect for
        collidable walls. *terrain_at(cx, cy)* returns the terrain string
        at a pixel position.
        """
        movement_rules.update_motion(
            self,
            wall_rects,
            terrain_at,
            pygame.key.get_pressed(),
        )

        player_visual_rules.update_runtime_visuals(self, pygame.time.get_ticks())

    # ── reset on room transition ────────────────────────
    def place(self, x, y):
        """Teleport to (x, y) and zero ice velocity."""
        movement_rules.teleport(self, x, y)

    # ── reset for new dungeon run ───────────────────────
    def reset_for_dungeon(self, progress):
        """Reset in-dungeon stats for a fresh dungeon entry.

        Persistent coins are synced from *progress*.  In-dungeon boosts
        (speed, HP) are reset to base values from progress.
        Equipment (armor, +1 weapons, compass) is loaded from progress.
        """
        self.progress = progress
        self.coins = progress.coins

        movement_rules.reset_runtime_movement(self)

        # Runes — sync loadout BEFORE max-HP reset so stat_runes can scale it.
        rune_rules.sync_runtime_to_progress(self, progress)
        rune_rules.on_room_enter(self)

        combat_rules.reset_runtime_combat(self, progress.max_hp)

        # Armor — persists across levels, loaded from progress
        self.armor_hp = getattr(progress, 'armor_hp', 0)

        # Compass uses — persists across levels
        tool_rules.reset_runtime_tools(self, progress)

        # Equipped weapons and upgrades
        runtime_loadout = loadout_rules.build_runtime_weapon_state(
            progress,
            create_weapon,
        )
        self.weapon_ids = runtime_loadout["weapon_ids"]
        self.weapons = runtime_loadout["weapons"]
        self.current_weapon_index = 0
        self.weapon_upgrade_tiers = runtime_loadout["weapon_upgrade_tiers"]

        # Reset boosts
        consumable_rules.reset_runtime_consumables(self)
        player_visual_rules.reset_runtime_visuals(self)

        # Runes — already synced above; nothing more to do here.
        pass

        # Dodge state — reset cooldowns/i-frames
        dodge_rules.reset_runtime_dodge(self)

        # Active ability — cleared until a rune supplies one
        ability_rules.reset_runtime_ability(self)

        # Status effects — wipe carryover from previous run
        status_effects.reset_statuses(self)

        # Time scale — reset to normal
        time_rules.reset_time_scale(self)

    # ── boost properties ────────────────────────────────
    @property
    def is_speed_boosted(self):
        return effect_state_rules.is_speed_boosted(self, pygame.time.get_ticks())

    @property
    def is_attack_boosted(self):
        return effect_state_rules.is_attack_boosted(self, pygame.time.get_ticks())

    @property
    def compass_showing(self):
        return tool_rules.compass_showing(self, pygame.time.get_ticks())

    def _effective_speed_multiplier(self):
        return effect_state_rules.effective_speed_multiplier(
            self,
            pygame.time.get_ticks(),
        )

    # ── consumable use methods ──────────────────────────
    def cycle_potion(self):
        """Cycle the selected potion size: small → medium → large → small."""
        return consumable_rules.cycle_potion(self)

    def use_potion(self):
        """Use the currently selected potion. Returns True on success."""
        return consumable_rules.use_selected_potion(self)

    def use_speed_boost(self):
        """Activate a speed boost. Returns True on success."""
        return consumable_rules.use_speed_boost(self, pygame.time.get_ticks())

    def use_attack_boost(self):
        """Activate an attack boost. Returns True on success."""
        return consumable_rules.use_attack_boost(self, pygame.time.get_ticks())

    def use_stat_shard(self):
        """Spend a Boulder Stat Shard for a permanent +max_hp bump."""
        return consumable_rules.use_stat_shard(self)

    def use_tempo_rune(self):
        """Spend a Frost Tempo Rune for an extended attack-boost window."""
        return consumable_rules.use_tempo_rune(self, pygame.time.get_ticks())

    def use_mobility_charge(self):
        """Spend a Tide Mobility Charge for a short, sharp speed burst."""
        return consumable_rules.use_mobility_charge(self, pygame.time.get_ticks())

    def use_compass(self, dungeon):
        """Use the compass to find the portal direction. Returns True on success."""
        return tool_rules.use_compass(self, dungeon, pygame.time.get_ticks())
