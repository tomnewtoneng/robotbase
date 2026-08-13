---
name: robotbase
description: Use when building, simulating, or testing a robot or a robot behaviour in ROS 2 / Gazebo — e.g. "make a robot that navigates a maze / reaches a pose / avoids obstacles", writing or debugging a robot controller, running robot scenarios or evals, or bringing up a robot sim. Works from an empty session through a passing scenario. Keywords: robotbase, ROS 2, Gazebo, robot simulation, controller, scenario, differential drive, arm, URDF.
---

# Robotbase

Robotbase builds and tests robot simulations **declaratively** through the `robotbase` CLI (ROS 2
Jazzy + Gazebo Harmonic, headless in Docker). You author specs plus a controller, then run scenarios
that pass/fail on structured assertions. **Golden rule: prove a behaviour with a passing scenario,
never by reading code.** Drive everything through the `robotbase` CLI (no raw ROS/Gazebo).

## Setup (once)
- Docker must be running.
- Install the CLI so `robotbase` is on PATH: `pip install robotbase-kit` (or `uv tool install
  robotbase-kit`). For a one-off with no install, prefix a command with `uvx --from robotbase-kit`,
  e.g. `uvx --from robotbase-kit robotbase describe` (the package is `robotbase-kit`; the command is
  `robotbase`). Everything below is written as `robotbase <cmd>`.

## 1. Orient
- Already in a project? `robotbase describe` succeeds → work here, and read its `AGENTS.md`.
- Otherwise create one, then `cd` into it:

  ```
  robotbase create <name> --template differential-drive   # mobile base + LiDAR
  #   other templates: arm (manipulation) · drone · camera-bot
  #   or import your own robot:  --from-urdf <file.urdf>
  ```
  `create <name> --path <dir>` puts the project at `<dir>/<name>`. A created project ships a
  working robot, a `drive-forward` scenario, a starter `controller.py`, and its own `AGENTS.md` —
  read that too.

## 2. The build/test loop
1. **Ground truth first:** `robotbase describe` (robot geometry, world models + bounds, and every
   scenario's assertions — read straight from the files, so it can't drift) and `robotbase schema`
   (the authoring format for `robot.yaml`, `world.yaml` — walls/obstacles/goals — and scenarios +
   the available assertion types). Never restate geometry or assertions from memory; author a maze
   world and its scenario from `schema`, not guesswork.
2. **Read the target scenario's YAML** — its assertions *are* the definition of "pass".
   `robotbase test --list` shows the scenarios (count is printed on the hint line).
3. **Edit only the authored files:** `robot.yaml`, `world.yaml`, `simulation/scenarios/*.yaml`,
   `src/*/*/controller.py`. Never edit generated URDF/SDF/launch/bridges.
4. **Run:** `robotbase up` (first run pulls the runtime image + builds the workspace), then
   `robotbase test <scenario>` — exit 0 = pass, and it prints JSON `metrics` + `assertions`. You do
   **not** need to rebuild after editing the controller; just re-run the scenario.
5. **Iterate** the controller until the scenario passes. On failure: `robotbase diagnose` (plain
   why), then inspect the recorded episode: `robotbase episode summary | events | query --topic
   /scan --around <t> --window 1.5`.
6. **Robustness (optional):** `robotbase eval <scenario> --trials N` → success-rate + 95% CI.

## Watch it live (optional)
`robotbase studio` opens a browser viewer (3D scene + editable files + runs/evals). You keep driving
from the terminal; its edits, runs, and world update live.

## Gotchas
- **`/odom` is dead-reckoned** and drifts on wheel slip — a robot stalled against a wall still
  reports an advancing position. If `final_x`/`distance_travelled` look impossibly large it's stuck;
  cross-check `contact_count` / `no_contact`. Use `robotbase describe` for exact geometry.
- The CLI prints **JSON on stdout, next-step hints on stderr** — capture `2>/dev/null` when parsing.
- **One project's sim per machine** (headless). Run `robotbase down` before bringing up another.
- The starter controller already passes `drive-forward` — run it first to see a green result.

## Evidence discipline
Do **not** claim a behaviour works from reading source. Run the scenario, read the failed assertions
and `metrics`, inspect the episode on failure, iterate until it passes (exit 0, all assertions true),
then report the final metrics.
