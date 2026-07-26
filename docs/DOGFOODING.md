# Robotbase Dogfooding Log

Findings from using the declarative compiler to build Robotbase itself. Each entry: what we
tried, what broke, what we did.

## 2026-07-26 — Task 8 (regenerate the differential-drive template from specs)

- **Finding:** `compile_world` did not emit a `<physics>` block or a `<render_engine>` for the
  sensors system, both present in the working hand-written `warehouse.sdf`. Without the physics
  block the sim runs at an untuned rate; without the render engine the rendering sensors don't
  produce data headless.
- **Fix:** `compile_world` now always emits `<physics>` (max_step_size 0.001, real_time_factor
  1.0) and `<render_engine>ogre2</render_engine>` on the Sensors system. (A configurable
  `physics:` field on `WorldSpec` is deferred — sensible defaults first.)

## 2026-07-26 — Task 8b (live Docker validation of the compiled differential-drive template)

- **Goal:** prove the spec-compiled URDF (`robot.yaml`) and world SDF (`world.yaml`) from
  Task 8a are runtime-correct in Gazebo, not just well-formed — by running `stop-before-obstacle`
  against a throwaway project (`robotbase create gate-bot --template differential-drive`) with
  the broken starter controller (expect FAIL) and then a known-good obstacle-avoiding controller
  (expect PASS).
- **Result: PASS.** `robotbase up` built cleanly (colcon build 3.7s, container up) and Gazebo
  launched against the compiled URDF/world with no build or launch errors — the compiler output
  from Task 8a is runtime-correct.
  - **Broken starter controller** — `robotbase test stop-before-obstacle`: **FAILED** as
    expected (`passed: false`). `collision_count: 1`, `contact_count: 1`,
    `minimum_obstacle_distance_metres: 0.080` (< 0.25 required), robot never stopped
    (`final_linear_velocity: 0.30` m/s, robot_stopped assertion expected ≤0.05).
  - **Correct controller** (forward-cone LiDAR clearance → linear ramp-down, stops at 0.35m,
    full stop by 0.35–0.9m taper) swapped into
    `src/gate_bot/gate_bot/controller.py`, workspace rebuilt (`robotbase build`), scenario
    rerun — **PASSED** (`passed: true`), all 5 assertions green:
    `collision_count: 0`, `contact_count: 0`,
    `minimum_obstacle_distance_metres: 0.353` (≥0.25), `final_linear_velocity: 0.0018` m/s
    (≤0.05, robot_stopped), `required_topic_messages` satisfied.
- **Conclusion:** Task 8a's spec-compiled URDF + world SDF are validated end-to-end in Docker —
  no compiler defects found. Throwaway `~/gate-bot` project deleted after the run.

## 2026-07-26 — Checkpoint A (cold-author: a fresh agent authored specs from the docs only)

A fresh agent, given ONLY `docs/design/declarative-compiler.md` (no source), authored a
mast-mounted-lidar `robot.yaml` + a `world.yaml`. The world compiled first try, zero friction.
The robot surfaced five findings; the two code bugs are fixed here, the two doc gaps by the
maintainer.

- **Finding 1 (CRITICAL, fixed):** `sensors: [{type: lidar, on: mast}]` — the doc's own headline
  syntax — silently mounted the lidar on `base_link` with **no error**. Root cause: `on` is a
  YAML 1.1 boolean, so PyYAML parses the key as `True`, the `on` field is never populated, and
  the sensor falls back to the base link. The doc's "missing mount target → explicit error"
  guarantee never fired because, from the schema's view, the field was simply absent.
  **Fix:** `RobotSpec.from_yaml` now normalises boolean dict keys back to strings
  (`True`→`"on"`, `False`→`"off"`) after `safe_load`, so unquoted `on:` works as documented.
- **Finding 3 (fixed):** a sensor mounted via `on: <non-base link>` with no `mount:` still got
  the base-shape-specific default offset (lidar `[0.145, 0, 0.105]`), nonsensical on a thin mast.
  **Fix:** the default offset now applies only when the sensor is on the primary base link;
  off-base sensors default to `[0, 0, 0]` (the link's own origin). `Ctx` gained `base_link`.
- **Findings 2 & 4 (docs, maintainer):** the sensor `mount:` field (a `[x, y, z]` list, metres,
  relative to the link) is under-documented in the robot-spec surface, and the link-shape sugar's
  origin convention (geometry centred on the link/joint origin) is unstated. Clarified in
  `docs/design/declarative-compiler.md`.
- **Positive:** `parts:` composition, raw parts, sensor mounting, module defaults, and the entire
  `world.yaml` surface worked exactly as documented once the `on:` quoting issue was found.

## 2026-07-26 — Checkpoint B (import + run a real external URDF via `--from-urdf`)

- **Goal:** prove `robotbase create --from-urdf` produces a runnable project, using the
  differential-drive template's own hand-written `warehouse_bot.urdf.xacro` (copied to
  `~/ext-robot.urdf`) as a stand-in for a real external URDF — real, complete, gz-ready, and
  NOT compiler-generated.
- **Import mechanics — correct.** `robotbase create import-bot --from-urdf ~/ext-robot.urdf`
  produced `robot.yaml` with `use: custom`, and placed the URDF at
  `src/import_bot_description/urdf/import_bot.urdf.xacro`, byte-identical to the source
  (confirmed via `diff`). `robotbase up` built cleanly (3.9s) and launched with no build or
  launch errors.
- **Name-mismatch check — not a problem.** The imported URDF's internal
  `<robot name="warehouse_bot">` is left un-renamed to `import_bot` by the importer. This
  caused no observed runtime issue: `ros_gz_sim create -name import_bot` sets the Gazebo model
  name from the launch's `-name` argument (which the generator correctly derives from the
  *project* name), independent of the URDF's internal `<robot name>`. All bridged topics
  (`/cmd_vel`, `/odom`, `/scan`, `/tf`, `/joint_states`) are either literal/explicit topic
  names or built from the project name consistently by the generator, so the mismatch is
  cosmetic, not functional.
- **BLOCKING finding: imported sensors are invisible to the world compiler.** Broken-starter
  `robotbase test stop-before-obstacle` failed as expected, but for the wrong reason:
  `topic_message_counts: {"/scan": 0, ...}` and `minimum_obstacle_distance_metres: null` — the
  LiDAR never produced a single message in a 33.9s run. Swapping in the known-good
  forward-cone-LiDAR controller (verbatim from Task 8b, which passes cleanly against the
  *compiled* differential-drive template) and rebuilding still **failed**: the robot correctly
  waited forever for `/scan` data that never arrived (`distance_travelled_metres: ~0`,
  `required_topic_messages` still 0/5 expected). This is not a controller bug — the world
  itself cannot deliver sensor data to an imported custom URDF.
  - **Root cause:** `robotbase/generator.py`'s `_compile_specs()` skips URDF/sensor-fragment
    compilation entirely for `use: custom` robots (correct — it must not clobber the verbatim
    import) but as a side effect leaves `world_systems = []`, which is passed straight into
    `compile_world(..., robot_systems=world_systems)`. The world SDF compiler only emits the
    `gz-sim-sensors-system` (+`<render_engine>ogre2</render_engine>`), `gz-sim-imu-system`, and
    `gz-sim-contact-system` plugins when a robot's declared `sensors:` list calls for them
    (see `robotbase/robotspec/sensors.py`). A `--from-urdf` import always writes
    `sensors: []` to `robot.yaml` (sensors embedded in an opaque custom URDF are never parsed
    out), so none of those world systems are ever requested — even though `~/ext-robot.urdf`
    itself declares a `gpu_lidar`, an `imu`, and a `contact` sensor via its own `<gazebo>`
    blocks that need exactly those systems to function. Confirmed by diffing the compiled
    `warehouse.sdf` (only Physics/UserCommands/SceneBroadcaster plugins) against the original
    hand-written `warehouse.sdf` (also has Sensors+ogre2, Imu, Contact plugins).
  - **Recommended fix:** for `use: custom` parts, don't derive `world_systems` from an
    (always-empty) declared sensor list. Either (a) always include the baseline sensor-support
    systems (Sensors+ogre2, Imu, Contact) in the compiled world SDF whenever any part is
    `use: custom` — safe default, unused plugins are harmless — or (b) post-process the
    imported URDF (after xacro expansion) for embedded `<gazebo><sensor type="...">` blocks and
    derive `world_systems` from what's actually declared, for a precise fix. At minimum,
    `--from-urdf` should warn that embedded sensors are not auto-wired into the world.
- **Verdict:** broken starter controller = **FAIL** (as expected, though for the wrong root
  cause — no sensor data rather than no obstacle avoidance). Correct controller = **FAIL**
  (blocked by the missing world systems, not a controller defect). **BLOCKED** — did not
  hand-patch the generated project to force a pass, since the point was to learn what import
  needs; `~/import-bot` and `~/ext-robot.urdf` left in place for inspection.

## 2026-07-26 — Checkpoint B — re-verified after fix

- **Fix under test (commit `b1d6fd6`):** the `--from-urdf` importer now infers sensor types
  from the imported URDF's `<sensor type=...>` tags into `robot.yaml`, and the world compiler
  derives its gz systems from them — closing the gap found in the original Checkpoint B above.
- **Re-ran the same repro:** `robotbase create import-bot --from-urdf ~/ext-robot.urdf` against
  the same `~/ext-robot.urdf` (differential-drive template's `warehouse_bot.urdf.xacro`).
  `robot.yaml` now lists `sensors: [{type: lidar}, {type: imu}, {type: contact}]` (previously
  `sensors: []`), and the compiled `warehouse.sdf` contains the `gz-sim-sensors-system` plugin
  (`grep -c "gz-sim-sensors-system"` → 1, previously 0). `robotbase up` built and launched
  cleanly.
- **`/scan` now flows.** Broken-starter `robotbase test stop-before-obstacle`: **FAILED**, but
  now for the **right** reason — `topic_message_counts: {"/scan": 127, "/odom": 372}` (a real,
  non-zero LiDAR feed, vs. the previous silent `/scan: 0`), with a genuine collision:
  `collision_count: 1`, `contact_count: 1`, `minimum_obstacle_distance_metres: 0.080` (< 0.25
  required), robot never stopped (`final_linear_velocity: 0.30` m/s vs. ≤0.05 required).
- **Correct controller (verbatim forward-cone-LiDAR controller from Task 8b/Checkpoint B)**
  swapped into `src/import_bot/import_bot/controller.py`, workspace rebuilt (`robotbase build`,
  3.5s, passed), scenario rerun — **PASSED**: `collision_count: 0`, `contact_count: 0`,
  `minimum_obstacle_distance_metres: 0.352` (≥0.25), `final_linear_velocity: 0.0012` m/s
  (≤0.05, robot_stopped), `topic_message_counts: {"/scan": 133, "/odom": 391}`, all 5
  assertions green.
- **Verdict:** broken starter = **FAIL** (correct root cause this time — real collision from a
  live `/scan` feed, not missing sensor data). Correct controller = **PASS** (0 collisions,
  clearance 0.352m, robot stopped). **Import-time sensor inference is confirmed fixed** — an
  imported custom URDF's sensors now drive the compiled world's gz systems end-to-end.
- **Note:** hit an unrelated environment snag mid-run — a stale container mount namespace
  (`docker compose exec` refused with "possible container breakout detected") after the prior
  Checkpoint B session's container was left running; `docker compose down && docker compose up
  -d` recreated it cleanly. Not a compiler defect, just a leftover container from the earlier
  BLOCKED run.
- Cleanup: `~/import-bot` and `~/ext-robot.urdf` removed after verification.

## 2026-07-26 — Checkpoint C (cold-author a multi-sensor robot, docs only)

A fresh agent, docs only, authored a differential-drive robot with a lidar on a mast, an RGB
camera on the base front, and a depth camera on a separate boom — three sensors on three links.
**Compiled first try, zero errors; all three sensors landed on the intended links.** The
Checkpoint-A `on:` fix held (unquoted `on: mast` worked), and attaching a sensor to a
self-defined raw-part link was as easy as to `base_link`. Findings (all doc-only, minor):

- **Finding 1 (fixed):** the sensor `type` value `depth` was not in any authoritative list — only
  a prose aside in the Phasing section — so it read as a coin-flip against the gz-idiomatic
  `depth_camera`. **Fix:** added an authoritative **Sensor `type:` values** table to
  `docs/design/declarative-compiler.md` (type → topics → gz system, and the explicit note that
  `depth` is the token, not `depth_camera`).
- **Finding 2 (fixed):** the "sensible per-type default mount" was only exemplified for lidar.
  The new table + the existing default-mount note now cover every type.
- **Finding 3 (not a defect):** this run compiled clean, so the validation-error UX
  (missing-mount / orphan / name-clash) went unexercised here — already covered by unit tests.
- **Positives:** compiler defaults (auto-inertia, wheel joints, diff-drive plugin, gz sensor
  blocks) all rendered with no nudging; the "not finicky" claim held for a 3-sensor, 2-raw-part
  composition.
