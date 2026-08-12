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


def test_foxglove_url_endpoint(client):
    c, _ = client
    assert "8765" in c.get("/api/foxglove-url").json()["url"]


def test_index_page_renders_project(client):
    c, _ = client
    html = c.get("/").text
    assert "srvbot" in html and "drive-forward" in html and "/static/htmx.min.js" in html


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
