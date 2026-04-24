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
- ritual rooms can gate altar damage behind pulse windows for biome-specific timing play
- resource race rooms now escalate claimant pressure, allow steal-back/reclaim loops, and rename relic objectives per biome
- stealth rooms use a short search phase before full lockdown when alarms are triggered
- timed extraction rooms can escalate with pursuit waves before overtime cleanup begins
- escort rooms have higher escort durability, spawn the escort next to the player on entry, and highlight the exit destination in-room

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
- stealth rooms use biome-specific beacon layouts, labels, and search windows
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

Deferred follow-up after the initial breadth-first roadmap sweep:

1. Resource Race C2: interrupt and steal-back interactions
2. Stealth Passage S1/S2: patrol routes, vision cones, and partial-detection escalation
3. Timed Extraction T1/T2: route-closing events and stronger pursuit scripting
4. Puzzle P1 follow-up: additional anti-camping and alternate-solve variants beyond ordered, staggered, and paired rule sets

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
