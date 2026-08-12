import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from robotbase.generator import create_project, template_dir
from robotbase.studio.server import create_app
from robotbase.studio.service import StudioService


@pytest.fixture
def project(tmp_path):
    return create_project("tbot", str(tmp_path), template_dir("differential-drive"))


def test_latest_pose_reads_jsonl(project):
    svc = StudioService(project)
    assert svc.latest_pose() == {}
    rb = os.path.join(project, ".robotbase")
    os.makedirs(rb, exist_ok=True)
    open(os.path.join(rb, "telemetry.jsonl"), "w").write(json.dumps({"x": 1.0, "y": 2.0, "yaw": 0.5}))
    assert svc.latest_pose() == {"x": 1.0, "y": 2.0, "yaw": 0.5}


def test_start_up_launches_telemetry(project):
    calls = []

    class _FakeRT:
        def __init__(self, *_):
            pass

        def up(self):
            calls.append("up")
            return {"container": "up"}

        def start_telemetry(self):
            calls.append("telemetry")

        def down(self):
            calls.append("down")
            return {}

        def stop_telemetry(self):
            calls.append("stop_telemetry")

    svc = StudioService(project, runtime_factory=_FakeRT)
    job = svc.start_up()
    for _ in range(200):
        if job.status != "running":
            break
        time.sleep(0.01)
    assert "up" in calls and "telemetry" in calls


def test_telemetry_route_registered(project):
    # /telemetry is an infinite SSE stream (can't consume it in a test) — assert it's wired up
    app = create_app(project)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/telemetry" in paths
