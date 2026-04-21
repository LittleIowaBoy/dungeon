"""Player: 8-dir movement, ice momentum, health, inventory, weapon slot, consumables."""
import math
import pygame
from sprites import make_rect_surface
from settings import (
    PLAYER_BASE_SPEED, PLAYER_MAX_HP, PLAYER_SIZE,
    INVINCIBILITY_MS, FLASH_INTERVAL_MS,
    TILE_SIZE, ROOM_COLS, ROOM_ROWS,
    ICE_FRICTION, TERRAIN_SPEED,
    COLOR_PLAYER, COLOR_SPEED_GLOW,
    HEAL_SMALL, HEAL_MEDIUM, HEAL_LARGE,
    SPEED_BOOST_DURATION_MS, SPEED_BOOST_MULTIPLIER,
    ATTACK_BOOST_DURATION_MS, ATTACK_BOOST_MULTIPLIER,
    WEAPON_PLUS_MULTIPLIER, ARMOR_HP,
    COMPASS_DISPLAY_MS,
)
from weapons import create_weapon

# Potion size cycle order and healing values
_POTION_SIZES = ["small", "medium", "large"]
_POTION_ITEM_IDS = {
    "small": "health_potion_small",
    "medium": "health_potion_medium",
    "large": "health_potion_large",
}
_POTION_HEAL = {
    "small": HEAL_SMALL,
    "medium": HEAL_MEDIUM,
    "large": HEAL_LARGE,
}
_WEAPON_SLOT_KEYS = ("weapon_1", "weapon_2")
_LEGACY_WEAPON_PLUS_IDS = {
    "sword": "sword_plus",
    "spear": "spear_plus",
    "axe": "axe_plus",
}


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
        return pygame.time.get_ticks() < self._invincible_until

    @property
    def alive(self):
        return self.current_hp > 0

    def weapon_upgrade_tier(self, weapon_id):
        if weapon_id is None:
            return 0
        return self.weapon_upgrade_tiers.get(weapon_id, 0)

    # ── damage ──────────────────────────────────────────
    def take_damage(self, amount):
        if self.is_invincible:
            return
        # Armor absorbs damage first
        if self.armor_hp > 0:
            absorbed = min(amount, self.armor_hp)
            self.armor_hp -= absorbed
            amount -= absorbed
        self.current_hp = max(0, self.current_hp - amount)
        self._invincible_until = pygame.time.get_ticks() + INVINCIBILITY_MS

    # ── weapon switching ────────────────────────────────
    def switch_weapon(self, index):
        if 0 <= index < len(self.weapons):
            self.current_weapon_index = index

    def _load_equipped_weapons(self, progress):
        self.weapon_ids = []
        self.weapons = []
        equipped_slots = getattr(progress, "equipped_slots", {})
        for slot_key in _WEAPON_SLOT_KEYS:
            weapon_id = equipped_slots.get(slot_key)
            weapon = create_weapon(weapon_id)
            if weapon is None:
                continue
            self.weapon_ids.append(weapon_id)
            self.weapons.append(weapon)
        self.current_weapon_index = 0

    def attack(self):
        weapon = self.weapon
        if weapon is None:
            return None

        result = weapon.attack(
            self.rect.centerx, self.rect.centery,
            self.facing_dx, self.facing_dy,
        )
        if result is None:
            return None
        # Calculate damage multiplier
        multiplier = 1.0
        if self.is_attack_boosted:
            multiplier *= ATTACK_BOOST_MULTIPLIER
        upgrade_tier = self.weapon_upgrade_tier(self.current_weapon_id)
        if upgrade_tier > 0:
            multiplier *= WEAPON_PLUS_MULTIPLIER ** upgrade_tier
        # Apply multiplier to hitbox damage(s)
        use_glow = self.is_attack_boosted
        if isinstance(result, list):
            for hb in result:
                hb.damage = int(hb.damage * multiplier)
                if use_glow:
                    hb.set_glow()
        else:
            result.damage = int(result.damage * multiplier)
            if use_glow:
                result.set_glow()
        return result

    # ── movement / update ───────────────────────────────
    def update(self, wall_rects, terrain_at):
        """Called every frame. *wall_rects* is a list of pygame.Rect for
        collidable walls. *terrain_at(cx, cy)* returns the terrain string
        at a pixel position.
        """
        keys = pygame.key.get_pressed()

        # build raw direction from input
        raw_dx, raw_dy = 0.0, 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            raw_dx -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            raw_dx += 1.0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            raw_dy -= 1.0
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            raw_dy += 1.0

        # normalize so diagonal == cardinal speed
        mag = math.hypot(raw_dx, raw_dy)
        if mag > 0:
            raw_dx /= mag
            raw_dy /= mag
            self.facing_dx = raw_dx
            self.facing_dy = raw_dy

        # terrain at current center
        terrain = terrain_at(self.rect.centerx, self.rect.centery)
        self._on_ice = terrain == "ice"

        # compute effective speed
        speed = PLAYER_BASE_SPEED * self._effective_speed_multiplier()
        terrain_mult = TERRAIN_SPEED.get(terrain, 1.0)

        if self._on_ice:
            # ice momentum: input adds to velocity, friction decays
            self.velocity_x += raw_dx * speed * 0.15
            self.velocity_y += raw_dy * speed * 0.15
            self.velocity_x *= ICE_FRICTION
            self.velocity_y *= ICE_FRICTION
        else:
            self.velocity_x = raw_dx * speed * terrain_mult
            self.velocity_y = raw_dy * speed * terrain_mult

        # move and collide (axis-separated)
        self._move_axis(self.velocity_x, 0, wall_rects)
        self._move_axis(0, self.velocity_y, wall_rects)

        # invincibility flash + speed boost glow
        if self.is_invincible:
            now = pygame.time.get_ticks()
            self._visible = ((now // FLASH_INTERVAL_MS) % 2 == 0)
            if self._visible:
                self.image = self._base_image
            else:
                self.image = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE),
                                            pygame.SRCALPHA)
        else:
            self._visible = True
            if self.is_speed_boosted:
                # cyan glow border around player
                glow = pygame.Surface((PLAYER_SIZE + 4, PLAYER_SIZE + 4),
                                      pygame.SRCALPHA)
                glow.fill((*COLOR_SPEED_GLOW, 80))
                glow.blit(self._base_image, (2, 2))
                self.image = glow
                self.rect = glow.get_rect(center=self.rect.center)
            else:
                self.image = self._base_image

    # ── collision helper ────────────────────────────────
    def _move_axis(self, dx, dy, wall_rects):
        self.rect.x += dx
        self.rect.y += dy
        for wall in wall_rects:
            if self.rect.colliderect(wall):
                if dx > 0:
                    self.rect.right = wall.left
                elif dx < 0:
                    self.rect.left = wall.right
                if dy > 0:
                    self.rect.bottom = wall.top
                elif dy < 0:
                    self.rect.top = wall.bottom

    # ── reset on room transition ────────────────────────
    def place(self, x, y):
        """Teleport to (x, y) and zero ice velocity."""
        self.rect.center = (x, y)
        self.velocity_x = 0.0
        self.velocity_y = 0.0

    # ── reset for new dungeon run ───────────────────────
    def reset_for_dungeon(self, progress):
        """Reset in-dungeon stats for a fresh dungeon entry.

        Persistent coins are synced from *progress*.  In-dungeon boosts
        (speed, HP) are reset to base values from progress.
        Equipment (armor, +1 weapons, compass) is loaded from progress.
        """
        self.progress = progress
        self.max_hp = progress.max_hp
        self.current_hp = self.max_hp
        self.speed_multiplier = 1.0
        self.coins = progress.coins
        self._invincible_until = 0
        self._visible = True
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        # Armor — persists across levels, loaded from progress
        self.armor_hp = getattr(progress, 'armor_hp', 0)

        # Compass uses — persists across levels
        self.compass_uses = getattr(progress, 'compass_uses', 0)
        self.compass_direction = None
        self.compass_arrow = None
        self._compass_display_until = 0

        # Equipped weapons and upgrades
        if hasattr(progress, "ensure_loadout_state"):
            progress.ensure_loadout_state()
        self._load_equipped_weapons(progress)

        # Upgrade tiers (with legacy inventory fallback)
        inv = progress.inventory
        self.weapon_upgrade_tiers = dict(getattr(progress, "weapon_upgrades", {}))
        for weapon_id, legacy_item_id in _LEGACY_WEAPON_PLUS_IDS.items():
            if inv.get(legacy_item_id, 0) > 0:
                self.weapon_upgrade_tiers[weapon_id] = max(
                    self.weapon_upgrade_tiers.get(weapon_id, 0),
                    1,
                )

        # Reset boosts
        self.speed_boost_until = 0
        self.attack_boost_until = 0
        self.selected_potion_size = "small"

    # ── boost properties ────────────────────────────────
    @property
    def is_speed_boosted(self):
        return pygame.time.get_ticks() < self.speed_boost_until

    @property
    def is_attack_boosted(self):
        return pygame.time.get_ticks() < self.attack_boost_until

    @property
    def compass_showing(self):
        return pygame.time.get_ticks() < self._compass_display_until

    def _effective_speed_multiplier(self):
        if self.is_speed_boosted:
            return SPEED_BOOST_MULTIPLIER
        return self.speed_multiplier

    # ── consumable use methods ──────────────────────────
    def cycle_potion(self):
        """Cycle the selected potion size: small → medium → large → small."""
        idx = _POTION_SIZES.index(self.selected_potion_size)
        self.selected_potion_size = _POTION_SIZES[(idx + 1) % len(_POTION_SIZES)]

    def use_potion(self):
        """Use the currently selected potion. Returns True on success."""
        if self.progress is None:
            return False
        item_id = _POTION_ITEM_IDS[self.selected_potion_size]
        inv = self.progress.inventory
        if inv.get(item_id, 0) <= 0:
            return False
        heal = _POTION_HEAL[self.selected_potion_size]
        self.current_hp = min(self.current_hp + heal, self.max_hp)
        inv[item_id] -= 1
        if inv[item_id] <= 0:
            del inv[item_id]
        return True

    def use_speed_boost(self):
        """Activate a speed boost. Returns True on success."""
        if self.progress is None:
            return False
        inv = self.progress.inventory
        if inv.get("speed_boost", 0) <= 0:
            return False
        inv["speed_boost"] -= 1
        if inv["speed_boost"] <= 0:
            del inv["speed_boost"]
        self.speed_boost_until = pygame.time.get_ticks() + SPEED_BOOST_DURATION_MS
        return True

    def use_attack_boost(self):
        """Activate an attack boost. Returns True on success."""
        if self.progress is None:
            return False
        inv = self.progress.inventory
        if inv.get("attack_boost", 0) <= 0:
            return False
        inv["attack_boost"] -= 1
        if inv["attack_boost"] <= 0:
            del inv["attack_boost"]
        self.attack_boost_until = pygame.time.get_ticks() + ATTACK_BOOST_DURATION_MS
        return True

    def use_compass(self, dungeon):
        """Use the compass to find the portal direction. Returns True on success."""
        if self.compass_uses <= 0:
            return False
        self.compass_uses -= 1
        # Update progress
        if self.progress is not None:
            self.progress.compass_uses = self.compass_uses

        # Calculate direction from current room to exit
        cx, cy = dungeon.current_pos
        ex, ey = dungeon._exit_pos
        dx = ex - cx
        dy = ey - cy

        if dx == 0 and dy == 0:
            self.compass_direction = "HERE"
            self.compass_arrow = "●"
        else:
            # Map to 8-direction compass (screen coords: +y is down)
            direction = ""
            arrow = ""
            if dy < 0:
                direction += "N"
            elif dy > 0:
                direction += "S"
            if dx > 0:
                direction += "E"
            elif dx < 0:
                direction += "W"

            _ARROWS = {
                "N": "↑", "S": "↓", "E": "→", "W": "←",
                "NE": "↗", "NW": "↖", "SE": "↘", "SW": "↙",
            }
            arrow = _ARROWS.get(direction, "?")
            self.compass_direction = direction
            self.compass_arrow = arrow

        self._compass_display_until = pygame.time.get_ticks() + COMPASS_DISPLAY_MS
        return True
