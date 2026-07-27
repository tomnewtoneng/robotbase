"""The external ground-truth judge: run the scenario under domain randomization; solved iff
robustness == 1.0. Identical for both arms (the harness runs it, never the agent)."""
from __future__ import annotations

import json
import subprocess


def robustness_via_cli(project_dir: str, scenario: str, trials: int, seed: int) -> float:
    """Shell `robotbase test <scenario> --trials N --seed S` in the project; parse robustness.

    NOTE: the real CLI exits with status 1 whenever robustness < 1.0 (confirmed against a
    live `robotbase up` project) -- i.e. on exactly the runs this judge most needs to read.
    subprocess.run(check=True) would raise CalledProcessError before the JSON is ever parsed,
    so this does not use check=True; it parses stdout regardless of return code and only
    raises if stdout isn't valid JSON at all.
    """
    proc = subprocess.run(
        ["robotbase", "test", scenario, "--trials", str(trials), "--seed", str(seed)],
        cwd=project_dir, capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"robotbase test exited {proc.returncode} with unparsable output: "
            f"stdout={proc.stdout[:200]!r} stderr={proc.stderr[:200]!r}"
        )
    if "robustness" in data:
        return float(data["robustness"])
    # suite-shaped fallback: find the scenario's robustness
    for r in data.get("results", []):
        if r.get("scenario") == scenario:
            return float(r["robustness"])
    # single-run shape (`--trials 1`): no robustness aggregation, just a pass/fail verdict.
    if "passed" in data:
        return 1.0 if data["passed"] else 0.0
    raise ValueError(f"could not find robustness in judge output: {proc.stdout[:200]}")


def judge(project_dir: str, scenario: str, trials: int = 3, seed: int = 0, runner=None) -> dict:
    runner = runner or robustness_via_cli
    robustness = runner(project_dir, scenario, trials, seed)
    return {"robustness": robustness, "solved": robustness == 1.0}
