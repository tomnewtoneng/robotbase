# Robotbase

**The batteries-included developer-experience layer for agent-driven robotics.**

Setting up ROS 2 + Gazebo is a rite of passage. Robotbase makes that headache vanish and
gives coding agents structured tools — over MCP and a CLI — to *create, build, launch,
inspect, test, and debug* a robotics project. It's "Supabase for ROS 2" in feeling: great
primitives, zero setup pain, works locally in one command.

Local-first and open-core. No cloud, no accounts in the core.

## Watch an agent teach itself

The reason Robotbase exists, demonstrated end-to-end: a coding agent with **no knowledge of
the solution** was given a project whose controller drives forward and ignores the LiDAR,
and told to make it stop before obstacles. Using only the Robotbase tools, it read the
failing scenario assertions, wrote an obstacle-avoidance controller, re-ran the scenario,
and drove it from FAIL to PASS — stopping 0.5 m before the box, zero collisions, never
touching Gazebo by hand. Full write-up in [PROOF.md](PROOF.md).

That's the thesis: **a declarative local ROS environment plus structured agent tools makes
coding agents materially better at robotics.** We've since re-run that loop on harder tasks
(goal-seeking, navigate-around-an-obstacle, arm joint control) — see
[ROBOTBENCH.md](docs/ROBOTBENCH.md).

## Quickstart

**Prerequisites:** Docker, Python 3.12, and a Linux environment. On Windows this means
**WSL2 + Docker Desktop** (WSL integration enabled); on macOS, Docker Desktop. _Developed
and tested on Windows/WSL2; other hosts should work via Docker but aren't yet verified._

```bash
# Until it's on PyPI, install from a clone:
git clone https://github.com/tomnewtoneng/robotbase.git
cd robotbase && python3 -m venv .venv && source .venv/bin/activate && pip install -e .

# Create an agent-ready project (pick a robot: differential-drive | camera-bot | arm)
robotbase create my-bot --template differential-drive
cd my-bot
robotbase up                          # start the container + build (first run builds the image)

robotbase test stop-before-obstacle   # FAILS — the starter controller ignores the LiDAR
robotbase diagnose                    # explains *why* in plain language

# Point a coding agent (e.g. Claude Code — it reads .mcp.json for the robotbase MCP tools)
# at this directory and ask it to make the scenario pass, or edit
# src/my_bot/my_bot/controller.py yourself. Then:
robotbase test stop-before-obstacle   # ...PASSES
```

## What you get

Everything runs headless in Docker (software-rendered Gazebo — no GPU required).

- **`robotbase create --template <name>`** — generate a project from a robot template:
  `differential-drive` (LiDAR), `camera-bot` (+ forward camera), or `arm` (a 2-DOF
  manipulator). Emits the manifest, `AGENTS.md`, and Claude Code MCP config.
- **`robotbase describe`** — structured ground truth: the robot's dimensions and joints,
  the world's layout and arena bounds, and every scenario's assertions.
- **`robotbase test [--all] [--trials N]`** — run a scenario, or the whole suite; with
  `--trials` it applies **domain randomization** and reports a *robustness* score, and
  `--all` tracks behavioral **regressions** between runs.
- **`robotbase diagnose`** — plain-language *why* a run failed, correlating the failed
  assertions with the episode (collision, closest approach) and the control behaviour.
- **`robotbase episode summary | events | query`** — every run is recorded to a portable
  **MCAP** episode (Foxglove/Rerun-openable); query bounded, downsampled slices of any topic.
- **`robotbase bench`** — score the controller on **[RobotBench](docs/ROBOTBENCH.md)**, a
  versioned benchmark for robot behaviours *and the agents that write them*.
- **MCP server + CLI** — the same loop-closing operations for a coding agent or a human.

Sensors and behaviours are composable primitives (LiDAR, contact/bumper, camera, odometry;
`no_contact`, `robot_reached_pose`, `joint_positions_reached`, `minimum_path_length`, …).
The scenario/manifest/result formats are a documented, versioned spec —
[docs/SCENARIO-FORMAT.md](docs/SCENARIO-FORMAT.md).

## Sim-agnostic by design

Robotbase is the **layer over the simulator, not a simulator**. The durable value is the
*contract* — the scenario runner, format, assertions, and results are backend-independent.
The Gazebo + ROS 2 runtime is one backend; a **MuJoCo** backend (in-process, no ROS/Docker)
runs the *same* scenario runner and format unchanged. See `robotbase/sim/`.

## Status

**Alpha, and proven end-to-end.** The full local loop works (create → build → launch → run
scenarios → agent fixes the controller). It ships **three robot templates across two robot
classes**, a growing scenario/assertion/metric vocabulary, MCAP episode recording +
query + attachments, auto-diagnosis, a domain-randomized eval/suite layer, RobotBench, and a
proven sim-agnostic adapter (Gazebo + MuJoCo). 60+ unit tests, code-reviewed core, MIT.

Known limitations: developed on Windows/WSL2 (other hosts untested); not yet on PyPI or a
published Docker image; the scenario library is intentionally small and growing.

## Docs

- [VISION.md](docs/VISION.md) — what Robotbase is and where it's going, strategically.
- [ROADMAP.md](docs/ROADMAP.md) — the build path and what's done.
- [IDEAS.md](docs/IDEAS.md) — the ranked expansion backlog.
- [ROBOTBENCH.md](docs/ROBOTBENCH.md) — the benchmark for robot behaviours and AI agents.
- [SCENARIO-FORMAT.md](docs/SCENARIO-FORMAT.md) — the versioned manifest/scenario/result spec.
- [design/mcap-recording.md](docs/design/mcap-recording.md) · [design/optional-visualization.md](docs/design/optional-visualization.md)
- [PROOF.md](PROOF.md) — the canonical proof: an agent teaching itself obstacle avoidance.

## License

[MIT](LICENSE). Open-core: the core is and will stay MIT-licensed.
