import os

import pytest
from fastapi.testclient import TestClient

from robotbase.generator import create_project, template_dir
from robotbase.studio.server import create_app


@pytest.fixture
def client(tmp_path):
    project = create_project("srvbot", str(tmp_path), template_dir("differential-drive"))
    return TestClient(create_app(project)), project


def test_project_endpoint(client):
    c, _ = client
    r = c.get("/api/project")
    assert r.status_code == 200 and r.json()["robot"]["template"] == "differential-drive"


def test_runs_and_evals_endpoints(client):
    c, project = client
    assert c.get("/api/runs").json() == []
    ed = os.path.join(project, ".robotbase", "evals", "eval_z")
    os.makedirs(ed)
    open(os.path.join(ed, "report.json"), "w").write('{"eval_id":"eval_z","success_rate":1.0}')
    assert c.get("/api/evals").json()[0]["eval_id"] == "eval_z"
    assert c.get("/api/evals/eval_z").json()["success_rate"] == 1.0



def test_files_endpoints_round_trip_and_reject_disallowed(client):
    c, _ = client
    files = c.get("/api/files").json()
    assert any(item["path"] == "robot.yaml" for item in files)
    before = c.get("/api/files/content", params={"path": "robot.yaml"})
    assert before.status_code == 200 and "differential-drive" in before.json()["content"]
    saved = c.post("/api/files/save", json={"path": "robot.yaml", "content": before.json()["content"] + "\n# saved\n"})
    assert saved.status_code == 200 and "saved" in c.get("/api/files/content", params={"path": "robot.yaml"}).json()["content"]
    assert c.get("/api/files/content", params={"path": "../secret"}).status_code == 400
    assert c.post("/api/files/save", json={"path": ".robotbase/x", "content": "no"}).status_code == 400


def test_foxglove_url_endpoint(client):
    c, _ = client
    assert "8765" in c.get("/api/foxglove-url").json()["url"]


def test_run_detail_endpoint_includes_events(client):
    c, project = client
    rd = os.path.join(project, ".robotbase", "runs", "run_x")
    os.makedirs(rd)
    open(os.path.join(rd, "result.json"), "w").write('{"run_id":"run_x","passed":true,"metrics":{}}')
    open(os.path.join(rd, "episode.json"), "w").write('{"events":[{"type":"e","timestamp":1.0}],"scenario_spec":{}}')
    j = c.get("/api/runs/run_x").json()
    assert j["passed"] is True and j["events"][0]["type"] == "e"


def test_index_page_renders_project(client):
    c, _ = client
    html = c.get("/").text
    assert "srvbot" in html and "drive-forward" in html
    assert "/static/studio.css" in html and "/static/htmx.min.js" in html
    assert "ROBOTBASE" in html
    for section in ("Project", "Scenarios", "Runs", "Evals"):
        assert section in html
    assert "/static/three.min.js" in html and 'id="btn-3d"' in html
    assert 'id="btn-files"' in html and 'id="file-list"' in html
    assert 'id="btn-reset"' in html and 'id="clear-runs"' in html
    assert 'id="btn-chat"' not in html   # chat pane removed — agent is driven from the terminal


def test_run_endpoint_uses_injected_fake_and_locks(tmp_path):
    # inject a fake runtime so no Docker is needed; assert the job starts and a 2nd is busy
    import threading
    from robotbase.results import Metrics
    from robotbase.studio.service import StudioService
    from robotbase.studio.server import create_app
    project = create_project("lockbot", str(tmp_path), template_dir("differential-drive"))
    gate = threading.Event()

    class _FakeRT:
        def __init__(self, *_):
            pass

        def reset(self):
            pass

        def set_robot_pose(self, p):
            pass

        def spawn_box(self, o):
            pass

        def run_action(self, a):
            pass

        def collect_metrics(self):
            gate.wait(1.0)
            return Metrics(distance_travelled_metres=2.0)

    svc = StudioService(project, runtime_factory=_FakeRT)
    c = TestClient(create_app(project, service=svc))
    first = c.post("/api/run", json={"scenario": "drive-forward"}).json()
    assert first["status"] in ("running", "done")
    second = c.post("/api/run", json={"scenario": "drive-forward"}).json()
    assert second["status"] == "busy"
    gate.set()


def test_delete_and_clear_runs_endpoints(client):
    c, project = client
    for rid in ("run_p", "run_q"):
        rd = os.path.join(project, ".robotbase", "runs", rid)
        os.makedirs(rd)
        open(os.path.join(rd, "result.json"), "w").write(f'{{"run_id":"{rid}","passed":true,"metrics":{{}}}}')
    assert len(c.get("/api/runs").json()) == 2
    assert c.delete("/api/runs/run_p").status_code == 200
    assert [r["run_id"] for r in c.get("/api/runs").json()] == ["run_q"]
    assert c.delete("/api/runs/does_not_exist").status_code == 404
    assert c.delete("/api/runs").json()["cleared"] == 1
    assert c.get("/api/runs").json() == []


def test_delete_and_clear_evals_endpoints(client):
    c, project = client
    d = os.path.join(project, ".robotbase", "evals", "eval_k")
    os.makedirs(d)
    open(os.path.join(d, "report.json"), "w").write('{"eval_id":"eval_k","success_rate":1.0}')
    assert c.delete("/api/evals/eval_k").status_code == 200
    assert c.get("/api/evals").json() == []


def test_job_stop_endpoint_idle(client):
    c, _ = client
    assert c.post("/api/job/stop").json()["stopped"] is False


def test_telemetry_ensure_endpoint(tmp_path):
    from robotbase.studio.service import StudioService
    project = create_project("telbot", str(tmp_path), template_dir("differential-drive"))

    class _FakeRT:
        def __init__(self, *_):
            pass

        def start_telemetry(self):
            pass

    svc = StudioService(project, runtime_factory=_FakeRT)
    c = TestClient(create_app(project, service=svc))
    r = c.post("/api/telemetry/ensure")
    try:
        assert r.status_code == 200 and r.json()["telemetry"] == "on"
    finally:
        svc._telemetry_on = False
