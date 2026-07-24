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
  build                          build the ROS workspace
  launch [--gui]                 start the simulation (--gui to watch in Foxglove)
  test [NAME] [--gui] [--list]   run a scenario, or --list them
  status                         report simulation status
  topics                         list active ROS topics

Inspect a recorded run:
  episode summary [RUN]          topics, message counts, duration (RUN defaults to latest)
  episode events [RUN]           the derived event timeline (e.g. collision)
  episode query [RUN] --topic T [--around SEC] [--window SEC]
                                 a bounded, downsampled slice of one topic

Author behaviours:
  scenario add <name>            scaffold a new scenario to work on
  scenario list                  list scenarios

  help                           show this help

Docs: https://github.com/tomnewtoneng/robotbase
"""


def _hint(msg: str) -> None:
    """Print a human next-step hint to stderr (keeps stdout clean for scripts)."""
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
  - {{type: run_node, package: {package}, executable: obstacle_controller}}
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
    sub.add_parser("up", help="start the container and build the workspace")
    sub.add_parser("stop", help="stop the simulation (keep the container)")
    sub.add_parser("down", help="stop and remove the container")
    sub.add_parser("build", help="build the ROS workspace")
    sub.add_parser("status", help="report simulation status")
    sub.add_parser("topics", help="list ROS topics")
    sub.add_parser("help", help="show help")

    launch_p = sub.add_parser("launch", help="start the simulation")
    launch_p.add_argument("--gui", nargs="?", const="foxglove", default="none")

    test = sub.add_parser("test", help="run a scenario (or --list)")
    test.add_argument("scenario", nargs="?")
    test.add_argument("--list", action="store_true")
    test.add_argument("--gui", nargs="?", const="foxglove", default="none")

    scen = sub.add_parser("scenario", help="author scenarios (add | list)")
    scen.add_argument("action", choices=["add", "list"])
    scen.add_argument("name", nargs="?")

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
        if args.list or not args.scenario:
            print("\n".join(sorted(scenarios)) or "(no scenarios yet)")
            _hint("Run one:  robotbase test <name> --gui    Add one:  robotbase scenario add <name>")
            return
        if args.scenario not in scenarios:
            print(f"unknown scenario {args.scenario!r}; available: {sorted(scenarios)}")
            sys.exit(2)
        result = run_scenario(
            Scenario.from_yaml(scenarios[args.scenario]),
            rt,
            os.path.join(project, ".robotbase", "runs"),
        )
        print(json.dumps(result.model_dump(), indent=2))
        if result.passed:
            _hint(f"{args.scenario} passed ✓")
        else:
            _hint(
                f"{args.scenario} failed — inspect the assertions above, edit "
                f"src/{controller_pkg}/{controller_pkg}/obstacle_controller.py, and rerun. "
                "Or let a coding agent fix it."
            )
        sys.exit(0 if result.passed else 1)

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
