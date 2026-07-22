"""In-process runtime that wraps a project's ROS 2 / Gazebo operations.

This is the transport-agnostic seam: the MCP server and scenario runner call
these methods and never touch docker or ROS commands directly. Every method
shells into the project's compose container with a bounded timeout and returns
structured, size-capped data.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import time

from robotbase.results import Metrics
from robotbase.schema import Manifest, ManifestError

MAX_OUTPUT_LINES = 200


class RuntimeUnavailable(RuntimeError):
    """The container or ROS graph could not be reached within the timeout."""


class Runtime:
    def __init__(self, project_dir: str, service: str = "ros"):
        self.project_dir = project_dir
        self.service = service
        # Defaults; overridden by the project's robotbase.yaml when present so
        # the runtime is project-agnostic (the open-core seam).
        self.launch_package = "warehouse_bot_bringup"
        self.launch_file = "simulation.launch.py"
        self.world = "warehouse"
        self.robot_name = "warehouse_bot"
        manifest_path = os.path.join(project_dir, "robotbase.yaml")
        if os.path.exists(manifest_path):
            try:
                m = Manifest.from_yaml(manifest_path)
                self.launch_package = m.launch_package
                self.launch_file = m.launch_file
                self.world = m.world_name
                self.robot_name = m.robot_name
            except ManifestError:
                pass  # keep defaults on a malformed manifest

    # ---- low-level exec ------------------------------------------------
    def _compose(self, *args: str, detached: bool = False, timeout: float = 60.0):
        flags = ["-dT"] if detached else ["-T"]
        cmd = ["docker", "compose", "exec", *flags, self.service, *args]
        try:
            return subprocess.run(
                cmd, cwd=self.project_dir, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeUnavailable(f"timed out running: {' '.join(args)}") from e
        except FileNotFoundError as e:
            raise RuntimeUnavailable("docker/compose not available on PATH") from e

    def _ros(self, cmd: str, detached: bool = False, timeout: float = 60.0):
        setup = (
            "source /opt/ros/jazzy/setup.bash; "
            "[ -f /workspace/install/setup.bash ] && source /workspace/install/setup.bash; "
        )
        return self._compose("bash", "-lc", setup + cmd, detached=detached, timeout=timeout)

    def _restart_container(self) -> None:
        # Restart the whole compose service for a pristine slate. This is the
        # only reliable way to clear a prior sim: the `gz sim` server orphans
        # itself and survives pkill, so stale spawned entities leak between
        # runs. The mounted build/install volume persists across the restart.
        try:
            subprocess.run(
                ["docker", "compose", "restart", self.service],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeUnavailable("container restart timed out") from e
        time.sleep(3)

    @staticmethod
    def _cap(text: str) -> list[str]:
        return text.splitlines()[-MAX_OUTPUT_LINES:]

    # ---- build ---------------------------------------------------------
    def build(self, clean: bool = False) -> dict:
        start = time.monotonic()
        pre = "rm -rf build install log && " if clean else ""
        proc = self._ros(pre + "colcon build --symlink-install", timeout=600)
        lines = self._cap(proc.stdout) + self._cap(proc.stderr)
        return {
            "passed": proc.returncode == 0,
            "duration_seconds": round(time.monotonic() - start, 1),
            "errors": [ln for ln in lines if "error" in ln.lower()][:50],
            "warnings": [ln for ln in lines if "warning" in ln.lower()][:20],
        }

    # ---- simulation lifecycle -----------------------------------------
    def launch(self, wait_seconds: float = 45.0) -> dict:
        self._restart_container()  # pristine slate: no leaked sim/bridge/controller
        # Create the scratch dir host-side so it is owned by the host user, not
        # by root inside the container (which would block host-side writes).
        os.makedirs(os.path.join(self.project_dir, ".robotbase"), exist_ok=True)
        self._ros(
            "mkdir -p /workspace/.robotbase && "
            f"ros2 launch {self.launch_package} {self.launch_file} "
            "> /workspace/.robotbase/launch.log 2>&1",
            detached=True,
            timeout=30,
        )
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            topics = [t["name"] for t in self.list_topics()]
            if "/scan" in topics and "/odom" in topics:
                self._start_recorder()
                return {"running": True, "topics": sorted(topics)}
            time.sleep(2)
        return {"running": False, "topics": sorted(t["name"] for t in self.list_topics())}

    def _start_recorder(self) -> None:
        # Record metrics across the whole episode (from launch until collect).
        # The recorder resets its output file on startup, so no stale data leaks.
        self._ros(
            "python3 /workspace/scripts/metrics_collector.py "
            "--output /workspace/.robotbase/metrics.json",
            detached=True,
            timeout=15,
        )

    def stop(self) -> dict:
        self._ros(
            "pkill -f 'ros2 launch'; pkill -f 'gz sim'; pkill -f parameter_bridge; "
            "pkill -f robot_state_publisher; pkill -f ros_gz_sim; "
            "pkill -f obstacle_controller; pkill -f metrics_collector; true",
            timeout=20,
        )
        return {"running": False}

    def reset(self) -> dict:
        # Deterministic reset = pristine container + relaunch (design open-risk
        # #2: prefer determinism over in-place gz-service world reset). launch()
        # restarts the container, so no prior state can leak in.
        return self.launch()

    def simulation_status(self) -> dict:
        proc = self._ros("pgrep -f 'gz sim' >/dev/null && echo running || echo stopped", timeout=15)
        running = "running" in proc.stdout
        topics = [t["name"] for t in self.list_topics()] if running else []
        return {
            "running": running,
            "gazebo": running,
            "ros_graph_ready": "/scan" in topics,
            "topic_count": len(topics),
        }

    # ---- ROS graph inspection -----------------------------------------
    def list_topics(self) -> list[dict]:
        proc = self._ros("ros2 topic list -t 2>/dev/null", timeout=25)
        out: list[dict] = []
        for ln in self._cap(proc.stdout):
            ln = ln.strip()
            if not ln:
                continue
            name, _, typ = ln.partition(" ")
            out.append(
                {"name": name, "type": typ.strip("[] "), "publishers": None, "subscribers": None}
            )
        return out

    def inspect_topic(
        self, topic: str, duration_seconds: float = 2.0, maximum_messages: int = 3
    ) -> dict:
        proc = self._ros(
            f"timeout {int(duration_seconds) + 2} ros2 topic echo {topic} --once 2>&1",
            timeout=duration_seconds + 10,
        )
        sample = "\n".join(self._cap(proc.stdout))[:4000]
        return {"topic": topic, "received": bool(proc.stdout.strip()), "sample": sample}

    # ---- scenario setup ------------------------------------------------
    def set_robot_pose(self, pose) -> None:
        z = math.sin(pose.yaw / 2.0)
        w = math.cos(pose.yaw / 2.0)
        req = (
            f'name: "{self.robot_name}", '
            f"position: {{x: {pose.x}, y: {pose.y}, z: 0.1}}, "
            f"orientation: {{x: 0, y: 0, z: {z}, w: {w}}}"
        )
        self._ros(
            f"gz service -s /world/{self.world}/set_pose "
            "--reqtype gz.msgs.Pose --reptype gz.msgs.Boolean "
            f"--timeout 3000 --req '{req}'",
            timeout=15,
        )

    def spawn_box(self, obstacle) -> None:
        p, s = obstacle.pose, obstacle.size
        sdf = (
            '<?xml version="1.0"?><sdf version="1.9">'
            f'<model name="{obstacle.id}"><static>true</static>'
            f"<pose>{p.x} {p.y} {p.z} 0 0 0</pose><link name=\"link\">"
            f'<collision name="c"><geometry><box><size>{s.x} {s.y} {s.z}</size>'
            "</box></geometry></collision>"
            f'<visual name="v"><geometry><box><size>{s.x} {s.y} {s.z}</size></box></geometry>'
            "<material><ambient>0.8 0.2 0.2 1</ambient><diffuse>0.9 0.2 0.2 1</diffuse>"
            "</material></visual></link></model></sdf>"
        )
        rb_dir = os.path.join(self.project_dir, ".robotbase")
        os.makedirs(rb_dir, exist_ok=True)
        rel = f".robotbase/obs_{obstacle.id}.sdf"
        with open(os.path.join(self.project_dir, rel), "w") as f:
            f.write(sdf)
        self._ros(
            f"ros2 run ros_gz_sim create -world {self.world} "
            f"-name {obstacle.id} -file /workspace/{rel} "
            f"-x {p.x} -y {p.y} -z {p.z}",  # -x/-y/-z: create ignores the SDF <pose>
            timeout=20,
        )

    # ---- actions -------------------------------------------------------
    def run_action(self, action) -> None:
        t = action.type
        if t == "wait":
            time.sleep(action.duration_seconds or 1.0)
        elif t == "wait_for_topic":
            self._wait_for_topic(action.topic, action.timeout_seconds or 5.0)
        elif t == "run_node":
            # use_sim_time keeps the control loop synced to simulation time, so
            # a wall-clock timer can't overshoot when the sim runs faster than
            # real time. Applied by the harness so any agent controller benefits.
            self._ros(
                f"ros2 run {action.package} {action.executable} "
                "--ros-args -p use_sim_time:=true "
                "> /workspace/.robotbase/node.log 2>&1",
                detached=True,
                timeout=20,
            )
        # unknown/other action types are ignored (forward-compatible).

    def _wait_for_topic(self, topic: str, timeout_seconds: float) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if any(t["name"] == topic for t in self.list_topics()):
                return
            time.sleep(1)

    # ---- metrics -------------------------------------------------------
    def collect_metrics(self, settle_seconds: float = 1.0) -> Metrics:
        # Stop the whole-episode recorder and read the metrics it accumulated.
        self._ros("pkill -f metrics_collector; true", timeout=15)
        time.sleep(settle_seconds)
        path = os.path.join(self.project_dir, ".robotbase", "metrics.json")
        try:
            with open(path) as f:
                return Metrics(**json.load(f))
        except (OSError, json.JSONDecodeError, TypeError):
            return Metrics()
