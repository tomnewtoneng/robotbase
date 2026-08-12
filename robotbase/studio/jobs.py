"""A minimal single-lock background job runner for Studio. One sim per project (port 8765), so
only one up/run/eval may be active at a time; a concurrent request gets a `busy` job back."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Callable


@dataclass
class Job:
    id: str
    kind: str
    label: str
    status: str = "running"       # running | done | error | busy
    result: dict | None = None
    error: str | None = None


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: Job | None = None

    @property
    def current(self) -> Job | None:
        return self._current

    def start(self, kind: str, label: str, fn: Callable[[], dict]) -> Job:
        with self._lock:
            if self._current is not None and self._current.status == "running":
                return Job(id="busy", kind=kind, label=label, status="busy",
                           error="a run is already in progress")
            job = Job(id="job_" + uuid.uuid4().hex[:12], kind=kind, label=label)
            self._current = job

        def _run() -> None:
            try:
                job.result = fn()
                job.status = "done"
            except Exception as e:  # noqa: BLE001 — surface any job failure to the UI
                job.error = str(e)
                job.status = "error"

        threading.Thread(target=_run, daemon=True).start()
        return job

    def snapshot(self) -> dict:
        j = self._current
        if j is None:
            return {"status": "idle"}
        return {"id": j.id, "kind": j.kind, "label": j.label,
                "status": j.status, "result": j.result, "error": j.error}
