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
