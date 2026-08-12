import os

import pytest

from robotbase.generator import create_project, template_dir
from robotbase.studio.service import StudioService


@pytest.fixture
def project(tmp_path):
    return create_project("studiobot", str(tmp_path), template_dir("differential-drive"))


def test_project_facts_include_robot_and_scenarios(project):
    svc = StudioService(project)
    p = svc.project()
    assert p["robot"]["template"] == "differential-drive"
    assert any(s["name"] == "drive-forward" for s in p["scenarios"])


def test_list_runs_empty_then_present(project):
    svc = StudioService(project)
    assert svc.list_runs() == []
    run_dir = os.path.join(project, ".robotbase", "runs", "run_abc")
    os.makedirs(run_dir)
    open(os.path.join(run_dir, "result.json"), "w").write(
        '{"run_id": "run_abc", "scenario": "drive-forward", "passed": true, "metrics": {}}')
    runs = svc.list_runs()
    assert runs and runs[0]["run_id"] == "run_abc"


def test_list_and_get_evals(project):
    svc = StudioService(project)
    ev_dir = os.path.join(project, ".robotbase", "evals", "eval_xyz")
    os.makedirs(ev_dir)
    open(os.path.join(ev_dir, "report.json"), "w").write(
        '{"eval_id": "eval_xyz", "scenario": "drive-forward", "success_rate": 1.0}')
    assert svc.list_evals()[0]["eval_id"] == "eval_xyz"
    assert svc.get_eval("eval_xyz")["success_rate"] == 1.0


def test_foxglove_deeplink_shape(project):
    svc = StudioService(project)
    fx = svc.foxglove()
    assert "localhost:8765" in fx["url"] and "layout" in fx["hint"].lower()


def test_get_run_merges_episode_sidecar(project):
    svc = StudioService(project)
    rd = os.path.join(project, ".robotbase", "runs", "run_1")
    os.makedirs(rd)
    open(os.path.join(rd, "result.json"), "w").write(
        '{"run_id":"run_1","scenario":"drive-forward","passed":false,'
        '"metrics":{"distance_travelled_metres":0.1},'
        '"assertions":[{"type":"robot_moved_minimum_distance","passed":false,"expected":1.0,"actual":0.1}]}')
    open(os.path.join(rd, "episode.json"), "w").write(
        '{"events":[{"type":"closest_approach","timestamp":6.9,"detail":"0.08 m"}],'
        '"scenario_spec":{"name":"drive-forward","actions":[]}}')
    run = svc.get_run("run_1")
    assert run["passed"] is False and run["assertions"][0]["passed"] is False
    assert run["events"][0]["type"] == "closest_approach"
    assert run["scenario_spec"]["name"] == "drive-forward"



def test_files_allowlist_and_round_trip(project):
    svc = StudioService(project)
    paths = [item["path"] for item in svc.list_files()]
    assert "robot.yaml" in paths and "simulation/scenarios/drive-forward.yaml" in paths
    assert any(path.endswith("/controller.py") for path in paths)
    assert svc._allowed("robot.yaml") and svc._allowed("src/studiobot/studiobot/controller.py")
    assert not svc._allowed("../secret") and not svc._allowed(".robotbase/x")
    assert not svc._allowed("src/studiobot_description/urdf/studiobot.urdf.xacro")
    path = next(path for path in paths if path.endswith("/controller.py"))
    content = svc.read_file(path)["content"]
    svc.write_file(path, content + "\n# Studio round trip\n")
    assert "Studio round trip" in svc.read_file(path)["content"]
    with pytest.raises(ValueError):
        svc.read_file(".robotbase/x")


def test_get_run_without_sidecar_tolerates(project):
    svc = StudioService(project)
    rd = os.path.join(project, ".robotbase", "runs", "run_2")
    os.makedirs(rd)
    open(os.path.join(rd, "result.json"), "w").write('{"run_id":"run_2","passed":true,"metrics":{}}')
    run = svc.get_run("run_2")
    assert run["events"] == [] and run["scenario_spec"] == {}


def test_saving_world_spec_recompiles_project(project, monkeypatch):
    calls = []
    monkeypatch.setattr("robotbase.generator.recompile_project", lambda root: calls.append(root) or True)
    svc = StudioService(project)
    content = svc.read_file("world.yaml")["content"]
    result = svc.write_file("world.yaml", content + "\n# refresh scene\n")
    assert result["project_changed"] is True
    assert calls == [project]


def test_failed_world_compile_rolls_back_source(project, monkeypatch):
    svc = StudioService(project)
    original = svc.read_file("world.yaml")["content"]
    calls = 0
    def compile_then_recover(root):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("invalid wall")
        return True
    monkeypatch.setattr("robotbase.generator.recompile_project", compile_then_recover)
    with pytest.raises(ValueError, match="could not compile world.yaml"):
        svc.write_file("world.yaml", "invalid: [")
    assert svc.read_file("world.yaml")["content"] == original
    assert calls == 2


def test_ensure_telemetry_starts_supervisor_idempotently(project):
    """The 3D viewer must show live motion for a sim the agent launched, not only one brought up
    via Studio — so ensure_telemetry starts the supervisor without a full up(), idempotently."""
    counters = {"factory": 0, "start": 0}

    class FakeRT:
        def __init__(self, _dir):
            counters["factory"] += 1
        def start_telemetry(self):
            counters["start"] += 1

    svc = StudioService(project, runtime_factory=FakeRT)
    out = svc.ensure_telemetry()
    try:
        assert out["telemetry"] == "on" and svc._telemetry_on is True
        assert counters["start"] == 1
        again = svc.ensure_telemetry()
        assert again["telemetry"] == "already-on"
        assert counters["factory"] == 1  # no second runtime / supervisor spawned
    finally:
        svc._telemetry_on = False  # let the daemon supervisor thread exit


def _make_run(project, run_id):
    rd = os.path.join(project, ".robotbase", "runs", run_id)
    os.makedirs(rd)
    open(os.path.join(rd, "result.json"), "w").write(
        f'{{"run_id":"{run_id}","scenario":"drive-forward","passed":true,"metrics":{{}}}}')


def test_delete_and_clear_runs(project):
    svc = StudioService(project)
    _make_run(project, "run_a"); _make_run(project, "run_b")
    assert len(svc.list_runs()) == 2
    svc.delete_run("run_a")
    assert [r["run_id"] for r in svc.list_runs()] == ["run_b"]
    _make_run(project, "run_c")
    assert svc.clear_runs()["cleared"] == 2
    assert svc.list_runs() == []


def test_delete_run_rejects_traversal_and_unknown(project):
    svc = StudioService(project)
    with pytest.raises(ValueError):
        svc.delete_run("../../etc")
    with pytest.raises(ValueError):
        svc.delete_run("nope")


def test_delete_and_clear_evals(project):
    svc = StudioService(project)
    for eid in ("eval_1", "eval_2"):
        d = os.path.join(project, ".robotbase", "evals", eid)
        os.makedirs(d)
        open(os.path.join(d, "report.json"), "w").write(f'{{"eval_id":"{eid}","success_rate":1.0}}')
    assert len(svc.list_evals()) == 2
    svc.delete_eval("eval_1")
    assert len(svc.list_evals()) == 1
    assert svc.clear_evals()["cleared"] == 1
    assert svc.list_evals() == []


def test_stop_job_when_idle_is_noop(project):
    svc = StudioService(project)
    assert svc.stop_job()["stopped"] is False


def test_ensure_telemetry_survives_runtime_error(project):
    """The sim may not be up yet when the viewer opens; ensure_telemetry must not raise — the
    supervisor retries once a container exists."""
    class BoomRT:
        def __init__(self, _dir):
            pass
        def start_telemetry(self):
            raise RuntimeError("no container yet")

    svc = StudioService(project, runtime_factory=BoomRT)
    try:
        assert svc.ensure_telemetry()["telemetry"] == "on"
    finally:
        svc._telemetry_on = False
