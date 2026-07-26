# Declarative compiler — modular robots & worlds (design)

Status: **approved** (2026-07-25). Supersedes the archetype-only sketch in `robot-spec.md`
by generalising it: archetypes stop being opaque blobs and become composable *modules* over a
shared primitive layer, and the same foundation gets a sibling **world compiler**.

## Why

The Phase-1 robot compiler (`robotbase/robotspec/`, see `robot-spec.md`) proved the model —
`robot.yaml` compiles to URDF + bridges + world systems + manifest, and every sim gotcha is
the compiler's problem. But it is **archetype-locked**, i.e. "toy":

- **Sensors only mount to `base_link`** — hardcoded `<parent link="base_link">`. No camera on a
  gripper, no lidar on a mast, no IMU on an arm segment.
- **Each archetype is one opaque string blob** — `_differential_drive` emits base + 2 wheels +
  caster as a monolith. No custom chassis, no 4-wheeler, no arm-on-a-mobile-base.
- **The body is a single box/cylinder** — real robots are multi-link assemblies.

The goal (VISION / IDEAS §G): **a user or agent can fully assemble and customise a robot,
its sensors, and its world entirely in YAML** — modular, but *not finicky* (the common case
stays a one-liner). This is the Terraform model made literal: **modules composed over
resources.** Archetypes are modules; links/joints/sensors/plugins are the resources; you
author at either level and mix them, and there is always a level below so nothing is locked.

## Core architecture — a primitive IR that everything emits into

The one idea everything rests on: modules and sensors **contribute fragments to a shared
intermediate representation** instead of each printing a finished blob. The compiler merges
the fragments, validates the result, and renders URDF **once**.

### The IR (`robotbase/robotspec/ir.py`)

```
LinkIR    name, shape(box|cylinder|sphere)+size+mass+material   (sugar -> auto inertia)
          OR explicit visual / collision / inertial              (escape hatch)
JointIR   name, type, parent, child, xyz, rpy, axis, limits
Fragment  links[], joints[], gazebo[] (plugin/sensor/per-ref XML),
          bridges[], world_systems[], ready_topics[], manifest_contrib,
          exposes[]  (link names this fragment offers as mount points)
RobotIR   the accumulator: merged links/joints/gazebo/bridges/world_systems/
          ready_topics/manifest
```

`LinkIR` shape-sugar computes the inertia tensor from the primitive shape + mass (box /
cylinder / sphere formulas), so a raw `{name, shape, size, mass}` link "just works" — the
reason hand-authored parts aren't finicky. Explicit `visual`/`collision`/`inertial` blocks
remain available for anything the sugar can't express.

### Modules and sensors are fragment-emitters

- **Module** (archetype): `module(params, mount) -> Fragment`. Owns a chassis's links/joints,
  its control/odometry plugin, its runtime facts (`control`, `ready_topics`, `fixed_base`),
  and declares the links it `exposes` as mount points. `differential-drive` exposes
  `base_link`; `arm` exposes `tool0`; `quadrotor` exposes `base_link`.
- **Sensor**: `sensor(params, on_link, mount) -> Fragment`. Owns one link + a fixed joint to
  `on_link` + the gz `<sensor>` + the bridge + the world system it requires.

`_differential_drive` is rewritten from a string blob into an emitter — **same emitted URDF**,
composable shape. This keeps the Phase-1 validation intact while unlocking composition.

### Merge + validation (what keeps it non-finicky)

The compiler merges all fragments into one `RobotIR`, then validates before rendering. Clear
errors replace broken URDF:

- every joint's `parent`/`child` link exists (missing mount target -> explicit error);
- links form a **single tree** rooted at one base link — no orphans, no cycles;
- no duplicate link/joint names across parts (name clash -> explicit error);
- unknown module / sensor / shape -> explicit error (as today).

Then URDF is rendered once from the merged IR, world_systems deduped, ready_topics unioned.

## Robot spec surface

`parts` is the assembly primitive; each part is a **module** (`use:`) or a **raw part**
(`links:`/`joints:`). Sensors mount to **any** link via `on:`. `plugins:` is the final raw-gz
escape hatch.

```yaml
version: 1
name: my_bot
parts:
  - use: differential-drive          # a module
    drive: {wheel_separation: 0.4}
  - use: arm
    mount: {to: base_link, xyz: [0, 0, 0.15]}    # arm on the base = mobile manipulator
  - links: [{name: mast, shape: cylinder, size: [0.03, 0.5], mass: 0.2}]   # raw part
    joints:
      - {name: mast_joint, parent: base_link, child: mast, type: fixed, xyz: [0, 0, 0.1]}
sensors:
  - {type: lidar, on: mast}          # `on`: which link to attach to (any link)
  - {type: camera, on: tool0, mount: [0, 0, 0.05]}   # `mount`: [x,y,z] offset in metres, on that link
plugins: []                          # raw gz plugin passthrough — final escape hatch
```

**Sensor fields.** `on` is the link the sensor attaches to (default: the primary module's base
link). `mount` is an optional `[x, y, z]` offset **in metres, relative to `on`'s frame**; omit it
and the sensor gets a sensible per-type default — a *base-tuned* offset when it's on the base
link (e.g. lidar forward-and-up on the box body), or `[0, 0, 0]` (the link's own origin) on any
other link, so a `mast`-mounted lidar sits on the mast, not floating beside it. Override `mount`
whenever you want a specific pose.

**Sensor `type:` values** (the authoritative list — the YAML token, not the underlying gz sensor
name):

| `type` | publishes | gz world system pulled in | notes |
|--------|-----------|---------------------------|-------|
| `lidar` | `/scan` | Sensors | 2D planar scan |
| `camera` | `/image` (RGB) | Sensors | `resolution: [w, h]`, default 320×240 |
| `depth` | `/depth` (depth image) + `/depth/points` (cloud) | Sensors | not `depth_camera` — that's the internal gz type |
| `imu` | `/imu` | Imu | physics-based |
| `contact` | `/bumper` | Contact | always on the base body; ignores `on` |

Any other `type` is an error (`unknown sensor …`). `resolution` and `topic` are optional
overrides; `mount`/`on` are as above.

> **YAML gotcha, handled for you:** `on` is a YAML 1.1 boolean keyword, so a naive loader turns
> the key `on:` into `True`. Robotbase's loader normalises that back, so `on: mast` (unquoted,
> as shown) works — you don't need to quote it.

**Link-shape sugar origin.** A raw part's `{shape, size}` link centres its geometry on the
link's own origin (which sits at the joint's `xyz` in the parent frame). So a 0.5 m mast joined
at `xyz: [0, 0, 0.1]` extends 0.25 m below and above that point; to stand a mast *on top of* the
base, join it at half its length (`xyz: [0, 0, 0.25]` for a 0.5 m mast on a base whose top is at
z≈0).

### Backward compatibility

The loader normalises the **current** shape (`base:` + top-level `body:` / `drive:` /
`sensors:`) into `parts: [{use: <base>, body, drive}]` before compiling. Existing template
`robotbase.yaml` files and all 6 current `test_robotspec.py` tests keep passing unchanged. The
one-liner case stays a one-liner:

```yaml
version: 1
name: my_bot
base: differential-drive             # sugar for parts: [{use: differential-drive}]
sensors: [{type: lidar}]             # `on` defaults to the primary module's base link
```

### One deliberate limit (YAGNI)

The **contact** sensor stays anchored to the drive base's footprint (the "did the robot hit
something" sensor). Its collision-lump naming
(`base_footprint_fixed_joint_lump__base_link_collision`) is base-specific; per-link contact on
arbitrary links is a later refinement. Everything else mounts anywhere.

## World compiler (`robotbase/worldspec/`, mirroring `robotspec/`)

`WorldSpec` (Pydantic) -> `compile_world(spec, robot_systems) -> str` (SDF).

```yaml
version: 1
name: warehouse
ground: true                                   # ground-plane model
light: sun                                      # directional light
obstacles: [{shape: box, size: [0.3, 0.3, 0.5], at: [2, 0, 0.25]}]
walls:     [{from: [-3, -3], to: [3, -3], height: 0.5}]
goals:     [{name: dock, at: [4, 0], radius: 0.3}]
include:   [conveyor.sdf]                        # raw-SDF escape hatch
```

- **Sugar -> SDF models:** `obstacles` -> static box/cylinder models at pose; `walls` -> thin
  box models spanning `from -> to` at `height`; `goals` -> a visual-only translucent marker
  model **and** surfaced into the manifest (`world.goals`) so scenarios reference `goal: dock`
  by name.
- **`include`** -> raw `<include>` / inline passthrough of the referenced SDF file. (A
  primitive `models:` YAML layer is deferred — hand-written world SDF is relatively safe, no
  fixed-joint / scoped-topic landmines, so the escape hatch is an acceptable line here.)
- **The systems seam** (why worlds compile *with* robots): the world always emits the base
  systems (`Physics`, `UserCommands`, `SceneBroadcaster`) **unioned with the robot's
  `world_systems`**. A robot that adds a lidar makes the world load `gz-sim-sensors-system`
  automatically — derived from the robot's sensors, never hand-declared. The build step
  compiles the robot, reads `world_systems`, and passes them into `compile_world`.

## Templates compile from specs

Each template becomes `robot.yaml` + `world.yaml` + scenarios + starter controller. Build
path:

```
compile_robot(robot.yaml)  -> URDF + bridges + world_systems + manifest
compile_world(world.yaml, world_systems)  -> world SDF
render_launch(compiled)    -> the launch file        (already exists, robotspec/project.py)
```

**Validation gate** (same proof as Phase 1): a compiled template must **build and run its
scenario with the same result** as the hand-written template today — the broken starter
controller fails, a correct controller passes.

## Phasing

Each phase is independently shippable and tested. **Import is deliberately early** (before the
extra archetypes): meeting the existing standards where they are — running Robotbase's
runner/evals/MCP over a robot's *own* URDF/SDF — de-risks the whole format bet and proves the
moat (the eval layer) independent of whether anyone adopts the YAML authoring path.

1. **Primitive IR + merge/validation.** Rewrite `differential-drive` as an emitter; add the
   `parts:` surface + `base:`-sugar loader; link-shape sugar; sensors-on-any-link (`on:`). All
   6 existing `test_robotspec.py` tests stay green.
2. **World compiler.** `worldspec/` (sugar + `include` + the systems seam); wire the build
   path; regenerate the `differential-drive` template from `robot.yaml` + `world.yaml` and
   pass the validation gate.
3. **Import — bring-your-own URDF/SDF (elevated).** `create --from-urdf` (the "wrap" path:
   copy the URDF verbatim, write a thin `robot.yaml` with `use: custom` + a best-effort sensor
   bridge list); world SDF import already falls out of `include:`. This is what makes Robotbase
   useful to a team that keeps its own robot description, and it lets the runner/evals earn
   their keep without betting on format adoption.
4. **`camera` + `depth` sensor emitters** -> regenerate camera-bot.
5. **`arm` + `quadrotor` modules** -> regenerate arm + drone. Mobile-manipulator falls out of
   composition for free.

## Dogfooding (built into the sequence)

Each phase is used to build the next, and every friction point an agent (me or a dispatched
subagent) hits authoring against the new formats is recorded and addressed before moving on —
`docs/DOGFOODING.md` is the running log. The specific test that matters: give a *fresh* agent
only the format docs and ask it to author a robot/world it has never seen, cold. If it
faceplants, the format (or its errors/defaults/validation) is wrong, not the agent — fix that
before adding more surface.

## Testing

Extends the current pattern (pure-compile unit tests + a build-and-run validation gate):

- **Unit (pure compile):** spec -> IR -> URDF tokens / bridge list / world_systems / manifest
  fields; link-shape sugar -> inertia; sensor `on:` -> correct parent link; `base:`-sugar
  normalises to `parts:`.
- **Unit (validation errors):** orphan link, name clash, missing mount target, unknown
  module/sensor/shape each raise a clear typed error.
- **World unit:** `world.yaml` -> SDF tokens (obstacle/wall/goal models, light, ground);
  `robot_systems` union appears in the world; `include` passthrough.
- **Validation gate (per template):** compiled `robot.yaml` + `world.yaml` builds and runs its
  scenario with the same result as the hand-written template.

## Principles (carried from robot-spec.md)

- **Own the standard.** The robot/world specs are Robotbase's versioned formats; URDF and SDF
  are compiler outputs, never hand-edited.
- **The compiler owns the physics.** Every sim gotcha (collision-lump naming, scoped contact
  topic, deriving world systems, bridge types, inertia) is our code's job, not the user's.
- **Composable.** Modules x sensors x raw parts; adding one is a fragment-emitter, not a
  rewrite.
- **Escape hatch at every level.** Raw `links`/`joints`, raw `plugins`, `include: raw.sdf`,
  and `use: custom` (raw URDF) mean nothing the compiler can't yet express is ever a blocker.
