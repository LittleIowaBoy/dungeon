# Room Depth And Generation Plan

## Purpose

This document turns the current room-generation prototype set into two concrete next-stage plans:

1. deepen the mechanics of each implemented room family so the rooms feel distinct beyond their prototype rule,
2. formalize dungeon generation rules so those room families are assigned intentionally along a preplanned main path and later-generated side paths.

The current architecture already gives us the right seams:

- `content_db.py` owns the room catalog and per-dungeon overrides,
- `dungeon_topology.py` preplans the main path and branch stubs,
- `room_selector.py` maps topology context into a `RoomPlan`,
- `room.py` owns room objective state and completion rules,
- `objective_entities.py` owns room-specific runtime actors.

The next work should preserve that split and push more decision-making into data and planning rather than adding more one-off room logic inside `Dungeon`.

## Status Checkpoint (2026-04-23)

This plan now doubles as a resume point for the current implementation state.

### Implemented foundation

- `content_db.py` is live and seeds the room catalog from SQLite, including per-dungeon overrides and migration-safe metadata expansion.
- `dungeon_topology.py` now builds a full main path plus branch paths up front, with path metadata, difficulty bands, terminal flags, and reward tiers.
- `room_selector.py` now consumes path context, enforces stage-aware placement, applies anti-repeat rules, and passes template-owned shaping metadata into `RoomPlan`.
- `Dungeon` and `Room` now instantiate planned rooms directly from topology and selector output instead of relying on depth-only random generation.
- path terminals already guarantee bonus chests, and finale objective rooms can lock those rewards until completion.

### Implemented mechanic depth so far

- trap gauntlets now support dedicated sweeper, vent, crusher, and mixed-hazard variants, with entry switches, checkpoint reroutes, and challenge-side reward placement.
- escort rooms have active escort actors, cleanup fallback on escort death, metadata-driven spawn and durability tuning, and bomb-carrier safe-lane gating.
- puzzle rooms use metadata-driven plate counts, labels, layout offsets, trigger padding, and ordered, staggered, and paired rule variants.
- holdout rooms now require defending a zone when configured and support scripted reinforcement wave sizes.
- ritual rooms now support altar roles, reinforcement reactions, ward-linked shielding, and a revealed reliquary payoff on completion.
- resource-race rooms now support timed prize forfeiture, chest lockout, and fallback cleanup after the reward is lost.
- stealth rooms now support alarm beacons, visible lockdown states, and reinforcement-on-failure behavior.
- timed-extraction rooms now support loot-first escape flow, overtime reinforcement pressure, and reward-tier-aware chests.
- HUD, compass, minimap markers, and runtime objective entities now surface these room goals in play instead of leaving them implicit.

### Still shallow relative to the full plan

- puzzle rooms now ship the full P1–P4 progression (ordered/staggered/paired variants with telegraphing, anti-camping camp pulses, ordered-and-paired stabilizer skips, and per-biome motif tuning across Mud Caverns, Frozen Depths, and Sunken Ruins).
- holdout rooms still lack rotating hazard phases and optional pressure-reduction side actions.
- escort rooms still lack checkpoints, reward grading, and biome-specific variants.
- ritual rooms now cover the first linked-state/payoff slice, but still lack timing windows, tether variants, and biome-specific ritual layouts.
- resource-race rooms still lack visible enemy claim progress and partial-value recovery states.
- stealth rooms still lack patrol routes, vision cones, and partial-detection states.
- timed-extraction rooms still lack route collapse events and reward grading for clean vs overtime clears.

## Part 1: Mechanics Depth Plan

### Shared goal across all room families

Each room family should gain three additional layers beyond its current prototype:

- a spatial layer: the player should make routing and positioning choices, not only wait for a timer or touch a target,
- a pressure layer: enemies, hazards, or failure states should force tradeoffs while the objective is active,
- a payoff layer: completing the room well should feel meaningfully different from merely surviving it.

### Escort And Protection

Current prototype:

- one escort target moves toward the exit,
- enemies can focus the escort,
- if the escort dies the room falls back to a cleanup state.

Depth additions:

- add escort waypoints or lane checkpoints so the player has to clear specific pockets before the escort continues,
- add temporary cover/shrine nodes that the escort can pause at to recover or resist damage,
- add enemy behaviors that deliberately split pressure between player and escort instead of just retargeting,
- add a soft score on escort health preserved at exit and use it to scale the reward chest,
- add one or two room variants where the escort opens optional safe routes or bonus chests if preserved above a threshold.

Implementation slices:

- Phase E1: checkpoint-based escort movement and pause states,
- Phase E2: escort-preservation reward scaling,
- Phase E3: enemy archetype overrides for escort harassment,
- Phase E4: biome-specific escort variants.

### Escort Bomb Carrier

Current prototype:

- carrier only advances when the path is safe,
- if the carrier dies the room falls back to cleanup.

Depth additions:

- replace pure enemy-clear gating with breach segments or destructible locks that require escorting the carrier to multiple blast points,
- add a danger radius around the carrier so the player must keep distance during detonation windows,
- add fuse pressure where waiting too long increases enemy intensity or hazard density,
- allow the carrier to open shortcut routes or extra reward vaults when all blast points are completed,
- add failure grades: carrier death becomes survivable, but reduced payout or a harder extraction state follows.

Implementation slices:

- Phase B1: multi-stage blast objective with 2-3 target doors/barriers,
- Phase B2: detonation warning and positioning mechanic,
- Phase B3: reward vault or shortcut unlock,
- Phase B4: dungeon-specific carrier variants.

### Puzzle-Gated Doors

Current prototype:

- the player activates visible seal plates under combat pressure.

Depth additions:

- add multi-step puzzle states: ordered plates, paired plates, rotating seal priorities, or temporary decays,
- add readable puzzle cues in the room through symbols, floor marks, or lit rune states,
- add enemy waves or hazard pulses that specifically punish camping on the correct answer,
- add optional shortcut solutions like destroying a stabilizer or tanking a hazard to skip one puzzle step,
- add a success-grade reward based on plates solved without resets or damage taken.

Implementation slices:

- Phase P1: plate rule variants with visible telegraphing,
- Phase P2: anti-camping response events,
- Phase P3: alternate solve routes,
- Phase P4: per-dungeon puzzle motifs.

### Survival Holdout

Current prototype:

- the player survives a timer while reinforcements arrive in two waves.

Depth additions:

- add holdout zones or relic circles that require staying in contested ground rather than kiting forever,
- add rotating hazard phases so the best safe position changes during the holdout,
- build wave composition rules instead of only wave counts so late waves feel authored,
- add optional side actions during holdout such as activating defenses, closing spawn vents, or breaking buffers to reduce pressure,
- pay out better if optional side actions are completed before the timer ends.

Implementation slices:

- Phase H1: defend-a-zone rules,
- Phase H2: wave composition scripting,
- Phase H3: optional pressure-reduction interactions,
- Phase H4: biome hazard variants.

### Ritual Disruption

Current prototype:

- destroy altars with pulse behavior while enemies pressure the player.

Depth additions:

- give each altar a role: shield altar, summon altar, pulse altar, tether altar,
- add inter-altar links so kill order matters,
- add short vulnerable windows or disruption phases that reward timing,
- spawn ritualists or defenders whose behavior changes based on which altar falls,
- make a fully disrupted ritual spawn a reward state such as a revealed reliquary or a temporary safe room.

Implementation slices:

- Phase R1: altar roles and linked states,
- Phase R2: ritual defender reactions,
- Phase R3: disruption reward payoff,
- Phase R4: dungeon-specific ritual layouts.

### Resource Race

Current prototype:

- the player must secure a relic before timeout or lose the reward and clear the room.

Depth additions:

- add rival claimants or enemy interactors that visibly progress toward the relic,
- add contested-resource states where the player can interrupt, steal back progress, or choose to abandon the prize,
- add destructible containers or split loot caches so the player chooses between fast securement and full value,
- add extraction pressure after success so grabbing the resource changes the room tempo,
- add reward tiers based on how much of the resource was preserved.

Implementation slices:

- Phase C1: visible enemy claim progress,
- Phase C2: interrupt/steal-back interactions,
- Phase C3: split-cache reward tiers,
- Phase C4: biome-specific contested artifacts.

### Trap Gauntlet

Current prototype:

- mostly hazard terrain plus guaranteed chest.

Depth additions:

- add real trap entities: sweepers, darts, crushers, flame lanes, collapsing floors,
- define multiple traversal lanes with different risk/reward profiles,
- add switch interactions that disable one hazard lane while enabling another,
- add optional challenge chests behind the hardest trap sequence,
- add path memory so the room can be learned and mastered rather than read as random terrain noise.

Implementation slices:

- Phase G1: moving trap entity set,
- Phase G2: lane and switch layout rules,
- Phase G3: optional challenge-route rewards,
- Phase G4: biome-specific trap packs.

### Stealth Passage

Current prototype:

- visible alarm wards can trigger a lockdown fight.

Depth additions:

- add patrol routes and vision cones rather than only static alarm radii,
- add light/shadow pockets, cover objects, or silence shrines that let the player recover stealth,
- add an alarm escalation ladder: partial detection, search phase, full lockdown,
- add optional stealth reward caches for no-alarm clears,
- let some stealth rooms become alternate combat rooms on failure rather than always the same reinforcement script.

Implementation slices:

- Phase S1: patrol and vision-cone entities,
- Phase S2: partial-detection states,
- Phase S3: stealth-specific reward rules,
- Phase S4: biome-specific stealth gimmicks.

### Timed Extraction

Current prototype:

- secure the relic, escape to the portal, overtime spawns one reinforcement wave.

Depth additions:

- add seal phases where parts of the room close off over time,
- add extraction-route pressure such as collapses, hazard surges, or one-way doors,
- add enemy pursuit waves with composition rules tied to the extracted relic,
- add optional detours for bonus loot that increase extraction difficulty,
- make clean extractions preserve relic value and overtime extractions reduce the payout.

Implementation slices:

- Phase T1: route-closing and collapse events,
- Phase T2: pursuit wave scripting,
- Phase T3: clean vs overtime reward grading,
- Phase T4: biome-specific extraction complications.

## Part 2: Dungeon Generation Rules Plan

## Target gameplay shape

Each level should follow this generation contract:

- when the player loads into a level, the game generates the full main path to the portal room first,
- after the main path is locked, the generator builds secondary paths branching from deliberate anchor points on that main path,
- every path, including branches, should scale upward in difficulty from entrance to terminal room,
- every path terminal should provide an extra-loot chest,
- the room-family mix should feel intentional instead of weight-only random.

The current system already satisfies the first two points structurally. The missing pieces are path metadata, explicit per-path difficulty rules, terminal reward rules, and room-family assignment rules.

### Generation rule set A: topology first, then room assignment

Planned topology order:

1. Generate the main path from start room to portal room.
2. Mark each main-path room with `path_id="main"`, `path_index`, `path_length`, `difficulty_band`, and `is_path_terminal`.
3. Generate branch paths after the main path using anchor depths that depend on total level size.
4. Mark each branch room with its own `path_id`, local `path_index`, local `path_length`, local `difficulty_band`, and `is_path_terminal`.
5. Only after those path facts exist should the room selector assign a room family.

Required code changes:

- extend `TopologyRoom` to carry path metadata instead of only `depth`, `path_kind`, and `is_exit`,
- extend `TopologyPlan` to expose branch path groupings, not only a flat room map,
- keep the current invariant that the main path is always pre-seeded before any branch is created.

### Generation rule set B: path-local difficulty progression

Current gap:

- `depth` exists, but difficulty is still mostly a side effect of enemy count range and room-family weights.

Planned rule:

- every room receives a path-local progression value from `0.0` to `1.0` based on its index within its path,
- every room also receives a global level difficulty derived from the existing level config,
- room assignment uses both values so path difficulty is monotonic even when a branch starts halfway through the main route.

Difficulty bands:

- band 0: opener,
- band 1: early pressure,
- band 2: mid-path test,
- band 3: late-path challenge,
- band 4: terminal payoff.

Expected selection behavior:

- early rooms should strongly prefer standard combat, mild puzzle, or light traversal,
- mid rooms should introduce objective complexity and mixed pressure,
- late rooms should bias toward escort, ritual, resource-race, extraction, or harder puzzle variants,
- path terminals should be high-pressure but still reward-facing.

Required code changes:

- extend `RoomPlan` with `path_id`, `path_index`, `path_length`, `path_progress`, `difficulty_band`, `is_path_terminal`, and `reward_tier`,
- change `RoomSelector.build_room_plan()` to accept full path context instead of only `depth`, `path_kind`, and `is_exit`,
- add explicit monotonic difficulty selection rules instead of relying only on generation weights.

### Generation rule set C: terminal reward-room guarantees

Goal:

- every path end should contain a chest with extra loot.

Planned rule:

- every branch terminal gets a guaranteed reward chest,
- the main-path portal room also gets a guaranteed reward chest, but it unlocks only when the room objective is completed,
- reward quality scales with path difficulty and path type.

Reward tiers:

- branch short path terminal: small bonus tier,
- branch long path terminal: medium bonus tier,
- main-path finale terminal: highest bonus tier.

Required code changes:

- add `reward_tier` or `terminal_reward_profile` to `RoomPlan`,
- add richer chest tables so terminal rooms can request better rewards than baseline random chests,
- add a room-side rule for locked reward chests in objective finales so the player cannot bypass the objective by opening the chest immediately.

### Generation rule set D: room-family incorporation rules

The room catalog should stop behaving like a flat enabled list and start behaving like a constraint-driven pool.

Proposed placement rules:

- `escort_protection`: main-path mid to late band only,
- `escort_bomb_carrier`: main-path late band or long-branch terminal only,
- `puzzle_gated_doors`: wildcard mid-band room or branch mid-band room,
- `survival_holdout`: main-path finale or rare long-branch finale,
- `ritual_disruption`: mid to late on both main and branch paths,
- `resource_race`: mid to late on both path types, especially branch terminals,
- `trap_gauntlet`: branch-heavy and reward-path-heavy, rarely on main path,
- `stealth_passage`: branch opener, branch mid, or main-path wildcard,
- `timed_extraction`: mid to late on both path types, biased toward high-tension branches.

Anti-repetition rules:

- no identical room family twice in a row on the same path,
- avoid back-to-back rooms with the same objective pressure profile,
- cap escort-family frequency to avoid consecutive escort levels,
- require at least one reward-facing branch archetype when a level has 2 or more branches.

Required code changes:

- extend room-template metadata with placement constraints such as `path_stage_min`, `path_stage_max`, `terminal_role`, `repeat_cooldown`, `reward_affinity`, and `pairing_tags`,
- let `content_db.py` seed those fields in the base table and in per-dungeon overrides,
- let `RoomSelector` track per-path recent history during a level build.

### Generation rule set E: per-dungeon and per-level pacing profiles

Current gap:

- the level config only carries path length and basic enemy ranges.

Planned additions in `dungeon_config.py`:

- branch count range,
- branch length range,
- branch reward bias,
- objective complexity ramp,
- stealth frequency bias,
- ritual/escort/resource weighting overrides,
- finale family preferences.

Planned additions in `content_db.py`:

- more per-dungeon overrides so each biome favors a different subset of room families and room variants,
- biome-specific mechanic variants for each family rather than only ritual and extraction.

### Generation rule set F: branch reward structure

Each branch should communicate why it exists.

Planned branch archetypes:

- detour branch: lower reward, lower risk, useful for recovery,
- challenge branch: harder rooms, better chest,
- specialist branch: concentrates a room family such as stealth, trap, or ritual,
- vault branch: shortest branch, hardest terminal, highest chest reward.

Rule:

- choose a branch archetype when the branch is created,
- assign room-family pools and reward tiers from that archetype,
- use path-local difficulty within that branch instead of inheriting only main-path depth.

### Generation rule set G: tests and validation

New invariants to test:

- main path is generated before branches and remains connected,
- branch generation happens only after the main path metadata is fixed,
- path-local difficulty never decreases along a path,
- every path terminal has a guaranteed chest,
- path terminal reward tier is higher than non-terminal rewards,
- room-family placement obeys branch/main restrictions,
- no immediate room-family repeats on the same path unless explicitly allowed.

New test targets:

- `tests/test_dungeon_topology.py`: path metadata, terminal marking, branch archetype assignment,
- `tests/test_room_selector.py`: stage-aware room-family selection and anti-repeat rules,
- `tests/test_content_db.py`: new metadata columns and per-dungeon overrides,
- `tests/test_room_objectives.py`: terminal chest unlock rules for objective finale rooms.

## Recommended implementation order

### Phase 1: data and metadata

- extend `TopologyRoom` and `RoomPlan` with path metadata,
- extend `content_db.py` schema with placement and reward fields,
- extend `dungeon_config.py` with per-level branch and pacing profile fields.

### Phase 2: selector rewrite

- update `RoomSelector` so it consumes path context and recent room history,
- add stage-aware selection and anti-repeat rules,
- keep the current room objective rules unchanged while the selector becomes smarter.

### Phase 3: terminal reward rules

- guarantee chests for all path terminals,
- add reward tiers and objective-finale chest locks,
- validate terminal payout behavior in tests.

### Phase 4: mechanic depth expansion

- deepen room families in an order that supports the new generator:
  - trap gauntlet,
  - puzzle-gated doors,
  - ritual disruption,
  - survival holdout,
  - resource race,
  - stealth passage,
  - timed extraction,
  - escort protection,
  - escort bomb carrier.

This order prioritizes families that most improve branch identity first, then deepens the heavier multi-actor rooms.

## Outstanding Next Steps

Single source of truth for forward work. Older per-snapshot "Recommended Next Slice" sections have been removed to prevent stale plans from contradicting each other. Add new ideas here; do not re-introduce per-snapshot recommendations.

### Meta-progression (T-series continuation, post-T18)

- **T19 — Keystone-tier preview on the Records screen.** Surface `KEYSTONE_TIER_COIN_BONUSES` ("Tier 1 +25, Tier 2 +50, Tier 3 +100 — current: tier 2") so the diminishing-returns curve is visible at a glance.
- **T20 — Biome mastery cosmetic / dossier badge.** First time any biome reaches `BIOME_ATTUNEMENT_MAX_PER_BIOME`, unlock a small dossier badge / colour change. First permanent unlock state separate from inventory — paves the way for an achievements substrate.
- **T21 — Abandon-run history line.** Track and display the most recent N abandoned runs ("3 of last 5 mud_caverns runs abandoned at level 2") to surface friction points without changing rules.

### Room mechanic depth (per Part 1 plan, ordered)

1. **Puzzle-Gated Doors — P1 follow-up.** Stronger anti-camping reactions and alternate solve routes on top of the existing ordered / staggered / paired variants (P2 camp pulses + P3 stabilizer skips already shipped; this slice pushes P1 deeper).
2. **Survival Holdout — H1–H4 are complete** (shrink, migration, stabilizer-anchor, minimap telegraphs). No outstanding holdout work.
3. **Ritual Disruption — timing-window / tether variants.** R1 link modes, R2 role chain, R3 wrong-strike punishment, R4 in-world role glyph, and R5 minimap role halo are shipped. Next push: per-altar disruption windows or inter-altar tethers that punish destroying the wrong link first.
4. **Escort & Bomb Carrier — reward grading + branch archetype specialization.** E2 (escort-preservation reward scaling), B-series carrier blast-point variants, and per-biome E4 / B4 overrides are still open.
5. **Per-biome `*_4` content slices** for room families that lack biome variants beyond their base template (e.g. trap G4 biome packs, stealth S4 gimmicks, extraction T4 complications). Defer until 1–4 reach parity.

### Notes for future slices

- The T-series letter is shared between trap-gauntlet biome theming (T1–T5), biome reward activation (T6–T9), and the meta-progression milestone (T10–T18). Future slices in this letter line are reserved for meta-progression follow-ups (T19+).
- The `Recommended implementation order` section above remains the static phase plan. The Outstanding Next Steps list above is the live work queue.

## Handoff Snapshot (2026-04-29y)

- **T18 — Records / dossier main-menu screen.** Read-only consolidation slice that surfaces every meta-progression value built up across T10–T17 in one place, accessible from the main menu without entering a run. Validates that the existing screen + view + state-machine pattern generalizes cleanly to a no-input "stats page" use case.
- Wiring:
    - `game_states.py`: added `GameState.RECORDS = auto()`.
    - `menu.py`:
        - `MainMenuScreen.OPTIONS` extended to `["Play", "Room Tests", "Character", "Shop", "Records", "Quit"]`. `handle_events` maps `"Records"` → `GameState.RECORDS`.
        - New `RecordsScreen` class. Holds `progress`, lazily builds three font sizes (title 40 / row-title 22 / body 18 / small 16). `handle_events` returns `GameState.MAIN_MENU` on ESC / Enter / Space; ignores everything else. `draw(surface, view)` renders title centred at top, then a stack of per-biome rows (~92 px tall each: dungeon name + terrain label, then completions / attunement (purple) on one line, trophies / next-attunement on the second line, optional run-start grant in the right column), then a centred keystone summary line, totals line, and a footer hint.
    - `menu_view.py`:
        - New frozen dataclass `RecordsBiomeRowView` (dungeon_name, terrain_label, completion_label, attunement_label, next_attunement_label, trophy_label, starting_grant_label).
        - New frozen dataclass `RecordsView` (title, biome_rows tuple, keystone_summary, totals_summary, back_label, footer_hint).
        - New module-level dict `_RECORDS_TROPHY_LONG_LABELS` mapping trophy ids to dossier-friendly plurals ("Stat Shards", "Tempo Runes", "Mobility Charges").
        - New `build_records_view(screen)` builder. Iterates `DUNGEONS` in order; reads `progress.biome_completions`, `progress.biome_attunements`, `progress.inventory` defensively (`getattr` + `or {}`). Caps display at `BIOME_ATTUNEMENT_MAX_PER_BIOME` with `(max)` suffix; otherwise calls `progress.biome_attunement_progress(terrain)` for the next-attunement line. Suppresses trophy / starting-grant labels when terrain is not in `TERRAIN_TROPHY_IDS` (future-proofs against new biomes that don't ship a trophy). Keystone summary uses `progress.keystone_starting_coin_bonus()` when crafted, falls back to `"(none crafted)"`. Totals = lifetime completion sum + sum of all biome trophies.
    - `rpg.py`:
        - Imported `RecordsScreen` and `build_records_view`.
        - Added `self._records_screen = RecordsScreen(self.progress)` next to other screen constructions in `__init__`.
        - State-machine dispatch: `elif self.state == GameState.RECORDS: self._handle_records(events)` after the SHOP branch.
        - New `_handle_records(events)` method analogous to `_handle_main_menu` but with no `save_progress` call (read-only screen).
        - Draw branch: `elif self.state == GameState.RECORDS:` calls `self._records_screen.draw(self.screen, build_records_view(self._records_screen))`.
- Persistence: none added. T18 is purely a render of state owned by T13–T17. Save/load is unchanged.
- UI design notes:
    - Attunement progress reuses the same soft-purple `(220, 180, 255)` hue already used on `DungeonSelectScreen` cards (T17), keeping visual continuity between "where to spend a run" and "what runs have earned".
    - Trophy and run-start-grant lines use `COLOR_COIN` to visually link them to the shop's trade-up loop.
    - Footer hint reads `Press ESC or Enter to return` so the screen feels like a peek, not a sub-menu the player has to navigate.
- Tests (`tests/test_menu_view.py`): five new tests in `MenuViewProjectionTests` plus an updated assertion in `test_build_main_menu_view_projects_title_and_selection` (options tuple now includes `"Records"`). New tests cover: row-per-dungeon listing + empty-state defaults, completions / attunement / trophy / run-start labels populating from progress, `(max)` label at the attunement cap, keystone summary surfacing the coin bonus when owned, and `RecordsScreen.handle_events` returning `MAIN_MENU` on ESC while ignoring unrelated keys. Suite is **692 OK** (was 687 pre-T18).
- Lessons:
    - The view-dataclass + builder pattern scales cleanly to consolidation screens: `build_records_view` is ~60 lines of pure projection and the screen class is ~80 lines of layout — no rules logic was added or duplicated. Confirms T13–T17 architecture investment pays off for downstream UI surfaces.
    - Read-only menu screens should *not* call `save_progress` in their handler. The T18 handler matches `_handle_main_menu` minus the `save_progress` call. Saving on a screen the player only viewed would needlessly thrash the SQLite file.
    - When new top-level menu options change `MainMenuScreen.OPTIONS`, the `test_build_main_menu_view_projects_title_and_selection` assertion is the canonical regression — keep it in sync in the same edit.

## Handoff Snapshot (2026-04-29x)

- **T17 — biome attunements (secondary meta-progression token).** Introduces a *parallel* meta loop alongside keystones. Where keystones reward breadth (clear all 3 biomes for the craft), attunements reward depth (repeated runs in a single biome). Each `BIOME_ATTUNEMENT_THRESHOLD = 3` completions in the same biome grants one attunement (capped at `BIOME_ATTUNEMENT_MAX_PER_BIOME = 3` per biome, so 9 attunements is the global ceiling). Each attunement of a biome grants +1 of that biome's trophy at the start of every run in *that* biome — a biome-specialist perk that accelerates the keystone craft loop.
- Wiring:
  - [settings.py](settings.py): new constants `BIOME_ATTUNEMENT_THRESHOLD = 3`, `BIOME_ATTUNEMENT_MAX_PER_BIOME = 3`. Block-comment documents the dual meta-progression model.
  - [progress.py](progress.py): new fields `biome_completions: dict[str, int]` (monotonic per-terrain counter, never reset on death/abandon) and `biome_attunements: dict[str, int]`. New helpers `record_biome_completion(terrain)` (returns 0/1 — number of attunements granted), `_terrain_for_dungeon(dungeon_id)`, `biome_attunement_starting_trophies(dungeon_id)`, `biome_attunement_progress(terrain)` (returns `(completions_toward_next, threshold)`). `complete_dungeon_from_runtime` now calls `record_biome_completion` after the dungeon is marked complete. `begin_dungeon_run` grants attunement trophies to inventory after the snapshot (parallel to the keystone coin pattern — abandon reverts the bonus, never compounds across snapshot/restore cycles).
  - [save_system.py](save_system.py): new `biome_meta` SQLite table (`terrain TEXT PK, completions INTEGER, attunements INTEGER`). Created via `CREATE TABLE IF NOT EXISTS` — no migration needed since the table simply doesn't exist for old DBs (load yields empty dicts, fully backward compatible). Save deletes-and-rewrites all rows for terrains present in either dict.
  - [menu_view.py](menu_view.py): `DungeonCardView.attunement_label: str = ""` (new defaulted field). `_build_attunement_label(progress, terrain)` formats `Attune N/cap (p/threshold next)` while below cap, switches to `Attune N/cap (max)` at the per-biome ceiling, returns `""` for biomes with no completions or attunements.
  - [menu.py](menu.py): `DungeonSelectScreen.draw` renders the attunement label below the trophy line in soft purple `(220, 180, 255)` to visually distinguish it from the gold coin/trophy text.
- Test coverage:
  - [tests/test_biome_attunements.py](tests/test_biome_attunements.py): new test module — 13 tests covering counter ticking, threshold-grant cadence, per-biome cap, unknown-terrain rejection, helper introspection, completion-hook integration, run-start trophy grant, abandon-reverts-grant, and SQLite save/load round-trip (round-trip uses an isolated temp-dir DB via monkeypatching `save_system._DB_PATH`).
  - [tests/test_menu_view.py](tests/test_menu_view.py): three new dungeon-select projection tests for the attunement label (blank when no progress; shows `Attune N/cap (p/threshold next)` mid-progress; shows `(max)` at cap, never `next`).

### Verification

- `python -m unittest discover -s tests` → 687/687 OK (was 671 pre-T17; +16 net new tests, 1 pre-existing skip unchanged).

### Meta-progression Loop Map (post-T17)

Two complementary meta tokens, each with its own recipe and effect:
- **Prismatic Keystones** (T10–T16): breadth — 1 of each biome trophy crafts at the shop. Cap 3 owned. Tiered run-start coin bonus 25/50/100 (cumulative 25/75/175). Universal effect — applies to every run.
- **Biome Attunements** (T17): depth — 3 completions in the same biome auto-grants 1 attunement. Cap 3 per biome (9 global). Each attunement grants +1 of that biome's trophy at run start in that biome. Specialist effect — accelerates the keystone craft loop by topping up the trophy stockpile.

## Handoff Snapshot (2026-04-29w)

- **T16 — keystone cap-reached craft hint polish.** Closes a loose end from T13/T14: when `meta_keystones >= KEYSTONE_MAX_OWNED`, the shop's `[4] Craft Keystone` hint is replaced by `Keystones complete (3/3) — meta route maxed`. The previous behaviour silently dropped the hint once any single trophy was missing AND continued to show `[4] Craft Keystone` even at cap (a no-op key prompt that misleads the player). The new acknowledgement appears whenever the player has crafted all keystones, regardless of trophy stockpile.
- Wiring:
  - [menu_view.py](menu_view.py): `_build_trophy_strings` now precomputes `at_cap = keystone_count >= KEYSTONE_MAX_OWNED` and renames `can_craft` → `has_each_trophy` for clarity. Branch order: trade hint → cap acknowledgement (replaces craft hint entirely when at cap) → otherwise the existing tier-aware craft hint (when player has 1 of each trophy and is below cap). The cap message coexists with the exchange hint when the player still has surplus to trade.
- Test coverage:
  - [tests/test_menu_view.py](tests/test_menu_view.py): two new tests — `test_build_shop_view_surfaces_keystone_cap_message_when_maxed` (asserts the cap line appears AND `[4] Craft Keystone` is suppressed even with 1 of each trophy on hand) and `test_build_shop_view_keystone_cap_message_appears_alongside_exchange_hint` (verifies the cap message coexists with the trade hint when surplus exists).

### Verification

- `python -m unittest discover -s tests` → 671/671 OK (was 669 pre-T16; +2 tests).

## Handoff Snapshot (2026-04-29v)

- **T15 — per-biome trophy counts on dungeon-select cards.** Each dungeon card now displays the player's owned count of that biome's challenge-route trophy in `COLOR_COIN` (e.g., Mud Caverns shows `Shard x2`, Frozen Depths shows `Rune x0`, Sunken Ruins shows `Dash x1`). At a glance, the player can see which biome to revisit to round out the next prismatic-keystone craft (recipe: 1 of each).
- Wiring:
  - [settings.py](settings.py): new `TERRAIN_TROPHY_IDS = {"mud": "stat_shard", "ice": "tempo_rune", "water": "mobility_charge"}` — single source of truth for the biome→trophy mapping (previously implicit, scattered across `content_db.py` `trap_challenge_reward_kind` declarations).
  - [menu_view.py](menu_view.py): `DungeonCardView` gains `trophy_label: str = ""` (defaulted for backward compat with any future card use). `build_dungeon_select_view` reads `getattr(screen.progress, "inventory", {}) or {}` defensively, looks up the trophy via `TERRAIN_TROPHY_IDS`, and formats `f"{_TROPHY_SHORT_LABELS[trophy_id]} x{count}"`. Imports `TERRAIN_TROPHY_IDS`.
  - [menu.py](menu.py): `DungeonSelectScreen.draw` renders `card.trophy_label` in `COLOR_COIN` at `y + 112` (below the existing terrain row) when the label is non-empty.
- Test coverage:
  - [tests/test_menu_view.py](tests/test_menu_view.py): two new tests — `test_build_dungeon_select_view_card_trophy_labels_reflect_inventory` (asserts mud→Shard x2, ice→Rune x0, water→Dash x1, and verifies every card's terrain is in `TERRAIN_TROPHY_IDS`) and `test_build_dungeon_select_view_card_trophy_labels_default_to_zero` (asserts every card ends with " x0" for an empty inventory — the label is never blank for a known biome terrain, even with zero trophies).

### Verification

- `python -m unittest discover -s tests` → 669/669 OK (was 667 pre-T15; +2 new tests).

## Handoff Snapshot (2026-04-29u)

- **T14 — keystone visibility loop closure.** Two final feedback gaps closed: (1) main-menu footer surfaces `Prismatic Keystones: N / 3` so a player loading a save sees their banked meta progress before entering the dungeon-select screen; (2) shop craft toast — when the player spends trophies for a keystone, an immediate HUD-style banner queues `Keystone N/3 crafted!  Next run: +M coins` so the reward is visible at the moment of decision (the next run-start banner replaces it via the shared single-slot tracker).
- Wiring:
  - [damage_feedback.py](damage_feedback.py): `KeystoneBonusBannerTracker` generalized — now stores arbitrary text instead of just an amount. `report_keystone_starting_bonus(amount, ...)` formats `"+{amount} keystone coins"` then reports. New sibling `report_keystone_craft_toast(owned, max_owned, next_run_bonus, ...)` formats the craft message and uses the same single-slot tracker (re-reporting replaces, matching the existing pattern). `build_keystone_bonus_banner_view` now returns `(text, age_fraction)` instead of `(amount, age_fraction)`.
  - [hud_view.py](hud_view.py): banner builder passes `banner_data[0]` straight through as `text` (no formatting at the view layer anymore — the reporter owns the message).
  - [menu_view.py](menu_view.py): `MainMenuView` gains `keystone_status_text: str = ""`. `build_main_menu_view` reads `getattr(screen, "progress", None)` defensively and formats the footer when `meta_keystones > 0`. Imports `KEYSTONE_MAX_OWNED` for the `N / max` display.
  - [menu.py](menu.py): `MainMenuScreen.__init__(progress=None)` stashes the optional progress object (default keeps old test instantiation working). `MainMenuScreen.draw` renders the footer in `COLOR_COIN` near the bottom of the screen using a new `_small_font`. `ShopScreen.handle_events` K_4 path now calls `damage_feedback.report_keystone_craft_toast(progress.meta_keystones, KEYSTONE_MAX_OWNED, progress.keystone_starting_coin_bonus())` after a successful craft.
  - [rpg.py](rpg.py): `MainMenuScreen(self.progress)` — pass progress at construction so the footer reflects meta state from the moment the menu first renders.
- Test coverage:
  - [tests/test_damage_feedback.py](tests/test_damage_feedback.py): existing 5 banner tests updated to assert text strings (`"+75 keystone coins"`) instead of bare amounts. Three new tests for the craft toast — `test_craft_toast_formats_owned_and_next_bonus`, `test_craft_toast_with_zero_owned_is_dropped`, `test_craft_toast_replaces_starting_bonus_banner` (verifies the shared single-slot tracker semantics).
  - [tests/test_menu_view.py](tests/test_menu_view.py): updated default-projection test to assert empty footer when no progress; new `test_build_main_menu_view_surfaces_keystone_footer_when_owned` (with 2 keystones) and `test_build_main_menu_view_omits_keystone_footer_when_none_owned` (zero keystones).

### Verification

- `python -m unittest discover -s tests` → 667/667 OK (was 662 pre-T14; +5 net new tests).

### Keystone Visibility Audit (post-T14)

The full meta-progression feedback loop now has touchpoints at every player decision surface:
- **Craft moment** (shop K_4): toast queues `Keystone N/3 crafted!  Next run: +M coins`.
- **Pre-craft preview** (shop trophy hint, T13): `[4] Craft Keystone (1 of each) — next tier +N coins/run`.
- **Trophy summary** (shop, T12): `Prismatic Keystone x{N} (+M run-start coins)`.
- **Main menu** (T14): `Prismatic Keystones: N / 3` footer.
- **Dungeon select** (T12): `Prismatic Keystones: N (+M coins each run)` badge.
- **Run start** (T11): in-dungeon HUD banner `+M keystone coins`.

## Handoff Snapshot (2026-04-29t)

- **T13 — keystone meta-bonus tier scaling.** The flat per-keystone +25 coin payout has been replaced with a tiered table `KEYSTONE_TIER_COIN_BONUSES = (25, 50, 100)`. Cumulative payout: 1→25, 2→75, 3→175 coins per run. The 3rd keystone is now worth 4× the 1st, making `KEYSTONE_MAX_OWNED = 3` feel like a real ceiling rather than a soft suggestion.
- Wiring:
  - [settings.py](settings.py): `KEYSTONE_STARTING_COIN_BONUS = 25` removed; `KEYSTONE_TIER_COIN_BONUSES = (25, 50, 100)` added in its place. Comment block updated to document the cumulative payouts.
  - [progress.py](progress.py): `keystone_starting_coin_bonus()` now returns `sum(KEYSTONE_TIER_COIN_BONUSES[:owned])` where `owned = min(meta_keystones, len(table))` — defensive against any future drift between the counter cap and the tier table length. New `next_keystone_tier_bonus()` returns the *next* tier value (or 0 at cap) for UI hints.
  - [menu_view.py](menu_view.py): `build_dungeon_select_view` and `_build_trophy_strings` both call `progress.keystone_starting_coin_bonus()` (single source of truth) instead of multiplying. The shop trophy hint now appends `— next tier +N coins/run` to the `[4] Craft Keystone` prompt when the player is below the keystone cap, so they can see the escalating reward at the moment they're deciding to spend trophies.
- Test coverage:
  - [tests/test_progress.py](tests/test_progress.py): old "scales linearly" test rewritten to assert tiered cumulative sum; two new tests — `test_starting_bonus_caps_at_max_owned_tiers` (defensive overflow guard) and `test_next_keystone_tier_bonus_returns_next_entry_or_zero_at_cap` (full ladder including cap).
  - [tests/test_menu_view.py](tests/test_menu_view.py): dungeon-select badge test updated to assert `sum(KEYSTONE_TIER_COIN_BONUSES[:2])` (75 coins for 2 keystones, not 50).

### Verification

- `python -m unittest discover -s tests` → 662/662 OK (was 660 pre-T13; +3 tier tests, -1 obsolete linear-scale assertion).

## Handoff Snapshot (2026-04-29s)

- **T12 — surface the meta-keystone bonus outside the shop.** The T11 starting-coin bonus was previously invisible until the player checked their coin count. T12 closes that feedback gap with two complementary surfaces:
  1. *Dungeon-select badge* — small prismatic-purple line under the difficulty row showing `Prismatic Keystones: N  (+M coins each run)` when `meta_keystones > 0`.  Visible BEFORE pressing Enter so returning players see why their first-run coins look high.
  2. *Run-start HUD banner* — large fading `+M keystone coins` text at top-center on the first frame of every run when the bonus is positive. Lifetime `KEYSTONE_BONUS_BANNER_LIFETIME_MS = 2400` (alpha + slight rise tied to age).
- Wiring:
  - [damage_feedback.py](damage_feedback.py): added `KeystoneBonusBannerTracker` (single-slot, re-report replaces) plus `KEYSTONE_BONUS_BANNER_LIFETIME_MS = 2400`. Public API: `report_keystone_starting_bonus(amount, now_ticks=None)` queues the banner; `build_keystone_bonus_banner_view(now_ticks=None)` returns `(amount, age_fraction)` or `None`. `reset_all` extended to clear the banner so room-test entry / death-restart never carry a stale message.
  - [hud_view.py](hud_view.py): new `KeystoneBonusBannerHUDView(text, age_fraction)` dataclass; `HUDView.keystone_bonus_banner: KeystoneBonusBannerHUDView | None = None` (defaulted for backward compat). `build_hud_view` reads from `damage_feedback.build_keystone_bonus_banner_view` and formats the text once at projection time.
  - [hud.py](hud.py): new `_draw_keystone_bonus_banner` renders the banner with a black 4-corner outline, COLOR_COIN fill, and a single `set_alpha` on the composite surface so the entire glyph fades together. Drawn LAST in `HUD.draw` so it sits above all other chrome.
  - [rpg.py](rpg.py): `_start_dungeon` now calls `damage_feedback.report_keystone_starting_bonus(bonus)` AFTER `damage_feedback.reset_all()`, using `progress.keystone_starting_coin_bonus()`. Order matters — the reset would otherwise clear the freshly-queued banner.
  - [menu_view.py](menu_view.py): `DungeonSelectView` gains `keystone_status_text: str = ""` (defaulted). `build_dungeon_select_view` populates it from `getattr(progress, "meta_keystones", 0) * KEYSTONE_STARTING_COIN_BONUS` only when keystones > 0.
  - [menu.py](menu.py): `DungeonSelectScreen.draw` renders the keystone status line at `diff_y + 18` in prismatic `(220, 180, 255)` only when present (preserves the existing layout when keystones = 0).
- Test coverage:
  - [tests/test_damage_feedback.py](tests/test_damage_feedback.py): new `KeystoneBonusBannerTrackerTests` (5 tests) — basic queue+age, zero/negative-amount drop, lifetime expiry, re-report replacement, `reset_all` clears.
  - [tests/test_menu_view.py](tests/test_menu_view.py): existing dungeon-select test extended to assert empty status; new test asserts the populated badge text format.

### Verification

- `python -m unittest discover -s tests` → 660/660 OK (was 654 pre-T12; +5 banner tracker, +1 dungeon-select badge).

## Handoff Snapshot (2026-04-29r)

- **T11 — `prismatic_keystone` as permanent meta-progression token.** Crafted keystones now live on `progress.meta_keystones` (a persistent integer counter) instead of the per-run inventory, so they survive death and abandon. Each keystone owned grants `KEYSTONE_STARTING_COIN_BONUS = 25` coins at the start of every dungeon run, capped at `KEYSTONE_MAX_OWNED = 3` (max +75 coins per run). This gives the long-arc collection arc a tangible mechanical payoff that reinforces every future run.
- Wiring:
  - [settings.py](settings.py): added `KEYSTONE_MAX_OWNED = 3` and `KEYSTONE_STARTING_COIN_BONUS = 25` next to the existing `BIOME_TROPHY_KEYSTONE_ID` block.
  - [progress.py](progress.py): `PlayerProgress` gains `self.meta_keystones: int = 0`, never wiped by `restore_run_state`, `complete_dungeon_from_runtime`, or `resolve_dungeon_death` (it lives outside the snapshot/sync loop). New `keystone_starting_coin_bonus()` returns `meta_keystones * KEYSTONE_STARTING_COIN_BONUS`. `begin_dungeon_run` now snapshots FIRST, then adds the bonus to `self.coins` — abandon reverts to the pre-bonus baseline and a fresh `begin_dungeon_run` re-applies the bonus exactly once (no compounding exploit). `migrate_legacy_state` folds any T10 inventory-stored keystones into the meta counter, capped at `KEYSTONE_MAX_OWNED`.
  - [shop.py](shop.py): `Shop.craft_keystone` now increments `progress.meta_keystones` instead of `inventory[BIOME_TROPHY_KEYSTONE_ID]`. `Shop.can_craft_keystone` checks `meta_keystones < KEYSTONE_MAX_OWNED` (replaces the old inventory `max_owned` check).
  - [save_system.py](save_system.py): added `meta_keystones INTEGER NOT NULL DEFAULT 0` column to the `player` table schema, with an `ALTER TABLE` migration for existing saves; updated `save_progress` upsert and `load_progress` SELECT to round-trip the field.
  - [menu_view.py](menu_view.py): `_build_trophy_strings` now reads `getattr(progress, "meta_keystones", 0)` for the keystone count and renders `Keystone xN (+N*25 run-start coins)` in the shop summary, surfacing the meta-bonus payoff in the same place the player crafts the keystone.
  - [rpg.py](rpg.py): `_build_trophy_tally_lines` reads the keystone count from `meta_keystones` (not inventory). Guard relaxed from `if not inventory` to `if inventory is None` so an empty inventory + nonzero keystones still surfaces the keystone line on the level-complete screen.
- Test coverage:
  - [tests/test_progress.py](tests/test_progress.py): new `MetaKeystoneStartingBonusTests` (5 tests) — default counter zero, linear bonus scaling, snapshot-pre-bonus + live-coins-with-bonus on `begin_dungeon_run`, zero-keystones is neutral, legacy-inventory migration with cap idempotence.
  - [tests/test_save_system.py](tests/test_save_system.py): new round-trip test asserts `meta_keystones` survives save/load.
  - [tests/test_shop.py](tests/test_shop.py): updated three `PrismaticKeystoneCraftTests` cases to assert the credit lands on `meta_keystones` (not inventory) and that `KEYSTONE_MAX_OWNED` blocks the craft.
  - [tests/test_rpg_runtime.py](tests/test_rpg_runtime.py): updated `TrophyTallyHelperTests.test_lists_only_nonzero_trophies_in_canonical_order` to source the keystone count from `meta_keystones` instead of inventory.

### Verification

- `python -m unittest discover -s tests` → 654/654 OK (was 648 pre-T11; +5 progress tests, +1 save round-trip, 4 T10 tests rewired).

## Handoff Snapshot (2026-04-29q)

- **T10 — biome trophy run-summary tally + rare crafted `prismatic_keystone`** completes the long-arc collection loop opened by T9. The level-complete screen now lists every biome trophy the player owns post-run, and the post-run shop gains a fourth hotkey (`K_4`) to craft a `prismatic_keystone` from one of each biome trophy.
- Wiring:
  - [settings.py](settings.py): added `BIOME_TROPHY_KEYSTONE_ID = "prismatic_keystone"` alongside the T9 trophy tunables. Recipe is implicit ("1 of each in `BIOME_TROPHY_IDS`") so adding a 4th biome later only requires touching the trophy id tuple.
  - [item_catalog.py](item_catalog.py): added `prismatic_keystone` entry under `category="biome_reward"` with `max_owned=3`, `can_purchase=False`, `can_loot=False`, and a prismatic icon color `(235, 200, 255)`. Mirrors the T5 trophy fields exactly.
  - [shop.py](shop.py): `Shop` gains `can_craft_keystone(progress)` (1+ of each trophy and keystone below `max_owned`) and `craft_keystone(progress)` (debits 1 of each trophy, dropping inventory keys at zero per the consume_inventory_item pattern, credits 1 keystone). Both are pure rules — no pygame, no UI.
  - [menu.py](menu.py): `ShopScreen.handle_events` adds `K_4` dispatch *before* the `if not items: continue` guard so the craft hotkey works in an empty shop, mirroring T9's exchange-key placement.
  - [menu_view.py](menu_view.py): `_TROPHY_SHORT_LABELS` extended with `prismatic_keystone → "Keystone"`. `_build_trophy_strings(progress)` now (a) appends `Keystone xN` to the summary when the player owns one, (b) emits `[4] Craft Keystone (1 of each)` in the hint when the recipe is satisfied, alongside or independent of the existing `[1/2/3]` exchange hint.
  - [rpg.py](rpg.py): added module-level `_BIOME_TROPHY_DISPLAY` map (long-form labels like "Boulder Stat Shards") and `_build_trophy_tally_lines(progress)` helper. Defensive: returns `()` when `progress` lacks an `inventory` attribute or it's empty, which keeps existing `_on_level_complete` test mocks (SimpleNamespace without inventory) green. `_on_level_complete` appends the tally tuple to its existing `detail_lines` after `complete_dungeon_from_runtime` (so the inventory reflects the post-run state).
- Test coverage:
  - [tests/test_shop.py](tests/test_shop.py): new `PrismaticKeystoneCraftTests` class with five tests — needs one of each, false when any missing, debit/credit + key pruning, preserves extra trophies above one, and target-cap rejection.
  - [tests/test_rpg_runtime.py](tests/test_rpg_runtime.py): new `TrophyTallyHelperTests` class with three tests — empty inventory, missing inventory attr, and only-nonzero-trophies-in-canonical-order projection.

### Verification

- `python -m unittest discover -s tests` → 648/648 OK (was 640 pre-T10; +5 keystone craft tests, +3 trophy tally helper tests).

## Handoff Snapshot (2026-04-29p)

- **T9 — biome trophy shop exchange** lets players salvage surplus biome trophies in the post-run shop. The conversion is a one-way 3:1 trade (`BIOME_TROPHY_EXCHANGE_RATIO`) so players never accidentally farm a single biome's challenge route — surplus stays meaningful but never fully wasted.
- Wiring:
  - [settings.py](settings.py): added `BIOME_TROPHY_IDS = ("stat_shard", "tempo_rune", "mobility_charge")` and `BIOME_TROPHY_EXCHANGE_RATIO = 3`.
  - [shop.py](shop.py): `Shop` gains three pure-rules methods:
    - `can_exchange_trophy(from_id, to_id, progress)` — validates ids are different biome trophies, source has at least the ratio in inventory, and target isn't at `max_owned`.
    - `exchange_trophy(from_id, to_id, progress)` — debits `ratio` from source (drops the inventory key when count hits zero, matching `consume_inventory_item`'s pattern) and credits 1 to target. Returns `False` on any precondition failure.
    - `best_trophy_source_for(to_id, progress)` — picks the surplus trophy with the largest exchangeable stack to act as the auto-source for the UI hotkeys (ties broken by `BIOME_TROPHY_IDS` order).
  - [menu.py](menu.py): `ShopScreen` gains three hotkeys via `_TROPHY_EXCHANGE_KEYS = {K_1: "stat_shard", K_2: "tempo_rune", K_3: "mobility_charge"}`. Each spends 3 of the player's largest other-trophy stack and grants 1 of the target. A new footer block renders the trophy summary line and exchange hint (small grey text) below the existing "Press ESC to return" prompt.
  - [menu_view.py](menu_view.py): `ShopView` extended with two new optional fields (`trophy_summary_text`, `trophy_exchange_hint`, both defaulting to `""` for backwards-compat). New `_build_trophy_strings(progress)` helper produces both strings — both empty when the player owns no trophies, hint omitted when no surplus is available.
- Test coverage:
  - [tests/test_shop.py](tests/test_shop.py) (new file): `BiomeTrophyExchangeTests` covers nine scenarios — minimum-surplus enforcement, debit/credit, inventory-key pruning at zero, same-id rejection, non-trophy-id rejection, target-cap rejection, source auto-pick (largest), no-surplus → `None`, and self-exclusion in the auto-pick.
  - [tests/test_menu_view.py](tests/test_menu_view.py): existing shop projection test extended to assert the empty trophy strings; two new tests verify the summary/hint surface when trophies are owned, and that the exchange hint is hidden when no source has the surplus ratio.

### Verification

- `python -m unittest discover -s tests` → 640/640 OK (was 629 pre-T9; +9 trophy-exchange tests, +2 menu-view trophy-string tests).

## Handoff Snapshot (2026-04-29o)

- **T8 — biome reward spend feedback flashes** gives the player visual confirmation when a trophy is spent. Each successful `use_stat_shard` / `use_tempo_rune` / `use_mobility_charge` queues a brief expanding-ring flash anchored at the player's rect center, colored to match the trophy (brown / ice blue / teal). The ring grows over `BIOME_REWARD_FLASH_LIFETIME_MS` (600 ms) and the line thickness shrinks as it expands so it visually fades.
- Wiring:
  - [damage_feedback.py](damage_feedback.py): added `BiomeRewardFlashTracker` (a third singleton tracker alongside `HealthBarTracker` and `DamageNumberTracker`) plus tunables `BIOME_REWARD_FLASH_LIFETIME_MS=600`, `BIOME_REWARD_FLASH_MAX_RADIUS=48`, and a `BIOME_REWARD_FLASH_COLORS` map keyed by trophy id. Public API: `report_biome_reward_flash(entity, kind, now_ticks=None)` queues a flash; `build_biome_reward_flash_views(now_ticks=None)` projects active flashes; `reset_all()` now also clears the flash tracker.
  - [consumable_rules.py](consumable_rules.py): each of the three biome-reward `use_*` functions now calls `damage_feedback.report_biome_reward_flash(player, kind, now_ticks)` after the inventory consume succeeds (local import to avoid circular dep, mirroring the existing `pygame`/`identity_runes` local-import pattern in `use_selected_potion`).
  - [hud_view.py](hud_view.py): added `BiomeRewardFlashHUDView` dataclass and a new `biome_reward_flashes: tuple[...]` field on `HUDView`; `build_hud_view` reads from `damage_feedback.build_biome_reward_flash_views(now_ticks)`.
  - [hud.py](hud.py): new `_draw_biome_reward_flashes` renders each flash as a colored ring with `radius = BIOME_REWARD_FLASH_MAX_RADIUS * age_fraction` and `thickness = max(1, int(4 * (1.0 - age_fraction)))`. Drawn in the world-anchored overlay block right after damage numbers so HUD chrome stays on top.
- Test coverage:
  - [tests/test_damage_feedback.py](tests/test_damage_feedback.py): new `BiomeRewardFlashTrackerTests` with four tests — anchor-to-rect-center, unknown-kind drop, lifetime expiry, and `reset_all` clearing.
  - [tests/test_player.py](tests/test_player.py): the three T6 spend tests (`test_use_stat_shard_grants_permanent_max_hp_bump`, `test_use_tempo_rune_extends_attack_boost_window`, `test_use_mobility_charge_triggers_short_speed_burst`) now also assert that each successful spend queued a flash with the matching kind. The stat-shard test wraps the spends in a `pygame.time.get_ticks` patch so the flash lookup time matches the spawn time.

### Verification

- `python -m unittest discover -s tests` → 629/629 OK (was 625 pre-T8; +4 new tracker tests, +flash-queue assertions inside the existing T6 spend tests).

## Handoff Snapshot (2026-04-29n)

- **T7 — HUD biome reward badges + control docs** makes the T6 trophies legible to the player. The quick-bar now surfaces stat_shard / tempo_rune / mobility_charge counts alongside the existing potion/boost/compass slots, and the README documents the new key bindings.
- Wiring:
  - [hud_view.py](hud_view.py): extended `QuickBarHUDView` with three new optional fields (`stat_shard_count`, `tempo_rune_count`, `mobility_charge_count`, all defaulting to `0` so existing call sites keep working). `_build_quick_bar_view` now reads them from `player.progress.inventory`.
  - [hud.py](hud.py): three new badges drawn in `_draw_quick_bar` after the `[7] Compass` slot — `[8] Shard`, `[9] Rune`, `[0] Dash` — using the same icon colors as their item-catalog entries (`(200,140,70)` brown, `(160,210,255)` ice blue, `(90,230,200)` teal) so the badges match the dropped trophy color.
  - [README.md](README.md): added three lines under the controls list describing the K_8/K_9/K_0 bindings and what each trophy does in plain English.
- Test coverage:
  - [tests/test_hud_view.py](tests/test_hud_view.py): `_PlayerStub.progress.inventory` extended with non-zero counts for `stat_shard`/`tempo_rune`/`mobility_charge`; existing `test_build_hud_view_projects_player_and_minimap_state` extended with three new assertions on the projected counts.

### Verification

- `python -m unittest discover -s tests` → 625/625 OK (1 skipped). No new tests added — the existing HUD projection test covers the new fields by adding inventory entries + assertions in place.

## Handoff Snapshot (2026-04-29m)

- **T6 — biome reward activation handlers** turns the inert T5 trophies into spendable runtime effects. Each trophy now consumes one inventory token and applies a distinctive effect that reuses an existing player runtime field, so no new effect-state plumbing was needed:
  - `stat_shard` → permanent `+STAT_SHARD_MAX_HP_BONUS` (10) max_hp bump; also tops up `current_hp` by the same amount, capped at the new max. Stacks across multiple shards.
  - `tempo_rune` → extends `attack_boost_until` by `TEMPO_RUNE_DURATION_MS` (30 s, vs the 20 s `attack_boost` potion), using `max(existing, now+dur)` so re-spending while boosted only ever extends the window.
  - `mobility_charge` → extends `speed_boost_until` by `MOBILITY_CHARGE_DURATION_MS` (6 s — short, sharp burst vs the 20 s `speed_boost` potion), same `max(...)` extension semantics.
- Wiring:
  - [settings.py](settings.py): added `STAT_SHARD_MAX_HP_BONUS=10`, `TEMPO_RUNE_DURATION_MS=30_000`, `MOBILITY_CHARGE_DURATION_MS=6_000` under the existing boost-tuning block.
  - [consumable_rules.py](consumable_rules.py): three new functions `use_stat_shard(player)` / `use_tempo_rune(player, now_ticks)` / `use_mobility_charge(player, now_ticks)` mirroring the established `use_speed_boost` / `use_attack_boost` shape (early-out on missing `progress`, single `consume_inventory_item` call, then mutate runtime field).
  - [player.py](player.py): three thin delegators `Player.use_stat_shard()` / `.use_tempo_rune()` / `.use_mobility_charge()` (no-arg interface; rune/charge methods grab `pygame.time.get_ticks()` internally, matching the existing boost methods).
  - [rpg.py](rpg.py): three new key bindings — `K_8` → stat shard, `K_9` → tempo rune, `K_0` → mobility charge — appended after the existing `K_7` compass binding.
- Test coverage:
  - [tests/test_player.py](tests/test_player.py): three new tests added under `PlayerLoadoutTests`:
    - `test_use_stat_shard_grants_permanent_max_hp_bump` — verifies `+max_hp` and `+current_hp`, stacking across two shards, and the empty-inventory no-op.
    - `test_use_tempo_rune_extends_attack_boost_window` — verifies `attack_boost_until = now + TEMPO_RUNE_DURATION_MS` and the no-shard no-op.
    - `test_use_mobility_charge_triggers_short_speed_burst` — verifies `speed_boost_until = now + MOBILITY_CHARGE_DURATION_MS` and the no-shard no-op.

### Verification

- `python -m unittest discover -s tests` → 625/625 OK (was 622 pre-T6; +3 player tests). One transient failure in `test_dungeon_uses_planned_doors_and_preseeds_branches` reproduced once on first run and passed on the second; topology test is flaky and unrelated to T6 (no T6 file is in its dependency surface).

## Handoff Snapshot (2026-04-29l)

- **T5 — bespoke biome reward items** swaps the T4 stand-in chest mappings for dedicated biome-themed catalog entries so the trap-gauntlet challenge trophies read clearly in the inventory:
  - `stat_shard` → `"Boulder Stat Shard"` (mud_caverns, icon `(200, 140, 70)`).
  - `tempo_rune` → `"Frost Tempo Rune"` (frozen_depths, icon `(160, 210, 255)`).
  - `mobility_charge` → `"Tide Mobility Charge"` (sunken_ruins, icon `(90, 230, 200)`).
- All three new items live under a new `category="biome_reward"` and are loot-only (`can_purchase=False`, `can_loot=False`, `drop_weight=0`, `chest_drop_weight=0`) — they never appear in random chest rolls or shop pages, only as the guaranteed bonus drop when the player commits to a trap-gauntlet challenge route in the matching biome. Each tops out at `max_owned=5`.
- Wiring:
  - [item_catalog.py](item_catalog.py): three new entries appended below the weapon-upgrade overrides; default `storage_bucket="inventory"` is auto-applied so they slot into the standard inventory bucket without touching shop/menu paths.
  - [chest.py](chest.py): `_CHEST_BONUS_LOOT_BY_REWARD_KIND` now maps each kind to its own bespoke item id (`stat_shard`/`tempo_rune`/`mobility_charge`) instead of the T4 stand-ins (`attack_boost`/`armor`/`speed_boost`).
  - No changes needed in [room.py](room.py)/[dungeon.py](dungeon.py)/[rpg.py](rpg.py): the `reward_kind` plumbing already routes the controller's kind through to `Chest.set_reward_kind`/`Chest(reward_kind=…)`, so the catalog swap is transparent to the trap-gauntlet pipeline.
- Test coverage:
  - [tests/test_chest.py](tests/test_chest.py): `ChestRewardKindTests` updated to assert the new bespoke ids (`("loot", "stat_shard")`, `("loot", "tempo_rune")`, `("loot", "mobility_charge")`) plus the re-roll test.
  - [tests/test_item_catalog.py](tests/test_item_catalog.py): new `test_biome_reward_items_are_loot_only_and_excluded_from_random_chest_table` confirms each entry is `category="biome_reward"`, non-purchasable, non-enemy-loot, has `chest_drop_weight=0`, and is absent from `CHEST_LOOT_IDS`.

### Verification

- `python -m unittest discover -s tests` → 622/622 OK (was 621 pre-T5; +1 catalog-shape test, T4 chest-content tests updated in place).

## Handoff Snapshot (2026-04-29k)

- **T4 — actually drop biome-themed challenge rewards** wires T3's `reward_kind` data slice into actual chest loot. Committing to the trap-gauntlet challenge route now both upgrades the chest tier *and* appends a guaranteed biome-themed bonus item to its contents alongside the existing rolled drops. Stand-in mappings (existing item ids reused so no catalog churn — kind names stay biome-flavored so a later catalog pass can swap concrete drops without touching trap plumbing):
  - `chest_upgrade` → no extra item (default behavior unchanged).
  - `stat_shard` → `attack_boost` (mud_caverns Boulder Sweep Run).
  - `tempo_rune` → `armor` (frozen_depths Frost Vent Gauntlet).
  - `mobility_consumable` → `speed_boost` (sunken_ruins Floodgate Hazard Run).
- Wiring:
  - [chest.py](chest.py): new `_CHEST_BONUS_LOOT_BY_REWARD_KIND` map; `Chest.__init__` takes `reward_kind="chest_upgrade"`; new `set_reward_kind` mirrors `set_reward_tier` (re-rolls contents, no-op on looted); `_roll_contents` appends `("loot", bonus_loot_id)` whenever the kind maps to a non-`None` item.
  - [room.py](room.py): new `Room.chest_reward_kind()` reads the controller's `reward_kind` once `challenge_reward_applied` is true (else returns default `"chest_upgrade"`), so room-respawns preserve the biome bonus.
  - [dungeon.py](dungeon.py): chest spawn passes `reward_kind=room.chest_reward_kind()` so re-entry rebuilds the chest with the biome bonus intact.
  - [rpg.py](rpg.py): `upgrade_reward_chest` handler now also calls `chest.set_reward_kind(reward_kind)`; `spawn_reward_chest` forwards `reward_kind` from the payload to `Chest(...)`.
- Test coverage:
  - [tests/test_chest.py](tests/test_chest.py): new `ChestRewardKindTests` class with 6 tests — default kind keeps base contents; each biome kind appends its expected bonus loot; `set_reward_kind` re-rolls unopened chests; `set_reward_kind` on a looted chest is a no-op.
  - [tests/test_rpg_runtime.py](tests/test_rpg_runtime.py): `_DummyChest` + `_SpawnedChest` extended with `reward_kind`/`set_reward_kind` so the existing `upgrade_reward_chest` payload assertion still mirrors the real shape.

### Verification

- `python -m unittest discover -s tests` → 621/621 OK (was 615 pre-T4; +6 new chest reward-kind tests).

## Handoff Snapshot (2026-04-29j)

- **T3 — biome-themed trap challenge-route reward variants** finishes the trap-gauntlet biome theming pass (T1 damage, T2 tempo, T3 reward flavor). Each `trap_gauntlet` template now exposes `trap_challenge_reward_kind: str` (default `"chest_upgrade"`) that flows through to the challenge-route completion payload and HUD reward label. Biome opt-ins:
  - mud_caverns `Boulder Sweep Run` → `"stat_shard"` (HUD label `"Stat shard claimed"`).
  - frozen_depths `Frost Vent Gauntlet` → `"tempo_rune"` (HUD label `"Tempo rune claimed"`).
  - sunken_ruins `Floodgate Hazard Run` → `"mobility_consumable"` (HUD label `"Mobility charge claimed"`).
  - Default `chest_upgrade` keeps the existing `"Reward upgraded"` label.
- Wiring: [content_db.py](content_db.py) (`ROOM_TEMPLATE_COLUMNS`, `_plan_shape`, SQL DDL `TEXT NOT NULL DEFAULT 'chest_upgrade'`, `_ensure_schema_columns`, biome overrides + note text) → [room_plan.py](room_plan.py) (field on both dataclasses + `from_mapping`) → [room_selector.py](room_selector.py) (`str(template.trap_challenge_reward_kind or "chest_upgrade")` parse + ctor kwarg) → [room.py](room.py): `_build_trap_gauntlet_configs` stamps `reward_kind` onto the controller; `update_objective` adds `"reward_kind": controller.get("reward_kind", "chest_upgrade")` to the existing `upgrade_reward_chest` payload (chest tier upgrade still applies — biome flavor is additive); new module-level `_TRAP_REWARD_KIND_LABELS` dict drives `_trap_reward_status_label` text once the reward is claimed.
- Reward delivery is intentionally still a chest-tier upgrade for now; the kind currently surfaces as HUD-only flavor + payload metadata, so downstream consumers (rune drops, consumable spawns) can read `reward_kind` in a later slice without further data plumbing.
- Test coverage:
  - [tests/test_room_objectives.py](tests/test_room_objectives.py): existing `test_trap_challenge_lane_upgrades_reward_tier` updated to expect new `reward_kind: "chest_upgrade"` field; three new tests `test_trap_challenge_lane_payload_carries_biome_reward_kind` (stat_shard), `test_trap_challenge_lane_label_reflects_tempo_rune_reward`, `test_trap_challenge_lane_label_reflects_mobility_consumable_reward` exercise payload + HUD label per kind.
  - [tests/test_content_db.py](tests/test_content_db.py): three biome assertions confirm mud=stat_shard, frozen=tempo_rune, sunken=mobility_consumable.
  - [tests/test_rpg_runtime.py](tests/test_rpg_runtime.py): synthetic upgrade payload updated to include `reward_kind` (consumer ignores the field, but keeps the test's payload mirroring the real shape).

### Verification

- `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector tests.test_rpg_runtime` → 143/143 OK.
- `python -m unittest discover -s tests` → 615/615 OK (was 612 pre-T3; +3 new biome-reward tests).

## Handoff Snapshot (2026-04-29i)

- **T2 — biome-tuned trap speed scale** continues the trap-gauntlet biome theming pass alongside T1's intensity scale. Each `trap_gauntlet` room template now also exposes `trap_speed_scale: float` (default `1.0`); values >1 quicken hazards (sweepers move faster, vent/crusher cycles shorten) and values <1 slow them. Biome opt-ins:
  - mud_caverns `Boulder Sweep Run` → `0.85` (slow-and-heavy, paired with intensity 1.4 — boulders roll deliberately and crush hard).
  - frozen_depths `Frost Vent Gauntlet` → `1.25` (fast-and-light, paired with intensity 0.8 — vents pulse rapidly but each blast bites less, rewarding precise timing).
  - sunken_ruins `Floodgate Hazard Run` keeps default 1.0 (only intensity 1.15).
- Wiring follows the established pattern: [content_db.py](content_db.py) adds `trap_speed_scale` to `ROOM_TEMPLATE_COLUMNS`, `_plan_shape`, SQL DDL, `_ensure_schema_columns`, and the two biome overrides → [room_plan.py](room_plan.py) adds the field to both dataclasses + `from_mapping` row.get → [room_selector.py](room_selector.py) parses with `max(0.0, float(...))` + ctor kwarg → [room.py](room.py) `_build_trap_gauntlet_configs` stamps `speed_scale` onto the controller; new module-level `_scale_trap_cycle(base_ms, controller)` returns `max(50, round(base_ms / scale))` (inverse — higher scale ⇒ shorter ms). Sweeper config multiplies `speed`/`challenge_speed` by `speed_scale`; vent and crusher configs scale `cycle_ms`, `active_ms`, `challenge_cycle_ms`, `challenge_active_ms`. Vent timings are scaled before `_compute_timed_safe_spots` is called so safe-spot geometry continues to track the real cadence.
- Test coverage added in [tests/test_room_objectives.py](tests/test_room_objectives.py): `test_trap_gauntlet_default_speed_scale_keeps_base_hazard_timings`, `test_trap_gauntlet_high_speed_scale_quickens_hazard_timings` (1.25 → 2240/1440/1920/960 ms), `test_trap_gauntlet_low_speed_scale_slows_hazard_timings` (0.85 → 3294/2824/1529 ms). Two biome assertions added in [tests/test_content_db.py](tests/test_content_db.py) for mud=0.85 and frozen=1.25.

### Verification

- `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector` → 127/127 OK.
- `python -m unittest discover -s tests` → 612/612 OK (was 609 pre-T2; +3 new trap-speed tests).

## Handoff Snapshot (2026-04-29h)

- **T1 — biome-tuned trap intensity scale** kicks off the trap-gauntlet biome theming pass. Each `trap_gauntlet` room template now exposes a single `trap_intensity_scale: float` (default `1.0`) that multiplies the base damage of every hazard type (sweepers, vent lanes, crushers) when the room boots. Biome opt-ins:
  - mud_caverns `Boulder Sweep Run` → `1.4` (heavier hits to match the boulder fantasy).
  - frozen_depths `Frost Vent Gauntlet` → `0.8` (lighter individual ticks since vents pulse often).
  - sunken_ruins `Floodgate Hazard Run` → `1.15` (slightly punchier mixed-lane hits).
- Wiring follows the established data-layer pattern: [content_db.py](content_db.py) (`ROOM_TEMPLATE_COLUMNS`, `_plan_shape`, SQL DDL `REAL NOT NULL DEFAULT 1.0`, `_ensure_schema_columns`, biome overrides) → [room_plan.py](room_plan.py) (`RoomTemplate.trap_intensity_scale`, `from_mapping` row.get, `RoomPlan.trap_intensity_scale`) → [room_selector.py](room_selector.py) (`max(0.0, float(...))` parse + ctor kwarg) → [room.py](room.py) (`_build_trap_gauntlet_configs` stamps the scale onto the controller dict; new module-level `_scale_trap_damage(base, controller)` helper applies `max(1, round(base * scale))` to sweeper/vent/crusher `damage` values).
- Test coverage added in [tests/test_room_objectives.py](tests/test_room_objectives.py): `test_trap_gauntlet_default_intensity_keeps_base_hazard_damage` (1.0 → 8/7/9), `test_trap_gauntlet_high_intensity_scales_hazard_damage_up` (1.4 → 11/10/13), `test_trap_gauntlet_low_intensity_scales_hazard_damage_down` (0.8 → 6/6/7). Three biome assertions added in [tests/test_content_db.py](tests/test_content_db.py) confirming mud=1.4, frozen=0.8, sunken=1.15.

### Verification

- `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector` → 124/124 OK.
- `python -m unittest discover -s tests` → 609/609 OK (was 606 pre-T1; +3 new trap-intensity tests).

## Handoff Snapshot (2026-04-29g)

- **R5 — minimap role telegraph for ritual `role_chain` rooms** lands as the next slice on the ritual family. The minimap altar marker now wears a colored halo ring matching the in-world role glyph (R4), so kill order is readable both up-close and from the minimap glance.
- `Room.minimap_objective_status` extended: when the room is `objective_rule="destroy_altars"` with `ritual_link_mode="role_chain"` and not yet completed, it returns the active role string (`"summon"`, `"pulse"`, or `"ward"`) by delegating to the existing `_ritual_role_chain_active_role()` helper. Holdout-room behavior (shrink/migrate/anchor/contested) is unchanged. Other ritual link modes (`ward_shields_others`, `pulse_gates_damage`) still return `None` because they don't enforce a strict ordered chain.
- `HUD._minimap_status_ring_color` extended with an `altar` kind branch that maps the role string back to the same color triplets used by `_ALTAR_ROLE_COLORS` in [objective_entities.py](objective_entities.py): `summon=(255,130,110)`, `pulse=(255,220,110)`, `ward=(140,200,255)`. The 3px-radius ring already drew behind the dot for holdout rooms, so altars inherit that rendering pipeline for free — no plumbing changes in [dungeon.py](dungeon.py) or [hud_view.py](hud_view.py).
- No template/SQL changes needed; the slice purely consumes the existing `role` field stamped by `Room._build_altar_configs` and the existing `ritual_link_mode` plumbing.
- Test coverage added in [tests/test_room_objectives.py](tests/test_room_objectives.py):
  - `test_minimap_objective_status_reflects_active_role_for_role_chain_rituals` walks the full chain (summon → pulse → ward → None once all altars fall).
  - `test_minimap_objective_status_is_none_for_non_role_chain_ritual_rooms` guards `ward_shields_others` so non-chain modes stay at `None`.

### Verification
- Focused: `python -m unittest tests.test_room_objectives` → 93 OK.
- Full: `python -m unittest discover -s tests` → 606 OK.

## Handoff Snapshot (2026-04-29f)

- **R4 — visual telegraph for the active ritual role** lands as the next slice on the ritual family. Each ritual altar that carries a `role` now renders a small color-coded glyph (downward-pointing triangle) directly above its sprite, so players can resolve kill order at a glance instead of relying on the HUD `Break <role> first` label alone.
- New module-level constants in [objective_entities.py](objective_entities.py): `_ALTAR_ROLE_COLORS` maps `summon → orange-red`, `pulse → amber`, `ward → cool blue`; each role tuple is `(bright, dim)` so vulnerable altars render bright and shielded altars render dim. Unknown roles fall back to `_ALTAR_ROLE_DEFAULT_COLORS = ((230,230,230),(130,130,130))` so any future role still gets a glyph instead of vanishing.
- `AltarAnchor.role_glyph_color()` returns the bright color when the altar is vulnerable, the dim color when shielded by `invulnerable=True` (covers `role_chain` and `ward_shields_others`) or by a closed `window_gated` pulse window (covers `pulse_gates_damage`), and `None` when no `role` is configured (legacy single-role rituals stay glyph-free). The helper is the single source of truth so HUD/minimap follow-ups can reuse it without duplicating the gating logic.
- `AltarAnchor.draw_overlay` always runs (instead of returning early when the pulse is dormant) so the role glyph stays visible between pulses; the existing pulse-radius ring still draws only while `pulse_active`. The glyph itself is a 16×6 filled triangle with a 1px dark outline rendered ~6px above `rect.top`, so it pops against any tile color without overlapping the altar sprite.
- No template/SQL changes were needed — the slice purely consumes the existing `role` field that `Room._build_altar_configs` already stamps from `ritual_role_script`. Biome rooms inherit the glyph automatically.
- Test coverage added in `tests/test_room_objectives.py`:
  - `test_ritual_role_glyph_color_is_bright_for_active_role_and_dim_for_shielded` walks the role_chain transition (summon active → bright; pulse/ward shielded → dim; after summon falls, pulse turns bright while ward stays dim).
  - `test_ritual_role_glyph_color_returns_none_when_role_missing` guards the legacy no-role path.
  - `test_ritual_role_glyph_renders_above_altar_when_role_present` constructs a real `pygame.Surface`, calls `draw_overlay`, and samples a pixel just above the altar to confirm the glyph polygon actually paints (non-black).

### Verification
- Focused: `python -m unittest tests.test_room_objectives` → 91 OK.
- Full: `python -m unittest discover -s tests` → 604 OK.

## Handoff Snapshot (2026-04-29e)

- **R3 — punitive feedback for wrong-order ritual altar strikes** lands as the next slice on the ritual family. Striking a shielded altar (whether shielded by `role_chain`, `ward_shields_others`, or a closed `pulse_gates_damage` window) now flashes a brief `Wrong target` HUD cue and optionally spawns a small reinforcement wave so kill-order is taught actively rather than blocked silently.
- New per-template field `ritual_wrong_strike_spawn_count` flows through `content_db.py`, `RoomTemplate`, `RoomPlan`, `RoomSelector`, and `Room`. The selector clamps to `max(0, int(...))` so `0` (the default) cleanly disables the spawn while still allowing the HUD cue to fire.
- `AltarAnchor.take_damage` stamps `wrong_struck_pending=True` on its config dict whenever damage is rejected for `invulnerable=True` or for a closed `window_gated` window. Because the same dict lives in `Room.objective_entity_configs`, the room consumes the flag in `_consume_ritual_wrong_strikes(now_ticks)` during `update_objective`'s `destroy_altars` branch — which runs before `_maybe_trigger_ritual_reaction`, throttles re-fires through `_RITUAL_WRONG_STRIKE_COOLDOWN_MS=1500`, and stamps `_ritual_last_wrong_strike_at` for the HUD.
- HUD destroy_altars label gains a `wrong_strike_suffix` (` | Wrong target`) appended after `shield_suffix` while `now_ticks - _ritual_last_wrong_strike_at <= _RITUAL_WRONG_STRIKE_HUD_MS` (1500ms). Other ritual suffixes (pulse window, ward shielded, role_chain `Break <role> first`) continue to render unchanged so the new cue stacks atop existing telegraphs without rearranging them.
- Mud Caverns `Spore Totem Grove` opts in with `ritual_wrong_strike_spawn_count=1` and an updated notes string ("Striking a shielded totem releases a spore swarm."). Other biome ritual rooms keep the default `0` so they only flash the HUD cue without extra spawns until tuned.
- Test coverage added in `tests/test_room_objectives.py`: `test_ritual_wrong_strike_spawns_reinforcements_and_flashes_hud` asserts the `spawn_enemies / source=ritual_wrong_strike` update, the `enemy_configs` extend, the `Wrong target` HUD label, and the consumed flag; `test_ritual_wrong_strike_throttled_within_cooldown` proves the second strike inside 1500ms is silent; `test_ritual_wrong_strike_does_not_fire_on_legitimate_kill` guards that vulnerable-altar damage never stamps the flag. `tests/test_content_db.py` was extended for the new SQL column, the schema column-list literals, and the seeded-template tuple shape (one extra positional element after `ritual_payoff_label`).

### Verification
- Focused: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector` → 116 OK.
- Full: `python -m unittest discover -s tests` → 601 OK.

## Handoff Snapshot (2026-04-29d)

- Two slices land in this pass: **H4 polish (minimap status telegraphs for holdout state)** closes Milestone 3, and **R2 (ritual altar role inter-links — kill order matters)** opens the next pass on Milestone 1's ritual family with a new biome opt-in.

### H4 — minimap holdout telegraphs
- New `Room.minimap_objective_status(now_ticks=None)` projects holdout zone state into a tiny status hint string. Priority order (only one wins): `migrating` (within `_HOLDOUT_ZONE_MIGRATION_HUD_MS` of `last_migrated_at`), `anchored` (within `migration_anchor_until`), `contested` (radius hit `min_radius`), `shrinking` (still actively shrinking from initial). Returns `None` for non-holdout rooms and for fresh, full-radius zones, so existing minimap behavior is unchanged unless the room actively wants to telegraph state.
- `Dungeon.minimap_snapshot(now_ticks=None)` now optionally accepts a tick stamp and threads `objective_status` through the per-room dict. `MinimapRoomHUDView` gains an `objective_status: str | None = None` field; `_build_minimap_view(dungeon, now_ticks=None)` passes the tick through; `build_hud_view` already had `now_ticks` in scope so the wiring is one-liner additive.
- `HUD._draw_minimap_objective_marker` accepts an optional `status` argument and draws a 1-pixel halo ring around the marker dot when set. Color map (holdout-only for now): `migrating=(255,240,200)` warm flash, `anchored=(180,220,255)` cool, `contested=(255,110,90)` alert red, `shrinking=(245,170,90)` amber. Existing dot rendering is untouched so the kind/label glance still reads as before.
- Test stubs in `tests/test_hud_view.py` updated to accept the optional `now_ticks` arg on `minimap_snapshot` lambdas (4 stubs). New tests in `tests/test_room_objectives.py`: `test_minimap_objective_status_reflects_holdout_zone_state` walks the full status priority chain (fresh → shrinking → contested → anchored → migrating → fallback to contested when transient banners are clear), and `test_minimap_objective_status_is_none_for_non_holdout_rooms` guards the no-status path so other objective rooms are unaffected.

### R2 — ritual role inter-links
- New ritual link mode `role_chain` enforces kill order matching unique roles in `ritual_role_script`. The first unique role in the script must be wiped before the next role becomes vulnerable. `Room._refresh_ritual_links` now sets `invulnerable=True` for any altar whose role is not the current "active role"; `Room._ritual_role_chain_priority()` derives the priority tuple from `ritual_role_script`, and `Room._ritual_role_chain_active_role()` walks priority against currently-live roles. Existing `ward_shields_others` and `pulse_gates_damage` modes are untouched.
- HUD shield suffix is role-aware: when `link_mode=role_chain` and at least one altar is shielded, the suffix becomes `| Break <active_role> first N shielded` (`summon`, `pulse`, or `ward`). Other modes still render the existing `Break wards N shielded`. Playtest hint extends similarly: `"Break the <active_role> <label> first; the rest stay shielded until that role is gone."`
- Mud Caverns `Spore Totem Grove` (the only base-mode biome ritual room) opts in with `ritual_link_mode="role_chain"` and an updated notes string ("Destroy spore totems in script order — summoners first, then pulse heads, then wards — while fungal pulse rings punish camping."). Frozen Depths keeps `pulse_gates_damage`; Sunken Ruins `Tidal Idol Collapse` and the base template keep `ward_shields_others`.
- `AltarAnchor.take_damage` already short-circuits on `invulnerable=True` and `_build_image` already renders a shielded color, so no sprite changes were needed — the new mode reuses the existing visual cue and damage gating that `ward_shields_others` introduced.
- Test coverage added in `tests/test_room_objectives.py`: `test_ritual_role_chain_enforces_kill_order_from_role_script` walks all three vulnerability transitions for a 3-altar `summon,pulse,ward` script, asserting the HUD `Break <role> first` suffix and the playtest hint cycling through roles. `tests/test_content_db.py` extended to assert the mud_caverns override sets `ritual_link_mode=role_chain` and surfaces "script order" in the notes string.

### Verification
- Focused: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector tests.test_dungeon_topology tests.test_hud_view` → 138 OK.
- Full: `python -m unittest discover -s tests` → 598 OK.

## Handoff Snapshot (2026-04-29c)

- Milestone 3 (`Survival Holdout`) advances into the **H3 follow-up (relief tuning around migration)**. Stabilizers now interlock with H2 by also briefly anchoring the holdout zone in place: triggering one delays the next migration and surfaces a transient "Zone anchored" HUD beat, so the side action becomes meaningful in migration-enabled finales rather than competing with them.
- New per-template field `holdout_stabilizer_migration_delay_ms` flows through `content_db.py`, `RoomTemplate`, `RoomPlan`, `RoomSelector`, and `Room._build_holdout_configs`. The selector zeroes the field whenever `holdout_zone_migrate_ms <= 0` and defaults it to `migrate_ms` when a migration room leaves the override at zero, so misconfiguration cannot silently disable the new interlock.
- `Room._build_holdout_configs` stamps the holdout zone with `migration_baseline_ms=0`, `migrations_completed=0`, `migration_anchor_until=None`, and stamps each `holdout_stabilizer` config with `migration_delay_ms` plus a `zone_config` back-reference to the same holdout zone dict. `Room._apply_holdout_zone_migration` was refactored to a monotonic counter approach: it computes `expected_migrations = max(0, now_ticks - started_at - baseline_ms) // migrate_ms` and only advances when `expected_migrations > migrations_completed`. This guarantees baseline shifts can never cause `anchor_index` to regress when crossing modulo boundaries.
- `HoldoutStabilizer.sync_player_overlap` now bumps `zone_config["migration_baseline_ms"]` by `migration_delay_ms` and stamps `zone_config["migration_anchor_until"] = now_ticks + migration_delay_ms` whenever the activated stabilizer is wired to a migration-enabled zone. The existing `wave_delay_ms` reinforcement deferral still fires identically, so stabilizers retain their original purpose and gain the new anchor side benefit additively.
- HUD adds a transient ` | Zone anchored` suffix while `now_ticks <= migration_anchor_until`, slotted in the same position as the H2 ` | Zone moved` banner and mutually exclusive with it (the migration-just-fired banner takes precedence inside its own 1500ms window). The playtest hint extends the H2 migration clause to mention the anchor side benefit ("Optional stabilizers delay reinforcement waves and anchor the current circle.") whenever an unused stabilizer carries `migration_delay_ms > 0`; non-migration rooms keep the original wave-only hint.
- Base `survival_holdout` opts in with `holdout_stabilizer_migration_delay_ms=4500`, matching its `migrate_ms=4500` cadence so a single stabilizer activation defers the next migration by exactly one cycle while also delaying the next reinforcement wave. Biome overrides inherit the H2+H3 interlock automatically because `_override_template` only patches passed keys.
- Test coverage added in `tests/test_room_objectives.py`: `test_holdout_stabilizer_anchors_zone_and_defers_migration` activates a stabilizer just before the first migration boundary, asserts the baseline shift, the `Zone anchored` HUD beat, the delayed migration firing exactly at the deferred boundary, the `Pressure eased` reinforcement deferral still triggering, and the playtest hint mentioning the anchor side benefit; `test_holdout_stabilizer_skips_migration_defer_when_room_has_no_migration` guards the no-migration default path so existing biome rooms (and any holdouts that omit migration anchors) leave `migration_baseline_ms=0` and `migration_anchor_until=None` even when the stabilizer fires.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector` (110 OK) and the full `python -m unittest discover -s tests` suite (595 tests, OK).

## Handoff Snapshot (2026-04-29b)

- Milestone 3 (`Survival Holdout`) advances into **H2 (zone migration / multi-anchor holdouts)**. The `holdout_zone` now optionally cycles between a list of pre-resolved pixel anchors at a fixed cadence, so the player has to break camp at least once per finale instead of squatting on a static circle.
- New per-template fields `holdout_zone_migrate_ms` and `holdout_zone_migration_offsets` flow through `content_db.py`, `RoomTemplate`, `RoomPlan`, `RoomSelector`, and `Room._build_holdout_configs`. The selector parses the offset script (`"-5,-3;5,3"` style) using the existing `_parse_offset_script` helper and zeros out `migrate_ms` whenever no offsets resolve, so misconfiguration cannot wedge the zone in place.
- `Room._build_holdout_configs` now stamps `anchors` (a tuple of `(initial_portal_center, *offset_pixels)`), `anchor_index=0`, `migrate_ms`, and `last_migrated_at=None` onto the `holdout_zone` config. `Room._apply_holdout_zone_migration` runs once per `update_objective` tick on `holdout_timer` rooms, computes the active anchor as `(elapsed_real_time // migrate_ms) % len(anchors)` against `objective_started_at`, swaps `holdout_zone["pos"]`, force-clears `occupied=False`, and timestamps `last_migrated_at` so the HUD can flash a banner. `objective_target_info` already reads `config["pos"]`, so minimap/compass updates flow through automatically.
- `HoldoutZone.update` and `HoldoutZone.sync_player_overlap` were tightened to re-anchor `self.rect` from `config["pos"]` whenever the room migrates the zone. This keeps the existing distance-based occupancy check accurate without touching the GameLoop overlap pipeline.
- HUD adds a transient ` | Zone moved` suffix for `_HOLDOUT_ZONE_MIGRATION_HUD_MS = 1500` ms after each migration, slotted between the existing `Zone NN%` shrink suffix and the relief suffix; `Return to circle` continues to fire because the zone clears `occupied` on migration. The playtest hint appends `"It also migrates between anchors, forcing you to break camp."` whenever `migrate_ms > 0` and at least one alternate anchor resolved.
- Base `survival_holdout` opts in with `migrate_ms=4500, migration_offsets="-5,-3;5,3"`, giving a three-anchor cycle (portal center, NW, SE) inside the existing 9000ms timer. Biome overrides inherit the H1 shrink + H2 migration automatically because `_override_template` only patches passed keys.
- Test coverage added in `tests/test_room_objectives.py`: `test_holdout_zone_migrates_between_anchors_and_pauses_progress` drives `update_objective` across the migration boundaries, verifies the anchor index advance, the forced `occupied=False`, the HUD `Zone moved` flash, the `HoldoutZone` sprite rect re-anchoring, the progress pause while the player is outside the relocated circle, the second-boundary cycle, and the playtest hint clause; `test_holdout_zone_migration_disabled_when_no_offsets` guards the no-migration path so existing biome rooms (and test plans that omit offsets) keep their static-circle behavior.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector` (108 OK) and the full `python -m unittest discover -s tests` suite (593 tests, OK with 1 pre-existing skip).

## Handoff Snapshot (2026-04-29)

- Milestone 3 (`Survival Holdout`) opens with **H1 (contested-ground zone shrink)**. The holdout zone now narrows over real time toward a configurable contested-ground floor, so kiting around a static circle stops being a viable stall. Partial-credit on relief uptime (occupancy-only progress accrual) was already present from earlier passes and continues to work alongside the shrink.
- New per-template fields `holdout_zone_min_radius` and `holdout_zone_shrink_ms` flow through `content_db.py`, `RoomTemplate`, `RoomPlan`, `RoomSelector`, and `Room._build_holdout_configs`. `Room._apply_holdout_zone_shrink` runs once per `update_objective` tick on `holdout_timer` rooms and linearly interpolates `holdout_zone["radius"]` from `initial_radius` down to `min_radius` over `shrink_ms`, anchored on `objective_started_at` (so the floor is hit even if the player kites out of the circle). The base `survival_holdout` template opts in with `min_radius=56, shrink_ms=7500` against its `radius=96, duration=9000ms` defaults; biome overrides inherit the shrink behavior automatically because `_override_template` only patches the keys passed in.
- The HUD `holdout_timer` projection adds a `Zone NN%` suffix once the circle has shrunk below ~99% of its initial radius, slotted between the existing `Return to circle` and `Pressure eased / Stabilizers` suffixes so the contested-ground signal reads at a glance. The playtest hint also gains a `"The circle shrinks to contested ground over time."` clause whenever the room's holdout zone is configured with `shrink_ms > 0`.
- Test coverage added in `tests/test_room_objectives.py`: `test_holdout_zone_radius_shrinks_to_contested_floor_over_duration` asserts the linear interpolation midpoint, the clamp at `min_radius`, the new HUD suffix, and the new playtest hint clause; `test_holdout_zone_without_shrink_keeps_initial_radius_and_hides_zone_suffix` guards the no-shrink default path so existing biome holdouts that don't set shrink still render exactly as before. The `_plan` helper was extended to forward the two new kwargs.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector` (106 OK) and the full `python -m unittest discover -s tests` suite (591 tests, OK with 1 pre-existing skip; the previously-flagged shop-scroll failure no longer reproduced on this run).

## Handoff Snapshot (2026-04-28d)

- Milestone 2 (`Puzzle-Gated Doors`) closes out **P4 (per-dungeon puzzle motifs)**. All three biome puzzle overrides now consistently use the P1–P3 plumbing in a biome-flavored way:
  - **Mud Caverns / Rune Lock Gallery (`ordered_plates`)** opts in to a stabilizer (`count=1, hp=10`) read as a "crumbling buried glyph" and to a slow camp pulse (`damage=1, interval=1100ms, grace=1200ms, radius=38`) framed as cave-in dust.
  - **Frozen Depths / Mirror Rune Gallery (`paired_runes`)** keeps its pair-skip stabilizer and adds a frostbite camp pulse (`damage=1, interval=1200ms, grace=1100ms, radius=36`).
  - **Sunken Ruins / Tidal Counter-Seals (`staggered_plates`)** retains the existing tide-pulse + glyph-skip combo from P2/P3.
- No new code was needed — only tuning of `content_db.py` overrides plus updated `notes` strings that surface each motif in the playtest hint via the existing `_playtest_identifier_detail` plumbing.
- Test coverage extended in `tests/test_content_db.py` to assert each biome's stabilizer count/HP, camp-pulse damage/interval, and motif-flavored notes substrings (`"cave-in dust"`, `"frostbite"`, `"staggered tidal glyph order"`). Existing puzzle behavior tests in `tests/test_room_objectives.py` continue to use `_plan` defaults so their exact-string assertions are unaffected.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector` (104 OK) and the full `python -m unittest discover -s tests` suite (589 tests; only the pre-existing `test_build_shop_view_projects_item_rows_and_scroll_hints` shop-scroll failure remains, unrelated and present on `main`).
- **Milestone 2 (Puzzle-Gated Doors) is now complete** across all four planned slices.

## Handoff Snapshot (2026-04-28c)

- Milestone 2 (`Puzzle-Gated Doors`) advances into **P3 (alternate solve routes)** by extending the optional puzzle stabilizer to the `paired_runes` variant. `Room._maybe_append_puzzle_stabilizer` no longer short-circuits on paired puzzles, and `PuzzleStabilizer._apply_skip` now branches on `controller["variant"]`: ordered/staggered keep their existing "advance the next expected plate" behavior, while paired_runes resolves an entire pair (preferring whichever pair the player has already half-primed via `pending_pair_label`, otherwise the first un-activated pair in `pair_labels` order). Both branches share the existing skip-suffix HUD beat, the cancel-pending-stall safeguard, and the `consumed=True` marker.
- The paired_runes HUD branch now appends the existing `_puzzle_skip_suffix(now_ticks)` so the "Stabilizer skip" banner shows up consistently across all charge_plates variants. The playtest hint for paired_runes also picks up the existing `shortcut_suffix` ("Shatter the optional stabilizer to skip one step.") whenever a stabilizer is configured.
- Frozen Depths' `Mirror Rune Gallery` opts in: `puzzle_stabilizer_count=1, puzzle_stabilizer_hp=12`, with notes that mention the pair-skip shortcut. Tests updated accordingly: `test_puzzle_stabilizer_is_not_built_for_paired_runes` is replaced by `test_puzzle_stabilizer_skips_one_pair_for_paired_runes`, which half-primes pair B, smashes the stabilizer, and asserts that both B plates flip to activated, the pending-pair label clears, the HUD shows `Stabilizer skip`, and the playtest hint surfaces the shortcut.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog` (82 OK) and the full `python -m unittest discover -s tests` suite (589 tests; only the pre-existing `test_build_shop_view_projects_item_rows_and_scroll_hints` shop-scroll failure remains, unrelated to this slice and present on `main`).

## Handoff Snapshot (2026-04-28b)

- Milestone 2 (`Puzzle-Gated Doors`) advances into **P2 (anti-camping response events)**. Activated `pressure_plate` configs now stamp an `activated_at` timestamp and gain a `PressurePlate.apply_player_pressure(player)` hook that emits periodic damage pulses when the player lingers on a solved plate. Pulses stay disabled unless the puzzle controller has both `camp_pulse_damage` and `camp_pulse_interval_ms` set, and only fire after a configurable grace window. The HUD pressure suffix now distinguishes `Camp pulse` from the existing `Pressure spike` reset feedback.
- New per-template fields `puzzle_camp_pulse_damage`, `puzzle_camp_pulse_interval_ms`, `puzzle_camp_pulse_grace_ms`, and `puzzle_camp_pulse_radius` flow through `content_db.py`, `RoomTemplate`, `RoomPlan`, `RoomSelector`, and `Room._build_puzzle_plate_configs`. The Sunken Ruins `Tidal Counter-Seals` override opts in (`damage=2, interval=900ms, grace=900ms, radius=42px`) and its playtest hint now mentions both the stabilizer skip and the solved-seal tide pulse. Stall resets clear `activated_at` and `last_camp_pulse_at` so reset plates restart cleanly.
- The existing `rpg.GameLoop` objective-iteration loop already calls `apply_player_pressure(player)` on any objective sprite that exposes it (used by ritual altars), so plates were wired in without touching dungeon plumbing.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog` (82 tests, OK) and the full `python -m unittest discover -s tests` suite (589 tests; only the pre-existing `test_build_shop_view_projects_item_rows_and_scroll_hints` shop-scroll failure remains, unrelated to this slice and present on `main`).

## Handoff Snapshot (2026-04-28)

- Milestone 2 (`Puzzle-Gated Doors` P1) continues. Ordered and staggered puzzle rooms now support an optional **puzzle stabilizer** alternate-solve route: a destructible hex-shaped objective entity that, when shattered, auto-activates the next-expected plate, advances the puzzle progress index, suppresses any pending stall reaction, and surfaces a short "Stabilizer skip" HUD suffix. Paired-rune puzzles deliberately do not spawn the stabilizer in this slice because they have no linear next-target to advance.
- New per-template fields `puzzle_stabilizer_count` and `puzzle_stabilizer_hp` flow through `content_db.py`, `RoomTemplate`, `RoomPlan`, `RoomSelector`, and `Room._build_puzzle_plate_configs`. The Sunken Ruins `Tidal Counter-Seals` override now opts in with `count=1, hp=12` and an updated playtest hint.
- New sprite `PuzzleStabilizer` lives in `objective_entities.py`; `dungeon.py` instantiates it from configs whose `kind == "puzzle_stabilizer"`. `Room.remaining_puzzle_plates` and the puzzle HUD totals were tightened to count only `pressure_plate` configs so the stabilizer cannot accidentally satisfy completion or inflate the plate denominator.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog` (80 tests, OK) plus the focused `tests.test_menu_view -k room_test_select_view` projection check (1 test, OK).

## Handoff Snapshot (2026-04-23)

- Milestone 1 (`Trap Gauntlet` G1/G2) is complete in the current branch. The room family now covers sweeper, vent, crusher, and mixed-hazard variants, with entry switches, checkpoint reroutes, and challenge-side reward placement.
- Milestone 2 (`Puzzle-Gated Doors` P1) has started. The ordered-plate path now supports controller-owned target sequences, and a first new rule variant (`staggered_plates`) is live through the Sunken Ruins override.
- Verified during this handoff pass: `python -m unittest discover -s tests -p test_room_objectives.py`, `python -m unittest discover -s tests -p test_content_db.py`, `python -m unittest discover -s tests -p test_room_test_catalog.py`, and the targeted Room Tests menu projection check in `test_menu_view.py -k room_test_select_view`.
- Known residual note: a broader `test_menu_view.py` run previously exposed an unrelated shop-view assertion failure that was not part of this milestone work and was left untouched.
