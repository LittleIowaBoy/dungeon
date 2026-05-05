# Dungeon

Randomly generated top-down dungeon crawler built with pygame. The project currently combines topology-first level generation, data-driven room templates, persistent SQLite-backed progress, and a growing set of objective room families that vary by biome.

## Current State

The game currently supports three biome dungeons:

- Mud Caverns: earth-themed rooms with shrine, quarry, and boulder-flavored variants.
- Frozen Depths: ice-themed rooms with whiteout, crystal, and reliquary variants.
- Sunken Ruins: water-themed rooms with tide, floodgate, and sarcophagus variants.

Across those dungeons, the room catalog now includes distinct implementations for:

- standard combat
- escort protection
- escort bomb carrier
- puzzle gated doors
- survival holdout
- ritual disruption
- resource race
- trap gauntlet
- stealth passage
- timed extraction

## Room Tests

The main menu now includes a dedicated `Room Tests` path for single-room play-testing.

- The roster is built from the live room catalog, so it includes each base room once plus distinct biome counterparts when their merged rules differ.
- Selecting a room launches a deterministic single-room dungeon using that room's biome profile, terrain, pacing weights, and objective metadata.
- Room-test runs are ephemeral: dying, clearing the room, or choosing `Quit Level` returns directly to the room-test selector instead of mutating campaign progress.
- Test-room spawns avoid portal and door tiles, so a run does not auto-complete from an invalid starting position.
- Escort-focused room tests now place the escort adjacent to the player on entry and draw an in-room overlay toward the escort goal.

## Run

1. Create and activate a virtual environment.
2. Install dependencies.
3. Launch the game from the repo root.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python rpg.py
```

The game uses the standard library `sqlite3` module for progress persistence, so there is no separate database service to start.

## Test

Run the full automated test suite from the repo root:

```powershell
python -m unittest discover -s tests
```

For narrower iteration during room-mechanic work, these files are the usual fast slices:

```powershell
python -m unittest tests.test_room_objectives tests.test_room_selector tests.test_content_db
python -m unittest tests.test_player tests.test_runtime_rules tests.test_rpg_runtime
```

## Controls

- `WASD` or arrow keys: move
- `1` / `2`: switch equipped weapon slots
- `Space`: attack
- `E`: open chest when in range
- `Q`: cycle potion size
- `4`: use potion
- `5`: use speed boost
- `6`: use attack boost
- `7`: use compass
- `8`: use Boulder Stat Shard (permanent +max HP, biome reward)
- `9`: use Frost Tempo Rune (extended attack-boost window, biome reward)
- `0`: use Tide Mobility Charge (short, sharp speed burst, biome reward)
- `3`: use Spark Charge (reduces dodge cooldown by 60% for 12s)
- `Esc`: pause menu
- `F3`: toggle the play-test room identifier overlay during a run

In the Room Tests selector, use `Up` / `Down` or `W` / `S` to move, `Enter` or `Space` to launch the selected room, and `Esc` to return to the main menu.

## Play-Test Room Identifier

The room identifier overlay is a runtime-only testing aid. It is enabled from `settings.py` by default and can be toggled in two places while the game is running:

- directly with `F3`
- from the pause menu through `Toggle Room Identifier`

The overlay is intentionally non-persistent. It does not change objectives, rewards, combat rules, or saved progress.

## Objective Depth

The current room families now expose more of their mechanics directly in runtime play and play-testing:

- trap gauntlets use switchable safe lanes, checkpoint reroutes, and challenge-side cache placement across sweeper, vent, crusher, and mixed-hazard variants
- puzzle rooms support ordered plates, staggered-sequence plates, and paired-rune variants, including reinforcement penalties for resets or stalling
- holdout rooms can spawn stabilizers that delay future reinforcement waves and add clearer target guidance
- ritual rooms can gate altar damage behind pulse windows for biome-specific timing play, and the Spore Totem Grove now correctly empowers surviving altars when ward links are broken
- resource race rooms now escalate claimant pressure, allow steal-back/reclaim loops, and rename relic objectives per biome
- the Heartstone Claim variant of the resource race requires the player to physically carry a heart-shaped relic to the portal; taking damage drops it where the player stood, the portal stays sealed until delivery, and the HUD shows a `♥ Heartstone` badge while carrying
- stealth rooms use patrolling alarm beacons, forward vision cones, a short search phase, bonus caches that are lost when alarms trip, and biome-specific failure responses including escape and delayed seal-release variants
- timed extraction rooms can escalate with pursuit waves, temporarily seal the exit during collapse phases, preserve a clean-clear payout bonus, roll into overtime cleanup pressure, and explain the clean-vs-overtime result on the level-complete screen; while the clean-clear bonus is still earnable the HUD shows a `+N BONUS` badge next to the objective label
- escort rooms have higher escort durability, spawn the escort next to the player on entry, and highlight the exit destination in-room; once the escort reaches the exit the NPC despawns instead of lingering in the room
- objective rooms share a primary/secondary fallback model: when a primary objective fails (escort dies, alarm triggers a lockdown, the rival claims the relic) the room falls back to a "clear remaining enemies" secondary so the run can still progress

## Items & Equipment

Items are defined in `item_catalog.py` as a single `ITEM_DATABASE` dict and consumed by the shop, loot tables, and chest drops. Each entry carries category, rarity, cost, drop weights, and a `can_purchase` flag.

### Rarity

All items have a fixed rarity tier that gates stat magnitudes and affix generation:

`COMMON → UNCOMMON → RARE → EPIC → LEGENDARY`

Rarity affects color coding in the HUD and shop, and determines which affix pool an item draws from.

### Damage Types & Resistances

Combat recognises five damage types: `physical`, `fire`, `ice`, `lightning`, and `poison`. Armor pieces and accessories can carry per-type resistance values that reduce incoming damage multiplicatively. Enemy attacks specify a damage type so resistances interact with all combat sources.

### Armor

Beyond the base `armor` slot the game includes four named equipment sets:

| Set | Pieces |
|-----|--------|
| Iron | iron_chestplate, iron_helmet, iron_greaves, iron_gauntlets |
| Golem | golem_core, golem_helm, golem_treads, golem_fists |
| Wayfarer | wayfarer_vest, wayfarer_hood, wayfarer_boots, wayfarer_gloves |
| Spellweave | spellweave_robe, spellweave_cowl, spellweave_leggings, spellweave_bracers |

Each piece has a distinct resistance profile and stat spread to encourage build variety.

### Rings (Accessory)

Twelve rings across four progressive upgrade slots (`ring_slot_1` – `ring_slot_4`). Equipping all four **Oathbinder** rings grants a bonus dodge charge. Sanguine rings carry lifesteal.

| Ring | Effect |
|------|--------|
| iron_band, copper_ring, jade_ring | baseline defense/attack/speed |
| signet_ring, hunters_band | damage bonuses and resistance |
| lifesteal_ring, vampiric_band | lifesteal on hit |
| oathbinder_ring ×4 (one per slot) | set bonus: +1 dodge charge when all equipped |
| shadow_loop | dodge-cooldown reduction |

### Pendants (Accessory)

Eight pendants in a single `pendant_slot`. Damage-resistance pendants reduce a specific type; **serpent_charm** additionally cleanses poison stacks on equip.

| Pendant | Primary effect |
|---------|----------------|
| amulet_of_vigor | +max HP |
| pendant_of_swiftness | +move speed |
| ember_pendant | fire resistance |
| frost_pendant | ice resistance |
| storm_pendant | lightning resistance |
| venom_ward | poison resistance |
| serpent_charm | poison resistance + cleanse |
| void_locket | +all resistances (small) |

### Belts (Accessory)

Five belts in a `belt_slot`, each with a unique theme-keyed per-piece bonus:

| Belt | Bonus |
|------|-------|
| leather_belt | flat HP and defense |
| hunters_belt | +arrow damage |
| mages_sash | +spell damage |
| champions_girdle | +all damage |
| shadowweave_belt | +dodge distance |

### Consumables

| Item | Hotkey | Effect |
|------|--------|--------|
| Potion (small/medium/large) | `4` | restore HP |
| Speed Boost | `5` | +move speed for 8s |
| Attack Boost | `6` | +attack damage for 8s |
| Compass | `7` | reveal minimap |
| Spark Charge | `3` | −60% dodge cooldown for 12s; stacks up to 2 and retroactively shortens any in-flight cooldown |

### Shop Tabs

The in-run shop organises its stock into five tabs navigable with `Q` / `E` or `←` / `→`:

`Consumables → Armor → Accessories → Weapons → Trophies`

The **Trophies** tab shows owned biome rewards and exposes the trophy-exchange (`1`–`3`) and keystone-craft (`4`) hotkeys. The remaining tabs filter items by category so each visit shows only the relevant stock.

## Rune System

Runes are persistent per-run modifiers picked up from rare Rune Altar rooms. Each pickup offers a 1-of-3 choice across three categories with strict slot limits:

- **Stat runes (3 slots)**: simple offensive, defensive, and mobility tradeoffs (Bloodthirst, Glass Cannon, Last Stand, Sprinter, Heavy Hitter, etc.)
- **Behavior runes (1 slot)**: rewrite how attacks or abilities resolve (Ricochet, Shockwave, Vampiric Strike, Afterimage, Overclock, Chain Reaction, Static Charge, Boomerang, Shrapnel Burst)
- **Identity runes (1 slot)**: rewrite the run's game plan (The Pacifist, Glass Soul, Time Anchor, Necromancer, The Conduit)

Architecture seams:

- `rune_catalog.py`: rune definitions, categories, and rarity weights
- `rune_rules.py`: equip/unequip, altar offer generation, per-room state reset, save serialization
- `stat_runes.py` / `behavior_runes.py` / `identity_runes.py`: pure-function effect resolution called from `attack_rules.py`, `combat_rules.py`, `consumable_rules.py`, `dodge_rules.py`, `status_effects.py`, and `rpg.py`
- `allies.py`: the Necromancer skeleton ally sprite and per-frame update
- `hud_view.py` / `hud.py`: equipped-runes panel and per-rune meters (Time Anchor patience, Static Charge, Glass Soul i-frame)

## Architecture

The project is intentionally data-driven. The most important ownership seams are:

- `rpg.py`: main loop, state transitions, room-objective update application, and play-test toggle wiring
- `dungeon.py`: dungeon build, room transitions, sprite loading, minimap state
- `dungeon_topology.py`: topology planning, branch shapes, path metadata, reward tiers
- `room_selector.py`: template filtering and conversion from content rows to `RoomPlan`
- `room_test_catalog.py`: room-test roster assembly and deterministic plan construction for single-room launches
- `room_plan.py`: room template and runtime plan dataclasses
- `content_db.py`: room catalog schema, base templates, and per-dungeon biome overrides
- `room.py`: room runtime ownership, objective state machines, HUD copy, and reward logic
- `objective_entities.py`: room-specific non-enemy runtime actors such as altars, alarm beacons, stabilizers, traps, and escort NPCs
- `hud_view.py` / `hud.py`: gameplay HUD projection and rendering
- `menu_view.py` / `menu.py`: menu and pause-screen projection and rendering
- `progress.py` / `save_system.py`: persistent run and dungeon progress

## Biome Snapshot

Phase E widened biome identity beyond trap, puzzle, ritual, and extraction. The remaining objective families now also carry biome-specific variants through catalog data and progression tuning:

- escort rooms have biome-specific labels and escort tuning per dungeon
- holdout rooms have biome-specific zone labels and pressure tuning
- resource race rooms use biome-specific relic variants and claimant-pressure timing
- stealth rooms use biome-specific beacon layouts, patrol sweeps, labels, search windows, and failure responses
- frozen and water dungeon progression profiles now diverge from the mud baseline instead of sharing identical level pacing

## Roadmap Status

Breadth-first roadmap work completed so far:

- main-menu Room Tests selector with biome-aware single-room launches
- topology-first generation with path metadata, branch shaping, and terminal reward tiers
- runtime-toggleable play-test room identifier overlay
- trap gauntlet milestone closure: mixed hazard lanes, checkpoint reroutes, and challenge-side vault placement
- puzzle gated doors milestone started: staggered-sequence variant added on top of ordered and paired rules
- survival holdout depth slice
- ritual disruption timing-window slice
- breadth pass across resource race, stealth passage, and timed extraction
- runtime hardening for core rules and game-loop helper seams
- biome-specific room and progression expansion across mud, ice, and water dungeons
- README and project documentation refresh

**Item expansion (F1–F8) — completed May 2026:**

- **F1 — Rarity foundation**: `RARITY_COMMON` through `RARITY_LEGENDARY` tier constants; per-rarity affix lists wired into `item_catalog.py`; 912 tests
- **F2 — Damage types & resistances**: five damage types (`physical`, `fire`, `ice`, `lightning`, `poison`); per-type resistance fields on armor and accessories; enemy attacks carry type tags; 948 tests (+36)
- **F3 — Armor deepening**: 16 named armor pieces across four sets (Iron, Golem, Wayfarer, Spellweave); distinct resistance profiles and stat spreads; 990 tests (+42)
- **F4 — Rings**: 12 rings across four progressive accessory slots; Oathbinder set bonus (extra dodge charge); lifesteal on Sanguine rings; shadow_loop dodge-cooldown ring; 1026 tests (+36)
- **F5 — Pendants**: 8 pendants in a single pendant slot; per-type damage resistance pendants; `serpent_charm` cleanses poison on equip; 1051 tests (+25)
- **F6 — Belts**: 5 belts in a belt slot with theme-keyed per-piece bonuses (HP, arrow damage, spell damage, all damage, dodge distance); 1079 tests (+28)
- **F7 — Spark Charge consumable**: reduces dodge cooldown by 60% for 12s; stacks up to 2; retroactively shortens any in-flight cooldown; HUD quickbar slot and active-effect indicator; hotkey `3`; 1109 tests (+30)
- **F8 — Shop UI tabs**: five-tab shop (`Consumables`, `Armor`, `Accessories`, `Weapons`, `Trophies`) navigable with `Q`/`E` or `←`/`→`; Trophies tab gates exchange and keystone-craft hotkeys; `build_shop_view` projects tab state into `ShopView`; 1142 tests (+33)

**UI polish — May 2026:**

- **Menu highlighting**: all menus replace color-change cursor with an underline. The selected item keeps its natural color (rarity color for items, white for plain lists) and gains a 2px underline. Applies to the main menu, dungeon select, room test selector, room test category screen, shop, pause screens, character loadout panel, and all rune/item test-room sub-screens.
- **Shop Weapons tab**: `sword_plus`, `spear_plus`, and `axe_plus` re-categorised from `"equipment"` to `"weapon_upgrade"` so they appear in the Weapons tab rather than being silently hidden. `shop.py` and `menu.py` guard for the legacy pattern where `weapon_upgrade` items may lack an `upgrade_weapon_id`.
- **All Items test-room screen**: item names now use rarity colors. A description panel to the right of the item list shows the selected item's name, rarity tier, word-wrapped description, slot(s), and theme tag when the items panel is focused.

Deferred follow-up after the initial breadth-first roadmap sweep:

1. Stealth Passage S4: broader biome-specific failure gimmicks and stealth-only twists beyond the current escape and seal-release variants
2. Timed Extraction T2/T3: stronger pursuit scripting and additional clean-vs-overtime reward depth beyond the current completion bonus and result messaging
3. Puzzle P1 follow-up: additional anti-camping and alternate-solve variants beyond ordered, staggered, and paired rule sets

## Project Layout

Important files and directories:

- `tests/`: focused unit and integration tests for room content, selector behavior, topology, player runtime, and menu/HUD projection
- `ideas.txt`: longer-horizon biome, rune, item, and enemy ideas
- `room_depth_and_generation_plan.md`: planning document for room-family depth and generator evolution
- `requirements.txt`: Python dependency list

## Implementation Notes

When extending the game, prefer these patterns:

- add new room tuning or variants in `content_db.py` first
- pass new metadata through `room_selector.py` and `room_plan.py`
- keep room-family runtime state inside `room.py`
- put visible or overlap-driven objective entities in `objective_entities.py`
- ship new room work with focused runtime tests plus selector/content coverage
