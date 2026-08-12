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
import tempfile

from robotbase.generator import recompile_project
from robotbase.runtime import Runtime
from robotbase.schema import Scenario
from robotbase.scenario_runner import run_scenario

HELP = """robotbase — agent-ready ROS 2 robotics projects

Usage: robotbase <command> [options]

Start a project:
  create <name> [--path DIR]     generate a new project from the template
  doctor                         check the environment (Docker, image, ports, deps)
  up                             start the container and build the workspace
  stop                           stop the simulation (keep the container)
  down                           stop and remove the container

Author & inspect the spec:
  schema [--json]                the robot.yaml/world.yaml authoring format reference
  describe                       report the robot, world, and scenarios (structured facts)
  validate                       static physical validation of the compiled robot
  explain                        which links/joints/topics each spec declaration produced

Run & inspect:
  build                          build the ROS workspace
  launch [--gui]                 start the simulation (--gui to watch in Foxglove)
  test [NAME] [--gui] [--list]   run a scenario, or --list them
  test --all [--trials N]        run every scenario as a suite (robustness + regressions)
  eval NAME [--trials N]         statistically evaluate a scenario (success-rate + 95% CI)
  studio [--port N]              launch the Studio web control panel (studio extra)
  bench [--list] [--agent NAME]  score the controller on the RobotBench task set
  robotbench run|report          run the RobotBench validation harness / render results
  status                         report simulation status
  topics                         list active ROS topics

Inspect a recorded run:
  episode summary [RUN]          topics, message counts, duration (RUN defaults to latest)
  episode events [RUN]           the derived event timeline (e.g. collision)
  episode query [RUN] --topic T [--around SEC] [--window SEC]
                                 a bounded, downsampled slice of one topic
  diagnose [RUN]                 explain why a run failed (assertions + episode evidence)
  replay [RUN]                   open a recorded run's episode for visual replay in Foxglove
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
    create.add_argument("--from-urdf", dest="from_urdf", default=None,
                        help="import an existing URDF verbatim instead of the template robot")

    sub.add_parser("templates", help="list available robot templates")
    sub.add_parser("doctor", help="check the environment for common problems")
    sub.add_parser("describe", help="report robot/world/scenario facts")
    schema_p = sub.add_parser("schema", help="print the robot.yaml/world.yaml authoring format reference")
    schema_p.add_argument("--json", action="store_true", help="emit JSON Schema instead of prose")
    sub.add_parser("validate", help="static physical validation of the compiled robot")
    sub.add_parser("explain", help="attribute each compiled artifact to the spec line that made it")
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

    ev = sub.add_parser("eval", help="statistically evaluate a scenario over N randomized trials")
    ev.add_argument("scenario", nargs="?")
    ev.add_argument("--all", action="store_true", help="evaluate every scenario as a suite")
    ev.add_argument("--trials", type=int, default=10, help="number of randomized trials")
    ev.add_argument("--seed", type=int, default=0, help="base RNG seed (reproducible)")

    scen = sub.add_parser("scenario", help="author scenarios (add | list)")
    scen.add_argument("action", choices=["add", "list"])
    scen.add_argument("name", nargs="?")

    pol = sub.add_parser("policy", help="author policies (new)")
    pol.add_argument("action", choices=["new"])

    st = sub.add_parser("studio", help="launch the Studio web control panel (needs the studio extra)")
    st.add_argument("--port", type=int, default=8080)
    st.add_argument("--no-open", action="store_true", help="don't open a browser")

    clean = sub.add_parser("clean", help="delete old recorded runs")
    clean.add_argument("--keep", type=int, default=20, help="how many recent runs to keep")

    diag = sub.add_parser("diagnose", help="explain why a run failed")
    diag.add_argument("run", nargs="?", default="latest")

    rep = sub.add_parser("replay", help="show how to replay a recorded run in Foxglove")
    rep.add_argument("run", nargs="?", default="latest")

    bench = sub.add_parser("bench", help="score the controller against RobotBench")
    bench.add_argument("--list", action="store_true", help="list the RobotBench task set")
    bench.add_argument("--agent", help="tag the scorecard with the agent/model used")
    bench.add_argument("--trials", type=int, default=3, help="randomized trials per task")
    bench.add_argument("--seed", type=int, default=0)

    rbench = sub.add_parser("robotbench", help="run the RobotBench validation harness (run | report)")
    rbench.add_argument("action", choices=["run", "report"])
    rbench.add_argument("--task", default="all", help="task id (e.g. diff/reach-goal) or 'all'")
    rbench.add_argument("--arm", choices=["with", "without", "both"], default="both")
    rbench.add_argument("--model", default="claude-sonnet-5")
    rbench.add_argument("--trials", type=int, default=3, help="randomized trials per (task, arm)")
    rbench.add_argument("--seed", type=int, default=0)
    rbench.add_argument("--out", default="robotbase/robotbench/results",
                         help="directory to write/read trial record JSON files")
    rbench.add_argument("--records", default=None,
                         help="directory of trial record JSON files for `report` "
                              "(default: --out)")

    ep = sub.add_parser("episode", help="inspect a recorded run (summary | events | query)")
    ep.add_argument("action", choices=["summary", "events", "query"])
    ep.add_argument("run", nargs="?", default="latest")
    ep.add_argument("--topic")
    ep.add_argument("--around", type=float)
    ep.add_argument("--window", type=float, default=2.0)
    ep.add_argument("--max", type=int, default=40, dest="max_samples")

    return parser


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return

    args = _build_parser().parse_args(argv)
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
        from_urdf = os.path.abspath(args.from_urdf) if args.from_urdf else None
        dest = create_project(args.name, args.path, tdir, from_urdf=from_urdf)
        print(f"Created Robotbase project: {dest}  (template: {args.template})")
        _hint(f"Next:  cd {dest} && robotbase up   (then: robotbase test --gui)")
        return

    if args.cmd == "doctor":
        from robotbase.doctor import diagnose_environment

        project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
        report = diagnose_environment(project)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["status"] != "fail" else 1)

    if args.cmd == "describe":
        from robotbase.describe import describe

        project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
        print(json.dumps(describe(project), indent=2))
        _hint("Ground truth for this project — robot geometry, world layout, and scenarios.")
        return

    if args.cmd == "schema":
        from robotbase.robotspec.schema_docs import authoring_json_schema, authoring_reference

        print(json.dumps(authoring_json_schema(), indent=2) if args.json else authoring_reference())
        return

    if args.cmd == "validate":
        from robotbase.robotspec.schema import RobotSpec
        from robotbase.robotspec.validate import summarize, validate_robot

        project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
        robot_yaml = os.path.join(project, "robot.yaml")
        if not os.path.exists(robot_yaml):
            print("no robot.yaml in this project")
            sys.exit(2)
        spec = RobotSpec.from_yaml(robot_yaml)
        for p in spec.parts:                       # resolve project-relative custom urdf paths
            if p.use == "custom" and p.urdf and not os.path.isabs(p.urdf):
                p.urdf = os.path.join(project, p.urdf)
        report = summarize(validate_robot(spec))
        print(json.dumps(report, indent=2))
        _hint("Physical sanity of the compiled robot (mass, inertia, joint limits).")
        sys.exit(0 if report["ok"] else 1)

    if args.cmd == "explain":
        from robotbase.robotspec.explain import explain_robot
        from robotbase.robotspec.schema import RobotSpec

        project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
        robot_yaml = os.path.join(project, "robot.yaml")
        if not os.path.exists(robot_yaml):
            print("no robot.yaml in this project")
            sys.exit(2)
        spec = RobotSpec.from_yaml(robot_yaml)
        for p in spec.parts:
            if p.use == "custom" and p.urdf and not os.path.isabs(p.urdf):
                p.urdf = os.path.join(project, p.urdf)
        print(json.dumps(explain_robot(spec), indent=2))
        _hint("Each spec declaration and the links/joints/topics/gz-systems it produced.")
        return

    if args.cmd == "bench" and args.list:
        from robotbase.bench import BENCHMARK_VERSION, TASKS

        print(json.dumps({"benchmark": f"RobotBench v{BENCHMARK_VERSION}", "tasks": TASKS}, indent=2))
        return

    if args.cmd == "robotbench":
        from robotbase.robotbench.records import TrialRecord
        from robotbase.robotbench.report import render_markdown

        if args.action == "report":
            records_dir = args.records or args.out
            records = []
            for path in sorted(glob.glob(os.path.join(records_dir, "*.json"))):
                with open(path) as f:
                    records.append(TrialRecord(**json.load(f)))
            markdown = render_markdown(records)
            os.makedirs("docs", exist_ok=True)
            with open(os.path.join("docs", "ROBOTBENCH-RESULTS.md"), "w") as f:
                f.write(markdown)
            print(markdown)
            return

        # action == "run"
        from robotbase.robotbench import runner
        from robotbase.robotbench.cli_deps import (expand_arms, expand_tasks, real_generate, real_judge,
                                                     real_start_sim, real_teardown)

        try:
            from robotbase.robotbench.real_agent import RealAgent

            agent = RealAgent(model=args.model)
        except ImportError:
            print("robotbench run needs the real agent (Phase 2): install the `bench-agent` extra "
                  "and set ANTHROPIC_API_KEY. See docs/design/robotbench-validation.md.")
            sys.exit(2)

        tasks = expand_tasks(args.task)
        arms = expand_arms(args.arm)
        # Generated ROS project trees are scratch artefacts — keep them out of the
        # tracked repo (--out is only for the record JSONs, see below).
        workdir = tempfile.mkdtemp(prefix="rbench-projects-")
        os.makedirs(args.out, exist_ok=True)
        records = runner.run(
            tasks, arms, args.model, args.trials, agent,
            generate=real_generate(workdir), start_sim=real_start_sim,
            judge_fn=real_judge(args.trials), seed0=args.seed,
            teardown_fn=real_teardown,
        )
        for rec in records:
            fname = f"{rec.task_id.replace('/', '-')}-{rec.arm}-{rec.trial}.json"
            with open(os.path.join(args.out, fname), "w") as f:
                json.dump(rec.model_dump(), f, indent=2)
        print(render_markdown(records))
        return

    project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
    rt = Runtime(project)
    rt.gui = getattr(args, "gui", "none")
    scenarios = _scenarios(project)
    controller_pkg = rt.launch_package.removesuffix("_bringup")

    if args.cmd == "up":
        if recompile_project(project):
            _hint("Recompiled robot.yaml/world.yaml → URDF/SDF.")
        result = rt.up()
        print(json.dumps(result, indent=2))
        if result.get("build", {}).get("passed"):
            _hint("Ready. Run a scenario:  robotbase test --gui   (list: robotbase test --list)")
        else:
            _hint("Container up, but the build failed — check the errors above.")

    elif args.cmd == "build":
        if recompile_project(project):
            _hint("Recompiled robot.yaml/world.yaml → URDF/SDF.")
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
            _hint("Watch: open Foxglove, connect to ws://localhost:8765, and import "
                  "foxglove/layout.json. See docs/VISUALIZATION.md.")
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

    elif args.cmd == "replay":
        runs_dir = os.path.join(project, ".robotbase", "runs")
        if args.run in ("latest", "", None):
            dirs = [d for d in glob.glob(os.path.join(runs_dir, "*")) if os.path.isdir(d)]
            if not dirs:
                print("no runs found"); sys.exit(2)
            run_path = max(dirs, key=os.path.getmtime)
        else:
            run_path = os.path.join(runs_dir, args.run)
        mcap = os.path.join(run_path, "episode.mcap")
        if not os.path.exists(mcap):
            print(f"no episode.mcap for run {os.path.basename(run_path)!r}"); sys.exit(2)
        layout = os.path.join(project, "foxglove", "layout.json")
        print(json.dumps({
            "run": os.path.basename(run_path),
            "mcap": os.path.abspath(mcap),
            "layout": os.path.abspath(layout) if os.path.exists(layout) else None,
            "how_to_view": [
                "Open Foxglove (the desktop app, or https://studio.foxglove.dev in a browser).",
                "'Open local file' -> the .mcap above. On Windows/WSL it's under "
                "\\\\wsl.localhost\\<distro>\\... .",
                "Layouts -> Import -> the layout above (or just set the 3D panel's Display "
                "frame to 'odom').",
                "Press play to replay the run and scrub the timeline. The .mcap is "
                "self-contained (carries the scenario + result as an attachment).",
            ],
        }, indent=2))
        _hint("Replay it in Foxglove — see docs/VISUALIZATION.md. Share the .mcap and anyone "
              "with Foxglove can watch the exact run.")

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

    elif args.cmd == "policy":
        from robotbase.policy_scaffold import write_policy_starter
        try:
            path = write_policy_starter(project)
        except FileExistsError as e:
            print(f"policy already exists: {e}")
            sys.exit(2)
        print(f"Created {path}")
        _hint("Point a scenario at it — set its action to {type: run_policy, module: policy} — "
              "then:  robotbase test <scenario>")

    elif args.cmd == "studio":
        try:
            from robotbase.studio import run_server
        except ImportError:
            print("Studio needs the studio extra:  pip install robotbase-kit[studio]")
            sys.exit(1)
        run_server(project, args.port, not args.no_open)

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

    elif args.cmd == "eval":
        from robotbase.evals import run_eval, run_eval_suite
        from robotbase.eval_stats import render_markdown
        run_dir = os.path.join(project, ".robotbase", "runs")

        if args.all:
            specs = [Scenario.from_yaml(scenarios[n]) for n in sorted(scenarios)]
            if not specs:
                print("(no scenarios to evaluate)")
                sys.exit(2)
            report = run_eval_suite(specs, rt, run_dir, args.trials, args.seed)
        else:
            if not args.scenario or args.scenario not in scenarios:
                print(f"unknown scenario {args.scenario!r}; available: {sorted(scenarios)}")
                sys.exit(2)
            scenario = Scenario.from_yaml(scenarios[args.scenario])
            report = run_eval(scenario, rt, run_dir, args.trials, args.seed)

        eval_dir = os.path.join(project, ".robotbase", "evals", report["eval_id"])
        os.makedirs(eval_dir, exist_ok=True)
        with open(os.path.join(eval_dir, "report.json"), "w") as f:
            json.dump(report, f, indent=2)
        md = render_markdown(report)
        with open(os.path.join(eval_dir, "report.md"), "w") as f:
            f.write(md)
        print(md)
        _hint(f"Eval report saved: .robotbase/evals/{report['eval_id']}/  (report.json + report.md)")

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
