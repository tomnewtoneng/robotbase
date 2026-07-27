# RobotBench Suite v2 — authoring-first, tests the core value proposition (design)

Status: **approved design, spec under review** (2026-07-27). Supersedes the task set in
`robotbench-validation.md` (that doc's harness/metrics/judge-parity principles still hold; this
doc replaces **what we test** and adds the **authoring judge**). Read `docs/STRATEGY.md` first.

## Why revamp

The v1 suite (`fix a broken controller` × 4) mostly measured the **agent loop** — both arms edit
a Python node in an already-working project, so they scored nearly the same (0.75/0.75). That is
not what Robotbase *is*. Robotbase's core value proposition is exactly two things:

1. **The compiler** — a compact declarative spec compiles to correct multi-file URDF/SDF/launch,
   handling the wiring that bites: sensor plugins, Gazebo sensor *systems*, TF/joints, bridge
   topics.
2. **The knowledge layer** — `AGENTS.md` + the MCP tools that let an agent drive that compiler
   without knowing ROS/Gazebo internals.

On **authoring** tasks these two are inseparable by design (the knowledge layer's whole job is to
drive the compiler correctly), and their combined advantage over raw ROS **is** the product. So
v2 is **all authoring**. No `fix`/debug tasks. We delete the four v1 tasks.

## The claim under test (sharpened)

> Given the same simulator and the same acceptance test, an agent **authoring a robot + world
> from natural language** succeeds more often, faster, and knows whether it succeeded, **with**
> Robotbase's declarative compiler + knowledge layer than with raw ROS 2 / Gazebo.

## Experiment invariants (unchanged from v1)

- **Two arms, vary one thing.** WITH = empty project + robotbase MCP tools + `AGENTS.md`.
  WITHOUT = empty ROS 2 workspace + bash/read/edit/write + `RAW-ROS-ORIENTATION.md`.
- **Identical across arms:** the task prompt, the **provided controller**, and the **judge**.
  Only the *authoring surface* differs — the variable under test.
- **External shared judge.** Behavioral, format-agnostic (see below). Neither agent scores
  itself.
- **Metrics unchanged:** capped-aware report (solved rate · capped rate · self-verification
  accuracy over *concluded* runs · fp/fn · mean turns), transcripts persisted per trial.
- **Sequential trials**, fresh scaffold + teardown between trials (port 8765 / container are
  singletons).

## Fairness baseline (decided)

- **Isolation:** *fixed controller.* Both arms get the **same** provided controller; the agent
  only authors the robot + world. A result is attributable to the authoring, not to control-code
  skill.
- **Symmetric orientation:** WITHOUT gets `RAW-ROS-ORIENTATION.md` covering the **same
  environment facts** `AGENTS.md` gives WITH — distro (Jazzy), sim (Gazebo Harmonic, headless
  llvmpipe), `ros2 launch` / `ros_gz_sim create -x -y -z` / `colcon build`, where
  URDF/SDF/launch/`package.xml` live — and **nothing robot-specific: no robot XML, no sensor
  snippets, no templates.** "Product docs vs. platform docs"; neither hands over the answer.

## Robot interface contract (fair, standard ROS — stated to both arms)

For the shared judge to run the shared controller against either arm's output, the authored robot
must expose the ROS conventions any mobile robot exposes — this is not a Robotbase tax:

- subscribes `/cmd_vel` (`geometry_msgs/Twist`),
- publishes `/scan` (`sensor_msgs/LaserScan`) for LiDAR tasks and `/image` for camera tasks,
- spawns into Gazebo under a **known model name** (given in the task, e.g. `robot`),
- is brought up by a **known command**: WITH → `robotbase up`; WITHOUT → `ros2 launch <pkg>
  bringup.launch.py` (the orientation states this contract).

## The suite — 4 authoring discriminators

Each targets a spot where raw URDF/SDF has a **proven** sharp edge (we hit each in our own
dogfooding), so a Robotbase advantage is real, not contrived. Mobile-base + sensors only;
arm/quadrotor authoring is a deliberate fast-follow (our sim-control dogfooding there is thinner,
so a failure could be our bug, not a fair signal).

### 1. `author/diff-lidar-world` (kind: author)
- **Prompt:** "Build a differential-drive robot named `robot` with a forward-facing 2-D LiDAR,
  in a 6×6 m walled world containing a box obstacle at (2, 0). It must respond to `/cmd_vel` and
  publish `/scan`."
- **Provided controller:** `stop_at_1m.py` — drive forward at 0.3 m/s, stop when `/scan` shows an
  obstacle within 1 m ahead.
- **Acceptance (ground truth via gz pose):** robot's **min distance to the box** ∈ [0.8, 1.2] m
  and robot never penetrates the box (min > 0.4 m from box center face).
- **Discriminator:** the world must wire Gazebo's sensor *system* or `/scan` is silently empty —
  dogfooding-B. Compiler: one `sensors:` line + world sugar. Raw: sensor plugin **and** the world
  `<plugin>` system, or nothing publishes.

### 2. `author/sensor-on-mast` (kind: author)
- **Prompt:** "Build a differential-drive robot named `robot` with a 2-D LiDAR mounted on a mast
  0.5 m **above** the chassis, in a 6×6 m walled world with a **low** barrier (0.2 m tall) at
  (2, 0) and a **tall** box (0.6 m) at (3.5, 0). Respond to `/cmd_vel`, publish `/scan`."
- **Provided controller:** `stop_at_1m.py` (same as #1).
- **Acceptance:** the elevated scan clears the low barrier (robot does **not** stop for it) and
  stops for the tall box → min distance to the **tall box** ∈ [0.8, 1.2] m; min distance to the
  **low barrier** < 0.5 m (i.e. it drove over/past it without stopping).
- **Discriminator:** multi-link composition + sensor on a **non-base** link — dogfooding-A's
  `on: mast`. Compiler: `parts:` + `sensor … on: mast`. Raw: a mast link, a fixed joint at the
  right height, the sensor plugin on that link, and the bridge frame — all by hand.

### 3. `author/two-sensor` (kind: author)
- **Prompt:** "Build a differential-drive robot named `robot` with **both** a forward LiDAR
  (`/scan`) and a forward camera (`/image`), in a 6×6 m walled world with a box at (2, 0).
  Respond to `/cmd_vel`."
- **Provided controller:** `stop_at_1m.py` (uses `/scan`).
- **Acceptance:** #1's distance predicate **and** `/image` publishes ≥ 1 frame with the expected
  encoding/resolution during the run (both sensors actually live).
- **Discriminator:** every sensor is another plugin + bridge + frame to hand-wire. Compiler: two
  `sensors:` lines. Raw: two of everything, correctly.

### 4. `import/add-sensor` (kind: import)
- **Scaffold provides:** a raw external URDF (`vendor_bot.urdf`, a plain differential-drive base,
  **no** sensors, not a Robotbase project) + the walled world with a box at (2, 0).
- **Prompt:** "Bring the provided `vendor_bot.urdf` under management and add a forward LiDAR so the
  robot publishes `/scan`, in the provided world. Respond to `/cmd_vel`, spawn as model `robot`."
- **Provided controller:** `stop_at_1m.py`.
- **Acceptance:** #1's distance predicate (so the added sensor must actually work).
- **Discriminator:** the `--from-urdf` import path (elevated per prior decision) + augmenting an
  existing robot. Compiler: `robotbase import` then one `sensors:` line. Raw: hand-edit foreign
  URDF XML to add a sensor link/joint/plugin + bridge.

## Task dict schema (extends `robotbase/bench.py::TASKS`)

```python
{
  "id": "author/diff-lidar-world",
  "kind": "author",                 # "author" | "import"
  "robot": "mobile-base",
  "skill": "author robot+world from spec",
  "prompt": "<the natural-language authoring task, verbatim>",
  "model_name": "robot",            # gz spawn model name the controller/judge expect
  "controller": "stop_at_1m",       # provided controller module (same file both arms)
  "judge_scenario": "author_stop_at_1m",  # canonical acceptance spec name (see judge)
  "import_urdf": "vendor_bot.urdf", # only for kind == "import"; else absent
}
```

`BENCHMARK_VERSION` bumps to **2** (the task set changed; results are not comparable to v1).

## Scaffolds

Two scaffold builders replace the single broken-controller generator. Each returns a fresh
throwaway project dir under a scratch dir (never inside the repo). Per-arm, because the two arms
author into different structures.

- **`author` scaffold:**
  - WITH: an **empty Robotbase project** (`robotbase new`-equivalent minimal skeleton: project
    manifest + empty `robots/` + `worlds/` + the provided controller placed at the path the
    contract names) so `robotbase up` works once the agent writes `robot.yaml` + world.
  - WITHOUT: an **empty colcon workspace** (`src/authored_pkg/` with a stub `package.xml` +
    `CMakeLists.txt`/`setup.py`, an empty `launch/`, `urdf/`, `worlds/`, the provided controller
    node placed under the package) + `RAW-ROS-ORIENTATION.md` at the root.
  - Both: the **provided controller file** (identical bytes) and a `TASK.md` (the prompt).
- **`import` scaffold:** as `author`, plus `import_urdf` copied to a known path in both arms'
  scaffolds and referenced by the prompt.

The provided controller is stored once under `robotbase/robotbench/fixtures/controllers/` and
copied into each scaffold, so both arms are byte-identical.

## Arms & prompt (`arms.py` changes)

- New `build_author_prompt(task)` — uses `task["prompt"]` verbatim + the shared rules: "only
  author the robot/world (and package/launch); **do not modify the provided controller**"; "do
  not claim success until you have verified the robot's behavior yourself"; "when finished, stop";
  + the **interface contract** + the **bring-up command** for that arm.
- `without_orientation` for authoring returns the `RAW-ROS-ORIENTATION.md` contents (env-only, no
  templates) — this file is the single source, shipped in the scaffold and inlined into the
  prompt so the agent cannot miss it.
- `arm_context` gains a `kind`-aware branch selecting the authoring prompt/orientation. WITH tools
  = `["robotbase-mcp"]` + `AGENTS.md`; WITHOUT tools = `["bash","read","edit","write"]` +
  `RAW-ROS-ORIENTATION.md`.

## The authoring judge (`robotbase/robotbench/author_judge.py`, new)

Format-agnostic, behavioral, shared. Reuses `run_scenario` / the `Runtime` gz-ROS client /
`assertions.evaluate` where clean.

`author_judge(project_dir, task, *, bringup_fn, trials, seed) -> {"robustness", "solved"}`:

1. Look up the task's **canonical acceptance spec** by `judge_scenario` name (a small registry in
   this module): obstacles/world ground-truth, the provided controller module, the predicate, and
   the spawn-pose randomization range.
2. For each of `trials` seeds:
   a. `bringup_fn(project_dir, spawn_pose)` starts the arm's sim (WITH → `robotbase up`;
      WITHOUT → `colcon build` + `ros2 launch <pkg> bringup.launch.py`) with the robot spawned at
      the seeded pose (via `ros_gz_sim create -x -y -z`, honoring the flags-not-`<pose>` rule).
   b. Attach the gz/ROS measurement client; confirm the **interface contract** (`/cmd_vel`
      accepted, `/scan` — and `/image` where required — publishing). A missing interface = fail
      this trial (a mis-authored sensor cannot pass).
   c. Run the **provided controller** node for the scenario duration; sample the robot's
      **ground-truth gz model pose** throughout (not the robot's own odom/scan — so success can't
      be faked by a broken sensor).
   d. Evaluate the predicate from ground-truth metrics via `assertions.evaluate`.
   e. Tear down the sim.
3. `robustness = passes / trials`; `solved = robustness == 1.0`.

This slots into `runner.run_trial` in place of `judge_fn` for authoring tasks; `cli_deps` gains
`real_author_judge(trials)` and the per-arm `bringup_fn`s. The v1 `judge.py` (robotbase-test
shell-out) is retained only if any `fix` task returns; v2 does not use it.

**De-risking:** attaching the measurement client to a **raw** `ros2 launch` sim (WITHOUT arm) is
the one new/uncertain mechanism. The plan opens with a **spike** (Task 0): hand-author a minimal
raw ROS diff-drive package, launch it, and prove the gz-pose client + `/cmd_vel` injection work
against it, before building the task suite on top.

## Dogfooding (standing instruction)

The `author` tasks *are* dogfooding. To write each task's **reference solution** (the known-good
`robot.yaml` + world, used to smoke-test the judge and confirm the task is solvable at all), I
author it **through the current compiler by hand**. Any friction — a sensor that won't mount, a
world that renders a silent sensor, a mast that needs raw-SDF escape — is **recorded in
`docs/STRATEGY.md`'s findings log and fixed before the run**, or the task is adjusted. Otherwise
WITH's result reflects a compiler bug, not its value. Each reference solution is committed under
`robotbase/robotbench/fixtures/reference/<task>/`.

## Testing

- **Offline (fakes, no Docker/API):** task-dict schema + `expand_tasks`; scaffold builders create
  the expected per-arm structure with byte-identical controller; `build_author_prompt` parity
  (both arms same task text + contract; only orientation/tools differ; controller-immutability
  rule present); the `author_judge` predicate logic against **faked** ground-truth pose traces
  (pass/fail/penetration/low-barrier-clear cases) with a stub bring-up; `records`/`report`
  unchanged coverage still green.
- **Live smoke (Docker, one per task):** run the **reference solution** through the judge and
  assert `solved == True` (proves the task is solvable and the judge is calibrated) before any
  agent runs.
- **Live integration:** one real WITH + one real WITHOUT trial on `author/diff-lidar-world` with
  Sonnet, transcripts persisted, before the full batch.

## Run artifacts — durable & interrogable

Every run writes a self-contained, timestamped directory so results can be re-examined later
without re-running anything:

`robotbase/robotbench/results/runs/<UTC-timestamp>-v2/`
- `manifest.json` — run metadata: benchmark version, model, git SHA, caps, seeds, task list,
  start/end times, per-arm bring-up commands (reproducibility).
- `records/<task>-<arm>-<trial>.json` — the `TrialRecord` (existing schema).
- `transcripts/<task>-<arm>-<trial>.transcript.json` — the full agent transcript (existing
  persistence, `transcript_path` on the record).
- `judge/<task>-<arm>-<trial>/seed-<n>/` — the **authoring judge's** per-seed evidence: the
  ground-truth gz pose trace it sampled, the computed metric, the predicate verdict, and the
  bring-up log. This is what lets us answer *why* a trial passed or failed after the fact.
- `ROBOTBENCH-RESULTS.md` — the rendered report, also copied to `docs/` as the current headline.

The `results/` tree is git-ignored (large, machine-specific), but each definitive run's
`manifest.json` + `ROBOTBENCH-RESULTS.md` are committed under `docs/` as the durable record. A
run is never overwritten — each gets its own timestamped directory.

## Run plan

1. **Pilot n=1** across all 4 tasks × both arms (8 trials), transcripts saved → read every
   transcript, fix any harness unfairness, confirm the metrics table reads sensibly.
2. **Definitive n=3** (4 × 2 × 3 = 24 trials) → `docs/ROBOTBENCH-RESULTS.md` (v2), the shareable
   proof.

## Removed / out of scope

- **Deleted:** the four v1 `fix`-a-controller tasks and their broken-controller generator path
  from the *suite* (code may remain if a future `fix` task returns, but v2 ships none).
- **Deferred fast-follow:** `author/arm-reach`, `author/quadrotor-hover` (archetype breadth) —
  after the thesis validates on mobile+sensors.
- **Not in this spec:** leaderboard / multiple models (still Sonnet-only), funding artefacts.
