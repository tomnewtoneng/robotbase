# Robotbase — Roadmap

Where the project is going. See `VISION.md` for the why and the strategic layers; this doc
is the concrete build path, with an emphasis on **widening** (more robots, sensors,
scenarios). Priorities are a recommendation, not a contract.

## Status (2026-07)

**Alpha, MVP proven.** The full local loop works end-to-end (create → build → launch → run
scenarios → agent fixes the controller). A multi-template library with two robot templates
(`differential-drive`, `camera-bot`) reachable via `robotbase create --template`, two
scenarios, 22 unit tests, code-reviewed core, MIT-licensed, on GitHub. The scenario/manifest
formats are a versioned open spec (`SCENARIO-FORMAT.md`).

## Now — distribution (Track A, mostly human-driven)

The binding constraint is that the proven tool lives in a vacuum. Highest leverage:

- **Publish for real:** a PyPI package + a public `robotbase-runtime` Docker image so
  `pip install robotbase` works for a stranger. (Prep is code/CI; the publish needs the
  owner's tokens.)
- **The content moment:** record the "agent teaches itself obstacle avoidance" demo.
  `PROOF.md` is the written artifact.
- **Repo polish:** GitHub description/topics, a short demo GIF, CONTRIBUTING.

## Widening — robots

A **template library** with a generator that picks from it already exists (`robotbase
templates` / `create --template`), with `differential-drive` and `camera-bot` shipped.
Widening means more entries in it.

- **Multi-template generator:** `robotbase create <name> --template <type>` — **done**;
  templates registered and discoverable via `robotbase templates`.
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

- **Contact / bumper sensor:** **shipped** in both templates — a physics contact sensor on
  the base body, bridged to `/bumper`, giving *ground-truth* collisions (`contact_count`
  metric + `no_contact` assertion) independent of the LiDAR-proximity heuristic. Episode
  `events` now use it as the authoritative collision signal.
- **Camera (RGB):** publishes `/image` — **shipped** in the `camera-bot` template (320×240
  rgb8 @ 10 Hz, verified rendering headless under llvmpipe). Still open: **vision-based
  scenarios/assertions** (the agent processing images, not just ranges) and image-aware
  inspection tooling (bounded thumbnails/summaries, not raw frames — see the episode-query
  layer in `design/mcap-recording.md`).
- **Depth camera:** `/depth` / point cloud — 3D perception scenarios.
- **IMU:** `/imu` — orientation/acceleration; supports tip-over and stability assertions.

## Widening — scenarios & the assertion/metric vocabulary

New scenarios usually need new **assertion types** and **metrics**. Extending this
vocabulary (in `assertions.py` + the metrics collector, and documented in
`SCENARIO-FORMAT.md`) is itself the deepening work.

- **`reach-goal`:** **shipped** — robot drives to a target pose. Added the
  `robot_reached_pose` assertion + `final_x/y/yaw` metrics and an off-axis `reach-goal`
  example (ships failing: the straight-driving starter misses it). Still open: `turn-around`
  and a true path-length metric.
- **`turn-around-obstacle`:** navigate past an obstacle. Needs a "progressed past x" /
  waypoint assertion and true path length (vs. the current displacement-from-origin).
- **Completion-time / timeout assertions:** enforce `scenario.timeout_seconds` (today
  advisory) and add `max_completion_time`.
- **Manipulation assertions** (with the arm): joint reached, end-effector at pose, object
  grasped.
- **Path-length metric:** integrate odometry over the run (today `distance_travelled` is
  displacement from origin — misleading for turning paths).

## Widening — the episode record (the data layer)

The highest-leverage widening, and the one that reframes the rest: today a run's rich
signal (the full topic time-series) is computed and discarded — the agent gets a pass/fail
light, not a debuggable trace. **Record every run as a standard MCAP episode**, then give
agents bounded verbs to interrogate it. Full design in `design/mcap-recording.md`.

- **Record `episode.mcap` per run** (Phase 1): all bridged topics for the episode, landing
  in `.robotbase/runs/<run_id>/`, self-described by a sidecar `episode.json` (scenario +
  result + event timeline). Foxglove opens it directly; the file is ecosystem-portable
  (Foxglove/Rerun/Alloy all read MCAP).
- **Episode query verbs** (Phase 2): `episode summary` / `events` / `query --topic --around`
  as CLI + MCP tools, executed container-side, returning **bounded, downsampled** JSON —
  the "show me `/scan` and `/cmd_vel` in the second before impact" capability. This is what
  makes the data *interpretable by agents* rather than just stored.
- **Self-contained + retention** (Phase 3): MCAP attachments/annotations, image
  thumbnailing, `robotbase clean`. Add an "Episode & Result artifacts" section to
  `SCENARIO-FORMAT.md` (the format, versioned).

Why this over more robots: the sensors/scenarios below are *composable primitives* the
agent assembles; the episode record is the **substrate they all write to and read from**,
and it's the un-clonable data asset the eval/hub/data layers (VISION Layers 1–3) are built
on. Build the substrate before widening the vocabulary that feeds it.

## Optional visualization (human view)

An **optional, lightweight** way for humans to see the simulation, without ever making a
GUI a requirement (headless-first stays the default and the guarantee for the agent loop).
Full design in `design/optional-visualization.md`.

## Hardening backlog

- The contact sensor now provides ground truth (`no_contact`); consider deprecating the
  LiDAR `no_collision` heuristic once scenarios have migrated.
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

## The framing that orders everything below

A recurring design test: **are we doing the agent's job, or building the primitives it
composes?** The controller is always the agent's to write; a specific scenario is the
*user's* spec of what they want. What Robotbase ships is the **vocabulary** — sensors,
assertion types, metrics, world primitives — and the **episode record** they all write to.
When we ship a scenario (`reach-goal`) it is an *example*, never the product. We build the
SQL; the agent writes the query. This is why the episode/data layer leads: it's the
substrate every primitive feeds, and the thing an agent needs to interpret its own results.

## Recommended sequence

1. **Distribution** (publish + content) — get it out of the vacuum.
2. ~~**Episode record — Phase 1 (MCAP recording)**~~ — **done**; every run is recorded to a
   portable `episode.mcap` + sidecar. See `design/mcap-recording.md`.
3. ~~**Episode record — Phase 2 (query verbs)**~~ — **done**; `robotbase episode
   summary | events | query` (+ MCP tools) make the data interpretable by agents.
4. ~~**Contact sensor**~~ — **done**; ground-truth collisions via `/bumper` (`contact_count`
   + `no_contact`), on both templates.
5. **`reach-goal`** — **done** (`robot_reached_pose` + `final_x/y/yaw`, off-axis example);
   `turn-around` + a path-length metric still open.
6. **Multi-template generator + a second robot (arm)** — prove the format generalizes.
   (The generator + a `camera-bot` template already exist; the arm is the next stretch.)
7. **A second sim adapter** — begin owning "any sim," not just Gazebo.
8. **Ecosystem layers** — when adoption justifies them.
