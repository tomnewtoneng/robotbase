# Design — Optional Visualization (human view of the simulation)

> Status: **Foxglove path implemented** — `robotbase launch --gui` / `robotbase test --gui`
> start a Foxglove bridge on `ws://localhost:8765`; headless stays the default. The native
> Gazebo client and the screenshot artifact remain proposed.

## Goal

Let a human watch the simulation when they want to, via an opt-in flag — while the default
experience stays exactly as it is today: **headless, no GUI, no display required.**

## Principles (non-negotiable)

- **Headless-first stays the default and the guarantee.** The agent loop and the scenario
  runner never require, and never enable, a GUI. Determinism and performance are unaffected
  when visualization is off.
- **Optional and additive.** Off by default; opt-in only. Turning it on adds a view; it
  changes nothing about how the sim runs or how scenarios are scored.
- **Lightweight.** Minimal extra dependencies and overhead; no GPU requirement; works
  cross-platform (Windows/WSL2, Linux, macOS).

## Non-goals

- Not a replacement for RViz, Foxglove Studio, or the full Gazebo GUI as standalone tools.
- Not required by any scenario or by the agent workflow.
- No video-streaming/encoding pipeline in the core.

## Options considered

| Option | What it shows | Weight | Display needed | Cross-platform |
|---|---|---|---|---|
| **Foxglove Bridge** | robot model, TF, LiDAR, camera (ROS data) | light (1 node) | no (browser/desktop) | **yes** |
| **Gazebo GUI client** (`gz sim -g`) | the literal Gazebo scene (walls, obstacles) | heavy (full GUI) | yes (X11/Wayland; WSLg on Win11) | partial |
| RViz2 | robot + sensors (ROS data) | medium | yes (X11) | partial |
| gzweb | Gazebo scene in browser | heavy setup | no | partial |
| Final screenshot artifact | one image per run | ~free | no | yes |

The tension: the *literal* Gazebo scene (with the spawned obstacles) lives in Gazebo and
needs a display to render live; the *ROS view* (robot pose, TF, LiDAR, camera) needs no
display and is browser-based, but doesn't include world geometry that isn't published to
ROS.

## Recommended design

A **two-tier** approach, plus a near-free artifact:

1. **Primary — Foxglove Bridge (the recommended lightweight GUI).** When enabled, the
   launch starts a `foxglove_bridge` node exposing the ROS graph over
   `ws://localhost:8765`. The human opens Foxglove (desktop app or the web app) and connects
   to that URL to see the robot model, TF tree, LiDAR scan, and any camera feed — live,
   from any OS, no X11. This is the default meaning of `--gui`.
2. **Alternative — native Gazebo client.** For local Linux / WSLg users who want the full
   Gazebo scene (walls, spawned obstacles), `--gui=gazebo` attaches a `gz sim -g` client to
   the already-running headless server (which broadcasts the scene via `SceneBroadcaster`).
   Documented with the display caveat.
3. **Bonus — final screenshot artifact.** Independently and cheaply, the runtime can capture
   a headless render of the final frame per scenario run
   (`.robotbase/runs/<id>/screenshot.png`). This serves humans ("see how it ended") *and*
   agents (a bounded visual), with no live-GUI requirement. Optional; can default on because
   it's near-free.

## Interface

- **CLI flag:** `robotbase launch --gui` (and `robotbase up --gui` once `up` exists).
  Accepts an optional value: `--gui` = `foxglove` (default), `--gui=gazebo` = native client,
  `--gui=none` = explicit off. Default when the flag is absent: **off**.
- **Manifest:** the existing `visualisation` block gates it, off by default:
  ```yaml
  visualisation:
    foxglove: {enabled: false, port: 8765}
  ```
  The `--gui` flag overrides the manifest for a single run.
- **Runtime:** the runtime carries a `gui` setting (default `"none"`). The scenario runner
  never changes it, so agent-driven runs stay headless and deterministic; only human-facing
  entry points set it.
- **MCP (human opt-in):** the MCP server reads `ROBOTBASE_GUI` (default `none`). Set
  `ROBOTBASE_GUI=foxglove` before launching the agent to watch *its* scenario runs live in
  Foxglove — the agent never chooses this, so determinism/performance are unaffected unless
  a human asks.

## Implementation sketch

- Add `ros-jazzy-foxglove-bridge` to the runtime image (small; only used when enabled).
- **Launch file:** add a `gui` launch argument (default `none`). When `gui == foxglove`,
  conditionally include the `foxglove_bridge` node on `port`. The robot model is already
  available (`robot_state_publisher` publishes `/robot_description` + TF), so Foxglove's URDF
  and TF panels work out of the box; LiDAR and camera topics are already bridged.
- **Runtime:** `launch(gui="none")` passes `gui:=<value>` to the `ros2 launch` command; when
  a viewer is enabled, `launch()`'s return dict includes the endpoint (e.g.
  `{"visualization": "ws://localhost:8765 (Foxglove)"}`) so the CLI can print it.
- **CLI:** parse `--gui[=foxglove|gazebo|none]`; after launch, print how to view (the
  Foxglove URL, or that a Gazebo client was attached).
- **Gazebo client path:** `--gui=gazebo` runs `gz sim -g` against the running server
  (host-side where a display exists), independent of the bridge.
- **Screenshot artifact (optional):** at scenario end, request a headless render frame
  (`gz` camera / `--headless-rendering` frame grab) and save it under the run directory.

## Cost / tradeoffs

- One extra image dependency and, when enabled, one extra process + an open localhost port.
- Foxglove shows ROS data (robot, TF, sensors), not world geometry not published to ROS —
  the Gazebo client covers that case.
- Zero impact when off: the default headless path is byte-for-byte unchanged, so the
  agent-first guarantee holds.
