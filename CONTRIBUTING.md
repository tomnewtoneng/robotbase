# Contributing to Robotbase

Thanks for your interest! Robotbase is open-core (MIT) — the local engine is and stays free.

## Dev setup

You need Docker, Python 3.12, and (on Windows) WSL2 + Docker Desktop.

```bash
git clone https://github.com/tomnewtoneng/robotbase.git
cd robotbase && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,sim-mujoco]"
pytest                                  # the unit suite runs host-side, no Docker needed
```

The unit tests are fast and Docker-free (pure logic — schema, assertions, evals, diagnosis,
the episode-reader helpers, the MuJoCo adapter). End-to-end changes (anything touching the
container, ROS, or Gazebo) should also be verified against a generated project:
`robotbase create … && robotbase up && robotbase test …`.

## Principles (please keep to these)

- **Evidence over confidence.** Don't claim a behaviour works without a passing scenario /
  test. If a scenario ships, it must be *winnable* (a correct controller passes) and, when
  it's a starter task, *fail with the shipped broken starter*.
- **The format is the product.** Assertions, metrics, results, and the scenario runner are
  sim-agnostic — keep sim-specific mechanics behind the `SimAdapter` seam (`robotbase/sim/`).
- **Composable primitives, not canned tasks.** Ship sensors / assertions / metrics that an
  agent assembles; a shipped scenario is an *example*, never the product.
- **Structured over prose.** Machine-readable output; don't restate facts (robot dimensions,
  world bounds) that a tool like `robotbase describe` can surface from the source of truth.
- **Headless-first.** The agent loop never requires a GUI; visualization is additive.

## Adding things

- **A robot template:** a folder under `robotbase/templates/<name>/` — see an existing one
  and `docs/ROADMAP.md`. `robotbase templates` picks it up automatically.
- **An assertion / metric:** `robotbase/assertions.py` + the metrics collector, documented in
  `docs/SCENARIO-FORMAT.md` (bump nothing — additive fields don't change the v1 format).
- **A sim backend:** implement the `SimAdapter` protocol (`robotbase/sim/base.py`).

## PRs

Keep changes focused, add/extend tests, run `pytest`, and update the relevant doc
(`SCENARIO-FORMAT.md`, `ROADMAP.md`, or a `docs/design/*.md`). Descriptive commit messages.
