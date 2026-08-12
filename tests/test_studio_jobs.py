import time

from robotbase.studio.jobs import JobManager


def _wait(job, timeout=2.0):
    end = time.time() + timeout
    while job.status == "running" and time.time() < end:
        time.sleep(0.01)
    return job


def test_job_runs_and_records_result():
    jm = JobManager()
    job = jm.start("run", "drive-forward", lambda: {"passed": True})
    _wait(job)
    assert job.status == "done" and job.result == {"passed": True}


def test_job_records_error():
    jm = JobManager()

    def boom():
        raise RuntimeError("nope")

    job = _wait(jm.start("run", "x", boom))
    assert job.status == "error" and "nope" in job.error


def test_lock_rejects_concurrent_job():
    import threading
    jm = JobManager()
    gate = threading.Event()
    slow = jm.start("up", "slow", lambda: (gate.wait(1.0), {"ok": True})[1])
    busy = jm.start("run", "second", lambda: {"passed": True})
    assert busy.status == "busy"
    gate.set()
    _wait(slow)
    assert slow.status == "done"


def test_snapshot_is_json_safe():
    import json
    jm = JobManager()
    _wait(jm.start("eval", "e", lambda: {"n": 3}))
    snap = jm.snapshot()
    json.dumps(snap)   # must not raise
    assert snap["status"] == "done" and snap["kind"] == "eval"
