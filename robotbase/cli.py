"""The Robotbase CLI — create, run, and inspect agent-ready robotics projects.

Exposes the same operations as the MCP server for humans who prefer a shell.
Command output is JSON on stdout (so scripts/agents can parse it); human
next-step hints go to stderr. `robotbase test <scenario>` exits 0 on pass,
1 on fail. The project is taken from ROBOTBASE_PROJECT_DIR (default: cwd).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys

from robotbase.runtime import Runtime
from robotbase.schema import Scenario
from robotbase.scenario_runner import run_scenario

HELP = """robotbase — agent-ready ROS 2 robotics projects

Usage: robotbase <command> [options]

Start a project:
  create <name> [--path DIR]     generate a new project from the template
  up                             start the container and build the workspace
  stop                           stop the simulation (keep the container)
  down                           stop and remove the container

Run & inspect:
  describe                       report the robot, world, and scenarios (structured facts)
  build                          build the ROS workspace
  launch [--gui]                 start the simulation (--gui to watch in Foxglove)
  test [NAME] [--gui] [--list]   run a scenario, or --list them
  test --all [--trials N]        run every scenario as a suite (robustness + regressions)
  bench [--list] [--agent NAME]  score the controller on the RobotBench task set
  status                         report simulation status
  topics                         list active ROS topics

Inspect a recorded run:
  episode summary [RUN]          topics, message counts, duration (RUN defaults to latest)
  episode events [RUN]           the derived event timeline (e.g. collision)
  episode query [RUN] --topic T [--around SEC] [--window SEC]
                                 a bounded, downsampled slice of one topic
  diagnose [RUN]                 explain why a run failed (assertions + episode evidence)
  clean [--keep N]               delete old recorded runs (keep the newest N, default 20)

Author behaviours:
  scenario add <name>            scaffold a new scenario to work on
  scenario list                  list scenarios

  help                           show this help

Docs: https://github.com/tomnewtoneng/robotbase
"""


def _hint(msg: str) -> None:
    """Print a human next-step hint to stderr (keeps stdout clean for scripts)."""
    # Flush stdout first so the JSON result is fully written before the hint — otherwise,
    # when a caller merges the streams (2>&1), the unbuffered stderr hint can interleave
    # into the block-buffered stdout JSON and corrupt it.
    sys.stdout.flush()
    print(f"\n→ {msg}", file=sys.stderr)


def _scenarios(project: str) -> dict[str, str]:
    directory = os.path.join(project, "simulation", "scenarios")
    return {
        os.path.splitext(os.path.basename(p))[0]: p
        for p in glob.glob(os.path.join(directory, "*.yaml"))
    }


def _scenario_scaffold(name: str, package: str) -> str:
    return f"""version: 1
name: {name}
description: Describe what this scenario verifies.
timeout_seconds: 30

setup:
  reset_world: true
  robot:
    pose: {{x: 0.0, y: 0.0, yaw: 0.0}}
  # obstacles:
  #   - id: box_1
  #     type: box
  #     pose: {{x: 2.0, y: 0.0, z: 0.25}}
  #     size: {{x: 0.5, y: 1.0, z: 0.5}}

actions:
  - {{type: wait_for_topic, topic: /scan, timeout_seconds: 5}}
  - {{type: run_node, package: {package}, executable: controller}}
  - {{type: wait, duration_seconds: 10}}

assertions:
  # See docs/SCENARIO-FORMAT.md for all assertion types.
  - {{type: no_collision}}
  - {{type: required_topic_messages, topic: /scan, minimum_count: 5}}
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="robotbase", add_help=False)
    sub = parser.add_subparsers(dest="cmd")

    create = sub.add_parser("create", help="generate a new project")
    create.add_argument("name")
    create.add_argument(
        "--template", default="differential-drive",
        help="robot template to use (see: robotbase templates)",
    )
    create.add_argument("--path", default=".", help="parent directory for the new project")

    sub.add_parser("templates", help="list available robot templates")
    sub.add_parser("describe", help="report robot/world/scenario facts")
    sub.add_parser("up", help="start the container and build the workspace")
    sub.add_parser("stop", help="stop the simulation (keep the container)")
    sub.add_parser("down", help="stop and remove the container")
    sub.add_parser("build", help="build the ROS workspace")
    sub.add_parser("status", help="report simulation status")
    sub.add_parser("topics", help="list ROS topics")
    sub.add_parser("help", help="show help")

    launch_p = sub.add_parser("launch", help="start the simulation")
    launch_p.add_argument("--gui", nargs="?", const="foxglove", default="none")

    test = sub.add_parser("test", help="run a scenario (or --list / --all)")
    test.add_argument("scenario", nargs="?")
    test.add_argument("--list", action="store_true")
    test.add_argument("--all", action="store_true", help="run every scenario as a suite")
    test.add_argument("--trials", type=int, default=1,
                      help="run N randomized trials (domain randomization) and report robustness")
    test.add_argument("--seed", type=int, default=0, help="RNG seed for --trials")
    test.add_argument("--gui", nargs="?", const="foxglove", default="none")

    scen = sub.add_parser("scenario", help="author scenarios (add | list)")
    scen.add_argument("action", choices=["add", "list"])
    scen.add_argument("name", nargs="?")

    clean = sub.add_parser("clean", help="delete old recorded runs")
    clean.add_argument("--keep", type=int, default=20, help="how many recent runs to keep")

    diag = sub.add_parser("diagnose", help="explain why a run failed")
    diag.add_argument("run", nargs="?", default="latest")

    bench = sub.add_parser("bench", help="score the controller against RobotBench")
    bench.add_argument("--list", action="store_true", help="list the RobotBench task set")
    bench.add_argument("--agent", help="tag the scorecard with the agent/model used")
    bench.add_argument("--trials", type=int, default=3, help="randomized trials per task")
    bench.add_argument("--seed", type=int, default=0)

    ep = sub.add_parser("episode", help="inspect a recorded run (summary | events | query)")
    ep.add_argument("action", choices=["summary", "events", "query"])
    ep.add_argument("run", nargs="?", default="latest")
    ep.add_argument("--topic")
    ep.add_argument("--around", type=float)
    ep.add_argument("--window", type=float, default=2.0)
    ep.add_argument("--max", type=int, default=40, dest="max_samples")

    return parser


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return

    args = _build_parser().parse_args()
    if not args.cmd:
        print(HELP)
        return

    if args.cmd == "templates":
        from robotbase.generator import list_templates

        print("\n".join(list_templates()))
        return

    if args.cmd == "create":
        from robotbase.generator import create_project, template_dir

        try:
            tdir = template_dir(args.template)
        except ValueError as e:
            print(e)
            sys.exit(2)
        dest = create_project(args.name, args.path, tdir)
        print(f"Created Robotbase project: {dest}  (template: {args.template})")
        _hint(f"Next:  cd {dest} && robotbase up   (then: robotbase test --gui)")
        return

    if args.cmd == "describe":
        from robotbase.describe import describe

        project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
        print(json.dumps(describe(project), indent=2))
        _hint("Ground truth for this project — robot geometry, world layout, and scenarios.")
        return

    if args.cmd == "bench" and args.list:
        from robotbase.bench import BENCHMARK_VERSION, TASKS

        print(json.dumps({"benchmark": f"RobotBench v{BENCHMARK_VERSION}", "tasks": TASKS}, indent=2))
        return

    project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
    rt = Runtime(project)
    rt.gui = getattr(args, "gui", "none")
    scenarios = _scenarios(project)
    controller_pkg = rt.launch_package.removesuffix("_bringup")

    if args.cmd == "up":
        result = rt.up()
        print(json.dumps(result, indent=2))
        if result.get("build", {}).get("passed"):
            _hint("Ready. Run a scenario:  robotbase test --gui   (list: robotbase test --list)")
        else:
            _hint("Container up, but the build failed — check the errors above.")

    elif args.cmd == "build":
        result = rt.build()
        print(json.dumps(result, indent=2))
        _hint(
            "Run a scenario:  robotbase test <name>   (list: robotbase test --list)"
            if result["passed"]
            else "Build failed — fix the errors above and rebuild."
        )

    elif args.cmd == "launch":
        result = rt.launch()
        print(json.dumps(result, indent=2))
        if result.get("visualization"):
            _hint("Watch: connect Foxglove to ws://localhost:8765")
        _hint("Run scenarios:  robotbase test <name>    Stop:  robotbase stop")

    elif args.cmd == "clean":
        runs_dir = os.path.join(project, ".robotbase", "runs")
        runs = sorted((d for d in glob.glob(os.path.join(runs_dir, "*")) if os.path.isdir(d)),
                      key=os.path.getmtime, reverse=True)
        removed = 0
        for d in runs[args.keep:]:
            shutil.rmtree(d, ignore_errors=True)
            removed += not os.path.exists(d)
        kept = min(len(runs), args.keep)
        print(json.dumps({"kept": kept, "removed": removed}, indent=2))
        _hint(f"Removed {removed} old run(s); kept the {kept} most recent.")

    elif args.cmd == "diagnose":
        from robotbase.diagnose import collision_time, diagnose

        runs_dir = os.path.join(project, ".robotbase", "runs")
        if args.run in ("latest", "", None):
            dirs = [d for d in glob.glob(os.path.join(runs_dir, "*")) if os.path.isdir(d)]
            if not dirs:
                print("no runs found"); sys.exit(2)
            run_path = max(dirs, key=os.path.getmtime)
        else:
            run_path = os.path.join(runs_dir, args.run)
        result_file = os.path.join(run_path, "result.json")
        if not os.path.exists(result_file):
            print(f"no result for run {os.path.basename(run_path)!r}"); sys.exit(2)
        with open(result_file) as f:
            result = json.load(f)
        run_id = os.path.basename(run_path)
        events, control = [], None
        try:  # episode inspection is best-effort enrichment; diagnosis works without it
            events = rt.episode_events(run_id).get("events", [])
            ct = collision_time(events)
            if ct is not None:
                q = rt.episode_query(run_id, "/cmd_vel", around=ct, window=0.5, max_samples=1)
                control = q["samples"][-1] if q.get("samples") else None
        except Exception:
            pass
        print(json.dumps(diagnose(result, events, control), indent=2))

    elif args.cmd == "status":
        print(json.dumps(rt.simulation_status(), indent=2))

    elif args.cmd == "topics":
        print("\n".join(f"{t['name']}\t{t['type']}" for t in rt.list_topics()))

    elif args.cmd == "stop":
        print(json.dumps(rt.stop(), indent=2))
        _hint("Simulation stopped (container kept). Restart:  robotbase launch --gui")

    elif args.cmd == "down":
        print(json.dumps(rt.down(), indent=2))
        _hint("Container removed. Bring it back:  robotbase up")

    elif args.cmd == "scenario":
        scen_dir = os.path.join(project, "simulation", "scenarios")
        if args.action == "list":
            print("\n".join(sorted(scenarios)) or "(no scenarios yet)")
            return
        if not args.name:
            print("usage: robotbase scenario add <name>")
            sys.exit(2)
        if args.name in scenarios:
            print(f"scenario {args.name!r} already exists")
            sys.exit(2)
        os.makedirs(scen_dir, exist_ok=True)
        path = os.path.join(scen_dir, f"{args.name}.yaml")
        with open(path, "w") as f:
            f.write(_scenario_scaffold(args.name, controller_pkg))
        print(f"Created {path}")
        _hint(f"Edit it (see docs/SCENARIO-FORMAT.md), then:  robotbase test {args.name} --gui")

    elif args.cmd == "test":
        run_dir = os.path.join(project, ".robotbase", "runs")

        if args.all:  # suite: every scenario (each with --trials randomized trials)
            from robotbase.evals import compare_suites, run_suite

            specs = [Scenario.from_yaml(scenarios[n]) for n in sorted(scenarios)]
            report = run_suite(specs, rt, run_dir, args.trials, args.seed)
            # Behavioral regression tracking: diff against the previous suite run.
            hist = os.path.join(project, ".robotbase", "last-suite.json")
            changes = None
            if os.path.exists(hist):
                with open(hist) as f:
                    changes = compare_suites(json.load(f), report)
            os.makedirs(os.path.dirname(hist), exist_ok=True)
            with open(hist, "w") as f:
                json.dump(report, f, indent=2)
            if changes:
                report["changes"] = changes
            print(json.dumps(report, indent=2))
            _hint(f"{report['fully_passed']}/{report['scenarios']} scenarios fully passed "
                  f"(mean robustness {report['mean_robustness']})."
                  + (f"  ⚠ {len(changes['regressions'])} regression(s)."
                     if changes and changes["regressions"] else ""))
            sys.exit(0 if report["fully_passed"] == report["scenarios"] else 1)

        if args.list or not args.scenario:
            print("\n".join(sorted(scenarios)) or "(no scenarios yet)")
            _hint("Run one:  robotbase test <name>    All:  robotbase test --all    "
                  "Add one:  robotbase scenario add <name>")
            return
        if args.scenario not in scenarios:
            print(f"unknown scenario {args.scenario!r}; available: {sorted(scenarios)}")
            sys.exit(2)
        scenario = Scenario.from_yaml(scenarios[args.scenario])

        if args.trials > 1:  # domain randomization: robustness over N randomized trials
            from robotbase.evals import run_trials

            report = run_trials(scenario, rt, run_dir, args.trials, args.seed)
            print(json.dumps(report, indent=2))
            _hint(f"{args.scenario}: robustness {report['robustness']} "
                  f"({report['passed']}/{report['trials']} trials passed).")
            sys.exit(0 if report["passed"] == report["trials"] else 1)

        result = run_scenario(scenario, rt, run_dir)
        print(json.dumps(result.model_dump(), indent=2))
        if result.passed:
            _hint(f"{args.scenario} passed ✓")
        else:
            _hint(
                f"{args.scenario} failed — inspect the assertions above, edit "
                f"src/{controller_pkg}/{controller_pkg}/controller.py, and rerun. "
                "Or let a coding agent fix it."
            )
        sys.exit(0 if result.passed else 1)

    elif args.cmd == "bench":
        from robotbase.bench import scorecard
        from robotbase.evals import run_suite

        specs = [Scenario.from_yaml(scenarios[n]) for n in sorted(scenarios)]
        suite = run_suite(specs, rt, os.path.join(project, ".robotbase", "runs"),
                          args.trials, args.seed)
        card = scorecard(suite, {"agent": args.agent} if args.agent else None)
        print(json.dumps(card, indent=2))
        _hint(f"RobotBench score {card['score']}/100 — {card['solved']}/{card['tasks']} tasks solved.")
        sys.exit(0 if card["solved"] == card["tasks"] else 1)

    elif args.cmd == "episode":
        if args.action == "summary":
            out = rt.episode_summary(args.run)
            print(json.dumps(out, indent=2))
            _hint(
                "See what happened:  robotbase episode events    "
                "Zoom in:  robotbase episode query --topic /scan --around <t>"
            )
        elif args.action == "events":
            print(json.dumps(rt.episode_events(args.run), indent=2))
            _hint("Zoom in on a moment:  robotbase episode query --topic /scan --around <t>")
        else:
            if not args.topic:
                print("usage: robotbase episode query [RUN] --topic T [--around SEC] [--window SEC]")
                sys.exit(2)
            out = rt.episode_query(args.run, args.topic, args.around, args.window, args.max_samples)
            print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
