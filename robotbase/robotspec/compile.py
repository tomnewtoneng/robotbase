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
    if not parts and spec.base:
        parts = [Part(use=spec.base, body=spec.body, drive=spec.drive)]

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

    root = "base_footprint"
    if not any(l.name == root for f in fragments for l in f.links):
        root = fragments[0].links[0].name

    base_link = primary_base or root
    ctx = Ctx(world=world_name, robot_name=spec.name, body_size=body_size)
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
