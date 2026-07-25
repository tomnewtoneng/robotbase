# Robotbase Scenario Format — v1

This document specifies the declarative formats Robotbase uses: the **project manifest**,
the **scenario**, and the **scenario result**. They are deliberately decoupled from the
Robotbase implementation — any tool can read or write them. This is the contract; the
runtime is one implementation of it.

**Version:** 1. Every manifest and scenario declares `version: 1`. Breaking changes bump
the version; additive fields do not.

---

## 1. Project manifest (`robotbase.yaml`)

Describes a project so tooling can build, launch, and test it without hardcoding.

```yaml
version: 1

project:
  name: warehouse-bot            # kebab-case project identifier

runtime:
  ros_distribution: jazzy        # supported: jazzy
  simulator: gazebo-harmonic     # supported: gazebo-harmonic
  architecture: amd64

workspace:
  path: /workspace
  source_directory: src
  build_command: colcon build --symlink-install

robot:
  template: differential-drive
  name: warehouse_bot            # the spawned model name (snake_case)
  namespace: ""

sensors:
  lidar:    {enabled: true, topic: /scan}
  contact:  {enabled: true, topic: /bumper}
  odometry: {enabled: true, topic: /odom}

control:
  velocity_topic: /cmd_vel

launch:
  package: warehouse_bot_bringup # ROS package containing the launch file
  file: simulation.launch.py

simulation:
  world: src/warehouse_bot_description/worlds/warehouse.sdf
  world_name: warehouse          # the SDF <world name="...">
  headless: true

recording:
  enabled: true                  # record each run to an MCAP episode (default true)
  topics: []                     # [] = all topics; or an allow-list
  exclude: []                    # deny-list, e.g. [/image] to skip heavy camera frames

scenarios:
  directory: simulation/scenarios

agent:
  mcp: {enabled: true, port: 4381}
```

**Required, validated fields:** `version` (must be 1), `project.name`,
`runtime.ros_distribution` (must be a supported distro), `runtime.simulator` (must be a
supported simulator), `launch.package`, `launch.file`, `scenarios.directory`,
`agent.mcp.port`. `simulation.world_name` and `robot.name` default to `warehouse` /
`warehouse_bot` if omitted. Two optional `runtime` fields adapt the harness to non-mobile
robots: `ready_topics` (list — the topics whose presence means the sim is up; default
`[/scan, /odom]`, e.g. `[/joint_states]` for an arm) and `fixed_base` (bool — skip setting a
base pose for a bolted-down robot like an arm). The optional `recording` block controls
episode capture (§3.2); omitted, it defaults to recording all topics. Validation errors must
be clear and actionable.

---

## 2. Scenario

A scenario is a YAML file in the manifest's `scenarios.directory`. Its filename stem is the
scenario's name (`stop-before-obstacle.yaml` → `stop-before-obstacle`).

```yaml
version: 1
name: stop-before-obstacle
description: Confirm the robot stops before colliding with a static box.
timeout_seconds: 30

setup:
  reset_world: true
  robot:
    pose: {x: 0.0, y: 0.0, yaw: 0.0}
  obstacles:
    - id: obstacle_1
      type: box
      pose: {x: 2.0, y: 0.0, z: 0.25}
      size: {x: 0.5, y: 1.0, z: 0.5}

actions:
  - {type: wait_for_topic, topic: /scan, timeout_seconds: 5}
  - {type: run_node, package: warehouse_bot, executable: obstacle_controller}
  - {type: wait, duration_seconds: 10}

assertions:
  - {type: no_collision}
  - {type: minimum_obstacle_distance, minimum_metres: 0.25}
  - {type: robot_stopped, linear_velocity_tolerance: 0.05, angular_velocity_tolerance: 0.05}
  - {type: required_topic_messages, topic: /scan, minimum_count: 5}
```

### 2.1 `setup`
- `reset_world` (bool) — start from a pristine simulation.
- `robot.pose` — starting pose `{x, y, z, yaw}` (metres / radians; `z` defaults sensibly).
- `obstacles[]` — each has `id`, `type` (`box`), `pose {x,y,z}`, `size {x,y,z}`.

### 2.2 `actions` (ordered)
| type | fields | meaning |
|---|---|---|
| `wait` | `duration_seconds` | pause |
| `wait_for_topic` | `topic`, `timeout_seconds` | block until a topic is present |
| `run_node` | `package`, `executable` | start a ROS node (e.g. the controller) |

An implementation MAY support more action types; unknown types SHOULD be ignored or
reported, not fatal.

### 2.3 `assertions`
| type | fields | passes when |
|---|---|---|
| `no_contact` | — | the contact/bumper sensor never fired (ground-truth collision) |
| `no_collision` | — | no collision occurred during the run (LiDAR-proximity heuristic) |
| `minimum_obstacle_distance` | `minimum_metres` | closest approach to any obstacle ≥ value |
| `robot_stopped` | `linear_velocity_tolerance`, `angular_velocity_tolerance` | final velocity within tolerances |
| `required_topic_messages` | `topic`, `minimum_count` | at least N messages seen on the topic |
| `robot_moved_minimum_distance` | `minimum_distance_metres` | displacement from start ≥ value |
| `minimum_path_length` | `minimum_metres` | total path travelled ≥ value (e.g. proves a detour) |
| `robot_reached_pose` | `target_x`, `target_y`, `position_tolerance_metres` | final position within tolerance of the target |
| `joint_positions_reached` | `joint_targets` (map name→radians), `joint_tolerance` | every named joint within tolerance of its target (arm) |

Unknown assertion types MUST fail (a scenario cannot silently pass on an unrecognized
check).

### 2.4 `randomize` (optional — domain randomization)
Turns a scenario from a single test into an **eval**. Declares ± jitter ranges applied to
the setup on each randomized trial, so a controller tuned to one exact configuration doesn't
look solved:

```yaml
randomize:
  robot_pose: {x: 0.1, y: 0.0, yaw: 0.05}   # ± metres / radians on the start pose
  obstacles:  {x: 0.3, y: 0.3}              # ± metres applied to each obstacle's x/y
```

`robotbase test <name> --trials N [--seed S]` runs N trials — trial 0 is the nominal
(unperturbed) setup, the rest sample within these ranges — and reports a **robustness**
fraction (`passed / trials`). `robotbase test --all` runs every scenario as a **suite** and
aggregates (`fully_passed`, `mean_robustness`), and diffs against the previous suite run to
flag behavioral **regressions**. Trials/suites drive any backend through the same runner, so
they are sim-agnostic.

---

## 3. Scenario result (JSON)

Every run produces a JSON-compatible result, written to
`.robotbase/runs/<run-id>/result.json`.

```json
{
  "run_id": "run_01jabc...",
  "scenario": "stop-before-obstacle",
  "passed": false,
  "started_at": "2026-07-22T04:10:00+00:00",
  "finished_at": "2026-07-22T04:10:13+00:00",
  "duration_seconds": 13.0,
  "metrics": {
    "collision_count": 1,
    "minimum_obstacle_distance_metres": 0.08,
    "distance_travelled_metres": 2.1,
    "final_linear_velocity": 0.3,
    "final_angular_velocity": 0.0,
    "topic_message_counts": {"/scan": 95}
  },
  "assertions": [
    {"type": "no_collision", "passed": false, "expected": 0, "actual": 1, "detail": ""}
  ],
  "diagnostics": []
}
```

- `passed` is the conjunction of all assertions (an empty assertion list is not a pass).
- Each assertion result carries `type`, `passed`, and optional `expected` / `actual` /
  `detail` for diagnosis.

### 3.1 Metric semantics (normative)
Metrics are measured across the **whole episode**, not a trailing window:
- `contact_count` — number of distinct contact episodes reported by the robot's
  contact/bumper sensor (ground-truth collisions from physics; `0` if it never fired).
- `collision_count` — `1` if the minimum LiDAR range dropped below the collision threshold
  (0.12 m) at any point during the run, else `0` (a proximity heuristic, not ground truth —
  prefer `contact_count`/`no_contact` where a contact sensor is present).
- `minimum_obstacle_distance_metres` — the closest the robot came to any obstacle over the
  run (`null` if no LiDAR data).
- `distance_travelled_metres` — straight-line displacement from the start pose (not path
  length; see `path_length_metres`).
- `path_length_metres` — total distance travelled along the path (odometry integrated over
  the run, with a small deadband against jitter). Exceeds `distance_travelled_metres`
  whenever the robot turns or detours. Note: it is wheel-odometry based, so it over-reads
  while the robot is stalled against something and its wheels slip — pair it with
  `no_contact` when using it as evidence of a real detour.
- `final_x` / `final_y` / `final_yaw` — the robot's final pose from the last odometry sample
  (metres / radians); the basis for `robot_reached_pose`.
- `final_linear_velocity` / `final_angular_velocity` — from the last odometry sample.
- `joint_positions` — final angle (radians) of each actuated joint, keyed by name (arm
  robots); the basis for `joint_positions_reached`.
- `topic_message_counts` — message counts observed per topic.

Which metrics a run reports depends on the robot: mobile robots populate the pose/collision
fields, an arm populates `joint_positions`. Unused fields keep their defaults.

### 3.2 Episode artifacts
Alongside `result.json`, a run directory `.robotbase/runs/<run-id>/` contains the recorded
episode (unless `recording.enabled` is false):

- **`episode.mcap`** — the full topic trace for the episode in [MCAP](https://mcap.dev),
  recorded with sim time. Openable directly in Foxglove/Rerun; the same file downstream
  robot-data tools ingest. This is the evidence behind the assertions.
- **`episode.json`** — a self-describing sidecar bundling `version`, the `run_id`, the
  `scenario_spec`, the full `result`, the `recording` metadata (`mcap` filename, `storage`,
  recorded `topics`), and a coarse `events` list (e.g. `collision`). It makes the run
  directory interpretable on its own, independent of the tool that produced it.

`episode.json` is also embedded into `episode.mcap` as an attachment (media type
`application/json`), so the single file is self-describing when shipped on its own. The
layout is versioned with this document. An implementation
SHOULD offer bounded queries over the episode (Robotbase provides `robotbase episode
summary | events | query`, and the matching MCP tools) so an agent can read *why* a run
failed — a downsampled slice of a topic around a timestamp — without a raw dump. `episode
events` derives a timeline from the trace: `collision` (contact/bumper ground truth, or a
LiDAR-proximity fallback), `closest_approach` (nearest obstacle distance and the robot's
position at that instant), and `stopped` (when the robot came to rest). Old runs are pruned
with `robotbase clean`.

---

## 4. Design principles

- **Evidence over confidence.** A behaviour is verified only by running the scenario and
  reading the assertions — never by inspecting source.
- **Machine-readable everything.** State and results are structured, bounded data, so an
  agent can consume them without scraping terminals.
- **Deterministic.** Each run starts from a pristine simulation; identical inputs yield
  identical verdicts.
- **Opinionated over universal.** v1 supports one configuration extremely well; the format
  is designed to grow (new action/assertion types, robots, simulators) without breaking.
