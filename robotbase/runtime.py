"""In-process runtime that wraps a project's ROS 2 / Gazebo operations.

This is the transport-agnostic seam: the MCP server and scenario runner call
these methods and never touch docker or ROS commands directly. Every method
shells into the project's compose container with a bounded timeout and returns
structured, size-capped data.
"""
from __future__ import annotations

import subprocess
import time

MAX_OUTPUT_LINES = 200


class RuntimeUnavailable(RuntimeError):
    """The container or ROS graph could not be reached within the timeout."""


class Runtime:
    def __init__(self, project_dir: str, service: str = "ros", world: str = "warehouse"):
        self.project_dir = project_dir
        self.service = service
        self.world = world

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
        self.stop()  # guarantee a single clean sim instance
        time.sleep(2)
        self._ros(
            "mkdir -p /workspace/.robotbase && "
            "ros2 launch warehouse_bot_bringup simulation.launch.py "
            "> /workspace/.robotbase/launch.log 2>&1",
            detached=True,
            timeout=30,
        )
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            topics = [t["name"] for t in self.list_topics()]
            if "/scan" in topics and "/odom" in topics:
                return {"running": True, "topics": sorted(topics)}
            time.sleep(2)
        return {"running": False, "topics": sorted(t["name"] for t in self.list_topics())}

    def stop(self) -> dict:
        self._ros(
            "pkill -f 'ros2 launch'; pkill -f 'gz sim'; pkill -f parameter_bridge; "
            "pkill -f robot_state_publisher; pkill -f ros_gz_sim; true",
            timeout=20,
        )
        return {"running": False}

    def reset(self) -> dict:
        # Deterministic reset = full teardown + relaunch (design open-risk #2:
        # prefer determinism over in-place gz-service world reset). launch()
        # already tears down any running sim first.
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
