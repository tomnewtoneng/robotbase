"""Compile a RobotSpec into the concrete ROS/Gazebo artifacts (see docs/design/declarative-compiler.md).

A robot is assembled from a `parts` list — each part is a module (archetype) or a raw
links/joints part — plus sensors that mount to any link. `base:` normalises to a one-part
assembly for backward compatibility. Fragments are merged, validated, and rendered once.
"""
from __future__ import annotations

from dataclasses import dataclass

from robotbase.robotspec.ir import Fragment, body_xyz
from robotbase.robotspec.semantic import Joint, RigidBody, RobotModel
from robotbase.robotspec.backends.urdf import render_body, render_joint, render_urdf
from robotbase.robotspec.merge import build_model, fixed_joint
from robotbase.robotspec.modules import MODULES, UnknownArchetype
from robotbase.robotspec.schema import Part, RobotSpec
from robotbase.robotspec.sensors import SENSORS, Ctx, UnknownSensor, infer_sensors_from_urdf

__all__ = ["CompiledRobot", "compile_robot", "compile_model",
           "UnknownArchetype", "UnknownSensor", "InvalidRawPart"]


class InvalidRawPart(ValueError):
    """A raw links/joints part (the escape hatch) is missing a required key."""


class ControlError(ValueError):
    """A `control:` override targets a joint/controller the robot does not have."""


def _apply_control(model, control) -> None:
    """Apply a spec's `control:` overrides onto the assembled RobotModel's typed controllers (in
    place). Raises ControlError if an override names a joint/controller the robot lacks."""
    if control is None:
        return
    for jname, gains in control.joints.items():
        matched = [c for c in model.controllers if c.joint == jname]
        if not matched:
            have = sorted(c.joint for c in model.controllers if c.joint)
            raise ControlError(
                f"control.joints: no controller for joint {jname!r}; joints with controllers: {have}")
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


@dataclass
class CompiledRobot:
    name: str
    urdf: str
    bridges: list
    world_systems: list[str]
    manifest: dict
    spawn_z: float = 0.1


def _need(d: dict, key: str, what: str):
    if key not in d:
        raise InvalidRawPart(f"raw {what} is missing required key {key!r}: {d}")
    return d[key]


def _raw_part(part: Part) -> Fragment:
    f = Fragment()
    for l in part.links:
        name = _need(l, "name", "link")
        if "xml" in l:
            f.links.append(RigidBody(name, raw_xml=l["xml"]))
        else:
            f.links.append(RigidBody(name, (l.get("shape", "box"), _need(l, "size", f"link {name!r}")),
                                     mass=l.get("mass", 1.0)))
    for j in part.joints:
        name = _need(j, "name", "joint")
        parent, child = _need(j, "parent", f"joint {name!r}"), _need(j, "child", f"joint {name!r}")
        xyz = " ".join(str(v) for v in j.get("xyz", [0, 0, 0]))
        rpy = " ".join(str(v) for v in j.get("rpy", [0, 0, 0]))
        if j.get("type", "fixed") == "fixed":
            f.joints.append(fixed_joint(name, parent, child, xyz=xyz, rpy=rpy))
        else:
            f.joints.append(Joint(name, j["type"], parent, child, xyz=xyz, rpy=rpy,
                                  axis=j.get("axis", "0 0 1")))
    return f


def _parts(spec: RobotSpec) -> list[Part]:
    # `base:` is sugar for a first part; any extra `parts:` compose onto it (a mast, a sensor mount,
    # a second module). Prepending — not replacing — means `base:` + `parts:` is the natural
    # authoring form, instead of a silent footgun where one drops the other.
    parts = list(spec.parts)
    if spec.base:
        parts = [Part(use=spec.base, body=spec.body, drive=spec.drive)] + parts
    return parts


def compile_model(spec: RobotSpec, world_name: str = "warehouse") -> RobotModel:
    """Assemble a spec into a typed RobotModel (the non-custom path) — the semantic surface the
    URDF/MJCF backends render and validate/explain read. Custom-import robots have no semantic model
    (their body is a verbatim external URDF); `compile_robot` handles those directly."""
    parts = _parts(spec)
    if any(p.use == "custom" for p in parts):
        raise InvalidRawPart(
            "custom-import robots have no semantic RobotModel; render/validate the imported URDF directly")

    fragments: list[Fragment] = []
    primary_base = None
    body_size = body_xyz(spec.body.size, spec.body.shape)
    for part in parts:
        if part.use is not None:
            if part.use not in MODULES:
                raise UnknownArchetype(
                    f"unknown module {part.use!r}; known: {sorted(MODULES)} (or use raw links/joints)")
            p = {"body": (part.body or spec.body).model_dump(),
                 "drive": (part.drive or spec.drive).model_dump()}
            frag = MODULES[part.use](p, part.mount)
            if primary_base is None and frag.exposes:
                primary_base = frag.exposes[0]
                b = part.body or spec.body
                body_size = body_xyz(b.size, b.shape)
        else:
            frag = _raw_part(part)
        fragments.append(frag)

    if not fragments:
        raise ValueError("robot has no parts: set `base:` or `parts:` in the spec")
    root = "base_footprint"
    all_links = [l for f in fragments for l in f.links]
    if not any(l.name == root for l in all_links):
        if not all_links:
            raise ValueError("robot has no links: every part is empty")
        root = all_links[0].name

    base_link = primary_base or root
    ctx = Ctx(world=world_name, robot_name=spec.name, body_size=body_size, base_link=base_link)
    for s in spec.sensors:
        if s.type not in SENSORS:
            raise UnknownSensor(f"unknown sensor {s.type!r}; known: {sorted(SENSORS)}")
        fragments.append(SENSORS[s.type](s.model_dump(), s.on or base_link, ctx))

    model = build_model(spec.name, root, fragments)
    _apply_control(model, spec.control)
    return model


def compile_robot(spec: RobotSpec, world_name: str = "warehouse") -> CompiledRobot:
    parts = _parts(spec)

    custom = next((p for p in parts if p.use == "custom"), None)
    if custom is not None:
        if not custom.urdf:
            raise InvalidRawPart("custom part requires `urdf: <path>` (the URDF file to import)")
        try:
            with open(custom.urdf) as fh:
                urdf = fh.read()
        except FileNotFoundError as e:
            raise InvalidRawPart(f"custom part urdf not found: {custom.urdf}") from e
        bridges, world_systems, ready_topics, sensors_manifest = [], [], [], {}
        ctx = Ctx(world=world_name, robot_name=spec.name,
                  body_size=body_xyz(spec.body.size, spec.body.shape))

        def _wire(frag) -> None:
            for sys_ in frag.world_systems:
                if sys_ not in world_systems:
                    world_systems.append(sys_)
            for t in frag.ready_topics:
                if t not in ready_topics:
                    ready_topics.append(t)
            sensors_manifest.update(frag.manifest_sensors)

        # (a) Sensors already present in the imported URDF: wire their bridge + world system so
        # they actually publish, but do NOT re-inject XML (it's already there).
        for t in infer_sensors_from_urdf(urdf):
            frag = SENSORS[t]({}, "base_link", ctx)
            bridges += frag.bridges
            _wire(frag)

        # (b) Sensors the author ADDS via `sensors:` (not in the URDF): inject their link/joint/
        # gazebo XML into the imported URDF — otherwise the bridge exists but no gz <sensor>
        # entity publishes (a silent /scan).
        sensor_xml: list[str] = []
        for s in spec.sensors:
            if s.type not in SENSORS:
                raise UnknownSensor(f"unknown sensor {s.type!r}; known: {sorted(SENSORS)}")
            frag = SENSORS[s.type](s.model_dump(), s.on or "base_link", ctx)
            bridges += frag.bridges
            sensor_xml += ([render_body(l) for l in frag.links]
                           + [render_joint(j) for j in frag.joints] + frag.gazebo)
            _wire(frag)
        if sensor_xml:
            idx = urdf.rfind("</robot>")
            if idx == -1:
                raise UnknownArchetype("imported URDF has no </robot> element to extend with sensors")
            urdf = urdf[:idx] + "".join(sensor_xml) + "\n" + urdf[idx:]
        manifest = {"robot": {"template": "custom", "name": spec.name},
                    "sensors": sensors_manifest, "control": {"velocity_topic": "/cmd_vel"},
                    "ready_topics": ready_topics, "fixed_base": False}
        return CompiledRobot(name=spec.name, urdf=urdf, bridges=bridges,
                             world_systems=world_systems, manifest=manifest, spawn_z=0.1)

    model = compile_model(spec, world_name)
    urdf = render_urdf(model)
    manifest = {
        "robot": {"template": spec.base, "name": spec.name},
        "sensors": model.manifest_sensors,
        "control": model.control,
        "ready_topics": model.ready_topics,
        "fixed_base": model.fixed_base,
    }
    return CompiledRobot(name=spec.name, urdf=urdf, bridges=model.bridges,
                         world_systems=model.world_systems, manifest=manifest, spawn_z=0.1)
