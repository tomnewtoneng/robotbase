# Robotbase Walking-Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that structured agent tools (MCP) let a coding agent autonomously close the build → test → fix loop on a ROS 2 robotics project, by hand-building one `warehouse-bot` and driving the canonical obstacle-avoidance demo end-to-end.

**Architecture:** A single hand-built ROS 2 Jazzy + Gazebo Harmonic project runs headless in Docker. A Python package (`robotbase/`) provides an in-process **runtime module** (launch/stop/reset/inspect/build), a **scenario runner** (YAML → structured JSON result), and an **MCP server** that wraps the runtime and exposes only loop-closing tools to a coding agent. Pure-logic units (schema, assertions, results, naming, MCP validation) are built test-first; sim assets and ROS/`gz` integration are validated by integration probes.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, the official Python MCP SDK (`mcp`), ROS 2 Jazzy (`rclpy`), Gazebo Harmonic (`gz sim`), the `ros_gz` bridge, Docker + Docker Compose. Dev host: Windows 11 + Docker Desktop (WSL2 backend); all commands run inside **WSL2 Ubuntu 24.04**.

## Global Constraints

- **ROS distribution:** ROS 2 **Jazzy** only. Base image `ros:jazzy-ros-base` (Ubuntu 24.04).
- **Simulator:** Gazebo **Harmonic** (`gz sim`, a.k.a. `gz-sim8`) only. No Ignition/Classic Gazebo commands.
- **Rendering:** headless, software-rendered via Mesa **llvmpipe**. Env inside sim container: `LIBGL_ALWAYS_SOFTWARE=1`, `OGRE_RTT_MODE=Copy` (fallback), no host GPU assumed.
- **Everything runs in Linux containers**; the host OS is irrelevant beyond providing Docker. Run all shell commands from the WSL2 Ubuntu 24.04 shell, with project files on the **WSL2 filesystem** (`~/robotbase`), never `/mnt/c`.
- **Localhost only.** The MCP server and any runtime endpoint bind to `127.0.0.1`. No cloud, no accounts, no auth in the core.
- **Structured, size-bounded outputs.** No tool returns unbounded raw logs; topic/log samples are capped.
- **Python:** 3.12, type-hinted, Pydantic v2 models for all external data (manifest, scenario, result).
- **TDD + frequent commits.** Pure-logic units are test-first. Commit at the end of every task.
- **Snake-case identifiers.** ROS package/module names derived from a project name must be valid Python identifiers (`warehouse-bot` → `warehouse_bot`).
- **Project root** for all paths below is `projects/Robotbase/` in the ToddyOS vault (destined to become a standalone repo).

---

## File Structure

```
projects/Robotbase/
├── pyproject.toml                     # package + pytest + deps
├── .gitignore
├── README.md
├── spike/                             # Task 1 — throwaway rendering gate
│   ├── Dockerfile
│   ├── minimal.sdf                    # world + diff-drive + gpu_lidar, single SDF
│   ├── check_scan.py                  # asserts /scan has real ranges
│   └── run-spike.sh
├── robotbase/                         # the Python package (pure + integration)
│   ├── __init__.py
│   ├── naming.py                      # Task 3 — name → snake_case
│   ├── schema.py                      # Task 4 — Pydantic manifest + scenario models
│   ├── results.py                     # Task 5 — Pydantic ScenarioResult model
│   ├── assertions.py                  # Task 6 — assertion evaluators over Metrics
│   ├── runtime.py                     # Task 8 — in-process runtime (launch/inspect/…)
│   ├── scenario_runner.py             # Task 9 — orchestrate scenario → ScenarioResult
│   └── mcp_server.py                  # Task 10 — MCP tools wrapping runtime
├── warehouse-bot/                     # Task 7 — the hand-built ROS project (system under test)
│   ├── compose.yaml
│   ├── Dockerfile
│   ├── AGENTS.md                      # Task 11
│   ├── robotbase.yaml                 # project manifest
│   ├── src/
│   │   ├── warehouse_bot/             # controller package (ament_python)
│   │   │   ├── package.xml
│   │   │   ├── setup.py
│   │   │   ├── setup.cfg
│   │   │   ├── resource/warehouse_bot
│   │   │   └── warehouse_bot/
│   │   │       ├── __init__.py
│   │   │       └── obstacle_controller.py   # intentionally-broken starter
│   │   ├── warehouse_bot_bringup/     # launch package (ament_python)
│   │   │   ├── package.xml
│   │   │   ├── setup.py
│   │   │   ├── resource/warehouse_bot_bringup
│   │   │   └── launch/simulation.launch.py
│   │   └── warehouse_bot_description/ # URDF/world assets (ament_cmake or data-only)
│   │       ├── package.xml
│   │       ├── CMakeLists.txt
│   │       ├── urdf/warehouse_bot.urdf.xacro
│   │       └── worlds/warehouse.sdf
│   └── simulation/scenarios/
│       ├── drive-forward.yaml
│       └── stop-before-obstacle.yaml
├── tests/
│   ├── test_naming.py                 # Task 3
│   ├── test_schema.py                 # Task 4
│   ├── test_results.py                # Task 5
│   ├── test_assertions.py             # Task 6
│   ├── test_scenario_runner.py        # Task 9 (with a fake runtime)
│   └── test_mcp_validation.py         # Task 10
└── docs/superpowers/
    ├── specs/2026-07-20-robotbase-walking-skeleton-design.md   # existing
    └── plans/2026-07-20-robotbase-walking-skeleton.md          # this file
```

---

## Task 1: Phase 0 rendering spike (the gate)

**This is a spike, not TDD.** It is a throwaway probe answering one question: does Gazebo Harmonic's `gpu_lidar` publish real `/scan` ranges headless under llvmpipe on this machine? **Do not proceed to Task 2 until this passes** (green light) or the platform decision is recorded (red light → move to Ubuntu laptop). Prerequisite: Docker Desktop running with WSL2 integration enabled for Ubuntu-24.04.

**Files:**
- Create: `spike/Dockerfile`, `spike/minimal.sdf`, `spike/check_scan.py`, `spike/run-spike.sh`

- [ ] **Step 1: Write the spike Dockerfile**

Create `spike/Dockerfile`:

```dockerfile
FROM ros:jazzy-ros-base

# Gazebo Harmonic + the ROS<->gz bridge for Jazzy
RUN apt-get update && apt-get install -y --no-install-recommends \
      gz-harmonic \
      ros-jazzy-ros-gz-sim \
      ros-jazzy-ros-gz-bridge \
      python3-numpy \
    && rm -rf /var/lib/apt/lists/*

ENV LIBGL_ALWAYS_SOFTWARE=1
ENV OGRE_RTT_MODE=Copy
WORKDIR /spike
COPY minimal.sdf check_scan.py ./
```

- [ ] **Step 2: Write a minimal world with a diff-drive robot + LiDAR**

Create `spike/minimal.sdf`. This is a single self-contained world: ground, one box, and a two-wheel robot carrying a `gpu_lidar`.

```xml
<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="spike">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>

    <light type="directional" name="sun">
      <cast_shadows>false</cast_shadows>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

    <model name="ground">
      <static>true</static>
      <link name="link">
        <collision name="c"><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></collision>
        <visual name="v"><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></visual>
      </link>
    </model>

    <model name="box">
      <static>true</static>
      <pose>2 0 0.25 0 0 0</pose>
      <link name="link">
        <collision name="c"><geometry><box><size>0.5 1.0 0.5</size></box></geometry></collision>
        <visual name="v"><geometry><box><size>0.5 1.0 0.5</size></box></geometry></visual>
      </link>
    </model>

    <model name="robot">
      <pose>0 0 0.1 0 0 0</pose>
      <link name="base">
        <inertial><mass>5</mass><inertia><ixx>0.1</ixx><iyy>0.1</iyy><izz>0.1</izz></inertia></inertial>
        <collision name="c"><geometry><box><size>0.3 0.3 0.2</size></box></geometry></collision>
        <visual name="v"><geometry><box><size>0.3 0.3 0.2</size></box></geometry></visual>
        <sensor name="lidar" type="gpu_lidar">
          <pose>0.15 0 0.1 0 0 0</pose>
          <topic>scan</topic>
          <update_rate>10</update_rate>
          <always_on>true</always_on>
          <visualize>false</visualize>
          <lidar>
            <scan><horizontal><samples>180</samples><resolution>1</resolution>
              <min_angle>-1.5708</min_angle><max_angle>1.5708</max_angle></horizontal></scan>
            <range><min>0.08</min><max>10.0</max><resolution>0.01</resolution></range>
          </lidar>
        </sensor>
      </link>
    </model>
  </world>
</sdf>
```

- [ ] **Step 3: Write the `/scan` checker**

Create `spike/check_scan.py`. It subscribes to `/scan`, waits up to 15 s, and asserts at least one message arrives with finite range values inside the sensor limits.

```python
import sys
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

class ScanCheck(Node):
    def __init__(self):
        super().__init__("scan_check")
        self.ok = False
        self.create_subscription(LaserScan, "/scan", self._cb, 10)

    def _cb(self, msg: LaserScan):
        finite = [r for r in msg.ranges if msg.range_min <= r <= msg.range_max]
        if len(finite) >= 10:
            self.get_logger().info(f"/scan OK: {len(finite)} finite ranges, min={min(finite):.2f}")
            self.ok = True

def main():
    rclpy.init()
    node = ScanCheck()
    end = node.get_clock().now().nanoseconds + 15 * 1_000_000_000
    while rclpy.ok() and not node.ok and node.get_clock().now().nanoseconds < end:
        rclpy.spin_once(node, timeout_sec=0.5)
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if node.ok else 1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write the spike runner**

Create `spike/run-spike.sh`. It launches `gz sim` headless in the background, bridges `/scan` from gz to ROS, then runs the checker.

```bash
#!/usr/bin/env bash
set -euo pipefail
source /opt/ros/jazzy/setup.bash

# Headless Gazebo server only (-s), run the world, start unpaused (-r)
gz sim -s -r --headless-rendering minimal.sdf &
GZ_PID=$!

# Bridge the gz LiDAR topic to a ROS 2 /scan topic
ros2 run ros_gz_bridge parameter_bridge \
  /scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan &
BRIDGE_PID=$!

sleep 5
set +e
python3 check_scan.py
RESULT=$?
set -e

kill $BRIDGE_PID $GZ_PID 2>/dev/null || true
exit $RESULT
```

- [ ] **Step 5: Build and run the spike**

Run (from `projects/Robotbase/spike`, inside WSL2):

```bash
docker build -t robotbase-spike .
docker run --rm robotbase-spike bash run-spike.sh
```

Expected on green light: log line `/scan OK: <N> finite ranges ...` and container exit code `0`.
Expected on red light: exit code `1` or a rendering/ogre2 error in the `gz sim` output.

- [ ] **Step 6: Record the outcome and commit the spike**

If green: note "Phase 0 GREEN on Windows/WSL2" in the design spec's §9 risk 1. If red: note the exact error and switch the dev target to the Ubuntu laptop before Task 2. Either way commit the spike so the probe is reproducible:

```bash
git add spike/
git commit -m "spike: phase 0 headless gazebo lidar rendering probe"
```

---

## Task 2: Python package scaffolding

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `robotbase/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: an installable `robotbase` package and a working `pytest` command for all later tasks.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "robotbase"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.6",
    "pyyaml>=6.0",
    "mcp>=1.2",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["robotbase*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
.pytest_cache/
build/
install/
log/
.robotbase/
*.egg-info/
```

- [ ] **Step 3: Create empty package markers**

Create `robotbase/__init__.py` containing `__version__ = "0.1.0"` and an empty `tests/__init__.py`.

- [ ] **Step 4: Create the venv and install**

Run (inside WSL2):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Expected: `pip install` succeeds; `pytest` reports `no tests ran` (exit 5) — acceptable, no tests yet.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore robotbase/__init__.py tests/__init__.py
git commit -m "chore: scaffold robotbase python package"
```

---

## Task 3: Project-name conversion utility

**Files:**
- Create: `robotbase/naming.py`, `tests/test_naming.py`

**Interfaces:**
- Produces: `to_snake_identifier(name: str) -> str` — lowercases, replaces `-`/spaces with `_`, and raises `ValueError` for names that cannot form a valid Python identifier.

- [ ] **Step 1: Write the failing test**

Create `tests/test_naming.py`:

```python
import pytest
from robotbase.naming import to_snake_identifier

def test_hyphen_to_underscore():
    assert to_snake_identifier("warehouse-bot") == "warehouse_bot"

def test_spaces_and_case():
    assert to_snake_identifier("Warehouse Bot") == "warehouse_bot"

def test_already_valid():
    assert to_snake_identifier("obstacle_bot") == "obstacle_bot"

def test_leading_digit_rejected():
    with pytest.raises(ValueError):
        to_snake_identifier("2bot")

def test_empty_rejected():
    with pytest.raises(ValueError):
        to_snake_identifier("")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_naming.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'robotbase.naming'`.

- [ ] **Step 3: Write minimal implementation**

Create `robotbase/naming.py`:

```python
import re

def to_snake_identifier(name: str) -> str:
    """Convert a project name into a valid snake_case Python identifier."""
    snake = re.sub(r"[\s-]+", "_", name.strip().lower())
    snake = re.sub(r"[^a-z0-9_]", "", snake)
    if not snake or not snake.isidentifier():
        raise ValueError(f"Cannot derive a valid identifier from {name!r}")
    return snake
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_naming.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add robotbase/naming.py tests/test_naming.py
git commit -m "feat: project-name to snake_case identifier conversion"
```

---

## Task 4: Manifest + scenario schema (Pydantic)

**Files:**
- Create: `robotbase/schema.py`, `tests/test_schema.py`

**Interfaces:**
- Produces:
  - `Manifest.from_yaml(path: str) -> Manifest` with fields `project_name: str`, `ros_distribution: str`, `simulator: str`, `launch_package: str`, `launch_file: str`, `scenarios_dir: str`, `mcp_port: int`. Raises `ManifestError` on invalid version/distro/simulator.
  - `Scenario.from_yaml(path: str) -> Scenario` exposing `name`, `description`, `timeout_seconds`, `setup: SetupSpec`, `actions: list[ActionSpec]`, `assertions: list[AssertionSpec]`.
  - `AssertionSpec` (`.type: str` plus type-specific optional fields `minimum_metres`, `linear_velocity_tolerance`, `angular_velocity_tolerance`, `topic`, `minimum_count`, `minimum_distance_metres`).
  - Exception `ManifestError`, `ScenarioError`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_schema.py`:

```python
import textwrap, pytest
from robotbase.schema import Scenario, Manifest, ManifestError

def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(textwrap.dedent(body))
    return str(p)

def test_scenario_parses(tmp_path):
    path = _write(tmp_path, "s.yaml", """
        version: 1
        name: stop-before-obstacle
        description: stop before the box
        timeout_seconds: 30
        setup:
          reset_world: true
          robot: {pose: {x: 0.0, y: 0.0, yaw: 0.0}}
          obstacles:
            - {id: o1, type: box, pose: {x: 2.0, y: 0.0, z: 0.25}, size: {x: 0.5, y: 1.0, z: 0.5}}
        actions:
          - {type: wait_for_topic, topic: /scan, timeout_seconds: 5}
          - {type: run_node, package: warehouse_bot, executable: obstacle_controller}
          - {type: wait, duration_seconds: 10}
        assertions:
          - {type: no_collision}
          - {type: minimum_obstacle_distance, minimum_metres: 0.25}
          - {type: robot_stopped, linear_velocity_tolerance: 0.03, angular_velocity_tolerance: 0.03}
          - {type: required_topic_messages, topic: /scan, minimum_count: 5}
    """)
    s = Scenario.from_yaml(path)
    assert s.name == "stop-before-obstacle"
    assert s.timeout_seconds == 30
    assert [a.type for a in s.assertions][0] == "no_collision"
    assert s.assertions[1].minimum_metres == 0.25

def test_manifest_rejects_bad_simulator(tmp_path):
    path = _write(tmp_path, "m.yaml", """
        version: 1
        project: {name: warehouse-bot}
        runtime: {ros_distribution: jazzy, simulator: webots}
        launch: {package: warehouse_bot_bringup, file: simulation.launch.py}
        scenarios: {directory: simulation/scenarios}
        agent: {mcp: {enabled: true, port: 4381}}
    """)
    with pytest.raises(ManifestError):
        Manifest.from_yaml(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'robotbase.schema'`.

- [ ] **Step 3: Write minimal implementation**

Create `robotbase/schema.py`:

```python
from __future__ import annotations
import yaml
from pydantic import BaseModel, ValidationError

SUPPORTED_DISTROS = {"jazzy"}
SUPPORTED_SIMULATORS = {"gazebo-harmonic"}

class ManifestError(ValueError): ...
class ScenarioError(ValueError): ...

class Pose(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0

class Size(BaseModel):
    x: float
    y: float
    z: float

class ObstacleSpec(BaseModel):
    id: str
    type: str = "box"
    pose: Pose
    size: Size

class RobotSetup(BaseModel):
    pose: Pose = Pose()

class SetupSpec(BaseModel):
    reset_world: bool = True
    robot: RobotSetup = RobotSetup()
    obstacles: list[ObstacleSpec] = []

class ActionSpec(BaseModel):
    type: str
    topic: str | None = None
    timeout_seconds: float | None = None
    duration_seconds: float | None = None
    package: str | None = None
    executable: str | None = None

class AssertionSpec(BaseModel):
    type: str
    minimum_metres: float | None = None
    minimum_distance_metres: float | None = None
    linear_velocity_tolerance: float | None = None
    angular_velocity_tolerance: float | None = None
    topic: str | None = None
    minimum_count: int | None = None

class Scenario(BaseModel):
    version: int
    name: str
    description: str = ""
    timeout_seconds: float = 30
    setup: SetupSpec = SetupSpec()
    actions: list[ActionSpec] = []
    assertions: list[AssertionSpec] = []

    @classmethod
    def from_yaml(cls, path: str) -> "Scenario":
        with open(path) as f:
            data = yaml.safe_load(f)
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise ScenarioError(str(e)) from e

class Manifest(BaseModel):
    project_name: str
    ros_distribution: str
    simulator: str
    launch_package: str
    launch_file: str
    scenarios_dir: str
    mcp_port: int

    @classmethod
    def from_yaml(cls, path: str) -> "Manifest":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            m = cls(
                project_name=data["project"]["name"],
                ros_distribution=data["runtime"]["ros_distribution"],
                simulator=data["runtime"]["simulator"],
                launch_package=data["launch"]["package"],
                launch_file=data["launch"]["file"],
                scenarios_dir=data["scenarios"]["directory"],
                mcp_port=data["agent"]["mcp"]["port"],
            )
        except (KeyError, TypeError, ValidationError) as e:
            raise ManifestError(f"Invalid manifest: {e}") from e
        if data.get("version") != 1:
            raise ManifestError("Unsupported manifest version")
        if m.ros_distribution not in SUPPORTED_DISTROS:
            raise ManifestError(f"Unsupported ROS distribution: {m.ros_distribution}")
        if m.simulator not in SUPPORTED_SIMULATORS:
            raise ManifestError(f"Unsupported simulator: {m.simulator}")
        return m
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schema.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add robotbase/schema.py tests/test_schema.py
git commit -m "feat: pydantic manifest and scenario schema with validation"
```

---

## Task 5: Scenario result model

**Files:**
- Create: `robotbase/results.py`, `tests/test_results.py`

**Interfaces:**
- Produces:
  - `Metrics` model: `collision_count: int`, `minimum_obstacle_distance_metres: float | None`, `distance_travelled_metres: float`, `final_linear_velocity: float`, `final_angular_velocity: float`, plus `topic_message_counts: dict[str, int]`.
  - `AssertionResult` model: `type: str`, `passed: bool`, `expected`, `actual` (both `float | int | None`), `detail: str = ""`.
  - `ScenarioResult` model with fields from spec §14, a `passed` computed at construction from `all(a.passed for a in assertions)`, and `write(run_dir: str) -> str` that writes `<run_dir>/result.json` and returns the path.
  - `new_run_id() -> str`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_results.py`:

```python
import json
from robotbase.results import Metrics, AssertionResult, ScenarioResult, new_run_id

def test_run_id_unique():
    assert new_run_id() != new_run_id()

def test_passed_is_conjunction():
    r = ScenarioResult(
        run_id="run_x", scenario="s",
        metrics=Metrics(collision_count=0, minimum_obstacle_distance_metres=0.4,
                        distance_travelled_metres=2.0, final_linear_velocity=0.0,
                        final_angular_velocity=0.0, topic_message_counts={"/scan": 20}),
        assertions=[AssertionResult(type="no_collision", passed=True),
                    AssertionResult(type="robot_stopped", passed=False)],
    )
    assert r.passed is False

def test_write_creates_json(tmp_path):
    r = ScenarioResult(run_id="run_y", scenario="s",
                       metrics=Metrics(collision_count=0, minimum_obstacle_distance_metres=None,
                                       distance_travelled_metres=1.0, final_linear_velocity=0.0,
                                       final_angular_velocity=0.0, topic_message_counts={}),
                       assertions=[AssertionResult(type="no_collision", passed=True)])
    path = r.write(str(tmp_path))
    data = json.loads(open(path).read())
    assert data["run_id"] == "run_y"
    assert data["passed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_results.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'robotbase.results'`.

- [ ] **Step 3: Write minimal implementation**

Create `robotbase/results.py`:

```python
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pydantic import BaseModel, model_validator

def new_run_id() -> str:
    return "run_" + uuid.uuid4().hex[:12]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class Metrics(BaseModel):
    collision_count: int = 0
    minimum_obstacle_distance_metres: float | None = None
    distance_travelled_metres: float = 0.0
    final_linear_velocity: float = 0.0
    final_angular_velocity: float = 0.0
    topic_message_counts: dict[str, int] = {}

class AssertionResult(BaseModel):
    type: str
    passed: bool
    expected: float | int | None = None
    actual: float | int | None = None
    detail: str = ""

class Diagnostic(BaseModel):
    source: str
    level: str
    message: str

class ScenarioResult(BaseModel):
    run_id: str
    scenario: str
    passed: bool = False
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    metrics: Metrics
    assertions: list[AssertionResult] = []
    diagnostics: list[Diagnostic] = []

    @model_validator(mode="after")
    def _compute_passed(self) -> "ScenarioResult":
        object.__setattr__(self, "passed",
                           bool(self.assertions) and all(a.passed for a in self.assertions))
        return self

    def write(self, run_dir: str) -> str:
        os.makedirs(run_dir, exist_ok=True)
        path = os.path.join(run_dir, "result.json")
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))
        return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_results.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add robotbase/results.py tests/test_results.py
git commit -m "feat: scenario result model with json persistence"
```

---

## Task 6: Assertion evaluators

**Files:**
- Create: `robotbase/assertions.py`, `tests/test_assertions.py`

**Interfaces:**
- Consumes: `AssertionSpec` (Task 4), `Metrics` and `AssertionResult` (Task 5).
- Produces: `evaluate(spec: AssertionSpec, metrics: Metrics) -> AssertionResult`. Supports the minimal set: `no_collision`, `robot_stopped`, `minimum_obstacle_distance`, `required_topic_messages`, `robot_moved_minimum_distance`. Unknown types return `passed=False` with a detail message.

- [ ] **Step 1: Write the failing test**

Create `tests/test_assertions.py`:

```python
from robotbase.schema import AssertionSpec
from robotbase.results import Metrics
from robotbase.assertions import evaluate

BASE = dict(collision_count=0, minimum_obstacle_distance_metres=0.4,
            distance_travelled_metres=2.0, final_linear_velocity=0.0,
            final_angular_velocity=0.0, topic_message_counts={"/scan": 20})

def m(**over): return Metrics(**{**BASE, **over})

def test_no_collision_pass_and_fail():
    assert evaluate(AssertionSpec(type="no_collision"), m()).passed is True
    assert evaluate(AssertionSpec(type="no_collision"), m(collision_count=1)).passed is False

def test_min_distance():
    spec = AssertionSpec(type="minimum_obstacle_distance", minimum_metres=0.25)
    assert evaluate(spec, m(minimum_obstacle_distance_metres=0.4)).passed is True
    assert evaluate(spec, m(minimum_obstacle_distance_metres=0.1)).passed is False

def test_robot_stopped():
    spec = AssertionSpec(type="robot_stopped", linear_velocity_tolerance=0.03,
                         angular_velocity_tolerance=0.03)
    assert evaluate(spec, m(final_linear_velocity=0.01, final_angular_velocity=0.0)).passed is True
    assert evaluate(spec, m(final_linear_velocity=0.2)).passed is False

def test_required_topic_messages():
    spec = AssertionSpec(type="required_topic_messages", topic="/scan", minimum_count=5)
    assert evaluate(spec, m(topic_message_counts={"/scan": 20})).passed is True
    assert evaluate(spec, m(topic_message_counts={"/scan": 2})).passed is False

def test_unknown_type_fails():
    assert evaluate(AssertionSpec(type="teleport_check"), m()).passed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assertions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'robotbase.assertions'`.

- [ ] **Step 3: Write minimal implementation**

Create `robotbase/assertions.py`:

```python
from __future__ import annotations
from robotbase.schema import AssertionSpec
from robotbase.results import Metrics, AssertionResult

def evaluate(spec: AssertionSpec, metrics: Metrics) -> AssertionResult:
    t = spec.type
    if t == "no_collision":
        ok = metrics.collision_count == 0
        return AssertionResult(type=t, passed=ok, expected=0, actual=metrics.collision_count)

    if t == "minimum_obstacle_distance":
        actual = metrics.minimum_obstacle_distance_metres
        ok = actual is not None and actual >= (spec.minimum_metres or 0.0)
        return AssertionResult(type=t, passed=ok, expected=spec.minimum_metres, actual=actual)

    if t == "robot_stopped":
        lin_ok = abs(metrics.final_linear_velocity) <= (spec.linear_velocity_tolerance or 0.0)
        ang_ok = abs(metrics.final_angular_velocity) <= (spec.angular_velocity_tolerance or 0.0)
        return AssertionResult(type=t, passed=lin_ok and ang_ok,
                               actual=metrics.final_linear_velocity)

    if t == "required_topic_messages":
        count = metrics.topic_message_counts.get(spec.topic or "", 0)
        ok = count >= (spec.minimum_count or 0)
        return AssertionResult(type=t, passed=ok, expected=spec.minimum_count, actual=count)

    if t == "robot_moved_minimum_distance":
        target = spec.minimum_distance_metres or 0.0
        ok = metrics.distance_travelled_metres >= target
        return AssertionResult(type=t, passed=ok, expected=target,
                               actual=metrics.distance_travelled_metres)

    return AssertionResult(type=t, passed=False, detail=f"Unknown assertion type: {t}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assertions.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add robotbase/assertions.py tests/test_assertions.py
git commit -m "feat: assertion evaluators over scenario metrics"
```

---

## Task 7: The hand-built `warehouse-bot` ROS project

**This is integration work validated by build + launch probes, not unit tests.** It produces the system-under-test: a diff-drive robot in a warehouse world that launches headless and exposes `/scan`, `/odom`, `/cmd_vel`, `/tf`, plus the intentionally-broken starter controller.

**Files:** all under `warehouse-bot/` (see File Structure). Create the three ROS packages, the world, the launch file, the manifest, the Dockerfile, and compose file.

- [ ] **Step 1: Write the controller package manifest and setup**

Create `warehouse-bot/src/warehouse_bot/package.xml`:

```xml
<?xml version="1.0"?>
<package format="3">
  <name>warehouse_bot</name>
  <version>0.1.0</version>
  <description>Warehouse bot controller (starter).</description>
  <maintainer email="tom@example.com">Tom</maintainer>
  <license>MIT</license>
  <depend>rclpy</depend>
  <depend>geometry_msgs</depend>
  <depend>sensor_msgs</depend>
  <depend>nav_msgs</depend>
  <export><build_type>ament_python</build_type></export>
</package>
```

Create `warehouse-bot/src/warehouse_bot/setup.py`:

```python
from setuptools import setup
package_name = "warehouse_bot"
setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Tom",
    maintainer_email="tom@example.com",
    description="Warehouse bot controller (starter).",
    license="MIT",
    entry_points={"console_scripts": [
        "obstacle_controller = warehouse_bot.obstacle_controller:main",
    ]},
)
```

Create `warehouse-bot/src/warehouse_bot/setup.cfg`:

```ini
[develop]
script_dir=$base/lib/warehouse_bot
[install]
install_scripts=$base/lib/warehouse_bot
```

Create empty `warehouse-bot/src/warehouse_bot/resource/warehouse_bot` and `warehouse-bot/src/warehouse_bot/warehouse_bot/__init__.py`.

- [ ] **Step 2: Write the intentionally-broken starter controller**

Create `warehouse-bot/src/warehouse_bot/warehouse_bot/obstacle_controller.py`:

```python
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan

class ObstacleController(Node):
    """Starter controller.

    The initial implementation drives forward without reacting correctly to
    obstacles. The coding agent is expected to improve it so the robot stops
    before hitting the box.
    """
    def __init__(self):
        super().__init__("obstacle_controller")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(LaserScan, "/scan", self._on_scan, 10)
        self.create_timer(0.1, self._tick)

    def _on_scan(self, msg: LaserScan):
        # Starter bug: LiDAR data is ignored entirely.
        pass

    def _tick(self):
        cmd = Twist()
        cmd.linear.x = 0.3  # always forward, never stops
        self.pub.publish(cmd)

def main():
    rclpy.init()
    node = ObstacleController()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write the description package (URDF + world)**

Create `warehouse-bot/src/warehouse_bot_description/package.xml` (build_type `ament_cmake`), `CMakeLists.txt` that installs `urdf/` and `worlds/`, `urdf/warehouse_bot.urdf.xacro` (a diff-drive robot: base link, two wheel joints with the `gz::sim::systems::DiffDrive` plugin publishing `/odom` and consuming `/cmd_vel`, a `gpu_lidar` publishing `scan`), and `worlds/warehouse.sdf` (ground plane, four walls, a goal marker, empty space for a spawned box; reuse the plugin/light/physics blocks from `spike/minimal.sdf`).

`CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.8)
project(warehouse_bot_description)
find_package(ament_cmake REQUIRED)
install(DIRECTORY urdf worlds DESTINATION share/${PROJECT_NAME})
ament_package()
```

`package.xml`:

```xml
<?xml version="1.0"?>
<package format="3">
  <name>warehouse_bot_description</name>
  <version>0.1.0</version>
  <description>Warehouse bot URDF and world.</description>
  <maintainer email="tom@example.com">Tom</maintainer>
  <license>MIT</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <export><build_type>ament_cmake</build_type></export>
</package>
```

`urdf/warehouse_bot.urdf.xacro` — a minimal diff-drive with LiDAR and the Gazebo systems:

```xml
<?xml version="1.0"?>
<robot name="warehouse_bot" xmlns:xacro="http://ros.org/wiki/xacro">
  <link name="base_footprint"/>
  <link name="base_link">
    <inertial><mass value="5.0"/><inertia ixx="0.1" ixy="0" ixz="0" iyy="0.1" iyz="0" izz="0.1"/></inertial>
    <collision><geometry><box size="0.3 0.3 0.15"/></geometry></collision>
    <visual><geometry><box size="0.3 0.3 0.15"/></geometry></visual>
  </link>
  <joint name="base_joint" type="fixed"><parent link="base_footprint"/><child link="base_link"/>
    <origin xyz="0 0 0.1"/></joint>

  <xacro:macro name="wheel" params="name y">
    <link name="${name}"><inertial><mass value="0.5"/>
      <inertia ixx="0.001" ixy="0" ixz="0" iyy="0.001" iyz="0" izz="0.001"/></inertial>
      <collision><geometry><cylinder radius="0.05" length="0.04"/></geometry></collision>
      <visual><geometry><cylinder radius="0.05" length="0.04"/></geometry></visual></link>
    <joint name="${name}_joint" type="continuous"><parent link="base_link"/><child link="${name}"/>
      <origin xyz="0 ${y} -0.05" rpy="-1.5708 0 0"/><axis xyz="0 0 1"/></joint>
  </xacro:macro>
  <xacro:wheel name="left_wheel" y="0.18"/>
  <xacro:wheel name="right_wheel" y="-0.18"/>

  <link name="lidar_link"/>
  <joint name="lidar_joint" type="fixed"><parent link="base_link"/><child link="lidar_link"/>
    <origin xyz="0.12 0 0.1"/></joint>

  <gazebo>
    <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">
      <left_joint>left_wheel_joint</left_joint>
      <right_joint>right_wheel_joint</right_joint>
      <wheel_separation>0.36</wheel_separation>
      <wheel_radius>0.05</wheel_radius>
      <topic>cmd_vel</topic>
      <odom_topic>odom</odom_topic>
      <frame_id>odom</frame_id>
      <child_frame_id>base_footprint</child_frame_id>
      <odom_publish_frequency>30</odom_publish_frequency>
    </plugin>
  </gazebo>
  <gazebo reference="lidar_link">
    <sensor name="lidar" type="gpu_lidar">
      <topic>scan</topic><update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>
      <lidar><scan><horizontal><samples>180</samples><resolution>1</resolution>
        <min_angle>-1.5708</min_angle><max_angle>1.5708</max_angle></horizontal></scan>
        <range><min>0.08</min><max>10.0</max><resolution>0.01</resolution></range></lidar>
    </sensor>
  </gazebo>
</robot>
```

`worlds/warehouse.sdf`: copy the `physics`, three `plugin` blocks, `light`, and `ground` model from `spike/minimal.sdf`; add four thin wall boxes forming a ~8×8 m room; do **not** hard-code the obstacle box (it is spawned per-scenario).

- [ ] **Step 4: Write the bringup/launch package**

Create `warehouse-bot/src/warehouse_bot_bringup/` as an `ament_python` package (mirror the `package.xml`/`setup.py`/`resource` pattern from Step 1, name `warehouse_bot_bringup`, depend on `ros_gz_sim`, `ros_gz_bridge`, `robot_state_publisher`, `xacro`). Create `launch/simulation.launch.py`:

```python
import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import xacro

def generate_launch_description():
    desc = get_package_share_directory("warehouse_bot_description")
    world = os.path.join(desc, "worlds", "warehouse.sdf")
    urdf_xacro = os.path.join(desc, "urdf", "warehouse_bot.urdf.xacro")
    robot_desc = xacro.process_file(urdf_xacro).toxml()

    return LaunchDescription([
        ExecuteProcess(
            cmd=["gz", "sim", "-s", "-r", "--headless-rendering", world],
            output="screen",
        ),
        Node(package="ros_gz_sim", executable="create",
             arguments=["-name", "warehouse_bot", "-string", robot_desc,
                        "-z", "0.1"], output="screen"),
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             parameters=[{"robot_description": robot_desc}], output="screen"),
        Node(package="ros_gz_bridge", executable="parameter_bridge", output="screen",
             arguments=[
                 "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
                 "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
                 "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
                 "/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
             ]),
    ])
```

- [ ] **Step 5: Write the project manifest**

Create `warehouse-bot/robotbase.yaml` matching the §9 schema (project name `warehouse-bot`, `ros_distribution: jazzy`, `simulator: gazebo-harmonic`, launch `warehouse_bot_bringup`/`simulation.launch.py`, scenarios dir `simulation/scenarios`, mcp port `4381`).

- [ ] **Step 6: Write the Dockerfile and compose file**

Create `warehouse-bot/Dockerfile`:

```dockerfile
FROM ros:jazzy-ros-base
RUN apt-get update && apt-get install -y --no-install-recommends \
      gz-harmonic ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge \
      ros-jazzy-robot-state-publisher ros-jazzy-xacro \
      python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*
ENV LIBGL_ALWAYS_SOFTWARE=1 OGRE_RTT_MODE=Copy
WORKDIR /workspace
```

Create `warehouse-bot/compose.yaml`:

```yaml
services:
  ros:
    build: .
    image: warehouse-bot:latest
    working_dir: /workspace
    volumes:
      - ./:/workspace
    environment:
      - LIBGL_ALWAYS_SOFTWARE=1
    command: sleep infinity
    network_mode: host
```

- [ ] **Step 7: Build the workspace inside the container**

Run (from `warehouse-bot/`, inside WSL2):

```bash
docker compose up -d
docker compose exec ros bash -lc "source /opt/ros/jazzy/setup.bash && colcon build --symlink-install"
```

Expected: `colcon build` finishes with `Summary: 3 packages finished`.

- [ ] **Step 8: Launch and probe the topics**

Run:

```bash
docker compose exec ros bash -lc "source /opt/ros/jazzy/setup.bash && source install/setup.bash && \
  ros2 launch warehouse_bot_bringup simulation.launch.py &
  sleep 10 && ros2 topic list | sort"
```

Expected: `/cmd_vel`, `/odom`, `/scan`, `/tf` all present. Then verify `/scan` carries data:
`ros2 topic echo /scan --once` prints a `LaserScan` with non-empty `ranges`.

- [ ] **Step 9: Commit**

```bash
git add warehouse-bot/
git commit -m "feat: hand-built warehouse-bot ros project (sim + starter controller)"
```

---

## Task 8: Runtime module

**Integration + light unit tests.** Wraps the container's ROS/`gz` operations behind a clean, transport-agnostic Python interface (the open-core seam).

**Files:**
- Create: `robotbase/runtime.py`

**Interfaces:**
- Consumes: `Manifest` (Task 4).
- Produces class `Runtime(project_dir: str)` with methods:
  - `build(clean: bool = False) -> dict` → `{"passed": bool, "duration_seconds": float, "errors": list[str], "warnings": list[str]}`
  - `launch() -> dict`, `stop() -> dict`, `reset() -> dict`, `simulation_status() -> dict`
  - `list_topics() -> list[dict]` → `[{"name","type","publishers","subscribers"}]`
  - `inspect_topic(topic: str, duration_seconds: float, maximum_messages: int) -> dict`
  - `spawn_box(obstacle) -> None`, `set_robot_pose(pose) -> None` (used by the runner)
  - Each method shells into the compose container with a bounded timeout and returns structured, size-capped data. Raises `RuntimeUnavailable` when the container/ROS graph is down.

- [ ] **Step 1: Write the runtime module**

Create `robotbase/runtime.py`. Implement each method by running `docker compose exec` commands with `subprocess.run(..., timeout=...)`, parsing stdout into the structured shapes above. `reset()` uses `gz service -s /world/warehouse/control` (world reset) and re-sets the robot pose via `gz service -s /world/warehouse/set_pose`; `spawn_box()` uses `gz service -s /world/warehouse/create` with an SDF box string. Cap all captured output at 200 lines / 20 KB. (Full method bodies follow the same `subprocess` pattern; keep each method under ~25 lines and single-responsibility.)

```python
from __future__ import annotations
import subprocess, time

class RuntimeUnavailable(RuntimeError): ...

class Runtime:
    def __init__(self, project_dir: str):
        self.project_dir = project_dir

    def _exec(self, cmd: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
        full = ["docker", "compose", "exec", "-T", "ros", "bash", "-lc",
                f"source /opt/ros/jazzy/setup.bash && source install/setup.bash 2>/dev/null; {cmd}"]
        try:
            return subprocess.run(full, cwd=self.project_dir, capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise RuntimeUnavailable(f"Timed out: {cmd}") from e

    def build(self, clean: bool = False) -> dict:
        start = time.monotonic()
        pre = "rm -rf build install log && " if clean else ""
        proc = self._exec(pre + "colcon build --symlink-install", timeout=600)
        errors = [ln for ln in proc.stdout.splitlines()[-200:] if "error" in ln.lower()]
        return {"passed": proc.returncode == 0, "duration_seconds": round(time.monotonic() - start, 1),
                "errors": errors, "warnings": []}

    def list_topics(self) -> list[dict]:
        proc = self._exec("ros2 topic list -t", timeout=30)
        out = []
        for ln in proc.stdout.splitlines()[:200]:
            if not ln.strip():
                continue
            name, _, typ = ln.partition(" ")
            out.append({"name": name, "type": typ.strip("[] "), "publishers": None, "subscribers": None})
        return out

    # launch(), stop(), reset(), simulation_status(), inspect_topic(),
    # spawn_box(), set_robot_pose() follow the same _exec pattern.
```

- [ ] **Step 2: Verify build() against the live container**

With the Task 7 container up, run a throwaway check (from `warehouse-bot/`):

```bash
python3 -c "from robotbase.runtime import Runtime; print(Runtime('.').build())"
```

Expected: `{'passed': True, 'duration_seconds': <n>, 'errors': [], 'warnings': []}`.

- [ ] **Step 3: Verify list_topics() after launch**

With the sim launched (Task 8 depends on Task 7's launch), run:

```bash
python3 -c "from robotbase.runtime import Runtime; print([t['name'] for t in Runtime('.').list_topics()])"
```

Expected: list includes `/scan`, `/odom`, `/cmd_vel`, `/tf`.

- [ ] **Step 4: Commit**

```bash
git add robotbase/runtime.py
git commit -m "feat: in-process runtime module wrapping ros/gz operations"
```

---

## Task 9: Scenario runner

**Files:**
- Create: `robotbase/scenario_runner.py`, `tests/test_scenario_runner.py`

**Interfaces:**
- Consumes: `Scenario` (Task 4), `Metrics`/`ScenarioResult`/`AssertionResult` (Task 5), `evaluate` (Task 6), `Runtime` (Task 8).
- Produces: `run_scenario(scenario: Scenario, runtime, run_dir: str) -> ScenarioResult`. It resets the world, applies setup (robot pose, spawn obstacles), executes actions in order, collects metrics from the runtime, evaluates every assertion, builds a `ScenarioResult`, writes it, and returns it. The `runtime` dependency is injected so the runner is unit-testable with a fake.

- [ ] **Step 1: Write the failing test with a fake runtime**

Create `tests/test_scenario_runner.py`:

```python
from robotbase.schema import Scenario, SetupSpec, ActionSpec, AssertionSpec
from robotbase.results import Metrics
from robotbase.scenario_runner import run_scenario

class FakeRuntime:
    def __init__(self, metrics): self._m = metrics; self.calls = []
    def reset(self): self.calls.append("reset")
    def set_robot_pose(self, pose): self.calls.append("pose")
    def spawn_box(self, obs): self.calls.append(f"spawn:{obs.id}")
    def run_action(self, action): self.calls.append(f"action:{action.type}")
    def collect_metrics(self): return self._m

def _scenario():
    return Scenario(version=1, name="stop-before-obstacle",
                    setup=SetupSpec(reset_world=True),
                    actions=[ActionSpec(type="wait", duration_seconds=1)],
                    assertions=[AssertionSpec(type="no_collision"),
                                AssertionSpec(type="minimum_obstacle_distance", minimum_metres=0.25)])

def test_runner_passes_when_metrics_clear(tmp_path):
    m = Metrics(collision_count=0, minimum_obstacle_distance_metres=0.4,
                distance_travelled_metres=2.0, final_linear_velocity=0.0,
                final_angular_velocity=0.0, topic_message_counts={"/scan": 20})
    result = run_scenario(_scenario(), FakeRuntime(m), str(tmp_path))
    assert result.passed is True
    assert len(result.assertions) == 2

def test_runner_fails_on_collision(tmp_path):
    m = Metrics(collision_count=1, minimum_obstacle_distance_metres=0.0,
                distance_travelled_metres=2.1, final_linear_velocity=0.0,
                final_angular_velocity=0.0, topic_message_counts={"/scan": 20})
    result = run_scenario(_scenario(), FakeRuntime(m), str(tmp_path))
    assert result.passed is False
    assert result.metrics.collision_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scenario_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'robotbase.scenario_runner'`.

- [ ] **Step 3: Write minimal implementation**

Create `robotbase/scenario_runner.py`:

```python
from __future__ import annotations
import time
from robotbase.schema import Scenario
from robotbase.results import ScenarioResult, new_run_id
from robotbase.assertions import evaluate

def run_scenario(scenario: Scenario, runtime, run_dir: str) -> ScenarioResult:
    started = time.time()
    if scenario.setup.reset_world:
        runtime.reset()
    runtime.set_robot_pose(scenario.setup.robot.pose)
    for obs in scenario.setup.obstacles:
        runtime.spawn_box(obs)
    for action in scenario.actions:
        runtime.run_action(action)
    metrics = runtime.collect_metrics()
    assertion_results = [evaluate(a, metrics) for a in scenario.assertions]
    result = ScenarioResult(
        run_id=new_run_id(), scenario=scenario.name, metrics=metrics,
        assertions=assertion_results, duration_seconds=round(time.time() - started, 1),
    )
    result.write(f"{run_dir}/{result.run_id}")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scenario_runner.py -v`
Expected: 2 passed.

- [ ] **Step 5: Add `run_action` and `collect_metrics` to the real Runtime**

In `robotbase/runtime.py` add `run_action(self, action)` (dispatch on `action.type`: `wait` → sleep; `wait_for_topic` → poll `ros2 topic echo --once`; `run_node` → launch the node via `_exec`; `send_velocity` → `ros2 topic pub` once) and `collect_metrics(self) -> Metrics` (subscribe to `/scan` and `/odom` for a short window via a small helper node run inside the container, compute `minimum_obstacle_distance_metres` from min `/scan` range, `final_linear_velocity` from last `/odom`, `distance_travelled_metres` from odom integration, and `collision_count` from a Gazebo contact topic or a distance-below-threshold heuristic). Cap the collection window at the scenario timeout.

- [ ] **Step 6: Commit**

```bash
git add robotbase/scenario_runner.py robotbase/runtime.py tests/test_scenario_runner.py
git commit -m "feat: scenario runner orchestrating setup, actions, assertions"
```

---

## Task 10: MCP server

**Files:**
- Create: `robotbase/mcp_server.py`, `tests/test_mcp_validation.py`

**Interfaces:**
- Consumes: `Runtime` (Task 8), `run_scenario` (Task 9), `Scenario` (Task 4).
- Produces: an MCP server exposing the loop-closing tools: `project_describe`, `workspace_build`, `simulation_launch`, `simulation_stop`, `simulation_reset`, `ros_list_topics`, `ros_inspect_topic`, `scenario_list`, `scenario_run`, `scenario_get_result`. Plus a pure helper `validate_scenario_name(name: str, available: list[str]) -> None` raising `ValueError` for unknown names (this is the unit-tested seam). Server binds `127.0.0.1` and reads the project dir from its working directory.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_validation.py`:

```python
import pytest
from robotbase.mcp_server import validate_scenario_name

def test_known_name_ok():
    validate_scenario_name("drive-forward", ["drive-forward", "stop-before-obstacle"])

def test_unknown_name_raises():
    with pytest.raises(ValueError):
        validate_scenario_name("teleport", ["drive-forward"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcp_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'robotbase.mcp_server'`.

- [ ] **Step 3: Write minimal implementation**

Create `robotbase/mcp_server.py`:

```python
from __future__ import annotations
import os, glob
from mcp.server.fastmcp import FastMCP
from robotbase.runtime import Runtime
from robotbase.schema import Scenario
from robotbase.scenario_runner import run_scenario

PROJECT_DIR = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
RUN_DIR = os.path.join(PROJECT_DIR, ".robotbase", "runs")

def validate_scenario_name(name: str, available: list[str]) -> None:
    if name not in available:
        raise ValueError(f"Unknown scenario {name!r}. Available: {available}")

def _scenario_paths() -> dict[str, str]:
    d = os.path.join(PROJECT_DIR, "simulation", "scenarios")
    return {os.path.splitext(os.path.basename(p))[0]: p
            for p in glob.glob(os.path.join(d, "*.yaml"))}

mcp = FastMCP("robotbase")
_runtime = Runtime(PROJECT_DIR)

@mcp.tool()
def workspace_build(clean: bool = False) -> dict:
    return _runtime.build(clean=clean)

@mcp.tool()
def ros_list_topics() -> list[dict]:
    return _runtime.list_topics()

@mcp.tool()
def scenario_list() -> list[str]:
    return sorted(_scenario_paths().keys())

@mcp.tool()
def scenario_run(name: str) -> dict:
    paths = _scenario_paths()
    validate_scenario_name(name, list(paths))
    scenario = Scenario.from_yaml(paths[name])
    return run_scenario(scenario, _runtime, RUN_DIR).model_dump()

# simulation_launch/stop/reset, ros_inspect_topic, project_describe,
# scenario_get_result registered with the same @mcp.tool() pattern,
# each delegating to the corresponding Runtime method.

def main():
    mcp.run()

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mcp_validation.py -v`
Expected: 2 passed.

- [ ] **Step 5: Full suite green**

Run: `pytest -q`
Expected: all tests from Tasks 3–10 pass.

- [ ] **Step 6: Commit**

```bash
git add robotbase/mcp_server.py tests/test_mcp_validation.py
git commit -m "feat: mcp server exposing loop-closing robotbase tools"
```

---

## Task 11: Scenarios, AGENTS.md, and the canonical proof

**Files:**
- Create: `warehouse-bot/simulation/scenarios/drive-forward.yaml`, `warehouse-bot/simulation/scenarios/stop-before-obstacle.yaml`, `warehouse-bot/AGENTS.md`, `warehouse-bot/.mcp.json`

- [ ] **Step 1: Write the two scenarios**

Create `warehouse-bot/simulation/scenarios/drive-forward.yaml`:

```yaml
version: 1
name: drive-forward
description: Robot drives at least one metre forward with odometry available.
timeout_seconds: 20
setup:
  reset_world: true
  robot: {pose: {x: 0.0, y: 0.0, yaw: 0.0}}
actions:
  - {type: wait_for_topic, topic: /odom, timeout_seconds: 5}
  - {type: run_node, package: warehouse_bot, executable: obstacle_controller}
  - {type: wait, duration_seconds: 6}
assertions:
  - {type: robot_moved_minimum_distance, minimum_distance_metres: 1.0}
  - {type: required_topic_messages, topic: /odom, minimum_count: 5}
```

Create `warehouse-bot/simulation/scenarios/stop-before-obstacle.yaml` (the §13 example: box at x=2.0, assertions `no_collision`, `minimum_obstacle_distance` ≥ 0.25, `robot_stopped`, `required_topic_messages` on `/scan` ≥ 5).

- [ ] **Step 2: Write AGENTS.md**

Create `warehouse-bot/AGENTS.md` from §18 of the parent spec: development commands, important topics (`/cmd_vel`, `/scan`, `/odom`, `/tf`), controller file path, and the "do not claim success without running the scenario and inspecting assertions" requirement.

- [ ] **Step 3: Write the Claude Code MCP config**

Create `warehouse-bot/.mcp.json`:

```json
{
  "mcpServers": {
    "robotbase": {
      "command": "python3",
      "args": ["-m", "robotbase.mcp_server"],
      "env": { "ROBOTBASE_PROJECT_DIR": "." }
    }
  }
}
```

- [ ] **Step 4: Run drive-forward via the runner (sanity)**

With the container up and the workspace built, run:

```bash
python3 -c "from robotbase.schema import Scenario; from robotbase.runtime import Runtime; \
from robotbase.scenario_runner import run_scenario; \
s=Scenario.from_yaml('simulation/scenarios/drive-forward.yaml'); \
print(run_scenario(s, Runtime('.'), '.robotbase/runs').passed)"
```

Expected: `True` (the starter controller *does* drive forward, so this scenario passes as-is).

- [ ] **Step 5: The canonical proof (manual, the sub-project's success criterion)**

From `warehouse-bot/` inside WSL2, run `claude`, then give the canonical prompt (§28): ask it to implement the obstacle controller and iterate until `drive-forward` and `stop-before-obstacle` both pass, using the Robotbase MCP tools and not claiming success without running scenarios. **Observe** the agent call `scenario_run` → read the failed `no_collision`/`minimum_obstacle_distance` assertions → edit `obstacle_controller.py` to brake on near LiDAR ranges → `workspace_build` → rerun → pass.

Success = `stop-before-obstacle` goes from failing to passing under agent control, with no manual Gazebo operation. Record the transcript/metrics as the proof artifact.

- [ ] **Step 6: Commit**

```bash
git add warehouse-bot/simulation/scenarios/ warehouse-bot/AGENTS.md warehouse-bot/.mcp.json
git commit -m "feat: scenarios, AGENTS.md, mcp config; canonical proof runnable"
```

---

## Self-Review

**Spec coverage** (design spec §1–§10):
- §3 dev environment → Task 1 prerequisites + Global Constraints. ✓
- §4 Phase 0 spike → Task 1. ✓
- §5.1 sim unit → Task 7. ✓
- §5.2 scenario runner + minimal assertions → Tasks 4, 6, 9. ✓
- §5.3 runtime module (transport-agnostic seam) → Task 8. ✓
- §5.4 MCP server (loop-closing tools) + AGENTS.md → Tasks 10, 11. ✓
- §6 proof loop → Task 11 Step 5. ✓
- §7 Python-throughout stack → all package tasks. ✓
- §10 acceptance criteria 1–6 → Task 1 (crit 1), Task 7 (crit 2), Task 9/11 (crit 3), Task 10 (crit 4), Task 11 Step 5 (crit 5), Global Constraints localhost (crit 6). ✓

**Placeholder scan:** integration-heavy methods in Tasks 8 and 9 Step 5 describe `subprocess`/dispatch bodies rather than full code, because their exact `gz`/`ros2` command strings must be tuned against the live container from Task 7 — the interface signatures and return shapes are fully specified, and the verification steps are concrete. This is intentional integration latitude, not an under-specified pure-logic unit. All pure-logic tasks (3, 4, 5, 6, 9 core, 10 helper) carry complete code and tests.

**Type consistency:** `Metrics`, `AssertionResult`, `ScenarioResult`, `AssertionSpec`, `Scenario`, `Runtime`, `run_scenario`, `evaluate`, `validate_scenario_name` names and signatures are consistent across Tasks 4–10. The runner injects a duck-typed runtime (`reset`, `set_robot_pose`, `spawn_box`, `run_action`, `collect_metrics`); Task 8/9 Step 5 add exactly those methods to the real `Runtime`. ✓

**Scope:** single sub-project, one testable deliverable per task, ends at the canonical proof. No further decomposition needed.
