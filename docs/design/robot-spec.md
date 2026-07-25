# Robot Spec — declarative robots (design)

Status: **proposed** (not yet implemented). The first step of *agent-native authoring*
(`IDEAS.md` §G): let an agent build robots by natural language instead of hand-writing URDF.

## Why

Scenarios, manifests, and controllers are already agent-authorable (clean YAML / Python).
**Robots aren't** — they're raw URDF/xacro, and every sim gotcha we hit this project lives
there: fixed-joint collision lumping, the contact sensor's scoped-topic path, per-sensor gz
plugin wiring, the ROS↔gz bridge types, `ready_topics`, `fixed_base`. An agent will faceplant
on that XML.

"Everything by natural language" is therefore not a new AI capability — it's a **format
problem.** The move is a high-level, Robotbase-owned **robot spec (`robot.yaml`)** that the
agent authors as *intent*, which Robotbase **compiles down to a correct URDF/xacro + the
launch bridges + the manifest sensor/runtime fields.** The agent never touches XML; we own
the gnarly compilation. That is "Supabase for robots": declare config, correct infra
materializes — and it turns the sim gotchas from the *user's* problem into *our compiler's*
problem (the defensible part).

We own the format (versioned, like `SCENARIO-FORMAT.md`); URDF is a build artifact.

## The format

Annotated `robot.yaml` for the differential-drive robot we ship today (the reference the
compiler must reproduce):

```yaml
version: 1
name: warehouse_bot

# Archetype — determines locomotion, control, odometry, ready_topics, fixed_base.
#   differential-drive | fixed-arm | quadrotor   (extensible; each is a compiler module)
base: differential-drive

body:
  shape: box                 # box | cylinder
  size: [0.35, 0.30, 0.15]   # metres (x, y, z for box)
  mass: 5.0

drive:                       # archetype-specific params (differential-drive here)
  wheel_radius: 0.05
  wheel_separation: 0.34

# Sensors — a list; each attaches a link + a gz sensor + a ROS bridge, and pulls in any
# world-level system it needs (see "What the compiler owns"). Mount pose is optional
# (sensible per-type default). type is the only required field.
sensors:
  - {type: lidar,   mount: [0.14, 0, 0.11]}          # -> /scan
  - {type: camera,  mount: [0.175, 0, 0.075], resolution: [320, 240]}  # -> /image
  - {type: depth,   resolution: [320, 240]}          # -> /depth (+ /depth/points)
  - {type: imu}                                      # -> /imu
  - {type: contact}                                  # -> /bumper (ground-truth collision)
```

And a `fixed-arm` (shows joints; mobile archetypes ignore `joints`, arms ignore `drive`):

```yaml
version: 1
name: warehouse_bot
base: fixed-arm
links:                       # optional explicit link chain; default is a simple N-link arm
  - {name: upper_arm, length: 0.40, radius: 0.035, mass: 0.15}
  - {name: forearm,   length: 0.40, radius: 0.030, mass: 0.15}
joints:
  - {name: shoulder_joint, type: revolute, axis: y, limits: [-3.14, 3.14],
     controller: position, gains: {p: 80, i: 2, d: 8}}
  - {name: elbow_joint,    type: revolute, axis: y, limits: [-3.14, 3.14],
     controller: position, gains: {p: 60, i: 2, d: 6}}
sensors: [{type: imu}]
```

A `quadrotor` names its control style; the compiler wires VelocityControl + OdometryPublisher:

```yaml
version: 1
name: warehouse_bot
base: quadrotor              # kinematic velocity flight: 3D /cmd_vel, 3D /odom
body: {size: [0.16, 0.16, 0.06], mass: 1.0}
sensors: [{type: imu}]
```

## Compilation model

Two kinds of composable modules; the compiler assembles them:

- **Archetype module** (`base`) — owns the chassis links/joints, the locomotion/control
  plugin, and the runtime facts:
  - `differential-drive` → base_footprint + base box + 2 wheels + caster; `DiffDrive`
    (cmd_vel/odom/tf) + `JointStatePublisher`; control `/cmd_vel`, `ready_topics` includes
    `/odom`, `fixed_base: false`.
  - `fixed-arm` → a `world` anchor link + base + the `links`/`joints` chain; a
    `JointPositionController` per joint + `JointStatePublisher`; control per-joint command
    topics, `ready_topics: [/joint_states]`, `fixed_base: true`.
  - `quadrotor` → body + 4 rotor visuals; `VelocityControl` (3D cmd_vel) +
    `OdometryPublisher` (dimensions 3); control `/cmd_vel`, `ready_topics: [/odom]`.
- **Sensor module** (each `sensors[]` entry) — cross-archetype; owns one link + one gz
  `<sensor>` + one bridge line, and declares the world system it requires:
  - `lidar` → gpu_lidar → `/scan`; needs the world **Sensors** system.
  - `camera` → camera (rgb8) → `/image`; needs **Sensors**.
  - `depth` → depth_camera → `/depth` + `/depth/points`; needs **Sensors**.
  - `imu` → imu → `/imu`; needs the world **Imu** system.
  - `contact` → contact sensor on the base body collision → `/bumper`; needs the world
    **Contact** system, and the bridge must target the sensor's *scoped* gz topic and remap
    it (the sensor ignores its `<topic>`).

The compiler emits three artifacts from one `robot.yaml`:
1. **`…_description/urdf/<name>.urdf.xacro`** — the full robot.
2. **launch bridge args** — the `parameter_bridge` lines (with the contact remap).
3. **manifest fields** — `sensors:`, `runtime.ready_topics`, `runtime.fixed_base`, `control`.

## What the compiler owns (the gotchas, so the agent never sees them)

- **Collision naming after fixed-joint lumping** — the contact sensor references
  `base_footprint_fixed_joint_lump__base_link_collision`; the compiler computes this from the
  archetype, not the user.
- **The contact sensor's scoped topic** — it ignores `<topic>`; the compiler emits the
  `/world/<world>/model/<robot>/link/…/contact` bridge + the remap to `/bumper`.
- **World systems from sensors** — any rendering sensor (lidar/camera/depth) ⇒ add the
  `Sensors` system to the world; `imu` ⇒ `Imu` system; `contact` ⇒ `Contact` system. Derived,
  never declared. (This is the seam to the *world spec*, §G — the robot's sensors inform the
  world's required plugins.)
- **Bridge message types** — the correct `@ros_type[gz_type` per sensor/control.
- **Sensible mounts, gains, inertias** — per-archetype/-sensor defaults so a one-line
  `{type: lidar}` just works; the agent overrides only when it cares.

## Import (bring-your-own-robot)

Two paths, both landing in the same pipeline:
- **Wrap** — `create --from-urdf my.urdf` copies the URDF verbatim and writes a thin
  `robot.yaml` that references it (`base: custom, urdf: my.urdf`) + a best-effort inferred
  sensor/bridge list. Immediate "test my robot" with no compilation risk.
- **Lift** (later) — parse a URDF *into* the spec where it maps cleanly, so the agent can
  then modify it declaratively.

## Validation

The spec is proven the moment a `robot.yaml` reproduces a shipped template: compile the
differential-drive `robot.yaml`, then assert the generated project **builds** and
`stop-before-obstacle` **runs with the same result** as the hand-written template (broken
starter fails; a correct controller passes). Same gate for camera-bot / arm / drone. Unit
tests cover the pure compile (spec → URDF string / bridge list / manifest fields).

## Phasing

1. **Robot spec + compiler for `differential-drive` — DONE.** `robotbase/robotspec/`
   (`schema.py`, `compile.py`, `project.py`): the archetype + `lidar`/`imu`/`contact` sensor
   modules → URDF + bridges (with the contact remap) + world systems + manifest fields.
   Validation gate passed: a `differential-drive` `robot.yaml` compiled a URDF + launch that
   **build** and run `stop-before-obstacle` correctly (broken starter → `contact_count` 1,
   `/scan` flowing) — i.e. the compiled LiDAR + contact sensor + drivetrain all work. 6 unit
   tests.
2. **`camera` + `depth` sensor modules** — regenerate camera-bot.
3. **`fixed-arm` + `quadrotor` archetypes** — regenerate arm + drone. Now all four templates
   are *compiled from specs*, and a template is just a bundled `robot.yaml` (+ world +
   scenarios + starter controller).
4. **Import** (`--from-urdf`, wrap) and **`robotbase init`** (drop into an existing project).
5. The **world spec** (`world.yaml` → SDF) is the sibling design; together they make the
   whole project agent-authorable.

## Principles

- **Own the standard.** The robot spec is Robotbase's format (versioned), the API the agent
  writes to; URDF is a compiler output, never hand-edited.
- **The compiler owns the physics.** Every sim gotcha is our code's job, not the user's — the
  spec stays about *intent*.
- **Composable.** Archetype × sensors; adding a sensor or an archetype is a module, not a
  rewrite.
- **Escape hatch.** `base: custom` (raw URDF) always works, so nothing the compiler can't yet
  express is a blocker.
