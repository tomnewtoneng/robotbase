# Robotbase — Roadmap

Where the project is going. See `VISION.md` for the why and the strategic layers; this doc
is the concrete build path, with an emphasis on **widening** (more robots, sensors,
scenarios). Priorities are a recommendation, not a contract.

## Status (2026-07)

**Alpha, MVP proven.** The full local loop works end-to-end (create → build → launch → run
scenarios → agent fixes the controller). One robot (differential drive), two scenarios,
22 unit tests, code-reviewed core, MIT-licensed, on GitHub. The scenario/manifest formats
are a versioned open spec (`SCENARIO-FORMAT.md`).

## Now — distribution (Track A, mostly human-driven)

The binding constraint is that the proven tool lives in a vacuum. Highest leverage:

- **Publish for real:** a PyPI package + a public `robotbase-runtime` Docker image so
  `pip install robotbase` works for a stranger. (Prep is code/CI; the publish needs the
  owner's tokens.)
- **The content moment:** record the "agent teaches itself obstacle avoidance" demo.
  `PROOF.md` is the written artifact.
- **Repo polish:** GitHub description/topics, a short demo GIF, CONTRIBUTING.

## Widening — robots

Today there is one robot template (differential drive). Widening means a **template
library** and a generator that can pick from it.

- **Multi-template generator:** `robotbase create <name> --template <type>`; templates
  registered and discoverable. (Requires factoring the current template into a named entry.)
- **Second mobile base:** Ackermann/car-like steering — exercises a different drive plugin
  and control model while reusing the world/sensor stack.
- **Manipulator (arm):** a fixed robotic arm — introduces joint-space control, a very
  different scenario family (reach a joint configuration, reach a cartesian pose, later
  grasp), and validates that the format generalizes beyond mobile robots.
- **Later:** quadruped, quadrotor/drone. Higher complexity; good "wow" once the framework
  is proven across mobile + arm.

Each robot template = URDF/xacro + world + launch + an intentionally-imperfect starter
controller + scenarios + a manifest `robot.template`/`robot.name`.

## Widening — sensors

Today: LiDAR (`/scan`) + odometry (`/odom`). Each new sensor = a URDF sensor + Gazebo
plugin + ROS–gz bridge + a manifest `sensors` entry, and often new metrics/assertions.

- **Contact / bumper sensor (high priority):** gives *true* collision detection and retires
  the current min-LiDAR-range heuristic — a correctness win, and it enables an honest
  `collision` assertion independent of range.
- **Camera (RGB):** publishes `/image`. Unlocks **vision-based scenarios** — the agent
  processes images, not just ranges. Strategically important (modern/Physical-AI-relevant)
  and a strong demo. Needs image-aware inspection tooling (bounded thumbnails/summaries, not
  raw frames, to keep agent output structured).
- **Depth camera:** `/depth` / point cloud — 3D perception scenarios.
- **IMU:** `/imu` — orientation/acceleration; supports tip-over and stability assertions.

## Widening — scenarios & the assertion/metric vocabulary

New scenarios usually need new **assertion types** and **metrics**. Extending this
vocabulary (in `assertions.py` + the metrics collector, and documented in
`SCENARIO-FORMAT.md`) is itself the deepening work.

- **`reach-goal`:** robot reaches a target pose. Needs a `robot_reached_pose` assertion and
  a final-position metric (x, y, yaw) + distance-to-goal.
- **`turn-around-obstacle`:** navigate past an obstacle. Needs a "progressed past x" /
  waypoint assertion and true path length (vs. the current displacement-from-origin).
- **Completion-time / timeout assertions:** enforce `scenario.timeout_seconds` (today
  advisory) and add `max_completion_time`.
- **Manipulation assertions** (with the arm): joint reached, end-effector at pose, object
  grasped.
- **Path-length metric:** integrate odometry over the run (today `distance_travelled` is
  displacement from origin — misleading for turning paths).

## Optional visualization (human view)

An **optional, lightweight** way for humans to see the simulation, without ever making a
GUI a requirement (headless-first stays the default and the guarantee for the agent loop).
Full design in `design/optional-visualization.md`.

## Hardening backlog

- Retire the LiDAR collision heuristic in favor of the contact sensor (see above).
- Enforce `scenario.timeout_seconds`.
- Path-length vs. displacement metric.
- Verify non-Windows hosts (Linux, macOS/Docker Desktop); add CI.
- De-duplicate `robotbase/template` vs. the `warehouse-bot` reference (generate one from the
  other, or make the reference a generated example).

## Sim-agnostic (strategic, Layer 0)

The runtime seam is already transport-agnostic. Realizing sim-agnosticism means a **sim
adapter interface** and a second backend (MuJoCo is the lightest first candidate; Isaac the
most strategic). This is what turns "layer on top of Gazebo" into "layer on top of *any*
sim" — the standard-owning position.

## Ecosystem layers (later — see VISION.md)

The hub (scenario/benchmark registry), cloud CI (behavioral regression testing), and the
eval/data layers come once the format has adoption. Design for their seams now (open
format, transport-agnostic runtime, machine-readable results — already done); build them
when there is demand.

## Recommended sequence

1. **Distribution** (publish + content) — get it out of the vacuum.
2. **Contact sensor** — true collisions; a cheap correctness + credibility win.
3. **Camera + a vision scenario** — the capability that most widens appeal and demo power.
4. **`reach-goal` / `turn-around` + the assertion/metric vocabulary** — richer behaviors.
5. **Multi-template generator + a second robot (arm)** — prove the format generalizes.
6. **A second sim adapter** — begin owning "any sim," not just Gazebo.
7. **Ecosystem layers** — when adoption justifies them.
