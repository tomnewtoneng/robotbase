# Robotbase

**The batteries-included developer-experience layer for agent-driven robotics.**

Setting up ROS 2 + Gazebo is a rite of passage. Robotbase makes that headache vanish and
gives coding agents structured tools — over MCP and a CLI — to *build, launch, inspect,
and test* a robotics project. It's "Supabase for ROS 2" in feeling: great primitives,
zero setup pain, works locally in one command.

Local-first and open-core. No cloud, no accounts in the core.

> One command creates an agent-ready ROS 2 simulation project. The point isn't just
> scaffolding — it's that coding agents get *structured, evidence-producing* access to
> build, drive, and verify the robot.

## Watch an agent teach itself

The reason Robotbase exists, demonstrated end-to-end: a coding agent with **no knowledge
of the solution** was given a project whose controller drives forward and ignores the
LiDAR, and told to make it stop before obstacles. Using only the Robotbase tools, it read
the failing scenario assertions, wrote an obstacle-avoidance controller, re-ran the
scenario, and drove it from FAIL to PASS — stopping 0.5 m before the box, zero collisions,
never touching Gazebo by hand. Full write-up in [PROOF.md](PROOF.md).

That's the thesis: **a declarative local ROS environment plus structured agent tools makes
coding agents materially better at robotics.**

## Quickstart

**Prerequisites:** Docker, Python 3.12, and a Linux environment. On Windows this means
**WSL2 + Docker Desktop** (with WSL integration enabled); on macOS, Docker Desktop.
_Robotbase is currently developed and tested on Windows/WSL2 — other hosts should work via
Docker but are not yet verified._

```bash
git clone https://github.com/tomnewtoneng/robotbase.git
cd robotbase
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Run the reference project
cd warehouse-bot
docker compose up -d          # first run builds the ~3.6 GB ROS+Gazebo image
robotbase build               # colcon-build the workspace

# The starter controller ignores the LiDAR, so this FAILS:
robotbase test stop-before-obstacle

# Now either point Claude Code at this directory (it reads .mcp.json for the
# robotbase MCP tools) and ask it to fix the controller, or edit
# src/warehouse_bot/warehouse_bot/obstacle_controller.py yourself — then:
robotbase test stop-before-obstacle    # ...PASSES
```

Create a fresh agent-ready project of your own:

```bash
robotbase create my-bot
cd my-bot && docker compose up -d && robotbase build
robotbase test --list
```

## How it works

Everything runs headless in Docker (software-rendered Gazebo — no GPU required).

- **`robotbase create`** — generates a project from the reference template (renames the
  ROS packages, emits the manifest, `AGENTS.md`, and Claude Code MCP config).
- **Runtime** — a thin, transport-agnostic layer that drives the container: build, launch,
  reset, inspect topics, spawn obstacles, collect metrics. Nothing above it knows about
  Docker or ROS commands.
- **Scenario runner** — runs a declarative scenario (setup → actions → assertions) and
  emits a machine-readable JSON result. Deterministic: each run gets a pristine sim.
- **MCP server + CLI** — expose the loop-closing operations (`workspace_build`,
  `simulation_launch`, `scenario_run`, `ros_inspect_topic`, …) to a coding agent or a human.

The scenario and manifest formats are a documented, versioned spec — see
[docs/SCENARIO-FORMAT.md](docs/SCENARIO-FORMAT.md).

## Status

**Alpha.** The full local loop works and is proven end-to-end (see PROOF.md): create →
build → launch → run scenarios → agent fixes the controller. It ships one robot template
(differential drive) and two scenarios (`drive-forward`, `stop-before-obstacle`), with 22
unit tests and a code-reviewed core.

Known limitations: developed on Windows/WSL2 (other hosts untested); no PyPI package or
published image yet; scenario library is intentionally small.

## Docs

- [VISION.md](docs/VISION.md) — what Robotbase is and where it's going, strategically.
- [ROADMAP.md](docs/ROADMAP.md) — the build path: widening to more robots, sensors, scenarios.
- [SCENARIO-FORMAT.md](docs/SCENARIO-FORMAT.md) — the versioned manifest/scenario/result spec.
- [design/optional-visualization.md](docs/design/optional-visualization.md) — proposed optional GUI (headless stays default).
- [PROOF.md](PROOF.md) — the canonical proof: an agent teaching itself obstacle avoidance.

## License

[MIT](LICENSE). Open-core: the core is and will stay MIT-licensed.
