"""A minimal single-lock background job runner for Studio. One sim per project (port 8765), so
only one up/run/eval may be active at a time; a concurrent request gets a `busy` job back."""
from __future__ import annotations

import inspect
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Job:
    id: str
    kind: str
    label: str
    status: str = "running"       # running | done | error | busy | stopped
    result: dict | None = None
    error: str | None = None
    stop: threading.Event = field(default_factory=threading.Event, repr=False)


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: Job | None = None

    @property
    def current(self) -> Job | None:
        return self._current

    def start(self, kind: str, label: str, fn: Callable) -> Job:
        with self._lock:
            if self._current is not None and self._current.status == "running":
                return Job(id="busy", kind=kind, label=label, status="busy",
                           error="a run is already in progress")
            job = Job(id="job_" + uuid.uuid4().hex[:12], kind=kind, label=label)
            self._current = job

        def _run() -> None:
            try:
                # Pass the stop event to functions that accept it; keep zero-arg fns working.
                takes_arg = False
                try:
                    takes_arg = len(inspect.signature(fn).parameters) >= 1
                except (TypeError, ValueError):
                    pass
                job.result = fn(job.stop) if takes_arg else fn()
                job.status = "done"
            except RunStopped:
                job.status = "stopped"
            except Exception as e:  # noqa: BLE001 — surface any job failure to the UI
                job.error = str(e)
                job.status = "error"

        threading.Thread(target=_run, daemon=True).start()
        return job

    def request_stop(self) -> dict:
        """Signal the running job to cancel. It ends as `stopped` once it unwinds (a long wait or
        sim call breaks via the stop event); a no-op if nothing is running."""
        j = self._current
        if j is None or j.status != "running":
            return {"stopped": False, "reason": "no run in progress"}
        j.stop.set()
        return {"stopped": True, "id": j.id}

    def snapshot(self) -> dict:
        j = self._current
        if j is None:
            return {"status": "idle"}
        return {"id": j.id, "kind": j.kind, "label": j.label,
                "status": j.status, "result": j.result, "error": j.error}


# Imported at end to avoid a circular import (scenario_runner imports nothing from studio).
from robotbase.scenario_runner import RunStopped  # noqa: E402
