# Visualization — watch and replay runs

Robotbase is headless-first (the agent loop never needs a GUI), but you can *watch* a run
live or *replay* a recorded one in [Foxglove](https://foxglove.dev) — the desktop app or the
browser version at <https://studio.foxglove.dev>. Every project ships a ready-made layout at
`foxglove/layout.json`.

## Watch a run live

```bash
robotbase test <scenario> --gui      # or: robotbase launch --gui
```

`--gui` starts a Foxglove bridge on `ws://localhost:8765`. Then, in Foxglove:

1. **Open connection** → **Foxglove WebSocket** → `ws://localhost:8765`.
2. **Layouts → Import** → the project's `foxglove/layout.json`. You'll get a 3D view
   (plus an image/plot panel for the camera/arm/drone templates).

If you set panels up by hand instead, the one thing that matters is the **3D panel's Display
frame** — set it to **`odom`** (mobile robots and the drone) or **`base_link`** (the arm).
Otherwise the world appears to slide around as the robot moves. Add the `/scan`, `/tf`, and
`/robot_description` topics to see the LiDAR, frames, and robot model.

> Note: the sim free-runs faster than real time, so a scenario finishes in a few seconds of
> wall-clock — replay (below) is the calmer way to inspect what happened.

## Replay a recorded run

Every run is recorded to a portable MCAP episode. To find and open the latest one:

```bash
robotbase replay            # prints the episode .mcap path + how to view it (RUN defaults to latest)
```

In Foxglove: **Open local file** → the `.mcap` it printed (on Windows/WSL it's under
`\\wsl.localhost\<distro>\...`), then **Import** the same `foxglove/layout.json`. Press play
and scrub the timeline — no sim or container needed.

## Share a run

The `.mcap` is **self-contained** — it carries the full topic trace *and* the scenario +
result as an attachment. Send someone the file and they can replay the exact run in Foxglove
(desktop or browser). It also opens in [Rerun](https://rerun.io) and robot-data platforms
that read MCAP. This is the shareable artifact behind a result: "here's my agent solving it."

## The layouts

`foxglove/layout.json` per template:

- **differential-drive / camera-bot** — 3D view following `odom` with `/scan`, `/tf`, the
  robot model (camera-bot adds an image panel for `/image`).
- **arm** — 3D view of the manipulator plus a plot of the joint angles.
- **drone** — 3D view following `odom` plus an altitude (`/odom.z`) plot.

They're starting points — tweak and re-export to taste (**Layouts → Export**).
