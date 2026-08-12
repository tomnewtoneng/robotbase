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


def test_get_run_without_sidecar_tolerates(project):
    svc = StudioService(project)
    rd = os.path.join(project, ".robotbase", "runs", "run_2")
    os.makedirs(rd)
    open(os.path.join(rd, "result.json"), "w").write('{"run_id":"run_2","passed":true,"metrics":{}}')
    run = svc.get_run("run_2")
    assert run["events"] == [] and run["scenario_spec"] == {}
