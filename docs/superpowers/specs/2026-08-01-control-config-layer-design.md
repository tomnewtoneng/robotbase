# Control-Config Layer (declarative controllers) — Design Spec

> Status: **approved design, 2026-08-01** — ready for an implementation plan.
> Author: Tom + Claude (brainstorming session).
> Relates to: `docs/STRATEGY.md` (P2 "compile the runtime", the vision's `Controller`/`Actuator`
> IR concepts + `controllers.yaml`), `docs/design/declarative-compiler.md` (the semantic IR + backends
> shipped in P4), the Product Vision PDF §5.4 (IR concepts) and §7 (Studio, which consumes this).

## 1. Goal

Make the robot's **control configuration** a first-class, declarative, tunable part of the spec —
the vision's `Controller`/`Actuator` IR concept — instead of the current state where control is
hardcoded inside each archetype and inconsistently exposed. Concretely: a `control:` block in
`robot.yaml` that tunes the compiled control plugins (PID gains, odometry rate, topic names),
compiled through a typed `Controller` IR to the Gazebo control plugins the compiler already emits.

This closes the last "hardcoded in the archetype" runtime gap and realises an IR concept the vision
has always listed but the code never had.

## 2. Non-goals (explicit)

- **The control *policy*/algorithm stays the agent's hand-written `controller.py`.** We do NOT compile
  the obstacle-avoidance / navigation / reaching algorithm. Per the project's own framing test:
  *"the controller is always the agent's to write; we build the SQL, the agent writes the query."*
  Compiling the policy away would defeat the "watch the agent learn" thesis.
- **No Robotbase control *library*.** ROS already exposes control algorithms (ros2_control,
  Nav2, MoveIt); shipping our own PID/pure-pursuit library would reinvent that and is off-moat. The
  place to *help* the agent with control is the knowledge layer, not our own code.
- **Not adopting ros2_control in this cut** (see §9 — it is a designed-for future backend).
- **Wheel/joint *geometry* is not moved into `control:`** — it stays in `drive:`/`body:` (geometry,
  single source of truth). `control:` only tunes non-geometry control knobs.

## 3. Background — what exists today

Robots, worlds, sensors, tests, and evals are compiled from specs (P1–P5, P4 semantic IR). But
**control is hardcoded in the archetype modules** (`robotbase/robotspec/modules.py`) and emitted as
**raw `<gazebo>` plugin strings** into `RobotModel.gazebo` (a `list[str]`). The P4 plan floated typing
these as "GazeboSystem" objects but deferred it, so they remain untyped strings. The exposure is
inconsistent:

| Archetype | Control plugin(s) emitted | Tunable today? |
|---|---|---|
| differential-drive | `gz-sim-diff-drive-system` (+ JointStatePublisher) | wheel geometry via `drive:`; **odom rate / topics hardcoded** |
| arm | 2× `gz-sim-joint-position-controller-system` (+ JointStatePublisher) | **PID gains hardcoded** (p80/i2/d8, p60/i2/d6) |
| quadrotor | `gz-sim-velocity-control-system` (+ OdometryPublisher) | **nothing exposed** |

Robotbase drives the sim with **gz-sim control plugins** baked into the URDF `<gazebo>` — there is no
`controller_manager`, no ros2_control, no `controllers.yaml`. The agent's `controller.py` publishes
the command topic (`/cmd_vel`, `/shoulder_cmd`); the gz plugin actuates.

## 4. Principle

Same shape as P4: **a typed IR concept + a rendering backend.** Archetypes construct typed
`Controller` objects (today's params as defaults); a `control:` block overrides params; the backend
renders them to the gz `<plugin>` XML. Progressive disclosure — the one-liner (`base: arm`) still
works unchanged; `control:` is opt-in tuning. Behavior-preserving — the golden guard freezes today's
output, so a spec with no `control:` block compiles byte-identically.

## 5. The IR type

`robotbase/robotspec/semantic.py` gains:

```python
@dataclass(frozen=True)
class Controller:
    """A control system the compiler configures (the vision's Controller/Actuator IR concept).
    kind selects the gz plugin; params carries its kind-specific control knobs; joint names the
    target joint for per-joint controllers (e.g. an arm's joint-position controllers)."""
    kind: str                       # "diff-drive" | "joint-position" | "velocity"
    params: dict                    # kind-specific control params (gains, freqs, topics)
    joint: str | None = None        # per-joint controllers (arm); None for whole-robot controllers
```

`RobotModel` gains `controllers: list[Controller] = field(default_factory=list)`.

`Controller` is frozen/hashable like the other semantic types; `params` is a plain dict of the
control knobs (kept a dict rather than per-kind subclasses to keep the first cut small — the set of
knobs is small and kind-keyed rendering handles the variation, mirroring how `Sensor` is rendered by
`gz_type`).

## 6. The backend

`robotbase/robotspec/backends/urdf.py` gains `render_controller(c: Controller) -> str` (and a small
`render_controllers(...)` grouper), keyed by `kind`, producing the gz `<plugin>` XML — the one place
control plugin strings are produced, mirroring `render_sensor`.

**Byte-identity constraint (critical).** The current archetypes wrap the actuator plugin *and* a
co-located support publisher (JointStatePublisher / OdometryPublisher) inside a single
`<gazebo>…</gazebo>` block. To stay byte-identical the renderer must reproduce that exact grouping.
Design detail for the plan: the co-located support publisher (JointStatePublisher / OdometryPublisher)
travels as a **fixed, non-tunable part of the rendered control block** for that archetype — it is
infrastructure, not part of the `control:` tuning surface. The `<gazebo reference="…">` friction
blocks (wheels/caster) are unrelated to control and stay archetype-emitted gazebo strings. The
golden guard (`tests/test_golden_output.py`) is the enforcement: at default params the compiled URDF
is byte-for-byte unchanged.

## 7. The `control:` spec surface

A new optional top-level `control:` block (Pydantic model on `RobotSpec`, `extra="forbid"` like the
rest of the schema). Override-only — every field defaults to the archetype's value.

Arm (per-joint PID gains — the main gap):
```yaml
base: arm
control:
  joints:
    shoulder: {p: 120, i: 2, d: 10}     # was hardcoded p80/i2/d8
    elbow:    {p: 90}                    # partial override; i/d keep defaults
```

Differential-drive / quadrotor (non-geometry control knobs):
```yaml
base: differential-drive
control:
  base: {odom_publish_frequency: 50}    # topic names also overridable here
```

- **`control.joints`** — keyed by joint name (joint names are unique across a robot, so this also
  disambiguates a mobile-manipulator's base + arm); overrides that joint's controller params.
- **`control.base`** — the whole-robot drive/velocity controller's non-geometry knobs
  (`odom_publish_frequency`, command/odom/tf topic names).
- **Geometry stays out:** the diff-drive plugin's `wheel_separation`/`wheel_radius` are *derived* from
  `drive:`/`body:` as today; `control:` never duplicates them, so they cannot disagree.
- `drive:` is unchanged (backward compatible); it provides wheel geometry that flows into the
  diff-drive controller's defaults.

## 8. Validation + explain/describe

- **Validation (P3 style):** a `control:` override that targets a joint/controller the robot does not
  have raises a clean typed error naming the bad key (e.g. `control.joints.wrist` on a 2-joint arm) —
  never a silent no-op.
- **Explain/describe (P1/P3 style):** `robotbase explain` attributes the controllers to their source
  (archetype default vs `control:` override), and each control value is tagged authored/default via
  the existing provenance mechanism, so "did my gain override take?" is answerable without reading the
  compiled URDF.

## 9. Backends — now and future

- **Now:** the gz-plugin backend (`render_controller`), byte-identical to today.
- **Future upgrade B — selectable controllers.** `control: {type: …}` to *swap* a controller, not just
  tune it (e.g. a different drive controller). Additive over the same `Controller` IR; recorded, not
  built now.
- **Future upgrade C — ros2_control backend.** A second backend emitting `controllers.yaml` +
  `controller_manager` + `gz_ros2_control` — the vision's named artifact, and whose `hardware_interface`
  is the **sim-to-real bridge** (swap the sim hardware plugin for a real one, same controllers, same
  `control:` spec). Additive backend over the same IR, exactly as MJCF was over `RobotModel` — not a
  rewrite. Recorded, not built now.

## 10. Testing

- **Golden byte-identity:** the 4 templates + references with no `control:` block compile byte-for-byte
  unchanged (existing `tests/test_golden_output.py`).
- **Override → effect:** a `control:` gain/rate/topic override changes exactly that value in the
  rendered plugin, defaults untouched.
- **Validation:** an override targeting a non-existent joint/controller raises the typed error.
- **Explain:** `explain`/`describe` report the controllers and mark overridden values as authored.
- **Live gate (human):** as with P2, the Docker bring-up (`ROBOTBENCH_LIVE=1 pytest
  tests/test_reference_solutions_live.py`) confirms the arm still reaches its configuration with the
  (default) gains live — flagged for Tom to run, since this environment has no Docker.

## 11. Files touched

- `robotbase/robotspec/semantic.py` — add `Controller`; add `controllers` to `RobotModel`.
- `robotbase/robotspec/backends/urdf.py` — add `render_controller` (+ grouper); `render_urdf`
  renders controllers into the control `<gazebo>` block.
- `robotbase/robotspec/modules.py` — the three archetypes emit typed `Controller`s (with today's
  params as defaults) instead of hardcoded plugin strings.
- `robotbase/robotspec/schema.py` — the `control:` Pydantic model on `RobotSpec` (`extra="forbid"`);
  merge overrides onto the archetype defaults during compile.
- `robotbase/robotspec/compile.py` — apply `control:` overrides to the assembled controllers.
- `robotbase/robotspec/validate.py`, `explain.py` — validation + provenance integration.
- `robotbase/robotspec/schema_docs` / `AGENTS.md` — document `control:` in the authoring reference.
- Tests: `tests/test_control.py` (new), plus golden + explain/validate coverage.

## 12. Scope guardrails / YAGNI

- Only the **actuator/controllers** (DiffDrive, JointPositionController, VelocityControl) become the
  typed, tunable surface. Support publishers (JointStatePublisher, OdometryPublisher) and sensor
  world-systems stay as-is.
- `params` is a dict, not per-kind typed subclasses (small knob set; revisit if it grows).
- No controller *selection/swapping* (B) and no ros2_control (C) in this cut.
- No new units handling; gains/rates are bare numbers as today.

## 13. Risks / open questions

- **Byte-identity decomposition** of the current combined `<gazebo>` blocks (actuator + co-located
  publisher) is the fiddliest part; the golden guard makes any mismatch loud, and the plan will work
  out the exact grouping.
- **Live verification** of the arm/quadrotor control is Docker-only; correct-by-construction +
  golden + the default-params byte-identity keep the risk low, but the live gate should be run.
- **Multi-controller disambiguation** beyond joint-name keying (e.g. two identical drive controllers)
  is not needed for the current archetypes; revisit if a future archetype requires it.
