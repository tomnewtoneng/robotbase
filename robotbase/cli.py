"""Minimal Robotbase CLI — enough to build, launch, and run scenarios.

Exposes the same operations as the MCP server for agents/humans who prefer a
shell. `robotbase test <scenario>` exits 0 on pass, 1 on fail. The project is
taken from ROBOTBASE_PROJECT_DIR (default: current directory).
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


def _scenarios(project: str) -> dict[str, str]:
    directory = os.path.join(project, "simulation", "scenarios")
    return {
        os.path.splitext(os.path.basename(p))[0]: p
        for p in glob.glob(os.path.join(directory, "*.yaml"))
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="robotbase")
    sub = parser.add_subparsers(dest="cmd", required=True)
    create = sub.add_parser("create", help="generate a new project from the template")
    create.add_argument("name")
    create.add_argument("--path", default=".", help="parent directory for the new project")
    sub.add_parser("build", help="build the ROS workspace")
    launch_p = sub.add_parser("launch", help="start the simulation")
    launch_p.add_argument(
        "--gui", nargs="?", const="foxglove", default="none",
        help="start a viewer (foxglove); default is headless",
    )
    sub.add_parser("status", help="report simulation status")
    sub.add_parser("topics", help="list ROS topics")
    test = sub.add_parser("test", help="run a scenario (or --list)")
    test.add_argument("scenario", nargs="?")
    test.add_argument("--list", action="store_true", help="list scenario names")
    test.add_argument(
        "--gui", nargs="?", const="foxglove", default="none",
        help="watch the scenario in a viewer (foxglove); default is headless",
    )
    args = parser.parse_args()

    if args.cmd == "create":
        from robotbase.generator import create_project, default_template_dir

        dest = create_project(args.name, args.path, default_template_dir())
        print(f"Created Robotbase project: {dest}")
        print("\nNext steps:")
        print(f"  cd {dest}")
        print("  docker compose up -d")
        print("  robotbase build")
        print("  robotbase test --list")
        return

    project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
    rt = Runtime(project)
    rt.gui = getattr(args, "gui", "none")
    scenarios = _scenarios(project)

    if args.cmd == "build":
        print(json.dumps(rt.build(), indent=2))
    elif args.cmd == "launch":
        print(json.dumps(rt.launch(), indent=2))
    elif args.cmd == "status":
        print(json.dumps(rt.simulation_status(), indent=2))
    elif args.cmd == "topics":
        print("\n".join(f"{t['name']}\t{t['type']}" for t in rt.list_topics()))
    elif args.cmd == "test":
        if args.list or not args.scenario:
            print("\n".join(sorted(scenarios)))
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
        sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
