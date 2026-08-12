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
