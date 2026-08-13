"""Unit tests for Runtime plumbing that doesn't need Docker (subprocess is mocked)."""
import pytest

from robotbase.runtime import Runtime, RuntimeUnavailable


class _Proc:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def test_restart_container_recreates_the_service(tmp_path, monkeypatch):
    # A pristine slate AND a container that was removed must both be handled: `up -d
    # --force-recreate` (not a bare `restart`, which silently no-ops on a missing container).
    calls = []
    monkeypatch.setattr("robotbase.runtime.subprocess.run",
                        lambda cmd, **kw: calls.append(cmd) or _Proc())
    monkeypatch.setattr("robotbase.runtime.time.sleep", lambda *_: None)
    Runtime(str(tmp_path))._restart_container()
    assert calls[0][:5] == ["docker", "compose", "up", "-d", "--force-recreate"]


def test_restart_container_raises_when_it_cannot_start(tmp_path, monkeypatch):
    # A run against a container that won't start must fail loudly, not proceed to read stale metrics.
    monkeypatch.setattr("robotbase.runtime.subprocess.run",
                        lambda *a, **k: _Proc(returncode=1, stderr="no such image"))
    monkeypatch.setattr("robotbase.runtime.time.sleep", lambda *_: None)
    with pytest.raises(RuntimeUnavailable):
        Runtime(str(tmp_path))._restart_container()


def test_start_telemetry_passes_world_and_robot(tmp_path, monkeypatch):
    # The telemetry node needs the world + robot names to read the ground-truth pose from gz
    # (/odom drifts). Without them it would silently fall back to the wrong-frame /odom pose.
    rt = Runtime(str(tmp_path))
    rt.world, rt.robot_name = "maze", "my_robot"
    monkeypatch.setattr(rt, "_ensure_telemetry", lambda: "/workspace/.robotbase/telemetry.py")
    calls = []
    monkeypatch.setattr(rt, "_ros", lambda cmd, **kw: calls.append(cmd))
    rt.start_telemetry()
    assert "--world maze" in calls[0] and "--robot my_robot" in calls[0]


def test_compose_files_layers_foxglove_only_with_gui(tmp_path):
    # Headless runs must publish NO host port (so two projects don't collide on 8765); the overlay
    # that publishes it is layered only when a GUI is requested.
    (tmp_path / "compose.foxglove.yaml").write_text("services: {}\n")
    rt = Runtime(str(tmp_path))
    assert rt._compose_files() == []
    rt.gui = "foxglove"
    assert rt._compose_files() == ["-f", "compose.yaml", "-f", "compose.foxglove.yaml"]


def test_port_conflict_gives_friendly_hint():
    assert "8765" in Runtime._port_conflict_hint(
        "Bind for 0.0.0.0:8765 failed: port is already allocated")
    assert Runtime._port_conflict_hint("some other error") is None


def test_start_recorder_passes_world_and_robot(tmp_path, monkeypatch):
    # The metrics collector scores final pose/distance from the same ground-truth source, so it
    # needs the world + robot names too — otherwise robot_reached_pose is scored in the odom frame.
    rt = Runtime(str(tmp_path))
    rt.world, rt.robot_name = "maze", "my_robot"
    calls = []
    monkeypatch.setattr(rt, "_ros", lambda cmd, **kw: calls.append(cmd))
    rt._start_recorder()
    assert "metrics_collector.py" in calls[0]
    assert "--world maze" in calls[0] and "--robot my_robot" in calls[0]
