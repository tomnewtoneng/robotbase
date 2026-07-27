# Robotbase — Ideas backlog

Where Robotbase could go beyond the current core (CLI + MCP, three robot templates, the
scenario/assertion/metric vocabulary, MCAP episode recording/query/attachments, `describe`,
and a proven sim-agnostic adapter seam). Organized by theme; ranked at the bottom.

**North star — "Terraform for robots"** (`VISION.md`): fully declarative robotics — **YAML
compiles into robots, sensors, worlds, runs (scenarios), and tests (evals)** — reproducibly,
and **portable from sim to real**. Everything the user/agent authors is config; the compiler
and backends materialise it. The crown jewels along the way are the agent loop and the evals
layer; the moat is accumulated behavioral eval data a competitor can't clone. Bias toward
whatever pushes more of the stack into clean, compilable config that ports across backends.

Status key: 🔲 not started · 🚧 in progress · ✅ done.

## ★ Priority roadmap (CURRENT — 2026-07-27) — read [`STRATEGY.md`](STRATEGY.md) first

This ordering (from the strategic cross-reference in `STRATEGY.md`) **supersedes the thematic
ranking at the bottom of this file**. Principle: **validation-first, then depth on the compiler
core — not more breadth.**

- **P0 — 🚧 Finish RobotBench (the gate).** Prove the core hypothesis (agents materially better
  WITH Robotbase). If it fails, see the kill-criteria in `STRATEGY.md`. *(in progress)*
- **P1 — 🔲 Explainability & traceability** (`robotbase explain`/`trace` + source maps in
  generated files). Highest-leverage new capability; the moat is inspectability.
- **P2 — 🔲 Compile the full runtime** (launch + controller + manifest from a `runtime.yaml`, not
  template-owned). Closes the imported-sensor-not-bridged gap. *(also §G below)*
- **P3 — 🔲 Static physical validation + value provenance** (inertia/mass/COM/TF/joint-limit
  checks; tag measured/imported/inferred/default/estimated). Validation ≥ generation.
- **P4 — 🔲 Lift the IR to a semantic model** — decouple `ir.py` from URDF strings; URDF/SDF/launch
  become pure backends. Deepest moat, biggest refactor — do it *after* P1–P3 and only if the
  thesis validates.
- **P5 — 🔲 Knowledge layer for agents** (packaged Claude Code skill + schema docs + failure-pattern
  tables; borrow the ROS2-skills check scripts). Amplifies the agent-native thesis.
- **Later:** MuJoCo as a first-class backend (unlocked by P4), Studio (§H), import depth, units.
  Breadth (§D robots/sensors) is opportunistic — not the moat.

## A. Turn scenarios into *evals* (the moat)

A scenario today is a pass/fail test. The leap is making it a benchmark.

- ✅ **Scenario suites + aggregate report** — `robotbase test --all` → per-scenario
  robustness + `fully_passed` / `mean_robustness`. "CI for robot behaviors."
- ✅ **Behavioral regression tracking** — each `--all` run is diffed against the previous
  (stored in `.robotbase/last-suite.json`), flagging scenarios whose robustness dropped.
- ✅ **Domain randomization** — `robotbase test <name> --trials N [--seed S]` jitters the
  setup (obstacle/start pose, per the scenario's `randomize` block) and reports a
  **robustness** fraction. The biggest lever: a controller tuned to one config no longer
  looks solved. (`stop-before-obstacle` ships with a `randomize` block.)
- 🔲 **Flakiness / determinism check** — run ×N *without* perturbation, report variance.
- 🔲 **Friction / physics randomization** — vary friction/mass, not just poses.

## B. Deepen the agent experience (the DX crown jewel)

"Great human DX = great agent-operability."

- ✅ **Auto-diagnosis of failures** — `robotbase diagnose [run]` (+ MCP `diagnose_run`)
  explains *why* the last run failed in plain language: each failed assertion → the episode
  event (collision, closest-approach with position) → the control behaviour ("still
  commanding vx=0.3 at impact — didn't slow or turn away"). Deterministic/rule-based (no
  LLM/API); an agent can elaborate. Templates' AGENTS.md lead failure-inspection with it.
  *Future:* optional LLM enrichment for free-form narration.
- ✅ **`robotbase doctor`** — checks Docker reachable, compose present, the runtime image
  built, port 8765 free (concurrent-project conflict), whether you're in a project + its
  container is up, and Python deps — each with ok/warn/fail + a fix. CLI + MCP
  (`environment_doctor`). Every gotcha we hit, turned into a check.
- 🔲 **Natural-language scenario authoring** — `robotbase scenario new "circle the obstacle"`
  → drafts the YAML. Zero-barrier authoring.
- 🔲 **Richer inspection** — object-detection summaries over `/image`, replay/step-through.

## C. Own the standard (network effects)

- 🔲 **The hub** — a registry for scenario packs, robot templates, worlds. *npm + Hugging
  Face for robotics.* VISION Layer 1.
- ✅ **RobotBench — benchmark *AI agents* at robot-controller writing** 🌶️ — a versioned task
  set (`robotbase bench --list`), a comparable **scorecard** (`robotbase bench [--agent
  NAME]` → 0–100 score = mean robustness, `solved`/`tasks`, agent-tagged), and the
  agent-benchmark protocol (formalizes the dogfooding). See `docs/ROBOTBENCH.md`. *Next:*
  automated agent dispatch per task; a public leaderboard; cross-robot-class scoring in one
  command.
- 🔲 **Shareable episode viewer** — a web page per episode ("watch my agent solve this").
- 🔲 **Format governance** — publish the scenario/manifest/result format as a spec + JSON
  Schema (SCENARIO-FORMAT.md is the start).

## D. Widen capability (the "can")

- 🚧 More robots: **drone/quadrotor shipped** (`drone` template — a new *aerial* class;
  kinematic velocity control, 3D `/cmd_vel` + `/odom` + IMU, a `reach-position` scenario;
  drove the `final_z` metric + 3D `robot_reached_pose`). Still: quadruped, mobile
  manipulator, Ackermann car.
- 🚧 More sensors: **IMU shipped** (both mobile templates — `/imu`, physics-based) and
  **depth camera shipped** (camera-bot — `/depth` 320×240 32FC1 depth image + `/depth/points`
  point cloud, renders headless under llvmpipe alongside the RGB camera). Still: force/torque.
- 🔲 **Grasping / pick-and-place** — the arm's natural next task.
- 🔲 Multi-robot scenarios (coordination).

## E. Frontier bets (the Physical AI narrative)

- ✅ **Scenarios as RL / gym environments** — `robotbase.sim.gym_env.RobotbaseArmEnv` is a
  Gymnasium env over the in-process MuJoCo arm whose **task is a scenario goal** (reach a
  joint config within tolerance — the same target/tolerance a `joint_positions_reached`
  assertion checks). Conforms to the gym API; a policy trains against it and is evaluated
  against the identical scenario through the runner. "Train *and* eval in one format."
  Optional `sim-rl` extra. *Next:* mobile-robot env (/scan+/odom obs, /cmd_vel action);
  a bundled training example.
- 🔲 **VLA / foundation-model eval** — benchmark vision-language-action models on scenarios.
  Layer-3 Physical-AI-native; almost no standard infra exists.
- 🔲 **Real-robot backend (sim-to-real) — now a core goal, not just a frontier bet.** "Port
  from sim to real" is half the vision: a real robot is just another *backend* (Terraform
  provider) behind the same declarative specs — run the same scenario against hardware, record
  the run in the same MCAP format, evaluate with the same assertions. The endgame the whole
  declarative stack is built toward.
- 🔲 **A robotics-specialized coding agent** (VISION Layer 4) living on the MCP tools.

## F. Distribution (the unlock — nothing matters without users)

- ✅ **Repo publish-ready** — README refreshed (accurate feature tour, sim-agnostic, 3
  templates), `CONTRIBUTING.md`, and `docs/PUBLISHING.md` (the PyPI + runtime-image runbook).
  Verified the wheel/sdist build and bundle all templates + sim adapters.
- 🔲 **PyPI upload + public Docker image** — the actual publish (needs owner accounts/tokens;
  steps in `docs/PUBLISHING.md`).
- 🔲 **`.devcontainer` / GitHub Codespaces** — "Open in Codespaces" → it just works in the
  browser (Docker-in-Docker; the headless sim runs, only the GUI wouldn't). Lowest-friction
  "try it now" without hosting infra.
- 🔲 **CI + a green "tests passing" badge** — GitHub Actions running `pytest`; trust signal.
- 🔲 **Animated robot GIFs** — capture spectator-camera frames *during* a run → looping GIF
  (headless, pure-Python encoder). A moving robot beats a still, for the README.
- 🔲 **Captured agent-solving artifact** — run a real subagent solving a scenario, capture its
  tool-calls + the before/after episode, render it as a shareable "AI teaches itself" page.
  Dogfooding-as-marketing.
- 🔲 The demo video / GIF (the "agent teaches itself" moment; `PROOF.md` is the written form).
- 🔲 Build-in-public content on the "Build With Toddy" brand (a structural edge).
- 🔲 Integration guides (Claude Code / Cursor / any agent).

## G. Declarative authoring — the "Terraform for robots" core (CURRENT FOCUS)

The heart of the vision: **everything is compilable YAML.** Scenarios (runs/tests) and
manifests already are, but **worlds are raw SDF and robots are raw URDF/xacro** — verbose,
physics-sensitive XML that an agent can't reliably write. Close that gap so a `robot.yaml` /
`world.yaml` / scenario is the *complete, reproducible* source of truth for a robotics
project, and a coding agent authors all of it by natural language:

- ✅ **Declarative robot spec (YAML → URDF)** — the key architectural move, **SHIPPED**
  (`robotbase/robotspec/`, design `docs/design/declarative-compiler.md`). A `robot.yaml` compiles
  to URDF + launch bridges + manifest via a shared primitive IR: a `parts` list of composable
  modules (`differential-drive`, `arm`, `quadrotor`) or raw links/joints, sensors
  (`lidar`/`camera`/`depth`/`imu`/`contact`) mounting to any link, tree-validated and rendered
  once. `base:` stays as one-line sugar. **All four templates compile from specs** and the
  differential-drive one is Docker-validated.
- ✅ **Declarative world spec (YAML → SDF)** — **SHIPPED** (`robotbase/worldspec/`): `world.yaml`
  (ground, light, obstacles, walls, goals, raw-SDF `include`) → world SDF, and a robot's sensors
  automatically pull the gz systems the world needs (the seam).
- ✅ **Bring-your-own-robot / world (import)** — **SHIPPED**: `create --from-urdf my_robot.urdf`
  wraps an existing URDF verbatim (inferring its sensors so the world wires them); world import is
  `world.yaml` `include:`. The runner/evals now run over *your* robot, not just the templates.
- 🔲 **`robotbase init`** — drop Robotbase into an *existing* project (like `supabase init`),
  not only greenfield `create`. (The remaining import piece.)
- 🔲 **Compile the launch + manifest, not just URDF/SDF.** Today `_compile_specs` regenerates only
  the URDF and world SDF; the launch (its `parameter_bridge` args) and `robotbase.yaml` manifest
  are still template-owned. Consequence: a `--from-urdf` import whose URDF has a **camera/depth**
  sensor renders it in Gazebo (the world system is inferred) but the `/image`//`/depth` ROS bridge
  is never added (the default diff-drive launch bridges lidar/imu/contact only). Regenerate the
  launch from `compiled.bridges` (and the manifest from `compiled.manifest`) so editing
  `robot.yaml` post-create fully rewires the project. Until then, launch/manifest are
  template-owned — a docs caveat on `--from-urdf`.
- 🔲 **Custom archetypes / mobile manipulators as templates** — composition works
  (diff-drive + arm compiles as one tree); package common compositions as templates.
- 🔲 **NL authoring end-to-end** — the agent goes from "test a diff-drive that avoids
  obstacles in a warehouse" to the robot spec + world spec + scenario + controller, all via
  the declarative formats. Robotbase becomes truly agent-native and drop-in-anywhere.

## H. Robotbase Studio — the GUI (the control plane over the declarative stack)

- 🔲 **One pane: chat with your agent + see files being edited + watch the 3D sim
  running/improving + read results.** The end-state that makes it feel like a product, not a
  CLI, and opens it to roboticists who aren't coding-agent power users. Big, different-skillset
  build (a web app). Pieces exist to lean on: Foxglove is embeddable for the live 3D; the
  Claude Agent SDK can host the agent-with-MCP-tools; the runtime already orchestrates.
  Sequence *after* (or alongside a minimal version of) G — the Studio's magic depends on NL
  authoring being smooth. A minimal `robotbase studio` (embed Foxglove live + episode/results,
  then add agent chat) is the incremental path.

---

## Ranking

**A–F done or in progress** (evals, auto-diagnosis, RobotBench, describe/doctor, MCAP
episodes, sim-agnostic + RL env, distribution groundwork + visualization). **Current focus
(2026-07-25, Tom): G — agent-native authoring**, i.e. everything by natural language:
declarative robot/world specs (YAML → URDF/SDF) so the agent authors robots and worlds the
way it already authors scenarios and controllers; plus import (bring-your-own-URDF) and
`robotbase init` for drop-in. Then **H — Robotbase Studio** (the unified GUI), sequenced
after a minimal authoring foundation because the Studio's value depends on NL authoring
being smooth. Remaining breadth (D robots/sensors, E frontier) slots in opportunistically.

Order to build G:
1. **Declarative robot spec (YAML → URDF)** — start with the mobile base; the foundational
   piece that makes robots agent-authorable.
2. **Declarative world spec (YAML → SDF)** — scenes from words.
3. **Import (`--from-urdf`) + `robotbase init`** — bring-your-own + drop-in.
4. **A minimal Studio** (Foxglove live embed + results), then agent chat.
