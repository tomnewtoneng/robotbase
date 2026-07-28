# RobotBench Suite v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace RobotBench's fix-a-controller suite with 4 from-scratch **authoring** tasks and a format-agnostic behavioral judge, so the benchmark measures Robotbase's core value proposition (the compiler + the knowledge layer) fairly and durably.

**Architecture:** New `author`/`import` task kinds drive per-arm scaffolds (WITH = empty Robotbase project; WITHOUT = empty colcon workspace + env-only orientation). Both arms author a robot+world that a **shared provided controller** must succeed against. A new behavioral judge (`author_judge.py`) brings up each arm's sim, runs the same controller, and scores the outcome from **Gazebo ground-truth pose** (not the robot's own sensors) across N seeded spawns. Every run persists a durable, timestamped artifact tree.

**Tech Stack:** Python 3.12, Pydantic v2, pytest; ROS 2 Jazzy + Gazebo Harmonic (headless llvmpipe) via Docker; claude-agent-sdk; reuses `robotbase/scenario_runner.py`, `assertions.py`, the gz/ROS `Runtime`.

## Global Constraints

- **Benchmark version = 2** everywhere it appears: `robotbase/bench.py::BENCHMARK_VERSION` and `robotbase/robotbench/records.py::BENCHMARK_VERSION`. Results are not comparable to v1.
- **Fairness is non-negotiable:** across arms, the task prompt, the provided controller (byte-identical), and the judge are identical. Only the authoring surface + tools + orientation differ.
- **Ground truth only:** the judge measures success from Gazebo **model pose**, never from the robot's own `/scan` or `/odom`.
- **Interface contract** (stated to both arms): authored robot subscribes `/cmd_vel` (`geometry_msgs/Twist`), publishes `/scan` (`sensor_msgs/LaserScan`; `/image` for camera tasks), spawns under model name `robot`, brought up by `robotbase up` (WITH) or `ros2 launch <pkg> bringup.launch.py` (WITHOUT).
- **`ros_gz_sim create` ignores SDF `<pose>`** — spawn pose is set with `-x/-y/-z` flags.
- **Scaffolds and run artifacts live under a scratch dir**, never inside the repo working tree. `robotbase/robotbench/results/` is git-ignored.
- **Offline-testable core:** every module except the live bring-up must be unit-testable with fakes (no Docker/API in the unit layer).
- **Provided controller is immutable to the agent:** the prompt forbids editing it; the scaffold is the single source, copied byte-identically into both arms.

---

## File Structure

- `robotbase/bench.py` — MODIFY: replace `TASKS` with the 4 v2 tasks; `BENCHMARK_VERSION = 2`.
- `robotbase/robotbench/records.py` — MODIFY: `BENCHMARK_VERSION = 2`.
- `robotbase/robotbench/fixtures/controllers/stop_at_1m.py` — CREATE: the provided controller node.
- `robotbase/robotbench/fixtures/RAW-ROS-ORIENTATION.md` — CREATE: env-only orientation for WITHOUT.
- `robotbase/robotbench/fixtures/reference/<task>/` — CREATE (Task 10): known-good authored solutions.
- `robotbase/robotbench/scaffolds.py` — CREATE: per-arm/per-kind scaffold builders.
- `robotbase/robotbench/arms.py` — MODIFY: `build_author_prompt`, kind-aware `arm_context`, authoring orientation.
- `robotbase/robotbench/acceptance.py` — CREATE: canonical acceptance-spec registry + pure predicate logic.
- `robotbase/robotbench/gz_probe.py` — CREATE (Task 0): Gazebo model-pose sampler + `/cmd_vel` liveness check.
- `robotbase/robotbench/author_judge.py` — CREATE: the behavioral judge orchestration.
- `robotbase/robotbench/cli_deps.py` — MODIFY: `real_author_judge`, per-arm `bringup_fn`, author scaffold generate factory.
- `robotbase/robotbench/runner.py` — MODIFY: select judge by kind; write run manifest + judge evidence.
- `robotbase/robotbench/report.py` — MODIFY (minor): render benchmark v2 header; copy manifest/report to `docs/`.
- `tests/test_robotbench_*.py` — CREATE/MODIFY per task.

---

## Task 0: Spike — raw-ROS Gazebo pose probe (DE-RISK) ✅ DONE (2026-07-28)

**Goal:** Prove the judge can measure a **raw** (non-Robotbase) `ros2 launch` sim before building the suite on it. Exploratory; ends in a reusable helper + a written finding.

**Outcome:** Probe viable via subprocess (no rclpy). Working mechanism: `gz topic -e -t /world/<world>/dynamic_pose/info -n 1`, parse the top-level model entry by name (gz omits near-zero fields → 0.0). Verified live: drove `/cmd_vel` fwd, `sample_model_pose` returned a clean monotonic trace (x 0→+1.036 m, y≈0). Deviation from the steps below: rather than hand-author `/tmp/spike_pkg` (world `empty`, model `robot`), I verified against a `robotbase create` diff-drive project (world `warehouse`, model `probebot`) — same `dynamic_pose/info` mechanism and same injected-`sh` seam, so it transfers to the raw WITHOUT arm unchanged. `sample_model_pose`/`cmd_vel_is_live` take an injected `sh(cmd)` (not a hardcoded world/subprocess) so both arms reuse them. See `docs/STRATEGY.md` finding + `tests/test_gz_probe.py` (5 tests).

**Files:**
- Create: `robotbase/robotbench/gz_probe.py`
- Create (throwaway, git-ignored): `/tmp/spike_pkg/` minimal raw diff-drive package
- Doc: append a finding to `docs/STRATEGY.md`

**Interfaces:**
- Produces: `sample_model_pose(model_name: str, duration_s: float, hz: float = 10) -> list[tuple[float, float, float]]` (returns (t, x, y) samples from `gz topic -e /world/<world>/pose/info` or `ros2 topic echo` of the gz pose bridge); `cmd_vel_is_live(timeout_s: float) -> bool` (publishes a zero Twist and confirms a subscriber exists).

- [ ] **Step 1: Hand-author a minimal raw diff-drive package in the Docker env**

By hand (not through Robotbase), create `/tmp/spike_pkg` with a URDF diff-drive + a `bringup.launch.py` that spawns it as model `robot` into an empty world. Bring it up:
```bash
wsl -d Ubuntu-24.04 bash -lc 'cd /tmp/spike_pkg && colcon build && source install/setup.bash && ros2 launch spike_pkg bringup.launch.py &'
```
Expected: a `robot` model in Gazebo, `/cmd_vel` and gz pose topics present.

- [ ] **Step 2: Prove pose sampling + cmd_vel liveness from the shell**

```bash
wsl -d Ubuntu-24.04 bash -lc 'source /opt/ros/jazzy/setup.bash && gz topic -e -t /world/empty/dynamic_pose/info -n 1 | head -40'
wsl -d Ubuntu-24.04 bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 topic pub -1 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}}" && echo OK'
```
Expected: pose info contains the `robot` model x/y; the robot moves. Record the exact topic/format that works.

- [ ] **Step 3: Implement `gz_probe.py` using the proven mechanism**

Wrap whatever worked in Step 2 into `sample_model_pose` and `cmd_vel_is_live` (subprocess to `gz topic`/`ros2 topic`, parse the pose of `model_name`). Keep it dependency-light (subprocess + regex/json parse), no rclpy node required.

- [ ] **Step 4: Verify the probe against the live spike**

```bash
wsl -d Ubuntu-24.04 bash -lc 'cd ~/robotbase && source .venv/bin/activate && python -c "from robotbase.robotbench.gz_probe import sample_model_pose; print(sample_model_pose(\"robot\", 2.0)[:3])"'
```
Expected: a non-empty list of (t, x, y) tuples.

- [ ] **Step 5: Record finding + commit**

Append to `docs/STRATEGY.md` findings log: the working pose topic/format, any gotcha, and the verdict (probe viable / needs rclpy). Commit `gz_probe.py` + the doc. If the probe proves infeasible via subprocess, STOP and escalate (the judge design needs revisiting).

```bash
git add robotbase/robotbench/gz_probe.py docs/STRATEGY.md && git commit -m "spike(robotbench): gz pose probe works against raw ros2 launch sim"
```

---

## Task 1: v2 task set + benchmark version bump

**Files:**
- Modify: `robotbase/bench.py:10-25`
- Modify: `robotbase/robotbench/records.py` (the `BENCHMARK_VERSION` line)
- Test: `tests/test_bench_tasks_v2.py`

**Interfaces:**
- Produces: `TASKS` list where each task has keys `id, kind, robot, skill, prompt, model_name, controller, judge_scenario` and (import only) `import_urdf`. `expand_tasks` (unchanged in `cli_deps.py`) resolves them.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bench_tasks_v2.py
from robotbase.bench import TASKS, BENCHMARK_VERSION
from robotbase.robotbench.records import BENCHMARK_VERSION as REC_VER

REQUIRED = {"id", "kind", "robot", "skill", "prompt", "model_name", "controller", "judge_scenario"}

def test_benchmark_version_is_2_everywhere():
    assert BENCHMARK_VERSION == 2 and REC_VER == 2

def test_suite_is_four_authoring_tasks():
    ids = [t["id"] for t in TASKS]
    assert ids == ["author/diff-lidar-world", "author/sensor-on-mast",
                   "author/two-sensor", "import/add-sensor"]
    assert {t["kind"] for t in TASKS} == {"author", "import"}

def test_every_task_has_required_keys_and_prompt():
    for t in TASKS:
        assert REQUIRED <= set(t), f"{t['id']} missing {REQUIRED - set(t)}"
        assert len(t["prompt"]) > 40 and t["model_name"] == "robot"
    imp = next(t for t in TASKS if t["kind"] == "import")
    assert imp["import_urdf"].endswith(".urdf")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_bench_tasks_v2.py -v`
Expected: FAIL (version is 1; old TASKS).

- [ ] **Step 3: Replace `TASKS` and bump versions**

In `robotbase/bench.py` set `BENCHMARK_VERSION = 2` and replace `TASKS` with the four v2 tasks. Copy each `prompt`, `model_name`, `controller`, `judge_scenario` **verbatim from the spec's "The suite" section** (`docs/design/robotbench-suite-v2.md`). Shape:
```python
TASKS = [
  {"id": "author/diff-lidar-world", "kind": "author", "robot": "mobile-base",
   "skill": "author robot+world from spec", "model_name": "robot",
   "controller": "stop_at_1m", "judge_scenario": "author_stop_at_1m",
   "prompt": "Build a differential-drive robot named `robot` with a forward-facing 2-D LiDAR, "
             "in a 6x6 m walled world containing a box obstacle at (2, 0). It must respond to "
             "/cmd_vel and publish /scan."},
  {"id": "author/sensor-on-mast", "kind": "author", "robot": "mobile-base",
   "skill": "author robot+world from spec", "model_name": "robot",
   "controller": "stop_at_1m", "judge_scenario": "author_mast_clear",
   "prompt": "Build a differential-drive robot named `robot` with a 2-D LiDAR mounted on a mast "
             "0.5 m above the chassis, in a 6x6 m walled world with a low barrier (0.2 m tall) "
             "at (2, 0) and a tall box (0.6 m) at (3.5, 0). Respond to /cmd_vel, publish /scan."},
  {"id": "author/two-sensor", "kind": "author", "robot": "mobile-base",
   "skill": "author robot+world from spec", "model_name": "robot",
   "controller": "stop_at_1m", "judge_scenario": "author_two_sensor",
   "prompt": "Build a differential-drive robot named `robot` with both a forward LiDAR (/scan) "
             "and a forward camera (/image), in a 6x6 m walled world with a box at (2, 0). "
             "Respond to /cmd_vel."},
  {"id": "import/add-sensor", "kind": "import", "robot": "mobile-base",
   "skill": "import + augment an existing URDF", "model_name": "robot",
   "controller": "stop_at_1m", "judge_scenario": "author_stop_at_1m",
   "import_urdf": "vendor_bot.urdf",
   "prompt": "Bring the provided vendor_bot.urdf under management and add a forward LiDAR so the "
             "robot publishes /scan, in the provided world. Respond to /cmd_vel, spawn as model "
             "`robot`."},
]
```
Set `BENCHMARK_VERSION = 2` in `robotbase/robotbench/records.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_bench_tasks_v2.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add robotbase/bench.py robotbase/robotbench/records.py tests/test_bench_tasks_v2.py
git commit -m "feat(robotbench): v2 authoring task set + benchmark version 2"
```

---

## Task 2: Provided controller fixture (`stop_at_1m`)

**Files:**
- Create: `robotbase/robotbench/fixtures/controllers/stop_at_1m.py`
- Create: `robotbase/robotbench/fixtures/__init__.py` (empty, so the dir ships in the package)
- Test: `tests/test_stop_at_1m_controller.py`

**Interfaces:**
- Produces: a runnable ROS 2 node module with a pure helper `desired_twist(ranges: list[float], stop_range_m: float = 1.0, speed: float = 0.3) -> tuple[float, float]` returning `(linear_x, angular_z)`, so the stop logic is unit-testable without ROS. The `main()` wires it to rclpy (`/scan` in, `/cmd_vel` out).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stop_at_1m_controller.py
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    "stop_at_1m",
    pathlib.Path("robotbase/robotbench/fixtures/controllers/stop_at_1m.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_drives_forward_when_clear():
    lin, ang = m.desired_twist([5.0] * 180)
    assert lin == 0.3 and ang == 0.0

def test_stops_when_obstacle_within_1m():
    ranges = [5.0] * 180; ranges[90] = 0.8   # dead ahead
    lin, ang = m.desired_twist(ranges)
    assert lin == 0.0

def test_ignores_inf_and_nan():
    lin, _ = m.desired_twist([float("inf"), float("nan"), 5.0])
    assert lin == 0.3
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_stop_at_1m_controller.py -v`
Expected: FAIL (file not found).

- [ ] **Step 3: Implement the controller**

```python
# robotbase/robotbench/fixtures/controllers/stop_at_1m.py
"""Provided RobotBench controller (IMMUTABLE to the agent): drive forward, stop within 1 m.
Subscribes /scan (LaserScan), publishes /cmd_vel (Twist). The pure helper is unit-tested."""
import math

def desired_twist(ranges, stop_range_m: float = 1.0, speed: float = 0.3):
    finite = [r for r in ranges if r is not None and math.isfinite(r) and r > 0.0]
    ahead = finite[len(finite)//3: 2*len(finite)//3] if finite else []
    if ahead and min(ahead) <= stop_range_m:
        return 0.0, 0.0
    return speed, 0.0

def main():  # pragma: no cover - live ROS entrypoint
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import LaserScan
    rclpy.init()
    node = Node("stop_at_1m")
    pub = node.create_publisher(Twist, "/cmd_vel", 10)
    def on_scan(msg):
        lin, ang = desired_twist(list(msg.ranges))
        t = Twist(); t.linear.x = lin; t.angular.z = ang; pub.publish(t)
    node.create_subscription(LaserScan, "/scan", on_scan, 10)
    rclpy.spin(node)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stop_at_1m_controller.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add robotbase/robotbench/fixtures/ tests/test_stop_at_1m_controller.py
git commit -m "feat(robotbench): provided stop_at_1m controller fixture"
```

---

## Task 3: Env-only orientation doc + scaffold builders

**Files:**
- Create: `robotbase/robotbench/fixtures/RAW-ROS-ORIENTATION.md`
- Create: `robotbase/robotbench/scaffolds.py`
- Test: `tests/test_robotbench_scaffolds.py`

**Interfaces:**
- Consumes: `robotbase.generator.create_project` / `template_dir` (existing) for the WITH skeleton is NOT used (author starts empty); instead build minimal dirs directly.
- Produces: `build_scaffold(task: dict, arm: str, dest_root: str) -> str` returning the scaffold dir. WITH → `{dest}/with/` containing an empty Robotbase project (`robotbase.yaml` manifest, empty `robots/`, `worlds/`, controller copied to `controllers/stop_at_1m.py`, `TASK.md`). WITHOUT → `{dest}/without/` containing `src/authored_pkg/` (`package.xml`, `setup.py`, empty `launch/ urdf/ worlds/`, controller copied to `authored_pkg/controllers/stop_at_1m.py`), `RAW-ROS-ORIENTATION.md`, `TASK.md`. For `kind == "import"`, both get `vendor_bot.urdf` at scaffold root (fixture created in this task).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_robotbench_scaffolds.py
import pathlib
from robotbase.robotbench.scaffolds import build_scaffold

AUTHOR = {"id": "author/diff-lidar-world", "kind": "author", "controller": "stop_at_1m",
          "model_name": "robot", "prompt": "Build a robot."}
IMPORT = {**AUTHOR, "id": "import/add-sensor", "kind": "import", "import_urdf": "vendor_bot.urdf",
          "prompt": "Import it."}

def _controller_bytes(d):
    return (pathlib.Path(d).rglob("stop_at_1m.py").__next__()).read_bytes()

def test_with_scaffold_is_empty_robotbase_project(tmp_path):
    d = build_scaffold(AUTHOR, "with", str(tmp_path))
    p = pathlib.Path(d)
    assert (p / "robotbase.yaml").is_file()
    assert (p / "robots").is_dir() and not any((p / "robots").iterdir())
    assert (p / "TASK.md").read_text().startswith("Build a robot")

def test_without_scaffold_is_empty_colcon_ws_with_orientation(tmp_path):
    d = build_scaffold(AUTHOR, "without", str(tmp_path))
    p = pathlib.Path(d)
    assert (p / "src" / "authored_pkg" / "package.xml").is_file()
    orient = (p / "RAW-ROS-ORIENTATION.md").read_text().lower()
    assert "gazebo harmonic" in orient and "ros_gz_sim create" in orient
    assert "<robot" not in orient and "<sensor" not in orient  # NO templates

def test_controller_is_byte_identical_across_arms(tmp_path):
    w = build_scaffold(AUTHOR, "with", str(tmp_path / "a"))
    wo = build_scaffold(AUTHOR, "without", str(tmp_path / "b"))
    assert _controller_bytes(w) == _controller_bytes(wo)

def test_import_scaffold_ships_vendor_urdf(tmp_path):
    d = build_scaffold(IMPORT, "with", str(tmp_path))
    assert (pathlib.Path(d) / "vendor_bot.urdf").is_file()
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_robotbench_scaffolds.py -v`
Expected: FAIL (no `scaffolds` module).

- [ ] **Step 3: Write `RAW-ROS-ORIENTATION.md` (env-only, NO templates)**

Content covers ONLY: distro=Jazzy; sim=Gazebo Harmonic headless llvmpipe; how to build (`colcon build`), launch (`ros2 launch <pkg> bringup.launch.py`), spawn (`ros_gz_sim create -x -y -z`, note `<pose>` is ignored); where `urdf/ worlds/ launch/ package.xml` go; the bring-up contract (judge runs `ros2 launch authored_pkg bringup.launch.py`, robot must spawn as model `robot`, expose `/cmd_vel` + `/scan`). **No robot XML, no `<sensor>` snippets, no example URDF/SDF.** (This is the parity mirror of `AGENTS.md`.)

- [ ] **Step 4: Implement `scaffolds.py` + the `vendor_bot.urdf` fixture**

Create `robotbase/robotbench/fixtures/vendor_bot.urdf` (a plain diff-drive base, no sensors — hand-written minimal URDF). Implement `build_scaffold` per the Interfaces block: make dirs, write a minimal `robotbase.yaml`, `package.xml`, `setup.py`, copy the controller from `fixtures/controllers/stop_at_1m.py`, write `TASK.md` = `task["prompt"]`, copy `RAW-ROS-ORIENTATION.md` (without only), copy `import_urdf` when `kind=="import"`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_robotbench_scaffolds.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add robotbase/robotbench/scaffolds.py robotbase/robotbench/fixtures/ tests/test_robotbench_scaffolds.py
git commit -m "feat(robotbench): per-arm authoring scaffolds + env-only orientation"
```

---

## Task 4: Authoring prompt + kind-aware arm context

**Files:**
- Modify: `robotbase/robotbench/arms.py`
- Test: `tests/test_robotbench_arms_author.py`

**Interfaces:**
- Consumes: task dict (with `kind`, `prompt`, `model_name`).
- Produces: `build_author_prompt(task: dict, arm: str) -> str` (task prompt verbatim + shared rules incl. "do NOT modify the provided controller", verify-before-claim, the interface contract, and the arm's bring-up command). `arm_context(arm, project_dir, task)` returns the authoring prompt when `task["kind"]` in `{"author","import"}`; WITH tools `["robotbase-mcp"]`+`["AGENTS.md"]`, WITHOUT tools `["bash","read","edit","write"]`+`["RAW-ROS-ORIENTATION.md"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_robotbench_arms_author.py
from robotbase.robotbench.arms import build_author_prompt, arm_context

T = {"id": "author/diff-lidar-world", "kind": "author", "model_name": "robot",
     "prompt": "Build a diff-drive robot with a LiDAR."}

def test_prompt_is_identical_task_text_both_arms():
    w = build_author_prompt(T, "with"); wo = build_author_prompt(T, "without")
    assert T["prompt"] in w and T["prompt"] in wo

def test_prompt_forbids_editing_controller_and_states_contract():
    p = build_author_prompt(T, "with").lower()
    assert "do not modify" in p and "/cmd_vel" in p and "/scan" in p and "model" in p

def test_bringup_command_differs_by_arm():
    assert "robotbase up" in build_author_prompt(T, "with")
    assert "ros2 launch" in build_author_prompt(T, "without")

def test_arm_context_wires_tools_and_docs():
    assert arm_context("with", "/p", T)["tools"] == ["robotbase-mcp"]
    ctx = arm_context("without", "/p", T)
    assert "bash" in ctx["tools"] and ctx["docs"] == ["RAW-ROS-ORIENTATION.md"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_robotbench_arms_author.py -v`
Expected: FAIL (`build_author_prompt` undefined).

- [ ] **Step 3: Implement in `arms.py`**

Add `build_author_prompt(task, arm)`: task prompt verbatim + rules block (only author robot/world/package/launch; **do not modify the provided controller**; do not claim success until you have verified the robot's behavior yourself; when finished, stop) + the interface-contract sentence (subscribe `/cmd_vel`, publish `/scan`, spawn model `robot`) + the arm's bring-up line (`robotbase up` / `ros2 launch authored_pkg bringup.launch.py`). Extend `arm_context` with a `kind`-aware branch that returns this prompt and the tool/doc wiring above; keep the existing fix-task branch for backward-compat tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_robotbench_arms_author.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add robotbase/robotbench/arms.py tests/test_robotbench_arms_author.py
git commit -m "feat(robotbench): kind-aware authoring prompt + arm context"
```

---

## Task 5: Acceptance-spec registry + predicate logic (pure)

**Files:**
- Create: `robotbase/robotbench/acceptance.py`
- Test: `tests/test_robotbench_acceptance.py`

**Interfaces:**
- Produces: `SPECS: dict[str, AcceptanceSpec]` keyed by `judge_scenario`. `AcceptanceSpec` (dataclass): `world_obstacles` (name→(x,y,half_extent)), `spawn_range` (x/y jitter for seeded poses), `duration_s`, `requires` (e.g. `["scan"]` or `["scan","image"]`), and `predicate(trace: list[tuple[float,float,float]], obstacles) -> bool`. Pure `min_distance_to(trace, ox, oy) -> float` helper. `spawn_pose(spec, seed) -> tuple[float,float,float]` (deterministic per seed).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_robotbench_acceptance.py
from robotbase.robotbench.acceptance import SPECS, min_distance_to, spawn_pose

def test_stop_at_1m_passes_when_stopped_in_band():
    spec = SPECS["author_stop_at_1m"]
    trace = [(t*0.1, x, 0.0) for t, x in enumerate([0.0,0.4,0.8,1.0,1.05,1.05,1.05])]
    assert spec.predicate(trace, spec.world_obstacles) is True     # min gap ~ 0.95 m

def test_stop_at_1m_fails_on_collision():
    spec = SPECS["author_stop_at_1m"]
    trace = [(i*0.1, i*0.25, 0.0) for i in range(12)]              # drives into box at x=2
    assert spec.predicate(trace, spec.world_obstacles) is False

def test_mast_clear_requires_pass_low_stop_tall():
    spec = SPECS["author_mast_clear"]
    # passes low barrier at x=2 (gap<0.5), stops ~1 m before tall box at x=3.5
    trace = [(i*0.1, x, 0.0) for i, x in enumerate([0,0.5,1.0,1.5,2.0,2.4,2.5,2.5])]
    assert spec.predicate(trace, spec.world_obstacles) is True

def test_spawn_pose_is_deterministic_per_seed():
    spec = SPECS["author_stop_at_1m"]
    assert spawn_pose(spec, 3) == spawn_pose(spec, 3) != spawn_pose(spec, 4)

def test_min_distance_helper():
    assert round(min_distance_to([(0,0,0),(0,1,0)], 0.0, 3.0), 2) == 2.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_robotbench_acceptance.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Implement `acceptance.py`**

Define `AcceptanceSpec` dataclass + `min_distance_to` (min Euclidean over trace to (ox,oy) minus obstacle half-extent, i.e. gap to face) + `spawn_pose` (seeded deterministic jitter within `spawn_range`). Register three specs:
- `author_stop_at_1m`: box at (2,0) half-extent 0.25; predicate = min gap to box ∈ [0.8,1.2] AND never < 0.4 (no penetration); `requires=["scan"]`.
- `author_mast_clear`: low barrier (2,0), tall box (3.5,0); predicate = min gap to **low barrier** < 0.5 (drove past) AND min gap to **tall box** ∈ [0.8,1.2]; `requires=["scan"]`.
- `author_two_sensor`: same geometry/predicate as `author_stop_at_1m`; `requires=["scan","image"]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_robotbench_acceptance.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add robotbase/robotbench/acceptance.py tests/test_robotbench_acceptance.py
git commit -m "feat(robotbench): acceptance-spec registry + pure predicate logic"
```

---

## Task 6: Author judge orchestration (offline-testable)

**Files:**
- Create: `robotbase/robotbench/author_judge.py`
- Test: `tests/test_robotbench_author_judge.py`

**Interfaces:**
- Consumes: `SPECS`/`spawn_pose` (Task 5); `gz_probe.sample_model_pose` + `cmd_vel_is_live` (Task 0) — both injected for testability; a `bringup_fn(project_dir, spawn_pose) -> teardown_callable`; a `run_controller_fn(project_dir, duration_s) -> None`.
- Produces: `author_judge(project_dir, task, *, bringup_fn, run_controller_fn, sample_fn, liveness_fn, evidence_dir=None, trials=3, seed=0) -> {"robustness": float, "solved": bool}`. Per seed: bring up at spawn pose → check `requires` interfaces live (fail trial if missing) → run controller → sample ground-truth trace → predicate → teardown. Writes each seed's trace + verdict under `evidence_dir` when given. `robustness = passes/trials`, `solved = robustness == 1.0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_robotbench_author_judge.py
import json, pathlib
from robotbase.robotbench.author_judge import author_judge

TASK = {"id": "author/diff-lidar-world", "judge_scenario": "author_stop_at_1m",
        "model_name": "robot"}

def _fakes(trace, live=True):
    calls = {"up": 0, "down": 0}
    def bringup(project, pose):
        calls["up"] += 1
        return lambda: calls.__setitem__("down", calls["down"] + 1)
    return calls, bringup, (lambda p, d: None), (lambda m, d, hz=10: trace), (lambda need, t: live)

def test_solved_when_all_trials_pass(tmp_path):
    good = [(i*0.1, x, 0.0) for i, x in enumerate([0,0.4,0.8,1.0,1.05,1.05])]
    calls, bringup, runc, sample, live = _fakes(good)
    out = author_judge("/p", TASK, bringup_fn=bringup, run_controller_fn=runc,
                       sample_fn=sample, liveness_fn=live, trials=3,
                       evidence_dir=str(tmp_path))
    assert out == {"robustness": 1.0, "solved": True}
    assert calls["up"] == 3 and calls["down"] == 3                 # torn down every trial
    assert len(list(pathlib.Path(tmp_path).glob("seed-*/verdict.json"))) == 3

def test_missing_interface_fails_trial_without_running():
    _, bringup, runc, sample, _ = _fakes([(0,0,0)])
    out = author_judge("/p", TASK, bringup_fn=bringup, run_controller_fn=runc,
                       sample_fn=sample, liveness_fn=(lambda need, t: False), trials=2)
    assert out["solved"] is False and out["robustness"] == 0.0

def test_teardown_runs_even_if_controller_raises():
    calls, bringup, _, sample, live = _fakes([(0,0,0)])
    def boom(p, d): raise RuntimeError("controller crashed")
    out = author_judge("/p", TASK, bringup_fn=bringup, run_controller_fn=boom,
                       sample_fn=sample, liveness_fn=live, trials=1)
    assert out["solved"] is False and calls["down"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_robotbench_author_judge.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Implement `author_judge.py`**

Look up `SPECS[task["judge_scenario"]]`. Loop `trials` seeds: compute `spawn_pose(spec, seed)`; `teardown = bringup_fn(project_dir, pose)`; in a `try/finally` that always calls `teardown()`: if `not liveness_fn(spec.requires, timeout)` → record fail, continue; `run_controller_fn(project_dir, spec.duration_s)`; `trace = sample_fn(task["model_name"], spec.duration_s)`; `ok = spec.predicate(trace, spec.world_obstacles)`; write `evidence_dir/seed-<n>/{trace.json,verdict.json}` when set. Aggregate.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_robotbench_author_judge.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add robotbase/robotbench/author_judge.py tests/test_robotbench_author_judge.py
git commit -m "feat(robotbench): behavioral author judge (offline-tested with fakes)"
```

---

## Task 7: Runner integration + durable run manifest

**Files:**
- Modify: `robotbase/robotbench/runner.py`
- Test: `tests/test_robotbench_runner.py` (extend)

**Interfaces:**
- Consumes: `author_judge` (via an injected `judge_fn` that already closes over the arm's bring-up), the existing `run_trial` signature.
- Produces: `run_trial` accepts `judge_fn` that returns `{"robustness","solved"}` (unchanged shape) — no signature change needed; the **new** work is a `write_manifest(run_dir, meta) -> None` helper and a `new_run_dir(results_root) -> str` (timestamped `runs/<UTC>-v2/`). `run(...)` writes `manifest.json` at start and the report at end into the run dir.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_robotbench_runner.py
def test_new_run_dir_and_manifest(tmp_path):
    from robotbase.robotbench.runner import new_run_dir, write_manifest
    import json, pathlib
    d = new_run_dir(str(tmp_path))
    assert pathlib.Path(d).is_dir() and "runs/" in d.replace("\\", "/")
    write_manifest(d, {"model": "claude-sonnet-5", "benchmark": 2, "seeds": [0,1,2]})
    m = json.loads((pathlib.Path(d) / "manifest.json").read_text())
    assert m["model"] == "claude-sonnet-5" and m["benchmark"] == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_robotbench_runner.py::test_new_run_dir_and_manifest -v`
Expected: FAIL (`new_run_dir` undefined).

- [ ] **Step 3: Implement `new_run_dir` + `write_manifest`**

Add both helpers to `runner.py` (`new_run_dir` = `os.makedirs(results_root + f"/runs/{utc}-v2", exist_ok=True)`; `write_manifest` = json dump). Keep `run_trial`'s existing transcript persistence; the judge-evidence dir is passed through the `judge_fn` closure (built in `cli_deps`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_robotbench_runner.py -v`
Expected: PASS (all, incl. the new one).

- [ ] **Step 5: Commit**

```bash
git add robotbase/robotbench/runner.py tests/test_robotbench_runner.py
git commit -m "feat(robotbench): durable timestamped run dir + manifest"
```

---

## Task 8: Real dependency wiring (`cli_deps`)

**Files:**
- Modify: `robotbase/robotbench/cli_deps.py`
- Test: `tests/test_robotbench_cli_deps.py` (extend/create — fakeable parts only)

**Interfaces:**
- Produces: `author_generate(workdir)` → `generate(task, trial)` calling `build_scaffold` per arm (returns the arm-appropriate scaffold; the runner passes `arm`, so `generate` closes over nothing arm-specific — instead expose `author_generate(workdir, arm)`); `real_bringup_with(project, pose)` (`robotbase up` after spawning) and `real_bringup_without(project, pose)` (`colcon build` + `ros2 launch` + spawn) returning teardown callables; `real_run_controller(project, duration)` (`ros2 run`/python the provided controller for `duration`); `real_author_judge(arm, trials, evidence_root)` → a `judge_fn(project, scenario, seed)` that calls `author_judge` with the arm's bring-up + real probe.

- [ ] **Step 1: Write the failing test (structure only — no Docker)**

```python
# tests/test_robotbench_cli_deps.py
from robotbase.robotbench import cli_deps

def test_author_generate_uses_scaffold(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli_deps, "build_scaffold",
                        lambda task, arm, root: seen.setdefault("call", (arm, root)) or "/scaf")
    gen = cli_deps.author_generate(str(tmp_path), "without")
    assert gen({"id": "author/x", "kind": "author"}, 0) == "/scaf"
    assert seen["call"][0] == "without"

def test_real_author_judge_returns_callable():
    jf = cli_deps.real_author_judge("with", trials=3, evidence_root="/tmp/e")
    assert callable(jf)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_robotbench_cli_deps.py -v`
Expected: FAIL (`author_generate` undefined).

- [ ] **Step 3: Implement the real deps**

Add `author_generate`, `real_bringup_with/without`, `real_run_controller`, `real_author_judge` to `cli_deps.py`, importing `build_scaffold`, `author_judge`, and `gz_probe`. The bring-up fns honor `-x/-y/-z` spawn flags and return teardown callables (`robotbase down` / kill launch + `gz` cleanup). `real_author_judge(arm, ...)` selects the arm's bring-up fn and closes over `sample_model_pose`/`cmd_vel_is_live`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_robotbench_cli_deps.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add robotbase/robotbench/cli_deps.py tests/test_robotbench_cli_deps.py
git commit -m "feat(robotbench): real bring-up + author-judge wiring"
```

---

## Task 9: Reference solutions + live calibration (DOGFOODING GATE, live)

**Files:**
- Create: `robotbase/robotbench/fixtures/reference/<task>/` (authored robot.yaml + world per task)
- Doc: append findings to `docs/STRATEGY.md`
- Test: `tests/test_reference_solutions_live.py` (marked `live`, skipped without Docker)

**Interfaces:**
- Consumes: the whole pipeline (scaffold → author_judge). Produces: a committed known-good solution per task that the judge scores `solved == True`.

- [ ] **Step 1: Author each reference solution THROUGH the compiler by hand**

For each of the 4 tasks, write the `robot.yaml` + world (WITH-arm form) that satisfies it, using only the current compiler surface. **Record every friction point** (a sensor that won't mount, a silent-`/scan` world, a mast needing raw-SDF escape) in `docs/STRATEGY.md`'s findings log.

- [ ] **Step 2: Fix compiler friction found in Step 1 (or adjust the task)**

For each friction: if it's a compiler bug, fix it in `robotspec/`/`worldspec/` (separate commit, with a regression test) — this is the product-improving payoff of dogfooding. If it's inherent difficulty that's *fair*, leave it. Re-author until each reference solves.

- [ ] **Step 3: Write the live calibration test**

```python
# tests/test_reference_solutions_live.py
import os, pytest
pytestmark = pytest.mark.skipif(os.environ.get("ROBOTBENCH_LIVE") != "1",
                                reason="needs Docker sim")

@pytest.mark.parametrize("task_id", ["author/diff-lidar-world", "author/sensor-on-mast",
                                     "author/two-sensor", "import/add-sensor"])
def test_reference_solution_is_solved_by_judge(task_id):
    # copy the reference solution into a WITH scaffold, run the real author_judge, assert solved
    ...  # fill with the real wiring using cli_deps.real_author_judge("with", 3, ...)
```

- [ ] **Step 4: Run the live calibration**

```bash
wsl -d Ubuntu-24.04 bash -lc 'cd ~/robotbase && source .venv/bin/activate && ROBOTBENCH_LIVE=1 pytest tests/test_reference_solutions_live.py -v'
```
Expected: 4 PASS (each reference solves → the task is solvable and the judge is calibrated). If any fails, the judge or the reference is wrong — fix before proceeding.

- [ ] **Step 5: Commit**

```bash
git add robotbase/robotbench/fixtures/reference/ tests/test_reference_solutions_live.py docs/STRATEGY.md
git commit -m "feat(robotbench): reference solutions + live judge calibration (dogfooding)"
```

---

## Task 10: Report v2 + end-to-end pilot run

**Files:**
- Modify: `robotbase/robotbench/report.py` (header already version-driven; confirm v2 renders)
- Create (git-ignored): `_rbench_run_v2.py` (the batch runner, like the existing `_rbench_run.py`)
- Doc: commit the pilot `manifest.json` + `ROBOTBENCH-RESULTS.md` under `docs/`

**Interfaces:** Consumes everything above. Produces the durable run dir + the rendered report.

- [ ] **Step 1: Confirm report renders benchmark v2**

Run the existing report unit tests: `pytest tests/test_robotbench_report.py -v` — they assert the headline structure; confirm the version string now reads `v2` (driven by `BENCHMARK_VERSION`). If a test hard-codes `v1`, update it.

- [ ] **Step 2: Write `_rbench_run_v2.py`**

Mirror `_rbench_run.py` but: iterate `expand_tasks("all")` (the 4 v2 tasks) × `["with","without"]`; use `author_generate(workdir, arm)`, `real_author_judge(arm, trials=3, evidence_root=<run>/judge)`, `transcript_dir=<run>/transcripts`, `CAPS = Caps(max_turns=30, timeout_s=1100, max_edits=10)`; write records under `<run>/records`; write `manifest.json` (model, git SHA, seeds, caps); render `<run>/ROBOTBENCH-RESULTS.md`.

- [ ] **Step 3: Pilot run n=1 (background, harness-tracked)**

Launch with `run_in_background: true`:
```bash
wsl -d Ubuntu-24.04 bash -lc 'cd ~/robotbase && source .venv/bin/activate && python _rbench_run_v2.py --trials 1'
```
Expected: 8 records (4 tasks × 2 arms), transcripts + judge evidence persisted, a rendered table.

- [ ] **Step 4: Read every pilot transcript + judge evidence; fix any unfairness**

Inspect each `<run>/transcripts/*.json` and `<run>/judge/**/verdict.json`. Confirm: WITHOUT genuinely had no template help; the judge measured ground truth; no arm was blocked by a harness bug. Record observations in `docs/STRATEGY.md`.

- [ ] **Step 5: Commit the pilot artefacts + finish**

```bash
git add docs/ROBOTBENCH-RESULTS.md docs/robotbench-runs/ docs/STRATEGY.md
git commit -m "feat(robotbench): v2 pilot run (n=1) — artefacts + findings"
```
Then STOP and report to the human before the definitive n=3 (API/Docker spend). Use superpowers:finishing-a-development-branch.

---

## Self-Review

- **Spec coverage:** task kinds (T1), scaffolds+orientation (T3), fairness prompt (T4), fixed controller (T2), behavioral ground-truth judge (T0 spike, T5 predicates, T6 orchestration, T8 real bring-up), interface contract (T4 prompt + T6 liveness check), durable artefacts (T7 manifest + T6 evidence + T10 commit), dogfooding (T9), run plan pilot→n=3 (T10 + stop gate). All spec sections map to a task.
- **Placeholder scan:** Task 9 Step 3 and Task 10 Step 2 intentionally leave the live-wiring bodies to the implementer (they depend on T8's exact signatures, which are defined in T8's Interfaces block) — every offline task carries complete code.
- **Type consistency:** `judge_fn` returns `{"robustness","solved"}` throughout (T6, T8, matches existing `runner.run_trial`); `build_scaffold(task, arm, root)`, `author_judge(project_dir, task, *, ...)`, `spawn_pose(spec, seed)`, `sample_model_pose(model, duration, hz)` signatures are consistent across T3/T5/T6/T8.
