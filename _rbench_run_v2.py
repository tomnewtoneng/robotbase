"""RobotBench v2 batch runner: authoring tasks x arms x trials.

Per trial: scaffold the arm, bring its container up so the agent can build/verify, run the live
agent to AUTHOR the robot+world, then score with the real behavioral judge (real bring-up +
ground-truth pose). Persists transcripts, per-seed judge evidence, records, a manifest, and a
rendered report under a timestamped run dir. Resilient: a failing trial is logged and the batch
continues. Never prints the API key.

    python _rbench_run_v2.py --arms with --tasks author/diff-lidar-world --trials 1 --judge-trials 1
"""
import argparse
import pathlib
import subprocess
import sys
import tempfile
import traceback

from robotbase.robotbench.agent import Caps
from robotbase.robotbench.cli_deps import author_generate, expand_tasks, real_author_judge
from robotbase.robotbench.real_agent import RealAgent
from robotbase.robotbench.records import BENCHMARK_VERSION, TrialRecord
from robotbase.robotbench.report import render_markdown
from robotbase.robotbench.runner import new_run_dir, write_manifest

MODEL = "claude-sonnet-5"


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
    except Exception:
        return "unknown"


def _bring_container_up(project_dir: str, arm: str) -> None:
    """Give the agent a live sim env to build/verify in (the judge later brings up its own)."""
    if arm == "with":
        subprocess.run([sys.executable, "-m", "robotbase", "up"], cwd=project_dir, timeout=1800)
    else:
        subprocess.run(["docker", "compose", "up", "-d"], cwd=project_dir, timeout=600)


def _teardown(project_dir: str, arm: str) -> None:
    if arm == "with":
        subprocess.run([sys.executable, "-m", "robotbase", "down"], cwd=project_dir, timeout=120)
    else:
        subprocess.run(["docker", "compose", "down"], cwd=project_dir, timeout=120)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="with,without", help="comma list: with,without")
    ap.add_argument("--tasks", default="all", help="'all' or a comma list of task ids")
    ap.add_argument("--trials", type=int, default=1, help="agent trials per (task, arm)")
    ap.add_argument("--judge-trials", type=int, default=1, help="judge seeds per trial")
    ap.add_argument("--max-turns", type=int, default=30, help="agent turn cap (keep modest so a "
                    "flailing run cannot burn budget; raise only if a task legitimately needs it)")
    args = ap.parse_args()
    caps = Caps(max_turns=args.max_turns, timeout_s=1400, max_edits=15)

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    tasks = expand_tasks("all") if args.tasks == "all" else \
        [t for tid in args.tasks.split(",") for t in expand_tasks(tid.strip())]

    run_dir = new_run_dir("robotbase/robotbench/results")
    transcripts = pathlib.Path(run_dir) / "transcripts"
    transcripts.mkdir(parents=True, exist_ok=True)
    records_dir = pathlib.Path(run_dir) / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(run_dir, {
        "benchmark": BENCHMARK_VERSION, "model": MODEL, "git_sha": _git_sha(),
        "arms": arms, "tasks": [t["id"] for t in tasks], "trials": args.trials,
        "judge_trials": args.judge_trials,
        "caps": {"max_turns": caps.max_turns, "timeout_s": caps.timeout_s, "max_edits": caps.max_edits},
    })
    print(f"RUN DIR: {run_dir}", flush=True)

    workdir = tempfile.mkdtemp(prefix="rbench-v2-")
    records = []
    for task in tasks:
        for arm in arms:
            for trial in range(args.trials):
                tag = f"{task['id'].replace('/', '_')}-{arm}-{trial}"
                print(f"=== starting {tag} ===", flush=True)
                try:
                    project = author_generate(workdir, arm)(task, trial)
                    _bring_container_up(project, arm)
                    result = RealAgent(model=MODEL).run(project, arm, task, caps)
                    tpath = transcripts / f"{tag}.transcript.json"
                    tpath.write_text(result.transcript, encoding="utf-8")
                    # Clear any sim the agent left running so the judge brings up cleanly.
                    if arm == "with":
                        subprocess.run([sys.executable, "-m", "robotbase", "stop"],
                                       cwd=project, timeout=60)

                    judge_fn = real_author_judge(arm, trials=args.judge_trials,
                                                 evidence_root=str(pathlib.Path(run_dir) / "judge" / tag))
                    verdict = judge_fn(project, task["judge_scenario"], seed=0)

                    rec = TrialRecord(
                        task_id=task["id"], arm=arm, model=MODEL, trial=trial, seed=0,
                        solved=verdict["solved"], robustness=verdict["robustness"],
                        claimed_solved=result.claimed_solved, controller_edits=result.controller_edits,
                        agent_turns=result.agent_turns, wall_clock_s=result.wall_clock_s,
                        tokens=result.tokens, stop_reason=result.stop_reason,
                        transcript_path=str(tpath))
                    (records_dir / f"{tag}.json").write_text(rec.model_dump_json(indent=2))
                    records.append(rec)
                    print(f"RECORD {tag} solved={rec.solved} robustness={rec.robustness} "
                          f"claimed={rec.claimed_solved} edits={rec.controller_edits} "
                          f"turns={rec.agent_turns} stop={rec.stop_reason}", flush=True)
                except Exception as e:  # one trial failing must not kill the batch
                    print(f"EXC {tag}: {e!r}", flush=True)
                    traceback.print_exc()
                finally:
                    try:
                        _teardown(project, arm)
                    except Exception:
                        pass

    if records:
        (pathlib.Path(run_dir) / "ROBOTBENCH-RESULTS.md").write_text(render_markdown(records))
        print(f"WROTE {run_dir}/ROBOTBENCH-RESULTS.md ({len(records)} records)", flush=True)
    print("RUN DONE", flush=True)


if __name__ == "__main__":
    main()
