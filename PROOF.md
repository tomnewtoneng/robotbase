# Canonical Proof — an agent closed the loop

This is the demonstration Robotbase exists to make:

> A declarative local ROS environment plus structured agent tools makes coding agents
> materially better at robotics development.

On 2026-07-22, a fresh coding agent — with **no knowledge of the solution** — was given
only a generated `differential-drive` project, the `robotbase` tools, and this task:

> The starter obstacle controller drives the robot forward but ignores the LiDAR, so it
> collides with the obstacle. Implement obstacle avoidance so `stop-before-obstacle`
> passes while `drive-forward` still passes. Iterate: run the scenario, read the failed
> assertions/metrics, improve the controller, rerun. Only edit `obstacle_controller.py`.
> Do not claim success until you have run each scenario and seen it pass.

## What the agent did

It read `AGENTS.md`, then used `robotbase test` to run scenarios and read the structured
JSON results. It implemented a forward-cone LiDAR controller with proportional braking:
minimum range within ±20° ahead → cruise at 0.3 m/s when clear (≥1.2 m), full stop when
close (≤0.5 m), linear deceleration in between. It verified both scenarios pass by
running them — not by inspecting source.

## Result (evidence, not confidence)

| Scenario | Verdict | Key metrics |
|---|---|---|
| `stop-before-obstacle` | **PASS** | collisions 0; min obstacle clearance **0.504 m** (≥ 0.25); final velocity ≈ 0 |
| `drive-forward` | **PASS** | distance travelled **1.93 m** (≥ 1.0); cruise speed maintained |

No manual Gazebo operation. No copying terminal output into the agent. The agent built,
launched, tested, inspected structured failures, and iterated entirely through the
Robotbase tools.

## Reproduce it yourself

From the repo root (inside WSL2 Ubuntu-24.04, Docker running):

```bash
source .venv/bin/activate
robotbase create my-bot --template differential-drive   # generates the project + broken starter
cd my-bot
robotbase up   # start the container + build the workspace
# Point Claude Code at this directory (uses .mcp.json) OR use the CLI directly:
robotbase test stop-before-obstacle   # fails with the starter controller
# ...implement obstacle avoidance in src/my_bot/my_bot/controller.py...
robotbase test stop-before-obstacle   # passes
```

Every generated project ships the **intentionally-broken** starter controller, so the demo is
reproducible from a clean `robotbase create`.
