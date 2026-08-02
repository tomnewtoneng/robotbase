![robotbase — describe your robot, world, and scenarios in YAML; compile to a running headless ROS 2 + Gazebo sim; get pass/fail evidence.](https://raw.githubusercontent.com/tomnewtoneng/robotbase/main/assets/robotbase-header.png)

**Declarative robotics.** Describe a robot, its sensors, its world, and the behaviours you want to
verify in YAML — Robotbase compiles that into a running, **headless** ROS 2 + Gazebo simulation and
gives you machine-readable evidence. Local-first and open-core: no cloud, no accounts in the core.

## What it is

Robotbase is the *layer over the simulator*, not a simulator. It's all YAML: `robot.yaml` (the
robot + its sensors), `world.yaml` (the world), and one or more **scenario** files under
`simulation/scenarios/*.yaml`. A scenario is the test — its `assertions:` block declares what
"working" means:

```yaml
# simulation/scenarios/drive-forward.yaml
assertions:
  - {type: robot_moved_minimum_distance, minimum_distance_metres: 1.0}
  - {type: required_topic_messages, topic: /scan, minimum_count: 5}
```

Robotbase compiles all of it into a complete ROS 2 + Gazebo project (URDF, world SDF, launch,
ROS↔gz bridges, control config) and runs it headless in Docker. You never hand-write the XML —
the way you never click through a cloud console with Terraform.

## How it works

```text
edit robot.yaml / world.yaml / a scenario  →  robotbase up  →  robotbase test
                       ▲                                              │
                       └────────── read the structured result / episode ──────────┘
```

**Prerequisites:** Docker, Python 3.12, and Linux (on Windows: WSL2 + Docker Desktop).

```bash
pip install robotbase

robotbase create my-bot        # scaffold a project (differential-drive by default)
cd my-bot
robotbase up                   # start the container + build (first run builds the image)
robotbase test drive-forward   # run a scenario; prints a structured pass/fail result
```

Every run is an objective result (metrics + assertions) plus a recorded **MCAP episode**
(Foxglove/Rerun-openable). Every action is a verb with a structured result, so a human and a coding
agent drive it the same way.

### Build your own robot and world

The scaffold is only a starting point — the robot, its sensors, the world, and the tests are all
yours to edit. Author declaratively and let the tool keep you honest:

```bash
robotbase schema      # the full robot.yaml / world.yaml / scenario authoring reference
# …edit robot.yaml and world.yaml…
robotbase validate    # static physics checks (mass, inertia, joint limits) before you launch
robotbase explain     # which links / joints / topics each line of your spec produced
robotbase describe    # structured ground truth for the robot, world, and scenarios
robotbase up          # recompile the specs, (re)build, and run
```

Define what "working" means as scenarios — each is a `simulation/scenarios/*.yaml` whose
`assertions:` block *is* the test:

```bash
robotbase scenario add reach-the-shelf
robotbase test reach-the-shelf
```

### Start from a template or an existing URDF

```bash
robotbase templates                                # list the built-in templates
robotbase create my-arm --template arm             # differential-drive | camera-bot | arm | drone
robotbase create my-bot --from-urdf my_robot.urdf  # import an existing URDF verbatim
```

## The knowledge layer (built for agents)

Robotbase is meant to be *operated by a coding agent*, so the tool teaches the agent how to use it —
there are no external docs to keep in sync.

- **One surface, CLI + MCP.** The full `robotbase` CLI is mirrored by a **19-tool MCP server**
  (`describe`, `explain`, `validate`, `build`, `test`, `diagnose`, `episode …`). A human types the
  commands; an agent calls the tools — same verbs, same structured results.
- **A built-in authoring reference.** `robotbase schema` (and the `authoring_schema` MCP tool)
  returns the full `robot.yaml` / `world.yaml` / scenario format — every field, the sensor/archetype
  vocabulary, the **assertion types**, and the common mistakes — as prose or JSON Schema. It's
  generated from the code, so it can't drift from what the compiler actually accepts.
- **Ground truth, not files to parse.** `describe` / `explain` / `validate` and the `episode` query
  verbs hand back structured facts about the compiled robot, world, topics, and recorded runs.
- **Every project is agent-ready.** `robotbase create` drops an `AGENTS.md` (project-specific
  instructions) and a `.mcp.json` into the new project.

**Setup for the MCP server: none** beyond `pip install -e .` — it ships in the core install. An
MCP-aware agent (e.g. Claude Code) opened in a project picks up the bundled `.mcp.json`
automatically. To run it by hand:

```bash
ROBOTBASE_PROJECT_DIR=. python -m robotbase.mcp_server   # stdio; ROBOTBASE_GUI=foxglove to watch runs
```

## Why it exists

Standing up ROS 2 + Gazebo by hand is a tax paid in opaque C++ tracebacks and terminal scraping —
and it's especially brutal for a coding agent. Robotbase removes it and replaces it with what agents
are good at:

- **Declarative, not fiddly.** A few lines of YAML; the compiler owns every sim gotcha (collision
  lumping, bridge wiring, inertia, control config) and, when the spec is wrong, returns an error that
  *names the field* instead of a crash.
- **Structured state, not log-scraping.** `describe` / `explain` / `validate` and the episode query
  verbs hand back ground truth, not console output to parse.
- **Evidence, not vibes.** A scenario is an objective pass/fail; you can't *claim* a robot works and
  be believed — you make the assertions pass. That closes the gap the project exists to close:
  **a coding agent can write robot code; on its own it can't tell whether the robot actually works.**

*Benchmark data — coding agents with vs. without Robotbase — coming soon.*

## Status

**Alpha, proven end-to-end.** The full local loop works — create → author the specs → build →
run → read the evidence — across four robot templates (differential-drive, camera-bot, arm, drone),
a growing scenario/assertion/metric vocabulary, MCAP episode recording + query, auto-diagnosis, a
domain-randomized eval layer, and a proven sim-agnostic runner (Gazebo + an in-process MuJoCo
backend). Local-first, MIT-licensed.

## License

MIT — see [LICENSE](LICENSE).
