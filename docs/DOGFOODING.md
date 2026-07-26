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
