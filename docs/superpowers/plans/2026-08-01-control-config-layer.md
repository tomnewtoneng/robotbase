# Control-Config Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the robot's control plugins a typed, declarative, tunable `control:` surface (the vision's `Controller`/`Actuator` IR concept), replacing the hardcoded plugin strings in the archetypes.

**Architecture:** Same shape as the P4 semantic IR: a typed `Controller` dataclass that each archetype constructs with today's params as defaults; a `render_controllers` backend that turns them into the gz `<plugin>` XML; a `control:` spec block whose overrides are applied in `compile_model` before rendering. Rendering is byte-identical to today's hardcoded strings (no `control:` block ⇒ unchanged output), so `tests/test_golden_output.py` is the safety net.

**Tech Stack:** Python 3.12, Pydantic v2, pytest. No new dependencies.

## Global Constraints

- **Behavior-preserving.** With no `control:` block, the compiled URDF is **byte-identical** to `main` for every template + reference. `tests/test_golden_output.py` enforces it; never regenerate the golden in this plan.
- **Policy stays the agent's.** This compiles control *config* only — never the control algorithm (`controller.py`).
- **Full suite green at every task.** `wsl.exe -d Ubuntu-24.04 -- bash -lc 'cd ~/robotbase && .venv/bin/python -m pytest -q'` passes at each task boundary (currently 260 passed, 4 skipped).
- **No new dependencies.**
- **Commit after every task.** End every commit message with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Because PowerShell→wsl mangles multi-line `-m`, write the message to `.git/COMMIT_MSG_TMP` and `git commit -F .git/COMMIT_MSG_TMP`.
- **WSL/paths:** run via `wsl.exe -d Ubuntu-24.04 -- bash -lc 'cd ~/robotbase && .venv/bin/python -m pytest ...'` (single commands — chained `&&`+echo can return empty); edit files under `\\wsl.localhost\Ubuntu-24.04\home\tom\robotbase\...`. Live tests self-skip offline, so plain `pytest -q` is the offline gate.

---

## File Structure

- `robotbase/robotspec/semantic.py` — MODIFY: add the `Controller` type; add `controllers: list[Controller]` to `RobotModel`.
- `robotbase/robotspec/ir.py` — MODIFY: add `controllers: list[Controller]` to `Fragment`.
- `robotbase/robotspec/backends/urdf.py` — MODIFY: add `render_plugin(c)` (per-kind `<plugin>`) and `render_controllers(list)` (wraps in one `<gazebo>`); `render_urdf` renders controllers between joints and gazebo.
- `robotbase/robotspec/modules.py` — MODIFY: the 3 archetypes emit typed `Controller`s (defaults) + move the JointState/Odometry publishers into controllers; friction `<gazebo reference>` blocks stay as `gazebo` strings.
- `robotbase/robotspec/merge.py` — MODIFY: `build_model` merges `f.controllers` into `model.controllers`.
- `robotbase/robotspec/schema.py` — MODIFY: add the `ControlSpec` Pydantic models and `RobotSpec.control`.
- `robotbase/robotspec/compile.py` — MODIFY: apply `control:` overrides in `compile_model`; add `ControlError`.
- `robotbase/robotspec/explain.py` — MODIFY: report controllers + override provenance.
- `robotbase/robotspec/schema_docs.py` + templates' `AGENTS.md` — MODIFY: document `control:`.
- Tests: `tests/test_backend_controllers.py` (new), `tests/test_control.py` (new), plus golden stays green.

---

## Reference — the exact current plugin strings (byte targets)

These are the strings `modules.py` emits today; `render_plugin` must reproduce them exactly. Copy verbatim.

**diff-drive** (one `<gazebo>` = DiffDrive + JointStatePublisher, then three `<gazebo reference>` friction blocks):
```
\n  <gazebo>
\n    <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">
\n      <left_joint>left_wheel_joint</left_joint><right_joint>right_wheel_joint</right_joint>
\n      <wheel_separation>{ws}</wheel_separation><wheel_radius>{wr}</wheel_radius>
\n      <topic>cmd_vel</topic><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>
\n      <frame_id>odom</frame_id><child_frame_id>base_footprint</child_frame_id>
\n      <odom_publish_frequency>30</odom_publish_frequency></plugin>
\n    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">
\n      <topic>joint_states</topic></plugin></gazebo>
\n  <gazebo reference="left_wheel"><mu1>1.0</mu1><mu2>1.0</mu2></gazebo>
\n  <gazebo reference="right_wheel"><mu1>1.0</mu1><mu2>1.0</mu2></gazebo>
\n  <gazebo reference="caster"><mu1>0.0</mu1><mu2>0.0</mu2></gazebo>
```
(`ws`, `wr` are the drive geometry floats, rendered as `str(ws)`.)

**arm** (one `<gazebo>` = 2× JointPositionController + JointStatePublisher):
```
\n  <gazebo>
\n    <plugin filename="gz-sim-joint-position-controller-system" name="gz::sim::systems::JointPositionController">
\n      <joint_name>shoulder_joint</joint_name><topic>shoulder_cmd</topic>
\n      <p_gain>80</p_gain><i_gain>2.0</i_gain><d_gain>8.0</d_gain></plugin>
\n    <plugin filename="gz-sim-joint-position-controller-system" name="gz::sim::systems::JointPositionController">
\n      <joint_name>elbow_joint</joint_name><topic>elbow_cmd</topic>
\n      <p_gain>60</p_gain><i_gain>2.0</i_gain><d_gain>6.0</d_gain></plugin>
\n    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">
\n      <topic>joint_states</topic></plugin></gazebo>
```
(Gains render as `str(value)`: default `p=80` (int)→`80`, `i=2.0` (float)→`2.0`, `d=8.0`→`8.0`.)

**quadrotor** (one `<gazebo>` = VelocityControl + OdometryPublisher):
```
\n  <gazebo>
\n    <plugin filename="gz-sim-velocity-control-system" name="gz::sim::systems::VelocityControl">
\n      <topic>cmd_vel</topic></plugin>
\n    <plugin filename="gz-sim-odometry-publisher-system" name="gz::sim::systems::OdometryPublisher">
\n      <odom_frame>odom</odom_frame><robot_base_frame>base_link</robot_base_frame>
\n      <dimensions>3</dimensions><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>
\n      <odom_publish_frequency>30</odom_publish_frequency></plugin></gazebo>
```

---

## Task 1: The `Controller` IR type

**Files:**
- Modify: `robotbase/robotspec/semantic.py`, `robotbase/robotspec/ir.py`
- Test: `tests/test_control.py` (new)

**Interfaces:**
- Produces: `semantic.Controller(kind: str, params: dict, joint: str | None = None)` — a non-frozen dataclass (params is mutated in place by overrides); `RobotModel.controllers: list[Controller]`; `Fragment.controllers: list[Controller]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_control.py
from robotbase.robotspec.semantic import Controller, RobotModel
from robotbase.robotspec.ir import Fragment


def test_controller_holds_kind_params_joint():
    c = Controller("joint-position", {"joint_name": "shoulder_joint", "p": 80, "i": 2.0, "d": 8.0},
                   joint="shoulder_joint")
    assert c.kind == "joint-position" and c.joint == "shoulder_joint"
    c.params["p"] = 120                      # params is mutable (overrides update in place)
    assert c.params["p"] == 120


def test_model_and_fragment_default_empty_controllers():
    assert RobotModel(name="r", root="a").controllers == []
    assert Fragment().controllers == []
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_control.py -q` → FAIL (no `Controller`).

- [ ] **Step 3: Implement**

In `semantic.py`, add near the other types (after `Sensor`):
```python
@dataclass
class Controller:
    """A control system the compiler configures (the vision's Controller/Actuator IR concept).
    ``kind`` selects the gz plugin; ``params`` carries its control knobs (gains, freqs, topics);
    ``joint`` names the target joint for per-joint controllers (an arm's joint-position controllers).
    Non-frozen: ``control:`` overrides mutate ``params`` in place during compile."""
    kind: str
    params: dict = field(default_factory=dict)
    joint: str | None = None
```
Add to `RobotModel` (after `joints`): `controllers: list[Controller] = field(default_factory=list)`.

In `ir.py`, add to `Fragment` (after `joints`): `controllers: list[Controller] = field(default_factory=list)` and extend the `TYPE_CHECKING` import to include `Controller`.

- [ ] **Step 4: Run tests** — `pytest tests/test_control.py -q` → PASS.

- [ ] **Step 5: Commit** — message `feat(control): Controller IR type + RobotModel/Fragment.controllers`.

---

## Task 2: The control backend — `render_plugin` + `render_controllers`

**Files:**
- Modify: `robotbase/robotspec/backends/urdf.py`
- Test: `tests/test_backend_controllers.py` (new)

**Interfaces:**
- Consumes: `Controller` (Task 1).
- Produces: `render_plugin(c: Controller) -> str` (the inner `<plugin>…</plugin>`, kinds: `diff-drive`, `joint-state-publisher`, `joint-position`, `velocity`, `odometry-publisher`); `render_controllers(cs: list[Controller]) -> str` (`""` when empty, else `\n  <gazebo>` + plugins + `</gazebo>`). Raises `UnknownGzController` for an unknown kind.

- [ ] **Step 1: Write the failing test** (byte-parity with the current strings)

```python
# tests/test_backend_controllers.py
from robotbase.robotspec.semantic import Controller
from robotbase.robotspec.backends.urdf import render_plugin, render_controllers


def test_render_controllers_empty_is_blank():
    assert render_controllers([]) == ""


def test_diff_drive_group_matches_current_bytes():
    diff = Controller("diff-drive", {
        "left_joint": "left_wheel_joint", "right_joint": "right_wheel_joint",
        "wheel_separation": 0.34, "wheel_radius": 0.05, "topic": "cmd_vel",
        "odom_topic": "odom", "tf_topic": "tf", "frame_id": "odom",
        "child_frame_id": "base_footprint", "odom_publish_frequency": 30})
    jsp = Controller("joint-state-publisher", {"topic": "joint_states"})
    assert render_controllers([diff, jsp]) == (
        '\n  <gazebo>'
        '\n    <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">'
        '\n      <left_joint>left_wheel_joint</left_joint><right_joint>right_wheel_joint</right_joint>'
        '\n      <wheel_separation>0.34</wheel_separation><wheel_radius>0.05</wheel_radius>'
        '\n      <topic>cmd_vel</topic><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>'
        '\n      <frame_id>odom</frame_id><child_frame_id>base_footprint</child_frame_id>'
        '\n      <odom_publish_frequency>30</odom_publish_frequency></plugin>'
        '\n    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">'
        '\n      <topic>joint_states</topic></plugin></gazebo>')


def test_joint_position_gains_render_as_str():
    c = Controller("joint-position",
                   {"joint_name": "shoulder_joint", "topic": "shoulder_cmd", "p": 80, "i": 2.0, "d": 8.0},
                   joint="shoulder_joint")
    assert render_plugin(c) == (
        '\n    <plugin filename="gz-sim-joint-position-controller-system" name="gz::sim::systems::JointPositionController">'
        '\n      <joint_name>shoulder_joint</joint_name><topic>shoulder_cmd</topic>'
        '\n      <p_gain>80</p_gain><i_gain>2.0</i_gain><d_gain>8.0</d_gain></plugin>')


def test_velocity_and_odometry_publisher():
    vel = Controller("velocity", {"topic": "cmd_vel"})
    odom = Controller("odometry-publisher", {
        "odom_frame": "odom", "robot_base_frame": "base_link", "dimensions": 3,
        "odom_topic": "odom", "tf_topic": "tf", "odom_publish_frequency": 30})
    assert render_controllers([vel, odom]) == (
        '\n  <gazebo>'
        '\n    <plugin filename="gz-sim-velocity-control-system" name="gz::sim::systems::VelocityControl">'
        '\n      <topic>cmd_vel</topic></plugin>'
        '\n    <plugin filename="gz-sim-odometry-publisher-system" name="gz::sim::systems::OdometryPublisher">'
        '\n      <odom_frame>odom</odom_frame><robot_base_frame>base_link</robot_base_frame>'
        '\n      <dimensions>3</dimensions><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>'
        '\n      <odom_publish_frequency>30</odom_publish_frequency></plugin>')
```

- [ ] **Step 2: Run to verify it fails** — FAIL (no `render_plugin`).

- [ ] **Step 3: Implement** in `backends/urdf.py` (import `Controller`; add near `render_sensor`):

```python
class UnknownGzController(ValueError):
    ...


def render_plugin(c: Controller) -> str:
    """The inner gz <plugin> for one Controller. Params render with str() so the archetype defaults
    reproduce today's exact strings (p=80 -> '80', i=2.0 -> '2.0')."""
    p = c.params
    if c.kind == "diff-drive":
        return (f'\n    <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">'
                f'\n      <left_joint>{p["left_joint"]}</left_joint><right_joint>{p["right_joint"]}</right_joint>'
                f'\n      <wheel_separation>{p["wheel_separation"]}</wheel_separation><wheel_radius>{p["wheel_radius"]}</wheel_radius>'
                f'\n      <topic>{p["topic"]}</topic><odom_topic>{p["odom_topic"]}</odom_topic><tf_topic>{p["tf_topic"]}</tf_topic>'
                f'\n      <frame_id>{p["frame_id"]}</frame_id><child_frame_id>{p["child_frame_id"]}</child_frame_id>'
                f'\n      <odom_publish_frequency>{p["odom_publish_frequency"]}</odom_publish_frequency></plugin>')
    if c.kind == "joint-state-publisher":
        return (f'\n    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">'
                f'\n      <topic>{p["topic"]}</topic></plugin>')
    if c.kind == "joint-position":
        return (f'\n    <plugin filename="gz-sim-joint-position-controller-system" name="gz::sim::systems::JointPositionController">'
                f'\n      <joint_name>{p["joint_name"]}</joint_name><topic>{p["topic"]}</topic>'
                f'\n      <p_gain>{p["p"]}</p_gain><i_gain>{p["i"]}</i_gain><d_gain>{p["d"]}</d_gain></plugin>')
    if c.kind == "velocity":
        return (f'\n    <plugin filename="gz-sim-velocity-control-system" name="gz::sim::systems::VelocityControl">'
                f'\n      <topic>{p["topic"]}</topic></plugin>')
    if c.kind == "odometry-publisher":
        return (f'\n    <plugin filename="gz-sim-odometry-publisher-system" name="gz::sim::systems::OdometryPublisher">'
                f'\n      <odom_frame>{p["odom_frame"]}</odom_frame><robot_base_frame>{p["robot_base_frame"]}</robot_base_frame>'
                f'\n      <dimensions>{p["dimensions"]}</dimensions><odom_topic>{p["odom_topic"]}</odom_topic><tf_topic>{p["tf_topic"]}</tf_topic>'
                f'\n      <odom_publish_frequency>{p["odom_publish_frequency"]}</odom_publish_frequency></plugin>')
    raise UnknownGzController(f"no URDF rendering for controller kind {c.kind!r}")


def render_controllers(cs: list[Controller]) -> str:
    """Render a group of controllers as one <gazebo> block (matches the current per-archetype grouping)."""
    if not cs:
        return ""
    return '\n  <gazebo>' + "".join(render_plugin(c) for c in cs) + '</gazebo>'
```

- [ ] **Step 4: Run tests** — `pytest tests/test_backend_controllers.py -q` → PASS.

- [ ] **Step 5: Commit** — `feat(control): render_plugin/render_controllers byte-identical to the current plugin strings`.

---

## Task 3: Migrate the archetypes + wire `render_urdf` (golden stays green)

**Files:**
- Modify: `robotbase/robotspec/modules.py`, `robotbase/robotspec/backends/urdf.py` (`render_urdf`), `robotbase/robotspec/merge.py` (`build_model`)
- Test: `tests/test_golden_output.py` (must stay byte-identical), `tests/test_modules.py`

**Interfaces:**
- Consumes: `render_controllers` (Task 2), `Fragment.controllers`, `RobotModel.controllers`.
- Produces: archetypes append typed `Controller`s to `f.controllers` instead of the control `<gazebo>` string; `render_urdf` inserts `render_controllers(model.controllers)` between joints and gazebo.

- [ ] **Step 1: Wire `render_urdf` + `build_model`.** In `backends/urdf.render_urdf`, insert the controllers between joints and gazebo:
```python
            + "".join(render_joint(j) for j in model.joints)
            + render_controllers(model.controllers)
            + "".join(model.gazebo)
```
In `merge.build_model`, inside the fragment loop add: `model.controllers += f.controllers`.

- [ ] **Step 2: Migrate `differential_drive` in `modules.py`.** Replace the single `f.gazebo.append('\n  <gazebo>…DiffDrive…JointStatePublisher…</gazebo>…friction…')` with:
```python
    f.controllers.append(Controller("diff-drive", {
        "left_joint": "left_wheel_joint", "right_joint": "right_wheel_joint",
        "wheel_separation": ws, "wheel_radius": wr, "topic": "cmd_vel",
        "odom_topic": "odom", "tf_topic": "tf", "frame_id": "odom",
        "child_frame_id": "base_footprint", "odom_publish_frequency": 30}))
    f.controllers.append(Controller("joint-state-publisher", {"topic": "joint_states"}))
    f.gazebo.append(
        '\n  <gazebo reference="left_wheel"><mu1>1.0</mu1><mu2>1.0</mu2></gazebo>'
        '\n  <gazebo reference="right_wheel"><mu1>1.0</mu1><mu2>1.0</mu2></gazebo>'
        '\n  <gazebo reference="caster"><mu1>0.0</mu1><mu2>0.0</mu2></gazebo>')
```
Import `Controller` from `robotbase.robotspec.semantic` at the top of `modules.py`.

- [ ] **Step 3: Migrate `arm`.** Replace the arm's control `<gazebo>` string with:
```python
    f.controllers.append(Controller("joint-position",
        {"joint_name": "shoulder_joint", "topic": "shoulder_cmd", "p": 80, "i": 2.0, "d": 8.0},
        joint="shoulder_joint"))
    f.controllers.append(Controller("joint-position",
        {"joint_name": "elbow_joint", "topic": "elbow_cmd", "p": 60, "i": 2.0, "d": 6.0},
        joint="elbow_joint"))
    f.controllers.append(Controller("joint-state-publisher", {"topic": "joint_states"}))
```
(The arm now appends nothing to `f.gazebo`.)

- [ ] **Step 4: Migrate `quadrotor`.** Replace its control `<gazebo>` string with:
```python
    f.controllers.append(Controller("velocity", {"topic": "cmd_vel"}))
    f.controllers.append(Controller("odometry-publisher", {
        "odom_frame": "odom", "robot_base_frame": "base_link", "dimensions": 3,
        "odom_topic": "odom", "tf_topic": "tf", "odom_publish_frequency": 30}))
```

- [ ] **Step 5: Run the golden guard + module tests**

Run: `wsl.exe -d Ubuntu-24.04 -- bash -lc 'cd ~/robotbase && .venv/bin/python -m pytest tests/test_golden_output.py tests/test_modules.py -q'`
Expected: **PASS, byte-identical** (the reference strings prove it). If a template differs, diff the compiled URDF against the golden and fix the plugin ordering/params so the bytes match — do NOT regenerate the golden.

- [ ] **Step 6: Run the full suite** — `pytest -q` → all green (260 passed, 4 skipped).

- [ ] **Step 7: Commit** — `refactor(control): archetypes emit typed Controllers; backend renders them (byte-identical)`.

---

## Task 4: The `control:` schema + override application + validation

**Files:**
- Modify: `robotbase/robotspec/schema.py`, `robotbase/robotspec/compile.py`
- Test: `tests/test_control.py`

**Interfaces:**
- Consumes: `RobotModel.controllers` (Task 1).
- Produces: `schema.ControlSpec` (`joints: dict[str, JointControl]`, `base: BaseControl | None`), `RobotSpec.control: ControlSpec | None`; `compile.ControlError`; `compile_model` applies overrides before returning the model.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_control.py
import pytest
from robotbase.robotspec.schema import RobotSpec
from robotbase.robotspec.compile import compile_model, ControlError


def _ctrl(model, joint):
    return next(c for c in model.controllers if c.joint == joint)


def test_control_overrides_arm_gains():
    spec = RobotSpec.model_validate({"name": "arm", "base": "arm",
        "control": {"joints": {"shoulder_joint": {"p": 120, "d": 10}}}})
    model = compile_model(spec)
    sh = _ctrl(model, "shoulder_joint")
    assert sh.params["p"] == 120 and sh.params["d"] == 10 and sh.params["i"] == 2.0   # i untouched
    assert _ctrl(model, "elbow_joint").params["p"] == 60                              # elbow default


def test_control_overrides_drive_odom_frequency():
    spec = RobotSpec.model_validate({"name": "r", "base": "differential-drive",
        "control": {"base": {"odom_publish_frequency": 50}}})
    model = compile_model(spec)
    diff = next(c for c in model.controllers if c.kind == "diff-drive")
    assert diff.params["odom_publish_frequency"] == 50


def test_control_bad_joint_raises():
    spec = RobotSpec.model_validate({"name": "arm", "base": "arm",
        "control": {"joints": {"wrist_joint": {"p": 1}}}})
    with pytest.raises(ControlError, match="wrist_joint"):
        compile_model(spec)


def test_control_base_without_drive_controller_raises():
    spec = RobotSpec.model_validate({"name": "arm", "base": "arm",
        "control": {"base": {"odom_publish_frequency": 50}}})
    with pytest.raises(ControlError, match="drive"):
        compile_model(spec)


def test_no_control_block_leaves_defaults():
    model = compile_model(RobotSpec.model_validate({"name": "arm", "base": "arm"}))
    assert _ctrl(model, "shoulder_joint").params["p"] == 80
```

- [ ] **Step 2: Run to verify it fails** — FAIL (no `control` field / `ControlError`).

- [ ] **Step 3: Add the schema** in `schema.py` (use the file's existing Pydantic import + `ConfigDict`; match the `extra="forbid"` pattern the other specs use):

```python
class JointControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p: int | float | None = None      # int|float preserves the user's numeric form (120 -> "120")
    i: int | float | None = None
    d: int | float | None = None


class BaseControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    odom_publish_frequency: int | float | None = None
    topic: str | None = None
    odom_topic: str | None = None
    tf_topic: str | None = None


class ControlSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    joints: dict[str, JointControl] = {}
    base: BaseControl | None = None
```
Add to `RobotSpec`: `control: ControlSpec | None = None`.

- [ ] **Step 4: Apply overrides in `compile.py`.** Add `ControlError` and an `_apply_control` helper, called at the end of `compile_model` before `return build_model(...)` — i.e. build the model, apply overrides, return it:

```python
class ControlError(ValueError):
    """A `control:` override targets a joint/controller the robot does not have."""


def _apply_control(model, control) -> None:
    if control is None:
        return
    for jname, gains in control.joints.items():
        matched = [c for c in model.controllers if c.joint == jname]
        if not matched:
            have = sorted(c.joint for c in model.controllers if c.joint)
            raise ControlError(f"control.joints: no controller for joint {jname!r}; joints with controllers: {have}")
        for c in matched:
            for k in ("p", "i", "d"):
                v = getattr(gains, k)
                if v is not None:
                    c.params[k] = v
    if control.base is not None:
        matched = [c for c in model.controllers if c.kind in ("diff-drive", "velocity")]
        if not matched:
            raise ControlError("control.base: robot has no drive/velocity controller to configure")
        for c in matched:
            for k in ("odom_publish_frequency", "topic", "odom_topic", "tf_topic"):
                v = getattr(control.base, k)
                if v is not None and k in c.params:
                    c.params[k] = v
```
In `compile_model`, change the final `return build_model(spec.name, root, fragments)` to:
```python
    model = build_model(spec.name, root, fragments)
    _apply_control(model, spec.control)
    return model
```

- [ ] **Step 5: Run tests** — `pytest tests/test_control.py -q` → PASS; then `pytest -q` → full suite green (golden still byte-identical because no `control:` block ⇒ default params).

- [ ] **Step 6: Commit** — `feat(control): declarative control: block overrides controller params, with validation`.

---

## Task 5: Explain / describe integration + provenance

**Files:**
- Modify: `robotbase/robotspec/explain.py`
- Test: `tests/test_explain.py`

**Interfaces:**
- Consumes: `RobotModel.controllers`, `spec.control`.
- Produces: `explain_robot(spec)` output includes a `controllers` list (kind, joint, params) with each value tagged authored (overridden in `control:`) vs default.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_explain.py
from robotbase.robotspec.schema import RobotSpec
from robotbase.robotspec.explain import explain_robot


def test_explain_reports_controllers_and_override_provenance():
    spec = RobotSpec.model_validate({"name": "arm", "base": "arm",
        "control": {"joints": {"shoulder_joint": {"p": 120}}}})
    out = explain_robot(spec)
    ctrls = out["controllers"]
    sh = next(c for c in ctrls if c.get("joint") == "shoulder_joint")
    assert sh["kind"] == "joint-position"
    assert sh["params"]["p"] == 120 and sh["source"] == "control:"        # overridden
    el = next(c for c in ctrls if c.get("joint") == "elbow_joint")
    assert el["source"] == "default"                                       # untouched
```

- [ ] **Step 2: Run to verify it fails** — FAIL (`controllers` key absent).

- [ ] **Step 3: Implement.** In `explain.py`, after assembling the explanation, add a `controllers` section built from `compile_model(spec).controllers`, marking a controller `"control:"` when its joint/kind appears in `spec.control`, else `"default"`:

```python
def _controllers_report(spec, world_name="warehouse") -> list[dict]:
    from robotbase.robotspec.compile import compile_model, _parts
    if any(p.use == "custom" for p in _parts(spec)):
        return []                                   # custom imports have no semantic controllers
    model = compile_model(spec)
    overridden_joints = set((spec.control.joints or {}) if spec.control else ())
    base_overridden = bool(spec.control and spec.control.base)
    rows = []
    for c in model.controllers:
        src = "default"
        if c.joint and c.joint in overridden_joints:
            src = "control:"
        elif c.kind in ("diff-drive", "velocity") and base_overridden:
            src = "control:"
        rows.append({"kind": c.kind, "joint": c.joint, "params": dict(c.params), "source": src})
    return rows
```
Add `"controllers": _controllers_report(spec, world_name)` to the dict `explain_robot` returns (both the normal and custom-import return paths; custom returns `[]`).

- [ ] **Step 4: Run tests** — `pytest tests/test_explain.py -q` → PASS; `pytest -q` → green.

- [ ] **Step 5: Commit** — `feat(control): explain reports controllers + control: override provenance`.

---

## Task 6: Docs — authoring reference + AGENTS.md

**Files:**
- Modify: `robotbase/robotspec/schema_docs.py`, each template's `AGENTS.md`, `docs/design/declarative-compiler.md`
- Test: `tests/test_authoring_knowledge.py` (the no-drift guard must still pass)

- [ ] **Step 1: Document `control:` in the authoring reference.** In `schema_docs.py`'s `authoring_reference()`, add a short `control:` section: `control.joints.<joint_name>: {p, i, d}` tunes a joint-position controller's PID gains; `control.base: {odom_publish_frequency, topic, odom_topic, tf_topic}` tunes the drive/velocity controller; geometry (`wheel_radius`/`wheel_separation`) stays in `drive:`. Keep it schema-derived/general (no task specifics) so the no-drift test passes.

- [ ] **Step 2: Run the no-drift guard** — `pytest tests/test_authoring_knowledge.py -q` → PASS (adjust the reference text until the guard is satisfied).

- [ ] **Step 3: Update `declarative-compiler.md`.** Add a short "Control configuration" subsection under the semantic-IR architecture: `Controller` is a typed IR concept; archetypes emit defaults; `control:` overrides; gz-plugin backend now, ros2_control a future backend (the sim-to-real bridge). One paragraph.

- [ ] **Step 4: Update each template `AGENTS.md`** (differential-drive, camera-bot, arm, drone): one line pointing at `control:` for tuning gains/odom rate, and reaffirming that the control *algorithm* is theirs to write in `controller.py`.

- [ ] **Step 5: Run the full suite** — `pytest -q` → green.

- [ ] **Step 6: Commit** — `docs(control): document the control: surface in the authoring reference + AGENTS`.

---

## Task 7: Future-work note in the spec + STRATEGY

**Files:**
- Modify: `docs/STRATEGY.md`, `docs/IDEAS.md`

- [ ] **Step 1: Record the future upgrades.** In `STRATEGY.md` (near the P-items / "Later") and `IDEAS.md`, add: the declarative `control:` config layer shipped (typed `Controller` IR + gz-plugin backend); **future — B:** selectable controllers (`control: {type: …}`); **C:** a ros2_control backend (`controllers.yaml`) which is also the `hardware_interface` sim-to-real bridge — additive backends over the same `Controller` IR.

- [ ] **Step 2: Commit** — `docs(control): record selectable-controller (B) + ros2_control (C) as future upgrades`.

---

## Self-Review

- **Spec coverage:** §1 goal → Tasks 1–4; §5 IR type → Task 1; §6 backend + byte-identity → Tasks 2–3; §7 `control:` surface → Task 4; §8 validation + explain → Tasks 4–5; §9 future backends → Task 7; §10 testing → tests in each task + golden guard; §11 files → all touched; §12 scope guardrails → only actuator/controllers typed (support publishers are typed but non-tunable; friction stays strings). Covered.
- **Placeholder scan:** every code step has real code; the exact byte targets are in the Reference section; no TBDs.
- **Type consistency:** `Controller(kind, params, joint)`, `render_plugin`/`render_controllers`, `RobotModel.controllers`, `Fragment.controllers`, `ControlSpec`/`JointControl`/`BaseControl`, `RobotSpec.control`, `ControlError`, `_apply_control`, `compile_model` used identically across Tasks 1→7.
- **Byte-identity:** Tasks 2–3's strings are copied verbatim from `modules.py`; render order (joints → controllers → gazebo) + the friction-stays-in-gazebo split reproduce the current concatenation exactly; the golden guard is the enforcement and must not be regenerated.
- **Risk gate:** live Docker bring-up is not runnable here; default-params byte-identity + golden + correct-by-construction overrides keep it low; flag the live gate (`ROBOTBENCH_LIVE=1 pytest tests/test_reference_solutions_live.py`) to the owner.
