"""StudioService — the framework-agnostic core of Studio. Reads project facts + artifacts and
drives run/eval/up/down through the core (describe / run_scenario / run_eval / Runtime), serialized
by a single JobManager. No web-framework imports — unit-tested directly."""
from __future__ import annotations

import glob
import json
import os
import threading
import time

from robotbase.describe import describe
from robotbase.runtime import Runtime
from robotbase.studio.jobs import Job, JobManager


class StudioService:
    def __init__(self, project_dir: str, runtime_factory=Runtime) -> None:
        self.project_dir = project_dir
        self._runtime_factory = runtime_factory
        self.jobs = JobManager()
        self._telemetry_on = False       # supervisor active between up and down
        self._telemetry_path = os.path.join(project_dir, ".robotbase", "telemetry.jsonl")

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

    _FILE_PATTERNS = ("robot.yaml", "world.yaml", "robotbase.yaml", "AGENTS.md", ".mcp.json",
                      "policy.py", "simulation/scenarios/*.yaml", "src/*/*/controller.py")

    def _allowed(self, path: str) -> bool:
        if not isinstance(path, str) or not path or os.path.isabs(path):
            return False
        normalized = os.path.normpath(path).replace("\\", "/")
        if normalized == ".." or normalized.startswith("../"):
            return False
        root = os.path.realpath(self.project_dir)
        target = os.path.realpath(os.path.join(root, normalized))
        try:
            if os.path.commonpath([root, target]) != root:
                return False
        except ValueError:
            return False
        if normalized in self._FILE_PATTERNS[:6]:
            return True
        parts = normalized.split("/")
        return ((len(parts) == 3 and parts[:2] == ["simulation", "scenarios"]
                 and parts[2].endswith(".yaml"))
                or (len(parts) == 4 and parts[0] == "src"
                    and parts[-1] == "controller.py"))

    def list_files(self) -> list[dict]:
        files = []
        for pattern in self._FILE_PATTERNS:
            for target in glob.glob(os.path.join(self.project_dir, pattern)):
                relative = os.path.relpath(target, self.project_dir).replace(os.sep, "/")
                if self._allowed(relative) and os.path.isfile(target):
                    files.append({"path": relative, "mtime": os.path.getmtime(target)})
        rank = lambda item: (0 if item["path"] in ("robot.yaml", "world.yaml", "robotbase.yaml")
                              else 1 if item["path"].startswith("simulation/scenarios/") else 2, item["path"])
        return sorted({item["path"]: item for item in files}.values(), key=rank)

    def read_file(self, path: str) -> dict:
        if not self._allowed(path):
            raise ValueError("file is not editable in Studio")
        target = os.path.join(self.project_dir, path)
        if not os.path.isfile(target):
            raise FileNotFoundError(path)
        return {"content": open(target, encoding="utf-8").read(), "mtime": os.path.getmtime(target)}

    def write_file(self, path: str, content: str) -> dict:
        if not self._allowed(path) or not isinstance(content, str):
            raise ValueError("file is not editable in Studio")
        target = os.path.join(self.project_dir, path)
        if not os.path.isfile(target):
            raise FileNotFoundError(path)
        previous = open(target, encoding="utf-8").read()
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(content)
        project_changed = path in ("robot.yaml", "world.yaml", "robotbase.yaml")
        if project_changed:
            from robotbase.generator import recompile_project
            try:
                recompile_project(self.project_dir)
            except Exception as exc:
                # A failed compile must not leave authored source and generated simulation apart.
                with open(target, "w", encoding="utf-8") as handle:
                    handle.write(previous)
                recompile_project(self.project_dir)
                raise ValueError(f"could not compile {path}: {exc}") from exc
        return {"mtime": os.path.getmtime(target), "project_changed": project_changed}


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

    # ---- telemetry supervisor ----
    # Robotbase restarts the sim container on every scenario reset, which kills the in-container
    # telemetry node. This daemon keeps it alive: while active, if the pose file goes stale (the
    # node heartbeats at 10 Hz), relaunch it. The staleness check is a cheap host-side file stat.
    def ensure_telemetry(self) -> dict:
        """Start the telemetry supervisor without a full ``up()``.

        The 3D viewer must show live motion for a sim the *agent* launched (via its MCP tools),
        not only one brought up through Studio's Up button. The supervisor relaunches the in-sim
        telemetry node whenever the pose file goes stale, so it attaches to whatever container is
        running. Idempotent: if a supervisor is already active (Up or a prior ensure), leave it."""
        if self._telemetry_on:
            return {"telemetry": "already-on"}
        self._telemetry_on = True
        rt = self._runtime_factory(self.project_dir)
        try:
            rt.start_telemetry()     # attach now if a sim is already up
        except Exception:  # noqa: BLE001 — the sim may not be up yet; the supervisor retries
            pass
        threading.Thread(target=self._supervise_telemetry, args=(rt,), daemon=True).start()
        return {"telemetry": "on"}

    def _supervise_telemetry(self, rt) -> None:
        while self._telemetry_on:
            time.sleep(2.0)                  # let start_up's launch write a first heartbeat
            try:
                mtime = os.path.getmtime(self._telemetry_path)
                stale = (time.time() - mtime) > 3.0
            except OSError:
                stale = True
            if stale and self._telemetry_on:
                try:
                    rt.start_telemetry()     # relaunch after a container restart killed it
                except Exception:  # noqa: BLE001 — best-effort; keep supervising
                    pass

    # ---- jobs (single-lock, background) ----
    def start_up(self) -> Job:
        def _job() -> dict:
            rt = self._runtime_factory(self.project_dir)
            out = rt.up()
            try:
                rt.start_telemetry()
                if not self._telemetry_on:
                    self._telemetry_on = True
                    threading.Thread(target=self._supervise_telemetry, args=(rt,), daemon=True).start()
            except Exception:  # noqa: BLE001 — telemetry is best-effort; up still succeeds
                pass
            return out
        return self.jobs.start("up", "up", _job)

    def start_down(self) -> Job:
        def _job() -> dict:
            self._telemetry_on = False       # stop the supervisor
            rt = self._runtime_factory(self.project_dir)
            try:
                rt.stop_telemetry()
            except Exception:  # noqa: BLE001
                pass
            try:
                os.remove(self._telemetry_path)   # so the viewer shows the robot at home when down
            except OSError:
                pass
            return rt.down()
        return self.jobs.start("down", "down", _job)

    def start_run(self, scenario: str) -> Job:
        def _job(stop) -> dict:
            from robotbase.schema import Scenario
            from robotbase.scenario_runner import run_scenario
            rt = self._runtime_factory(self.project_dir)
            run_dir = os.path.join(self.project_dir, ".robotbase", "runs")
            result = run_scenario(Scenario.from_yaml(self._scenario_path(scenario)), rt, run_dir,
                                  stop_event=stop)
            return result.model_dump()
        return self.jobs.start("run", scenario, _job)

    def start_eval(self, scenario: str | None, trials: int = 10, seed: int = 0,
                   all_scenarios: bool = False) -> Job:
        def _job(stop) -> dict:
            from robotbase.eval_stats import write_eval_report
            from robotbase.evals import run_eval, run_eval_suite
            from robotbase.schema import Scenario
            rt = self._runtime_factory(self.project_dir)
            run_dir = os.path.join(self.project_dir, ".robotbase", "runs")
            if all_scenarios:
                names = [s["name"] for s in describe(self.project_dir)["scenarios"]]
                specs = [Scenario.from_yaml(self._scenario_path(n)) for n in names]
                report = run_eval_suite(specs, rt, run_dir, trials, seed, stop_event=stop)
            else:
                report = run_eval(Scenario.from_yaml(self._scenario_path(scenario)), rt, run_dir,
                                  trials, seed, stop_event=stop)
            write_eval_report(self.project_dir, report)
            return report
        return self.jobs.start("eval", scenario or "all", _job)

    def stop_job(self) -> dict:
        """Cancel the in-progress run/eval (Studio's Stop button)."""
        return self.jobs.request_stop()

    # ---- artifact management (clear / delete from the side panes) ----
    def _delete_artifact(self, kind: str, artifact_id: str) -> dict:
        import shutil
        root = os.path.realpath(os.path.join(self.project_dir, ".robotbase", kind))
        target = os.path.realpath(os.path.join(root, artifact_id))
        # Guard against traversal — only a direct child dir of runs/ or evals/ may be removed.
        if os.path.dirname(target) != root or not os.path.isdir(target):
            raise ValueError(f"unknown {kind[:-1]}: {artifact_id}")
        shutil.rmtree(target)
        return {"deleted": artifact_id}

    def _clear_artifacts(self, kind: str) -> dict:
        import shutil
        root = os.path.join(self.project_dir, ".robotbase", kind)
        removed = 0
        for entry in glob.glob(os.path.join(root, "*")):
            if os.path.isdir(entry):
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
        return {"cleared": removed}

    def delete_run(self, run_id: str) -> dict:
        return self._delete_artifact("runs", run_id)

    def clear_runs(self) -> dict:
        return self._clear_artifacts("runs")

    def delete_eval(self, eval_id: str) -> dict:
        return self._delete_artifact("evals", eval_id)

    def clear_evals(self) -> dict:
        return self._clear_artifacts("evals")
