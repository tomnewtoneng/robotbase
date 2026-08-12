"""StudioService — the framework-agnostic core of Studio. Reads project facts + artifacts and
drives run/eval/up/down through the core (describe / run_scenario / run_eval / Runtime), serialized
by a single JobManager. No web-framework imports — unit-tested directly."""
from __future__ import annotations

import glob
import json
import os

from robotbase.describe import describe
from robotbase.runtime import Runtime
from robotbase.studio.jobs import Job, JobManager


class StudioService:
    def __init__(self, project_dir: str, runtime_factory=Runtime) -> None:
        self.project_dir = project_dir
        self._runtime_factory = runtime_factory
        self.jobs = JobManager()

    # ---- reads ----
    def project(self) -> dict:
        return describe(self.project_dir)

    def _scenario_path(self, name: str) -> str:
        return os.path.join(self.project_dir, "simulation", "scenarios", f"{name}.yaml")

    def _read_reports(self, kind: str, filename: str) -> list[dict]:
        out: list[dict] = []
        for d in sorted(glob.glob(os.path.join(self.project_dir, ".robotbase", kind, "*")),
                        key=os.path.getmtime, reverse=True):
            f = os.path.join(d, filename)
            if os.path.isfile(f):
                try:
                    out.append(json.load(open(f)))
                except (OSError, json.JSONDecodeError):
                    continue
        return out

    def list_runs(self) -> list[dict]:
        return self._read_reports("runs", "result.json")

    def _read_json(self, *parts: str) -> dict:
        path = os.path.join(self.project_dir, ".robotbase", *parts)
        try:
            return json.load(open(path))
        except (OSError, json.JSONDecodeError):
            return {}

    def get_run(self, run_id: str) -> dict:
        result = self._read_json("runs", run_id, "result.json")
        sidecar = self._read_json("runs", run_id, "episode.json")
        return {**result,
                "events": sidecar.get("events", []),
                "scenario_spec": sidecar.get("scenario_spec", {})}

    def list_evals(self) -> list[dict]:
        return self._read_reports("evals", "report.json")

    def get_eval(self, eval_id: str) -> dict:
        return json.load(open(os.path.join(self.project_dir, ".robotbase", "evals", eval_id, "report.json")))

    def status(self) -> dict:
        try:
            return self._runtime_factory(self.project_dir).simulation_status()
        except Exception as e:  # noqa: BLE001 — status must never 500 the UI
            return {"running": False, "error": str(e)}

    def foxglove(self) -> dict:
        return {"url": "https://studio.foxglove.dev/?ds=foxglove-websocket&ds.url=ws://localhost:8765",
                "hint": "Bring the sim up with the Foxglove bridge, then import foxglove/layout.json "
                        "(Layouts -> Import)."}

    def latest_pose(self) -> dict:
        return self._read_json("telemetry.jsonl")

    def job_snapshot(self) -> dict:
        return self.jobs.snapshot()

    # ---- jobs (single-lock, background) ----
    def start_up(self) -> Job:
        def _job() -> dict:
            rt = self._runtime_factory(self.project_dir)
            out = rt.up()
            try:
                rt.start_telemetry()
            except Exception:  # noqa: BLE001 — telemetry is best-effort; up still succeeds
                pass
            return out
        return self.jobs.start("up", "up", _job)

    def start_down(self) -> Job:
        def _job() -> dict:
            rt = self._runtime_factory(self.project_dir)
            try:
                rt.stop_telemetry()
            except Exception:  # noqa: BLE001
                pass
            return rt.down()
        return self.jobs.start("down", "down", _job)

    def start_run(self, scenario: str) -> Job:
        def _job() -> dict:
            from robotbase.schema import Scenario
            from robotbase.scenario_runner import run_scenario
            rt = self._runtime_factory(self.project_dir)
            run_dir = os.path.join(self.project_dir, ".robotbase", "runs")
            result = run_scenario(Scenario.from_yaml(self._scenario_path(scenario)), rt, run_dir)
            return result.model_dump()
        return self.jobs.start("run", scenario, _job)

    def start_eval(self, scenario: str | None, trials: int = 10, seed: int = 0,
                   all_scenarios: bool = False) -> Job:
        def _job() -> dict:
            from robotbase.eval_stats import write_eval_report
            from robotbase.evals import run_eval, run_eval_suite
            from robotbase.schema import Scenario
            rt = self._runtime_factory(self.project_dir)
            run_dir = os.path.join(self.project_dir, ".robotbase", "runs")
            if all_scenarios:
                names = [s["name"] for s in describe(self.project_dir)["scenarios"]]
                specs = [Scenario.from_yaml(self._scenario_path(n)) for n in names]
                report = run_eval_suite(specs, rt, run_dir, trials, seed)
            else:
                report = run_eval(Scenario.from_yaml(self._scenario_path(scenario)), rt, run_dir,
                                  trials, seed)
            write_eval_report(self.project_dir, report)
            return report
        return self.jobs.start("eval", scenario or "all", _job)
