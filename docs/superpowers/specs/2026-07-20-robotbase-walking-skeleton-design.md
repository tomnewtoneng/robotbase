# Robotbase — Walking-Skeleton Design

> Status: approved for implementation planning
> Date: 2026-07-20
> Scope: the **first sub-project** of Robotbase, not all of Robotbase.
> Parent spec: `projects/Robotbase/mvp.md.txt` (the full MVP vision)

## 1. Positioning

Robotbase is the **batteries-included developer-experience layer for agent-driven
robotics**. It takes the headache out of setting up ROS 2 + Gazebo and gives coding
agents structured access (via MCP and a CLI) to build, launch, inspect, operate, and
test a robotics application.

The guiding analogy is **"Supabase for ROS 2" in *feeling*, not infrastructure**:
setup pain vanishes, the primitives are good, and it works instantly — the same way
Supabase removes the headache of standing up a database. Robotbase is **local-first**.
There is no hosting, no accounts, and no cloud dependency in the core.

**Business model:** open-core. The local engine is open source (the wedge and the
credibility play). Monetisation comes *later* and *optionally* — hosted runners,
shared scenario libraries, pull-request simulation checks — layered behind the same
tool contract. This sub-project builds none of that, but must not foreclose it.

## 2. Why this sub-project exists

The full MVP (`mvp.md.txt`) specifies six components across six build phases and does
not run its own thesis-proving demo until the final phase. That front-loads the
hardest, most uncertain work — **deterministic headless Gazebo Harmonic with
world-reset, obstacle-spawn, and collision measurement** — while the payoff signal
comes last.

This sub-project inverts that risk. It builds the **thinnest vertical slice** that
runs the canonical demo end-to-end, so we prove or kill the core bet with the fewest
moving parts.

**The thesis to prove:**

> A declarative local ROS environment plus structured agent tools makes coding agents
> materially better at robotics development.

**Success for this sub-project (single criterion):** a coding agent (Claude Code,
running in WSL2) is pointed at one hand-built project, given the canonical prompt, and
autonomously closes the loop — build → run scenario → read structured failure → fix the
controller → rerun → pass — without the human operating Gazebo or copying terminal
output into the agent.

Everything the full MVP describes beyond this slice is **mechanical to add once the
engine is proven**, and is explicitly deferred (§8).

## 3. Development environment

Primary dev machine is a **Windows 11 workstation**; an old Ubuntu laptop is the
fallback. The Docker-first architecture absorbs the OS difference: ROS 2 Jazzy and
Gazebo Harmonic are Linux-only and run **in containers**, identical across hosts.

Committed setup:

- **Docker Desktop with the WSL2 backend** on Windows 11 is the container engine.
  (WSL2, not WSL1 — Docker Desktop requires the real Linux kernel WSL2 provides.)
- **The dev loop lives inside WSL2 (Ubuntu 24.04)** — Claude Code, the eventual
  `robotbase` CLI, and all project files. Ubuntu 24.04 is chosen because it is ROS 2
  Jazzy's target distro, keeping a clean bare-metal fallback path.
- **Project files stay on the WSL2 filesystem** (`~/robotbase/...`), never on the
  Windows `/mnt/c/...` mount — cross-filesystem Docker mounts are slow enough to make
  builds unusable.
- **Gazebo runs headless with Mesa llvmpipe software rendering** inside the container —
  no host-GPU dependency, deterministic, portable, and consistent with the
  "headless-first" principle. Slower sensor simulation is an acceptable trade for a
  diff-drive + LiDAR toy world.

Environment status as of writing: WSL2 set as default; Ubuntu 24.04 installing; Docker
Desktop install in progress. WSL Integration for the Ubuntu-24.04 distro must be
enabled in Docker Desktop settings before the spike.

## 4. Phase 0 — Rendering spike (throwaway, ~1 day)

The single riskiest assumption on this hardware. **Nothing else is built until this
passes.**

A throwaway Docker container that:

1. Boots Gazebo Harmonic **headless** with llvmpipe software rendering.
2. Loads a diff-drive robot and a static box.
3. Spins up a `gpu_lidar` sensor.
4. Confirms `/scan` publishes **real, non-degenerate range data** into ROS 2 Jazzy.

**Green light:** the whole project is viable on the Windows/WSL2 workstation → proceed
to the slice.

**Red light (ogre2-on-llvmpipe unreliable):** move the dev box to the Ubuntu laptop and
reassess a GPU rendering path before proceeding. This is a known flaky spot in headless
CI, so a red light is a plausible outcome, not a failure of the design.

## 5. The slice — one hand-built `warehouse-bot`

Hand-built, **not** generated. No template engine, no `robotbase create`. A single
project checked into the repo that we operate directly.

Decomposed into four units, each with one clear purpose and a well-defined interface:

### 5.1 Sim unit
- Diff-drive URDF (two driven wheels + caster) and a tiny warehouse world: ground
  plane, walls, one goal location, and space for a spawned box obstacle.
- Headless and deterministic; loads quickly.
- Publishes `/scan`, `/odom`, `/cmd_vel`, `/tf`, `/joint_states`.
- Ships the **intentionally-broken starter controller** (§15.2 of the parent spec):
  compiles and launches, drives forward, does not react correctly to obstacles.

### 5.2 Scenario runner unit
- Parses one scenario YAML (schema per §13 of the parent spec).
- Setup: reset world, set robot pose, spawn a box obstacle.
- Actions: wait, wait-for-topic, run node, send velocity.
- Evaluates a **minimal assertion set**: `no_collision`, `robot_stopped`,
  `minimum_obstacle_distance`, `required_topic_messages`.
- Emits the structured JSON result (schema per §14), written to
  `.robotbase/runs/<run-id>/result.json`.
- **Only two scenarios** ship: `drive-forward` and `stop-before-obstacle`.

### 5.3 Runtime module
- Plain Python module (not yet a standalone HTTP service) that performs build, launch,
  stop, reset, ROS inspection, and scenario execution.
- This is §11's runtime API **collapsed into an in-process module**, callable directly
  by the MCP server. It is split into a networked service later only if a real need
  appears.
- **Interface is transport-agnostic and clean** — this is the open-core seam. A hosted
  runner could later sit behind the same interface without changing the tool contract.

### 5.4 MCP server unit
- Exposes only the loop-closing tools:
  `project_describe`, `workspace_build`, `simulation_launch`, `simulation_stop`,
  `simulation_reset`, `ros_list_topics`, `ros_inspect_topic`, `scenario_list`,
  `scenario_run`, `scenario_get_result`.
- Localhost only (stdio or HTTP via the Python MCP SDK). Thin wrapper over the runtime
  module.
- Returns **structured, size-bounded** responses — never thousands of lines of raw log.
- Ships a hand-written `AGENTS.md` (§18 of the parent spec) for this one project.

## 6. Data flow (the proof loop)

```
Claude Code (WSL2)
  → MCP: project_describe / workspace_build
  → MCP: scenario_run("stop-before-obstacle")
      → runtime module: reset sim, spawn box, run controller, evaluate assertions
      → structured JSON result (failed: collision)
  → MCP: scenario_get_result  → agent reads failed assertions
  → agent edits obstacle_controller.py (its normal file tools, not an MCP tool)
  → MCP: workspace_build → scenario_run(...)  → repeat until passed
```

The agent modifies source with its own coding tools; Robotbase tools cover **runtime
interaction only**. Running this loop to a green `stop-before-obstacle` is the
acceptance test for the sub-project.

## 7. Stack

- **Python throughout** for the slice: runtime module, scenario runner, and MCP server
  (Python MCP SDK). One language, one virtualenv, least friction to prove the loop.
- Pydantic for manifest/scenario schema and result models.
- ROS 2 Jazzy Python client libraries; Gazebo Harmonic via the ROS–Gazebo bridge and
  `gz` transport/services for reset and spawn.
- The TypeScript-vs-Go CLI decision is **deferred with the CLI itself**.

## 8. Explicitly deferred

Built only *after* the slice proves the loop:

- `robotbase create` and the project template generator
- The CLI wrapper (`up`, `down`, `status`, `build`, `launch`, `stop`, `logs`, `doctor`)
- The remaining scenarios (`turn-around-obstacle`, `reach-goal`)
- Foxglove bridge and the local dashboard
- Codex agent configuration
- The standalone HTTP runtime service (kept in-process until proven necessary)
- Packaging and distribution
- Anything hosted, multi-user, or cloud (the paid open-core layer)

## 9. Open risks (named, not solved)

1. **Headless rendering reliability** — ogre2 on llvmpipe is the classic headless-CI
   flaky spot. Phase 0 answers this directly before any other work.
2. **Deterministic sim reset + obstacle spawn** — resetting world/robot state and
   spawning/removing obstacles reliably via `gz` services is the second-hardest thing
   after rendering. If per-run process teardown/relaunch proves more deterministic than
   in-place reset, prefer determinism over speed.
3. **Determinism generally** — scenario pass/fail must be stable across runs;
   flakiness would undermine the "evidence over agent confidence" principle.

## 10. Acceptance criteria for this sub-project

1. Phase 0 spike shows `/scan` publishing real ranges headless on the dev machine
   (or the fallback machine, with the platform decision recorded).
2. The hand-built `warehouse-bot` launches headless and is controllable via `/cmd_vel`.
3. The scenario runner runs `drive-forward` and `stop-before-obstacle` and produces
   deterministic structured JSON results.
4. The MCP server exposes the loop-closing tools and returns structured responses.
5. Claude Code, given the canonical prompt, autonomously turns a failing
   `stop-before-obstacle` into a passing one without manual Gazebo operation or
   terminal copy-paste.
6. All source and compute remain on the local machine.

Meeting these validates the thesis and unlocks the deferred, mechanical work of turning
the slice into the full Robotbase MVP.
