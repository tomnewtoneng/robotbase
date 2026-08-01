"""Merge Fragments into one RobotModel; the URDF backend renders it (see declarative-compiler.md).

The link-tree validation now lives in ``semantic.validate_tree`` (called by ``render_urdf``); this
module just merges the fragments' typed parts into a single ``RobotModel``.
"""
from __future__ import annotations

from robotbase.robotspec.ir import Fragment
from robotbase.robotspec.semantic import InvalidAssembly, Joint, RobotModel

__all__ = ["InvalidAssembly", "fixed_joint", "build_model"]


def fixed_joint(name, parent, child, xyz="0 0 0", rpy="0 0 0") -> Joint:
    """A fixed Joint factory (the raw-part escape hatch uses it). ``rpy`` is always set, so the origin
    renders both attributes — the historical fixed-joint form."""
    return Joint(name, "fixed", parent, child, xyz=xyz, rpy=rpy)


def build_model(name: str, root: str, fragments: list[Fragment]) -> RobotModel:
    """Merge fragments into one RobotModel: concatenate bodies/joints/gazebo/bridges, dedup
    world-systems and ready-topics, and take the last-set control/fixed_base (the module owning
    locomotion wins). Tree validation is deferred to render_urdf."""
    model = RobotModel(name=name, root=root)
    for f in fragments:
        model.bodies += f.links
        model.joints += f.joints
        model.controllers += f.controllers
        model.gazebo += f.gazebo
        model.bridges += f.bridges
        for s in f.world_systems:
            if s not in model.world_systems:
                model.world_systems.append(s)
        for t in f.ready_topics:
            if t not in model.ready_topics:
                model.ready_topics.append(t)
        if f.control is not None:
            model.control = f.control
        if f.fixed_base is not None:
            model.fixed_base = f.fixed_base
        model.manifest_sensors.update(f.manifest_sensors)
    return model
