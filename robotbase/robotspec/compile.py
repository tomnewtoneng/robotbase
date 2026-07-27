"""Compile a RobotSpec into the concrete ROS/Gazebo artifacts (see docs/design/declarative-compiler.md).

A robot is assembled from a `parts` list — each part is a module (archetype) or a raw
links/joints part — plus sensors that mount to any link. `base:` normalises to a one-part
assembly for backward compatibility. Fragments are merged, validated, and rendered once.
"""
from __future__ import annotations

from dataclasses import dataclass

from robotbase.robotspec.ir import Fragment, JointIR, LinkIR, link_from_shape
from robotbase.robotspec.merge import fixed_joint, merge_and_render
from robotbase.robotspec.modules import MODULES, UnknownArchetype
from robotbase.robotspec.schema import Part, RobotSpec
from robotbase.robotspec.sensors import SENSORS, Ctx, UnknownSensor

__all__ = ["CompiledRobot", "compile_robot", "UnknownArchetype", "UnknownSensor"]


@dataclass
class CompiledRobot:
    name: str
    urdf: str
    bridges: list
    world_systems: list[str]
    manifest: dict
    spawn_z: float = 0.1


def _raw_part(part: Part) -> Fragment:
    f = Fragment()
    for l in part.links:
        if "xml" in l:
            f.links.append(LinkIR(l["name"], l["xml"]))
        else:
            f.links.append(link_from_shape(l["name"], l.get("shape", "box"),
                                           l["size"], l.get("mass", 1.0)))
    for j in part.joints:
        xyz = " ".join(str(v) for v in j.get("xyz", [0, 0, 0]))
        rpy = " ".join(str(v) for v in j.get("rpy", [0, 0, 0]))
        if j.get("type", "fixed") == "fixed":
            f.joints.append(fixed_joint(j["name"], j["parent"], j["child"], xyz=xyz, rpy=rpy))
        else:
            axis = j.get("axis", "0 0 1")
            f.joints.append(JointIR(j["name"],
                f'\n  <joint name="{j["name"]}" type="{j["type"]}">'
                f'<parent link="{j["parent"]}"/><child link="{j["child"]}"/>'
                f'<origin xyz="{xyz}" rpy="{rpy}"/><axis xyz="{axis}"/></joint>',
                parent=j["parent"], child=j["child"]))
    return f


def compile_robot(spec: RobotSpec, world_name: str = "warehouse") -> CompiledRobot:
    parts = list(spec.parts)
    if spec.base:
        # `base:` is sugar for a first part; any extra `parts:` compose onto it (a mast, a
        # sensor mount, a second module). Prepending — not replacing — means `base:` + `parts:`
        # is the natural authoring form, instead of a silent footgun where one drops the other.
        parts = [Part(use=spec.base, body=spec.body, drive=spec.drive)] + parts

    custom = next((p for p in parts if p.use == "custom"), None)
    if custom is not None:
        with open(custom.urdf) as fh:
            urdf = fh.read()
        bridges, world_systems, ready_topics, sensors_manifest = [], [], [], {}
        ctx = Ctx(world=world_name, robot_name=spec.name, body_size=list(spec.body.size))
        sensor_xml: list[str] = []
        for s in spec.sensors:
            if s.type not in SENSORS:
                raise UnknownSensor(f"unknown sensor {s.type!r}; known: {sorted(SENSORS)}")
            frag = SENSORS[s.type](s.model_dump(), s.on or "base_link", ctx)
            bridges += frag.bridges
            # Inject the sensor's link/joint/gazebo XML into the imported URDF — otherwise the
            # bridge exists but no gz <sensor> entity publishes (a silent /scan). The imported
            # URDF is authoritative for the *body*; added sensors extend it.
            sensor_xml += [l.xml for l in frag.links] + [j.xml for j in frag.joints] + frag.gazebo
            for sys_ in frag.world_systems:
                if sys_ not in world_systems:
                    world_systems.append(sys_)
            for t in frag.ready_topics:
                if t not in ready_topics:
                    ready_topics.append(t)
            sensors_manifest.update(frag.manifest_sensors)
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

    fragments: list[Fragment] = []
    primary_base = None
    body_size = list(spec.body.size)
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
                body_size = (part.body or spec.body).size
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

    urdf, bridges, world_systems, m = merge_and_render(spec.name, root, fragments)
    manifest = {
        "robot": {"template": spec.base, "name": spec.name},
        "sensors": m["sensors"],
        "control": m["control"],
        "ready_topics": m["ready_topics"],
        "fixed_base": m["fixed_base"],
    }
    return CompiledRobot(name=spec.name, urdf=urdf, bridges=bridges,
                         world_systems=world_systems, manifest=manifest, spawn_z=0.1)
