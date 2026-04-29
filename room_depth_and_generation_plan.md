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

## Resume targets from current state

The original generator-foundation targets are complete enough that the next work should stay inside mechanic-depth slices.

Recommended next continuation order:

1. continue `Puzzle-Gated Doors` Phase P1 so plate rooms gain stronger anti-camping reactions and alternate solve routes on top of ordered, staggered, and paired variants,
2. implement `Survival Holdout` Phase H3 so the player gets optional side actions that reduce pressure during longer finales,
3. return to `Ritual Disruption` for timing-window or tether variants only after another family gains comparable depth,
4. leave escort reward grading and branch archetype specialization for a later pass once puzzle and holdout depth are in place.

## Handoff Snapshot (2026-04-28d)

- Milestone 2 (`Puzzle-Gated Doors`) closes out **P4 (per-dungeon puzzle motifs)**. All three biome puzzle overrides now consistently use the P1–P3 plumbing in a biome-flavored way:
  - **Mud Caverns / Rune Lock Gallery (`ordered_plates`)** opts in to a stabilizer (`count=1, hp=10`) read as a "crumbling buried glyph" and to a slow camp pulse (`damage=1, interval=1100ms, grace=1200ms, radius=38`) framed as cave-in dust.
  - **Frozen Depths / Mirror Rune Gallery (`paired_runes`)** keeps its pair-skip stabilizer and adds a frostbite camp pulse (`damage=1, interval=1200ms, grace=1100ms, radius=36`).
  - **Sunken Ruins / Tidal Counter-Seals (`staggered_plates`)** retains the existing tide-pulse + glyph-skip combo from P2/P3.
- No new code was needed — only tuning of `content_db.py` overrides plus updated `notes` strings that surface each motif in the playtest hint via the existing `_playtest_identifier_detail` plumbing.
- Test coverage extended in `tests/test_content_db.py` to assert each biome's stabilizer count/HP, camp-pulse damage/interval, and motif-flavored notes substrings (`"cave-in dust"`, `"frostbite"`, `"staggered tidal glyph order"`). Existing puzzle behavior tests in `tests/test_room_objectives.py` continue to use `_plan` defaults so their exact-string assertions are unaffected.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog tests.test_room_selector` (104 OK) and the full `python -m unittest discover -s tests` suite (589 tests; only the pre-existing `test_build_shop_view_projects_item_rows_and_scroll_hints` shop-scroll failure remains, unrelated and present on `main`).
- **Milestone 2 (Puzzle-Gated Doors) is now complete** across all four planned slices. Recommended next milestone: **Milestone 3 / Survival Holdout H1 (defend-a-zone refinements)** — extend the existing `holdout_zone` to support contested-ground rules (zone shrink/move, partial-credit on relief uptime) so kiting forever stops being optimal. Alternatively pivot to **Ritual Disruption R2 (altar role inter-links so kill order matters)** since altars already telegraph roles via `ritual_role_script`.

## Handoff Snapshot (2026-04-28c)

- Milestone 2 (`Puzzle-Gated Doors`) advances into **P3 (alternate solve routes)** by extending the optional puzzle stabilizer to the `paired_runes` variant. `Room._maybe_append_puzzle_stabilizer` no longer short-circuits on paired puzzles, and `PuzzleStabilizer._apply_skip` now branches on `controller["variant"]`: ordered/staggered keep their existing "advance the next expected plate" behavior, while paired_runes resolves an entire pair (preferring whichever pair the player has already half-primed via `pending_pair_label`, otherwise the first un-activated pair in `pair_labels` order). Both branches share the existing skip-suffix HUD beat, the cancel-pending-stall safeguard, and the `consumed=True` marker.
- The paired_runes HUD branch now appends the existing `_puzzle_skip_suffix(now_ticks)` so the "Stabilizer skip" banner shows up consistently across all charge_plates variants. The playtest hint for paired_runes also picks up the existing `shortcut_suffix` ("Shatter the optional stabilizer to skip one step.") whenever a stabilizer is configured.
- Frozen Depths' `Mirror Rune Gallery` opts in: `puzzle_stabilizer_count=1, puzzle_stabilizer_hp=12`, with notes that mention the pair-skip shortcut. Tests updated accordingly: `test_puzzle_stabilizer_is_not_built_for_paired_runes` is replaced by `test_puzzle_stabilizer_skips_one_pair_for_paired_runes`, which half-primes pair B, smashes the stabilizer, and asserts that both B plates flip to activated, the pending-pair label clears, the HUD shows `Stabilizer skip`, and the playtest hint surfaces the shortcut.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog` (82 OK) and the full `python -m unittest discover -s tests` suite (589 tests; only the pre-existing `test_build_shop_view_projects_item_rows_and_scroll_hints` shop-scroll failure remains, unrelated to this slice and present on `main`).
- Recommended immediate next slice: continue Milestone 2 with **P4 (per-dungeon puzzle motifs)** — give Mud Caverns and Frozen Depths their own `puzzle_gated_doors` overrides so each biome's puzzle reads visually and mechanically distinct (e.g., decay timers, terrain hazards on the wrong-step path) — or pivot to **Milestone 3 / Holdout H1 (defend-a-zone refinements)**. Either way, rerun the same focused suites before widening scope.

## Handoff Snapshot (2026-04-28b)

- Milestone 2 (`Puzzle-Gated Doors`) advances into **P2 (anti-camping response events)**. Activated `pressure_plate` configs now stamp an `activated_at` timestamp and gain a `PressurePlate.apply_player_pressure(player)` hook that emits periodic damage pulses when the player lingers on a solved plate. Pulses stay disabled unless the puzzle controller has both `camp_pulse_damage` and `camp_pulse_interval_ms` set, and only fire after a configurable grace window. The HUD pressure suffix now distinguishes `Camp pulse` from the existing `Pressure spike` reset feedback.
- New per-template fields `puzzle_camp_pulse_damage`, `puzzle_camp_pulse_interval_ms`, `puzzle_camp_pulse_grace_ms`, and `puzzle_camp_pulse_radius` flow through `content_db.py`, `RoomTemplate`, `RoomPlan`, `RoomSelector`, and `Room._build_puzzle_plate_configs`. The Sunken Ruins `Tidal Counter-Seals` override opts in (`damage=2, interval=900ms, grace=900ms, radius=42px`) and its playtest hint now mentions both the stabilizer skip and the solved-seal tide pulse. Stall resets clear `activated_at` and `last_camp_pulse_at` so reset plates restart cleanly.
- The existing `rpg.GameLoop` objective-iteration loop already calls `apply_player_pressure(player)` on any objective sprite that exposes it (used by ritual altars), so plates were wired in without touching dungeon plumbing.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog` (82 tests, OK) and the full `python -m unittest discover -s tests` suite (589 tests; only the pre-existing `test_build_shop_view_projects_item_rows_and_scroll_hints` shop-scroll failure remains, unrelated to this slice and present on `main`).
- Recommended immediate next slice: continue Milestone 2 with **P3 (more alternate solve routes)** — extend stabilizer support to the base `puzzle_gated_doors` template at higher path stages or wire a paired-rune-friendly shortcut — or pivot to **Milestone 3 / Holdout H1 (defend-a-zone refinements)**. Either way, rerun the same focused suites before widening scope.

## Handoff Snapshot (2026-04-28)

- Milestone 2 (`Puzzle-Gated Doors` P1) continues. Ordered and staggered puzzle rooms now support an optional **puzzle stabilizer** alternate-solve route: a destructible hex-shaped objective entity that, when shattered, auto-activates the next-expected plate, advances the puzzle progress index, suppresses any pending stall reaction, and surfaces a short "Stabilizer skip" HUD suffix. Paired-rune puzzles deliberately do not spawn the stabilizer in this slice because they have no linear next-target to advance.
- New per-template fields `puzzle_stabilizer_count` and `puzzle_stabilizer_hp` flow through `content_db.py`, `RoomTemplate`, `RoomPlan`, `RoomSelector`, and `Room._build_puzzle_plate_configs`. The Sunken Ruins `Tidal Counter-Seals` override now opts in with `count=1, hp=12` and an updated playtest hint.
- New sprite `PuzzleStabilizer` lives in `objective_entities.py`; `dungeon.py` instantiates it from configs whose `kind == "puzzle_stabilizer"`. `Room.remaining_puzzle_plates` and the puzzle HUD totals were tightened to count only `pressure_plate` configs so the stabilizer cannot accidentally satisfy completion or inflate the plate denominator.
- Verified during this handoff pass: `python -m unittest tests.test_room_objectives tests.test_content_db tests.test_room_test_catalog` (80 tests, OK) plus the focused `tests.test_menu_view -k room_test_select_view` projection check (1 test, OK).
- Recommended immediate next slice: keep iterating Milestone 2 by adding a puzzle-specific anti-camping reaction (e.g. periodic hazard pulse near solved plates) or by wiring the stabilizer into the base `puzzle_gated_doors` template at higher path stages, then rerun the same focused suites before widening scope.

## Handoff Snapshot (2026-04-23)

- Milestone 1 (`Trap Gauntlet` G1/G2) is complete in the current branch. The room family now covers sweeper, vent, crusher, and mixed-hazard variants, with entry switches, checkpoint reroutes, and challenge-side reward placement.
- Milestone 2 (`Puzzle-Gated Doors` P1) has started. The ordered-plate path now supports controller-owned target sequences, and a first new rule variant (`staggered_plates`) is live through the Sunken Ruins override.
- Verified during this handoff pass: `python -m unittest discover -s tests -p test_room_objectives.py`, `python -m unittest discover -s tests -p test_content_db.py`, `python -m unittest discover -s tests -p test_room_test_catalog.py`, and the targeted Room Tests menu projection check in `test_menu_view.py -k room_test_select_view`.
- Known residual note: a broader `test_menu_view.py` run previously exposed an unrelated shop-view assertion failure that was not part of this milestone work and was left untouched.
- Recommended immediate next slice: keep Milestone 2 local to puzzle rooms by adding a puzzle-specific anti-camping reaction or one alternate-solve route, then rerun the same focused suites before widening scope.
