# Semantic IR (P4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Robotbase's URDF-string IR with a **typed, backend-neutral semantic IR** — RigidBody / Joint / Sensor / Actuator / World concepts — where URDF, SDF, and launch become *pure backends* that render the IR, so the compiler owns robotics semantics rather than Gazebo XML.

**Architecture:** Introduce the semantic types and a URDF backend *alongside* the existing string IR, prove the backend renders byte-identical output for each construct, then migrate the emitters (modules, sensors, world) one at a time to produce semantic objects, and finally delete the string IR. **Every task keeps the full test suite green and the compiled URDF/SDF byte-identical** (a golden-output guard) — this is a refactor, not a behavior change. The payoff: validation/explain read typed fields instead of parsing XML, and a second backend (MJCF) becomes an additive file, not a rewrite — killing the vision's #1 kill-signal ("the IR is coupled to Gazebo/URDF").

**Tech Stack:** Python 3.12, Pydantic v2 / dataclasses, pytest. No new runtime dependencies. Existing modules: `robotbase/robotspec/{ir,modules,sensors,merge,compile,validate,explain}.py`, `robotbase/worldspec/{compile,schema}.py`.

## Global Constraints

- **Behavior-preserving.** The compiled URDF and world SDF must stay **byte-identical** to `main` for every shipped template + reference solution at every task boundary. Task 1 builds the golden-output guard that enforces this; no later task may change it without an explicit, reviewed reason.
- **Full suite green at every task.** 217 offline tests (`pytest -k "not live"`) pass at each task boundary; never commit red.
- **No new dependencies.** Semantic types are dataclasses/Pydantic already vendored.
- **Incremental, never big-bang.** The string IR (`LinkIR`/`JointIR`) and the semantic IR coexist until the final cleanup task; each migration task flips exactly one emitter and keeps the rest on the old path via adapters.
- **One source of truth stays one.** The shape→size rule (`ir.SHAPE_SIZE`) and the inertia formulas move into the semantic types unchanged; the knowledge layer's no-drift test must still pass.
- **Commit after every task.** End every commit message with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **WSL/paths:** run via `wsl.exe -d Ubuntu-24.04 -- bash -lc 'cd ~/robotbase && .venv/bin/python -m pytest ...'`; edit files under `\\wsl.localhost\Ubuntu-24.04\home\tom\robotbase\...`.

---

## File Structure

- `robotbase/robotspec/semantic.py` — CREATE: the typed IR — `Geometry` (`Box`/`Cylinder`/`Sphere`), `Inertial`, `Visual`/`Collision`, `RigidBody`, `Joint`, `Sensor`, `GazeboSystem`, `RobotModel`. Pure data + the inertia/geometry math (moved from `ir.link_from_shape`). No rendering.
- `robotbase/robotspec/backends/__init__.py` — CREATE: backend registry.
- `robotbase/robotspec/backends/urdf.py` — CREATE: `render_urdf(model: RobotModel) -> str`. The ONLY place URDF strings are produced.
- `robotbase/robotspec/backends/mjcf.py` — CREATE (Task 12, skeleton): `render_mjcf(model) -> str` for the common subset — proves the seam.
- `robotbase/worldspec/semantic.py` — CREATE: `WorldModel`, `StaticModel`, `Light`, `Physics`, world `Sensor`-systems.
- `robotbase/worldspec/backends/sdf.py` — CREATE: `render_sdf(world: WorldModel, systems) -> str`.
- `robotbase/robotspec/ir.py` — MODIFY then SHRINK: `LinkIR`/`JointIR`/`Fragment` become thin adapters over semantic types during migration, deleted in Task 11.
- `robotbase/robotspec/{modules,sensors,merge,compile}.py` — MODIFY: emit/consume semantic objects instead of XML strings, one per task.
- `robotbase/robotspec/{validate,explain}.py` — MODIFY: read semantic fields instead of parsing the compiled URDF.
- `robotbase/worldspec/compile.py` — MODIFY: build a `WorldModel`, render via the SDF backend.
- `tests/test_golden_output.py` — CREATE (Task 1): the byte-identical guard.
- `tests/test_semantic_*.py`, `tests/test_backend_*.py` — CREATE per task.

---

## Task 1: Golden-output guard (the safety net)

**Goal:** Freeze the current compiled URDF/SDF for every template + reference so any later refactor that changes a byte fails loudly. This must exist BEFORE touching the IR.

**Files:**
- Create: `tests/test_golden_output.py`
- Create: `tests/golden/` (committed expected outputs)

**Interfaces:**
- Produces: `golden_specs() -> list[tuple[str, RobotSpec, WorldSpec|None]]` enumerating the 4 templates' robot.yaml/world.yaml + the 4 reference solutions; a parametrized test comparing `compile_robot(spec).urdf` and `compile_world(wspec)` against committed golden files.

- [ ] **Step 1: Write the generator+test**

```python
# tests/test_golden_output.py
import glob, os, pathlib, pytest
from robotbase.robotspec.schema import RobotSpec
from robotbase.robotspec.compile import compile_robot
from robotbase.worldspec.schema import WorldSpec
from robotbase.worldspec.compile import compile_world

GOLDEN = pathlib.Path(__file__).parent / "golden"
REF = pathlib.Path(__file__).parent.parent / "robotbase" / "robotbench" / "fixtures" / "reference"
TPL = pathlib.Path(__file__).parent.parent / "robotbase" / "robotspec"  # templates resolved below

def _cases():
    cases = []
    # 4 templates
    from robotbase.generator import template_dir, list_templates
    for name in ["differential-drive", "camera-bot", "arm", "drone"]:
        d = pathlib.Path(template_dir(name))
        r, w = d / "robot.yaml", d / "world.yaml"
        if r.exists():
            cases.append((f"tpl-{name}", str(r), str(w) if w.exists() else None))
    # 4 references
    for d in sorted(glob.glob(str(REF / "*"))):
        r, w = os.path.join(d, "robot.yaml"), os.path.join(d, "world.yaml")
        if os.path.exists(r):
            cases.append((f"ref-{os.path.basename(d)}", r, w if os.path.exists(w) else None))
    return cases

def _compile(robot_yaml, world_yaml):
    spec = RobotSpec.from_yaml(robot_yaml)
    for p in spec.parts:
        if p.use == "custom" and p.urdf and not os.path.isabs(p.urdf):
            p.urdf = os.path.join(os.path.dirname(robot_yaml), os.path.basename(p.urdf))
    urdf = compile_robot(spec).urdf
    sdf = compile_world(WorldSpec.from_yaml(world_yaml))[0] if world_yaml else ""
    return urdf, sdf

@pytest.mark.parametrize("name,robot_yaml,world_yaml", _cases(), ids=lambda c: c if isinstance(c, str) else "")
def test_compiled_output_matches_golden(name, robot_yaml, world_yaml):
    urdf, sdf = _compile(robot_yaml, world_yaml)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.mkdir(exist_ok=True)
        (GOLDEN / f"{name}.urdf").write_text(urdf, encoding="utf-8")
        (GOLDEN / f"{name}.sdf").write_text(sdf, encoding="utf-8")
        pytest.skip("updated golden")
    assert urdf == (GOLDEN / f"{name}.urdf").read_text(encoding="utf-8")
    assert sdf == (GOLDEN / f"{name}.sdf").read_text(encoding="utf-8")
```

- [ ] **Step 2: Generate the golden files from current `main`**

Run: `UPDATE_GOLDEN=1 pytest tests/test_golden_output.py -q` (writes `tests/golden/*.urdf|.sdf`).

- [ ] **Step 3: Verify the guard passes against itself**

Run: `pytest tests/test_golden_output.py -q` — Expected: PASS (every case matches).

- [ ] **Step 4: Commit**

```bash
git add tests/test_golden_output.py tests/golden/
git commit -m "test(ir): golden-output guard freezes compiled URDF/SDF before the P4 refactor"
```

---

## Task 2: Semantic geometry + inertial (the leaf types)

**Goal:** Typed geometry + inertia, owning the math currently inside `ir.link_from_shape`, with no rendering.

**Files:**
- Create: `robotbase/robotspec/semantic.py`
- Test: `tests/test_semantic_geometry.py`

**Interfaces:**
- Produces: `Box(size: list[float])`, `Cylinder(radius, length)`, `Sphere(radius)` (all with `.kind`); `Inertial(mass: float, ixx, iyy, izz)`; `inertial_for(geometry, mass) -> Inertial` implementing the exact formulas from `ir.link_from_shape` (box `m*(y²+z²)/12`…, cylinder, sphere); `geometry_from_spec(shape: str, size: list[float]) -> Geometry` using `ir.SHAPE_SIZE` for validation (reuses `ShapeSizeError`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_semantic_geometry.py
import math, pytest
from robotbase.robotspec.semantic import Box, Cylinder, Sphere, inertial_for, geometry_from_spec
from robotbase.robotspec.ir import ShapeSizeError

def test_box_inertia_matches_legacy_formula():
    g = Box([0.4, 0.3, 0.2]); m = 5.0
    inr = inertial_for(g, m)
    assert inr.ixx == pytest.approx(m * (0.3**2 + 0.2**2) / 12)
    assert inr.iyy == pytest.approx(m * (0.4**2 + 0.2**2) / 12)
    assert inr.izz == pytest.approx(m * (0.4**2 + 0.3**2) / 12)

def test_cylinder_and_sphere_inertia():
    c = inertial_for(Cylinder(0.05, 0.1), 0.5)
    assert c.izz == pytest.approx(0.5 * 0.05**2 / 2)
    s = inertial_for(Sphere(0.05), 0.1)
    assert s.ixx == pytest.approx(2 * 0.1 * 0.05**2 / 5)

def test_geometry_from_spec_validates_length():
    assert isinstance(geometry_from_spec("box", [1, 2, 3]), Box)
    with pytest.raises(ShapeSizeError):
        geometry_from_spec("box", [1, 2])
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_semantic_geometry.py -q` → FAIL (no module).

- [ ] **Step 3: Implement `semantic.py` (geometry + inertial only)**

```python
# robotbase/robotspec/semantic.py
from __future__ import annotations
from dataclasses import dataclass, field
from robotbase.robotspec.ir import SHAPE_SIZE, ShapeSizeError

@dataclass(frozen=True)
class Box:      size: list[float];   kind: str = "box"
@dataclass(frozen=True)
class Cylinder: radius: float; length: float; kind: str = "cylinder"
@dataclass(frozen=True)
class Sphere:   radius: float;       kind: str = "sphere"
Geometry = Box | Cylinder | Sphere

@dataclass(frozen=True)
class Inertial:
    mass: float
    ixx: float; iyy: float; izz: float

def geometry_from_spec(shape: str, size) -> Geometry:
    if shape not in SHAPE_SIZE:
        from robotbase.robotspec.ir import UnknownShape
        raise UnknownShape(f"unknown shape {shape!r}; known: box, cylinder, sphere")
    need, fmt = SHAPE_SIZE[shape]
    size = list(size)
    if len(size) != need:
        raise ShapeSizeError(f"{shape} size must be {fmt} ({need} value(s)), got {len(size)}: {size}")
    if shape == "box":      return Box(size)
    if shape == "cylinder": return Cylinder(size[0], size[1])
    return Sphere(size[0])

def inertial_for(g: Geometry, mass: float) -> Inertial:
    if isinstance(g, Box):
        x, y, z = g.size
        return Inertial(mass, mass*(y*y+z*z)/12, mass*(x*x+z*z)/12, mass*(x*x+y*y)/12)
    if isinstance(g, Cylinder):
        r, h = g.radius, g.length
        i = mass*(3*r*r+h*h)/12
        return Inertial(mass, i, i, mass*r*r/2)
    r = g.radius; i = 2*mass*r*r/5
    return Inertial(mass, i, i, i)
```

- [ ] **Step 4: Run tests** — `pytest tests/test_semantic_geometry.py -q` → PASS.

- [ ] **Step 5: Commit** — `git add robotbase/robotspec/semantic.py tests/test_semantic_geometry.py && git commit -m "feat(ir): semantic geometry + inertia types (no rendering yet)"`

---

## Task 3: `RigidBody` + `Joint` + the URDF backend for a single body

**Goal:** Typed body/joint + the ONE function that renders a body to URDF, proven byte-identical to `ir.link_from_shape` for box/cylinder/sphere.

**Files:**
- Modify: `robotbase/robotspec/semantic.py` (add `RigidBody`, `Joint`)
- Create: `robotbase/robotspec/backends/__init__.py`, `robotbase/robotspec/backends/urdf.py`
- Test: `tests/test_backend_urdf.py`

**Interfaces:**
- Consumes: `Geometry`, `inertial_for` (Task 2).
- Produces: `RigidBody(name, geometry|None, mass, material, rgba)` (a `None` geometry = a massless frame link); `Joint(name, type, parent, child, xyz, rpy, axis, limit)`; `backends.urdf.render_body(body) -> str` and `render_joint(joint) -> str` whose output equals the current `ir.link_from_shape(...).xml` / `ir.fixed_joint(...).xml` byte-for-byte.

- [ ] **Step 1: Write the failing test (byte-parity with the legacy renderer)**

```python
# tests/test_backend_urdf.py
from robotbase.robotspec.ir import link_from_shape
from robotbase.robotspec.semantic import RigidBody
from robotbase.robotspec.backends.urdf import render_body

def test_render_body_matches_legacy_link_from_shape():
    legacy = link_from_shape("base_link", "box", [0.35, 0.30, 0.15], 5.0).xml
    body = RigidBody(name="base_link", geometry=("box", [0.35, 0.30, 0.15]), mass=5.0)
    assert render_body(body) == legacy
```

- [ ] **Step 2: Run to verify it fails** — FAIL (no `backends.urdf`).

- [ ] **Step 3: Implement `RigidBody`/`Joint` + `render_body`/`render_joint`**

Move the exact XML template string from `ir.link_from_shape` into `backends/urdf.render_body` (same `_fmt`, same attribute order, same whitespace — copy verbatim so bytes match). `RigidBody.geometry` accepts a `(shape, size)` tuple for now (semantic `Geometry` wiring lands in Task 4). Implement `render_joint` by copying `ir.fixed_joint`'s and the module joints' XML templates.

```python
# robotbase/robotspec/backends/urdf.py  (skeleton — copy the byte-exact templates from ir.py)
from robotbase.robotspec.semantic import RigidBody, Joint
from robotbase.robotspec.semantic import geometry_from_spec, inertial_for
from robotbase.robotspec.ir import _fmt  # reuse the identical number formatter

def render_body(b: RigidBody) -> str:
    if b.geometry is None:
        return f'\n  <link name="{b.name}"/>'
    shape, size = b.geometry
    g = geometry_from_spec(shape, size); inr = inertial_for(g, b.mass)
    geom = _geom_xml(g)  # <box.../> etc — copy from ir.link_from_shape
    return (f'\n  <link name="{b.name}">'
            f'\n    <inertial><mass value="{_fmt(b.mass)}"/>'
            f'<inertia ixx="{_fmt(inr.ixx)}" ixy="0" ixz="0" iyy="{_fmt(inr.iyy)}" iyz="0" izz="{_fmt(inr.izz)}"/></inertial>'
            f'\n    <collision><geometry>{geom}</geometry></collision>'
            f'\n    <visual><geometry>{geom}</geometry><material name="{b.material}"><color rgba="{b.rgba}"/></material></visual>'
            f'\n  </link>')
```

- [ ] **Step 4: Run tests** — PASS (byte-identical) + `pytest tests/test_golden_output.py -q` still PASS (nothing wired yet).

- [ ] **Step 5: Commit** — `git commit -m "feat(ir): RigidBody/Joint + URDF backend byte-identical to link_from_shape"`

---

## Task 4: Route `ir.link_from_shape` through the backend (adapter)

**Goal:** Make the legacy `link_from_shape` a thin wrapper that builds a `RigidBody` and calls `render_body`, so there is one renderer. Golden output unchanged.

**Files:** Modify `robotbase/robotspec/ir.py`; Test: extend `tests/test_backend_urdf.py`.

**Interfaces:**
- Produces: `ir.link_from_shape(name, shape, size, mass, material, rgba) -> LinkIR` now delegates to `RigidBody` + `render_body`; `LinkIR` unchanged (still `.xml`).

- [ ] **Step 1: Write the failing test** — assert `link_from_shape` output still equals the golden fixtures for a cylinder + sphere (not just box):

```python
def test_link_from_shape_cylinder_sphere_still_render_identically():
    for shape, size in (("cylinder", [0.05, 0.1]), ("sphere", [0.05])):
        # snapshot BEFORE the change was captured in golden; here assert non-empty valid xml
        xml = link_from_shape("l", shape, size, 0.5).xml
        assert f'<{ "cylinder" if shape=="cylinder" else shape}' in xml
```

- [ ] **Step 2: Run** — passes on current code (guard); the real guard is `test_golden_output`.
- [ ] **Step 3: Reimplement `link_from_shape`** to `return LinkIR(name, render_body(RigidBody(name, (shape, size), mass, material, rgba)))`, keeping its `ShapeSizeError`/`UnknownShape` behavior (now raised inside `geometry_from_spec`).
- [ ] **Step 4: Run the full suite + golden** — `pytest -k "not live" -q` → all PASS, `test_golden_output` byte-identical.
- [ ] **Step 5: Commit** — `git commit -m "refactor(ir): link_from_shape delegates to the URDF backend (one renderer)"`

---

## Task 5: Semantic `Sensor` + gz sensor rendering

**Goal:** A typed `Sensor` (kind, name, mount link, pose, params, topic, ros/gz bridge, gz world-system) with the URDF-`<gazebo>`/bridge rendering moved to the backend. Proven byte-identical to each `sensors.py` emitter.

**Files:** Modify `semantic.py` (+`Sensor`, `GazeboSystem`), `backends/urdf.py` (`render_sensor`); Modify `sensors.py` to build `Sensor` objects; Test: `tests/test_semantic_sensors.py`.

**Interfaces:**
- Produces: `Sensor(kind, name, mount_link, xyz, gz_type, topic, bridge, world_system, extra_xml)`; `SENSORS[type](params, on_link, ctx) -> Fragment` unchanged externally, but internally builds a `Sensor` and renders via the backend; `render_sensor(sensor) -> (link_xml, joint_xml, gazebo_xml)`.

- [ ] **Step 1: Write failing test** — for each of lidar/imu/camera/depth/contact, assert the compiled `<gazebo ...><sensor ...>` block equals the current output (capture current strings as expected constants).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — move each sensor's gz XML template into `render_sensor` keyed by `gz_type`; `sensors._lidar/_imu/...` construct a `Sensor` + call it. Keep the contact scoped-topic + remap logic (uses `ctx.robot_name`/`ctx.world`) intact.
- [ ] **Step 4: Run suite + golden → PASS.**
- [ ] **Step 5: Commit** — `git commit -m "refactor(ir): sensors emit semantic Sensor objects, backend renders gz XML"`

---

## Task 6: `RobotModel` + full URDF assembly in the backend

**Goal:** A `RobotModel(name, bodies, joints, sensors, gazebo_systems, bridges, ready_topics, control, fixed_base)` and `render_urdf(model)` that assembles the whole `<robot>...</robot>` — replacing `merge.merge_and_render`'s string concatenation.

**Files:** Modify `semantic.py`, `backends/urdf.py` (`render_urdf`); Test: `tests/test_backend_urdf.py`.

**Interfaces:**
- Consumes: `RigidBody`/`Joint`/`Sensor`.
- Produces: `render_urdf(model: RobotModel) -> str` byte-identical to `merge_and_render(...)[0]`; the link-tree validation (`merge._validate`) moves to `semantic.validate_tree(model)` operating on typed bodies/joints (same errors).

- [ ] **Step 1: Failing test** — build a `RobotModel` equivalent to a compiled diff-drive and assert `render_urdf(model)` equals the golden `tpl-differential-drive.urdf` body.
- [ ] **Step 2–4:** implement `render_urdf` (header + bodies + joints + gazebo, exact order/whitespace) and `validate_tree`; run golden → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(ir): RobotModel + render_urdf assembles the whole robot"`

---

## Task 7: Migrate `differential_drive` to emit a semantic fragment

**Goal:** `modules.differential_drive` returns typed bodies/joints/sensors/systems instead of pre-rendered XML. `Fragment` gains typed lists; `LinkIR`/`JointIR` become adapters.

**Files:** Modify `modules.py`, `ir.py` (`Fragment` holds `RigidBody`/`Joint`), `compile.py`/`merge.py` (consume typed). Test: golden + `tests/test_modules_semantic.py`.

- [ ] Steps: write a test asserting `differential_drive({...})` now exposes typed `bodies`/`joints`; reimplement it to append `RigidBody`/`Joint` (wheels/caster keep their exact inertias + placement math via `body_xyz`); the compiler renders via `render_urdf`. Run golden → byte-identical. Commit `refactor(ir): differential-drive emits semantic bodies/joints`.

---

## Task 8: Migrate `arm` + `quadrotor` archetypes

**Goal:** Same migration for the other two archetypes; their hardcoded link/joint XML becomes `RigidBody`/`Joint` with explicit inertials (copy the exact numbers so golden matches). Actuator plugins (diff-drive, joint-position-controller, velocity-control) become `GazeboSystem` objects the backend renders.

**Files:** Modify `modules.py`; Test: golden (`tpl-arm`, `tpl-drone`).

- [ ] Steps per archetype: typed test → reimplement → golden PASS → commit `refactor(ir): arm/quadrotor emit semantic fragments`.

---

## Task 9: Migrate `compile.py` + `_raw_part` + custom import onto the semantic path

**Goal:** `compile_robot` builds a `RobotModel` from fragments and calls `render_urdf`; the raw-part escape hatch builds `RigidBody`/`Joint` (keeping `InvalidRawPart` errors); the custom-import branch still splices author-added sensors, now rendered via `render_sensor`.

**Files:** Modify `compile.py`, delete `merge.merge_and_render`'s string path. Test: golden + existing `test_compile`/`test_import`/`test_renderer_robustness`.

- [ ] Steps: reimplement `compile_robot` to assemble a `RobotModel`; keep all current error classes + messages; run the full suite + golden → PASS. Commit `refactor(ir): compile_robot assembles a RobotModel rendered by the backend`.

---

## Task 10: Point `validate` + `explain` at the semantic IR (no XML parsing)

**Goal:** `validate_robot`/`explain_robot` read `RobotModel` fields (masses, inertials, joints, per-fragment provenance) directly instead of `ET.fromstring(urdf)`. Same outputs, cleaner + faster, and the `explain` drift-guard becomes structural.

**Files:** Modify `validate.py`, `explain.py`; Test: existing `test_validate`/`test_explain` unchanged must pass.

- [ ] Steps: add `validate_model(model) -> list[Finding]` (mass/inertia/joint-limit over typed fields); keep `validate_urdf` as a thin wrapper for external URDFs; `explain_robot` reports directly from the `RobotModel`'s fragment structure. Run suite → PASS. Commit `refactor: validate/explain read the semantic IR, not parsed XML`.

---

## Task 11: Delete the string IR

**Goal:** Remove `LinkIR`/`JointIR`/`Fragment`'s XML fields and any dead string-concatenation code; `semantic.py` + `backends/` are the only path.

**Files:** Modify `ir.py` (shrink to `SHAPE_SIZE`, `body_xyz`, exceptions, re-exports), `merge.py` (delete string renderer, keep `fixed_joint` as a `Joint` factory). Test: whole suite + golden.

- [ ] Steps: delete dead code; fix imports; run `pytest -k "not live"` + golden → PASS; grep for `.xml` string assembly to confirm none remain. Commit `refactor(ir): remove the URDF-string IR — backends are the only renderer`.

---

## Task 12: World semantic IR + SDF backend

**Goal:** Mirror the robot refactor for the world: `WorldModel` (models/obstacles/walls/lights/physics/systems) + `worldspec/backends/sdf.render_sdf`, byte-identical to `worldspec.compile_world`.

**Files:** Create `worldspec/semantic.py`, `worldspec/backends/sdf.py`; Modify `worldspec/compile.py`. Test: golden (`*.sdf`).

- [ ] Steps: `WorldModel` types → `render_sdf` byte-identical (Task 1 golden guards it) → `compile_world` builds a `WorldModel` and renders → suite + golden PASS. Commit `refactor(world): semantic WorldModel + SDF backend`.

---

## Task 13: Prove the seam — MJCF backend skeleton (the payoff)

**Goal:** A `backends/mjcf.render_mjcf(model)` covering the common subset (bodies + joints + a diff-drive body) — NOT full parity, just proof that a second backend is an *additive file* over the same `RobotModel`, killing the "IR coupled to Gazebo" signal.

**Files:** Create `robotbase/robotspec/backends/mjcf.py`; Test: `tests/test_backend_mjcf.py`.

**Interfaces:**
- Produces: `render_mjcf(model: RobotModel) -> str` emitting a `<mujoco><worldbody>...</worldbody></mujoco>` with a `<body>` per `RigidBody` and a `<joint>` per `Joint` (fixed → no joint; continuous/revolute → hinge). Sensors/plugins out of scope (documented).

- [ ] **Step 1: Failing test**

```python
# tests/test_backend_mjcf.py
from robotbase.robotspec.schema import RobotSpec
from robotbase.robotspec.compile import compile_model   # returns RobotModel (added in Task 6)
from robotbase.robotspec.backends.mjcf import render_mjcf

def test_mjcf_has_a_body_per_rigid_body():
    model = compile_model(RobotSpec.model_validate(
        {"name": "robot", "base": "differential-drive", "sensors": [{"type": "lidar"}]}))
    mj = render_mjcf(model)
    assert "<mujoco" in mj and mj.count("<body") >= 3   # base + wheels
```

- [ ] **Step 2–4:** implement the minimal MJCF renderer over `RobotModel`; run → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(ir): MJCF backend skeleton — proves the IR is backend-neutral"`

---

## Task 14: Docs + strategy update

**Goal:** Record that the moat gap is closed. Update `docs/STRATEGY.md` §2 (the "IR is a URDF buffer" kill-signal → RESOLVED), `docs/design/declarative-compiler.md` (the new semantic-IR + backends architecture), and README architecture note.

- [ ] Steps: edit the three docs; no code; commit `docs: semantic IR shipped — the "IR coupled to Gazebo" kill-signal is closed`.

---

## Self-Review

- **Spec coverage:** semantic types (T2–T3, T5, T6, T12), URDF backend (T3–T6), SDF backend (T12), migrate emitters (T7–T9, T12), validation/explain on typed IR (T10), delete string IR (T11), backend-neutrality proof (T13), the safety net (T1) and docs (T14). All of P4's "typed Robot/RigidBody/Joint/Sensor + URDF/SDF as backends + kills the Gazebo-coupling signal" maps to tasks.
- **The safety net is non-negotiable:** Task 1's golden guard + the 217 existing tests mean every refactor task is byte-verified; if a task can't stay byte-identical, that's a real behavior change to escalate, not to paper over.
- **Type consistency:** `RobotModel`/`RigidBody`/`Joint`/`Sensor`/`Geometry`/`Inertial` names are used identically T2→T13; `render_urdf`/`render_sdf`/`render_mjcf`/`render_body`/`render_joint`/`render_sensor` and `compile_model` are the stable backend interface.
- **Sequencing:** leaf types → single-body backend → adapter → sensors → whole-robot backend → migrate emitters → repoint validate/explain → delete string IR → world → MJCF → docs. Each task is independently reviewable and leaves the suite green.
- **Risk gate:** this is the biggest refactor; per `docs/STRATEGY.md` it should run only after the RobotBench thesis validates. Treat Task 1 as mandatory before any IR change.
