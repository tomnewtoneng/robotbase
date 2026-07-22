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
    project = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
    rt = Runtime(project)

    parser = argparse.ArgumentParser(prog="robotbase")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="build the ROS workspace")
    sub.add_parser("launch", help="start the headless simulation")
    sub.add_parser("status", help="report simulation status")
    sub.add_parser("topics", help="list ROS topics")
    test = sub.add_parser("test", help="run a scenario (or --list)")
    test.add_argument("scenario", nargs="?")
    test.add_argument("--list", action="store_true", help="list scenario names")
    args = parser.parse_args()

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
