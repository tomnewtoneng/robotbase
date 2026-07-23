# MCAP Episode Recording — Design

Status: **proposed** (not yet implemented). Companion to `optional-visualization.md`.

## Why

Today a scenario run emits a thin result: a pass/fail flag plus a handful of sampled
metrics (`collision_count`, `minimum_obstacle_distance_metres`, …). The rich signal — the
full time-series of every topic during the episode — is computed transiently by
`metrics_collector.py` and then **thrown away**. An agent that gets `FAIL: collision` has
to *guess* why; it can't ask "what did `/scan` and `/cmd_vel` look like in the second before
impact?"

Recording every run as an **MCAP file** fixes this and does several things at once:

- **Agents can debug, not guess.** The episode becomes a queryable trace behind every
  assertion — the concrete realization of the *evidence over confidence* principle.
- **Humans get replay for free.** MCAP is [Foxglove](https://foxglove.dev)'s native format;
  the recorded file is the offline counterpart to the live `--gui` bridge we already ship.
- **Episodes are ecosystem-portable.** Foxglove, [Rerun](https://rerun.io), and robot-data
  platforms like [Alloy](https://www.usealloy.ai) all ingest MCAP. Our episodes flow
  outward without a converter.
- **It is the substrate for the paid layers.** VISION Layer 3 (data & evals) and the
  benchmark hub are only possible if every run leaves behind a standard, labelled artifact.
  This is *Track C — own the standard* made concrete: the **scenario-labelled, MCAP-native
  sim episode**.

### Where this sits in the market

MCAP is the same format the robot-data-platform companies are built on — but they operate
at the *opposite end of the lifecycle*. Tools like Alloy are the **fleet operations data
lake**: real robots, in the field, *after* the run, at petabyte scale in the cloud.
Robotbase owns the **inner development loop**: *before* it's real, in sim, where the agent
is the developer closing the build→test→fix cycle. Same file format, same "robot data must
be agent-interrogable" thesis, different point in time. That is not competition — it means
our episodes are natively portable *into* those tools later, and it validates that the
recorded episode is the right unit to build on.

## Principles (inherited)

- **Headless-first.** Recording never needs a GUI. It is on by default for scenario runs
  and opt-out; it does not depend on `--gui`.
- **Structured over scraping.** Agents get bounded, downsampled query results — never a raw
  multi-MB dump. The file is the store; the query layer is the interface.
- **Local-first.** Episodes land in the project directory. No cloud, no account.
- **Composable, not canned.** We ship the *episode* (a primitive) and the *query verbs*
  (primitives). The agent decides what to ask. We do not pre-bake "the collision analysis."

## What we record

The bridged ROS topics for the whole episode — by default everything on the graph:
`/scan`, `/odom`, `/cmd_vel`, `/tf`, `/tf_static`, `/clock`, `/joint_states`, and `/image`
when the template has a camera. `/clock` is always recorded and recording uses sim time so
message log-times align with the simulation clock (the sim free-runs faster than wall time).

A manifest block controls scope so large topics (camera) can be excluded when not needed:

```yaml
recording:
  enabled: true            # default true for `robotbase test`; false disables
  topics: []               # [] = all bridged topics; else an allow-list
  exclude: []              # deny-list (e.g. [/image] to skip heavy camera frames)
  max_duration_seconds: 60 # hard cap; also bounded by scenario.timeout_seconds
```

## Where it lands

Co-located with the existing result, addressed by `run_id`:

```
.robotbase/runs/<run_id>/
  result.json     # already exists (ScenarioResult)
  episode.mcap    # NEW — the recorded trace
  episode.json    # NEW — sidecar: scenario spec + result + event timeline (see below)
```

`.robotbase/` stays gitignored. Retention is handled by `robotbase clean` (below).

## Lifecycle & mechanism

Recording rides the existing recorder seam (`Runtime._start_recorder`), which already
starts `metrics_collector.py` once `/scan` + `/odom` are up. We add an MCAP recorder next
to it:

1. **Start (in `launch()`),** once the graph is ready, detached inside the container:
   ```bash
   ros2 bag record --storage mcap --use-sim-time \
     -o /workspace/.robotbase/current/episode <topics...>
   ```
   The staging dir `/workspace/.robotbase/current/episode` is **removed first** each run —
   `ros2 bag record` refuses to write into an existing directory, and this guarantees no
   stale data leaks (same discipline as the metrics file reset).
2. **Run** — the scenario runner drives setup/actions unchanged.
3. **Stop (in `collect_metrics()`),** alongside stopping the metrics collector: send
   **SIGINT** (not SIGKILL) to the `ros2 bag` process so it writes the MCAP footer + chunk
   index cleanly. A hard kill leaves an unindexed, possibly-unreadable file.
4. **Finalize** — move the produced `.mcap` into `.robotbase/runs/<run_id>/episode.mcap`
   and write `episode.json`. Because the container writes as **root**, do the move
   **container-side** (`docker compose exec … mv`), avoiding a root-owned host-write
   problem (the known gotcha).

### The `run_id` timing wrinkle

The recorder starts in `launch()`, before the scenario runner mints the `run_id`. So the
bag records to the fixed staging path `current/`, and finalize relocates it into the
`run_id` directory at collect time — exactly mirroring how `metrics.json` is staged at a
fixed path and the result is then written under `runs/<run_id>/`.

## Making the episode self-describing

A raw bag of topics isn't yet *interpretable* — it needs to know which scenario it was and
what the assertions concluded. Two options:

- **Phase 1 — sidecar `episode.json`** (ship first): the scenario spec, the `ScenarioResult`,
  and a derived **event timeline** (`collision at t=…`, `min-range crossed 0.12 m at t=…`,
  `goal reached at t=…`) written next to the mcap. Simple, portable, immediately queryable.
- **Phase 3 — MCAP-native** (self-contained): embed the scenario YAML and result JSON as
  **MCAP attachments/metadata records**, and publish assertion/event markers on a
  `/robotbase/annotations` topic so they show up on the Foxglove timeline. Then the single
  `.mcap` is fully self-describing with nothing alongside it.

The episode layout (mcap + sidecar/attachments) becomes a **versioned part of the open
format** — add an "Episode & Result artifacts" section to `SCENARIO-FORMAT.md`, v1.

## The agent-facing query layer (the actual differentiator)

Recording a file is table stakes; the value is letting an agent (or human) **interrogate**
it without drowning in data. New CLI verbs + MCP tools, all returning **bounded, structured**
results — and all executed **container-side** (the MCAP reader runs where the ROS/mcap
deps already live, so the host never needs to parse the file):

- `robotbase episode summary <run_id>` — duration, topic list + message counts, and the
  event timeline. The at-a-glance "what happened."
- `robotbase episode events <run_id>` — just the derived events (assertion pass/fail
  moments, threshold crossings, goal-reached), each with a timestamp.
- `robotbase episode query <run_id> --topic /scan --around <t> --window <s>` — a
  **downsampled, size-capped** slice of one topic around a time of interest (e.g. ±1 s
  around the collision), as JSON. This is the "show me the second before impact" verb.
- **Images:** for `/image`, return bounded **thumbnails/summaries**, never raw frames —
  consistent with the ROADMAP camera note; keeps agent output structured.

Hard rule: every response is bounded/downsampled like the rest of the runtime. An agent
must never receive a 50 MB dump. `list_topics`/`inspect_topic` already set this precedent.

## Cost & performance

MCAP is chunked and compressed (zstd/lz4). A 30 s lidar+odom episode is a few MB; camera
episodes are larger, which is exactly why `recording.exclude` exists. Recorder overhead at
our rates (10 Hz lidar/camera, 30 Hz odom) is negligible even under llvmpipe. Episode size
is bounded by topic scope and `max_duration_seconds` / `scenario.timeout_seconds`.

## Retention

Runs accumulate under `.robotbase/runs/`. Add `robotbase clean [--keep N]` to prune old
runs (default keep last 20). `.robotbase/` remains gitignored. No auto-deletion of a run
that just failed — the failing episode is the most valuable one to keep.

## Dependencies

Add to the Dockerfile (its own layer, after the foxglove-bridge layer):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-rosbag2 ros-jazzy-rosbag2-storage-mcap \
    && rm -rf /var/lib/apt/lists/*
```

(MCAP is the default rosbag2 storage in Jazzy, but the `ros-base` image does not ship
rosbag2 — install it explicitly.)

## Phasing

1. **Substrate** — record `episode.mcap` + sidecar `episode.json` per scenario run;
   Dockerfile dep; manifest `recording` block; finalize into the run dir. Foxglove can open
   the file immediately. *(This is the piece to build next.)*
2. **Interrogation** — `episode summary` / `events` / `query` CLI + MCP tools, container-side
   reader, bounded output. This is what makes the data *interpretable by agents*.
3. **Self-contained + polish** — MCAP attachments/annotations topic, image thumbnailing,
   `robotbase clean` retention, richer event derivation. Add the "Episode & Result
   artifacts" section to `SCENARIO-FORMAT.md`.

## Open risks

- **Clean shutdown.** Must SIGINT, not SIGKILL, or the mcap is unindexed. Verify the
  detached `ros2 bag` PID is signalled specifically (not a broad `pkill` that races).
- **Root-owned files.** Keep all moves/reads container-side; the host never parses the mcap.
- **Sim-time skew.** Record `/clock` and use sim time, or log-times won't line up in
  Foxglove or in `--around <t>` queries.
- **Staging collision.** Always `rm -rf current/episode` before recording.
- **Size creep with cameras.** `recording.exclude: [/image]` is the escape hatch; document
  it in the camera-bot README.
