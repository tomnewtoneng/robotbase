"""`robotbase describe` — surface a project's robot / world / scenario facts as structured
data, so an agent can query ground truth instead of reading files or trusting numbers
restated in prose. Pure host-side parsing of the manifest, the robot URDF (xacro properties
+ literal joints), the world SDF (models + arena bounds), and the scenarios — no container.
"""
from __future__ import annotations

import glob
import math
import os
import xml.etree.ElementTree as ET

import yaml

from robotbase.policy_interface import policy_interface


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]  # strip any XML namespace


def _floats(text: str | None) -> list[float] | None:
    try:
        return [float(x) for x in (text or "").split()]
    except ValueError:
        return None


def describe(project_dir: str) -> dict:
    with open(os.path.join(project_dir, "robotbase.yaml")) as f:
        m = yaml.safe_load(f) or {}
    return {
        "project": (m.get("project") or {}).get("name"),
        "robot": _robot(project_dir, m),
        "sensors": m.get("sensors", {}),
        "command_joints": m.get("joints", {}),  # arm: joint -> command topic
        "policy_interface": policy_interface(m),  # obs/action contract for run_policy
        "ready_topics": (m.get("runtime") or {}).get("ready_topics", ["/scan", "/odom"]),
        "world": _world(project_dir, m),
        "scenarios": _scenarios(project_dir, m),
        "validation": _validation(project_dir),
    }


def _validation(project_dir: str) -> dict:
    """Static physical sanity of the compiled robot (mass/inertia/joint-limit), so agents see
    problems here as structured facts rather than only as a misbehaving sim."""
    from robotbase.robotspec.validate import summarize, validate_urdf
    urdfs = glob.glob(os.path.join(project_dir, "src", "*", "urdf", "*.urdf.xacro"))
    if not urdfs:
        return {"ok": True, "errors": 0, "warnings": 0, "findings": []}
    try:
        return summarize(validate_urdf(open(urdfs[0], encoding="utf-8").read()))
    except OSError:
        return {"ok": True, "errors": 0, "warnings": 0, "findings": []}


# Control plugin filename -> the `control:` kind an agent tunes (see the authoring reference).
_CONTROL_PLUGINS = {
    "gz-sim-diff-drive-system": "diff-drive",
    "gz-sim-joint-position-controller-system": "joint-position",
    "gz-sim-velocity-control-system": "velocity",
}
_CONTROL_PARAMS = ("joint_name", "topic", "p_gain", "i_gain", "d_gain",
                   "wheel_separation", "wheel_radius", "odom_publish_frequency")


def _controllers(root) -> list[dict]:
    """The compiled control plugins (kind + key params/gains) from the URDF <gazebo><plugin> blocks —
    ground-truth control config, so an agent sees the actual gains it can tune via `control:`."""
    out: list[dict] = []
    for plugin in root.iter():
        if _local(plugin.tag) != "plugin":
            continue
        kind = _CONTROL_PLUGINS.get(plugin.get("filename", ""))
        if not kind:
            continue
        params = {_local(c.tag): (c.text or "").strip()
                  for c in plugin if _local(c.tag) in _CONTROL_PARAMS}
        entry: dict = {"kind": kind, "params": params}
        if "joint_name" in params:
            entry["joint"] = params["joint_name"]
        out.append(entry)
    return out


def _link_geometry(link_el) -> dict | None:
    """The first geometry (shape + dimensions) on a link, from its collision/visual — the robot's
    real dimensions as ground truth. The compiled URDF is resolved geometry, not xacro properties, so
    this reads the actual `<box>/<cylinder>/<sphere>` a created project runs, not authoring macros."""
    for g in link_el.iter():
        t = _local(g.tag)
        if t == "box" and g.get("size"):
            return {"shape": "box", "size": _floats(g.get("size"))}
        if t == "cylinder" and g.get("radius"):
            return {"shape": "cylinder", "radius": float(g.get("radius")),
                    "length": float(g.get("length") or 0)}
        if t == "sphere" and g.get("radius"):
            return {"shape": "sphere", "radius": float(g.get("radius"))}
    return None


def _visual_origin(link_el) -> tuple[list[float], list[float]]:
    """The link's <visual><origin> (xyz, rpy), defaulting to zeros — offsets the mesh within the
    link frame, needed to place articulated links correctly."""
    for v in link_el:
        if _local(v.tag) == "visual":
            for c in v:
                if _local(c.tag) == "origin":
                    return (_floats(c.get("xyz")) or [0.0, 0.0, 0.0],
                            _floats(c.get("rpy")) or [0.0, 0.0, 0.0])
    return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]


def _robot(project_dir: str, m: dict) -> dict:
    info = {
        "template": (m.get("robot") or {}).get("template"),
        "name": (m.get("robot") or {}).get("name"),
        "fixed_base": (m.get("runtime") or {}).get("fixed_base", False),
    }
    urdfs = glob.glob(os.path.join(project_dir, "src", "*", "urdf", "*.urdf.xacro"))
    if not urdfs:
        return info
    try:
        root = ET.parse(urdfs[0]).getroot()
    except (ET.ParseError, OSError):
        return info

    # Per-link geometry (the robot's real dimensions) + the joints, from the compiled URDF.
    links: list[dict] = []
    joints: list[dict] = []
    for el in root.iter():
        tag = _local(el.tag)
        if tag == "link" and el.get("name"):
            g = _link_geometry(el)
            if g:
                vo_xyz, vo_rpy = _visual_origin(el)
                links.append({"name": el.get("name"), **g,
                              "visual_origin_xyz": vo_xyz, "visual_origin_rpy": vo_rpy})
        elif tag == "joint" and el.get("name") and "${" not in el.get("name"):
            # literal (non-macro) joints: the kinematic tree (parent/child/origin/axis/limits)
            j = {"name": el.get("name"), "type": el.get("type")}
            for child in el:
                ct = _local(child.tag)
                if ct == "parent" and child.get("link"):
                    j["parent"] = child.get("link")
                elif ct == "child" and child.get("link"):
                    j["child"] = child.get("link")
                elif ct == "origin":
                    j["origin_xyz"] = _floats(child.get("xyz")) or [0.0, 0.0, 0.0]
                    j["origin_rpy"] = _floats(child.get("rpy")) or [0.0, 0.0, 0.0]
                elif ct == "axis" and child.get("xyz"):
                    j["axis"] = _floats(child.get("xyz"))
                elif ct == "limit" and child.get("lower") and child.get("upper"):
                    j["limits"] = [float(child.get("lower")), float(child.get("upper"))]
            j.setdefault("origin_xyz", [0.0, 0.0, 0.0])
            j.setdefault("origin_rpy", [0.0, 0.0, 0.0])
            joints.append(j)
    if links:
        info["links"] = links
    if joints:
        info["joints"] = joints
    controllers = _controllers(root)
    if controllers:
        info["controllers"] = controllers
    return info


def _world(project_dir: str, m: dict) -> dict:
    rel = (m.get("simulation") or {}).get("world")
    if not rel:
        return {}
    try:
        root = ET.parse(os.path.join(project_dir, rel)).getroot()
    except (ET.ParseError, OSError):
        return {}

    models: list[dict] = []
    xs: list[float] = []
    ys: list[float] = []
    for model in root.iter():
        if _local(model.tag) != "model":
            continue
        pose = _floats(model.findtext("pose")) or [0.0, 0.0, 0.0]
        static = (model.findtext("static") or "").strip() == "true"
        # Only box geometry contributes a size / to the arena bounds — this excludes the
        # ground plane (whose huge size would otherwise swamp the wall extent).
        size = None
        for box_el in model.iter():
            if _local(box_el.tag) == "box":
                for child in box_el.iter():
                    if _local(child.tag) == "size":
                        size = _floats(child.text)
                        break
                break
        entry = {"name": model.get("name"), "static": static, "pose": [round(p, 3) for p in pose[:3]]}
        if size:
            entry["box_size"] = size
            if static:  # arena extent from static box models (walls) — yaw-aware AABB, since the
                # compiler emits rotated wall boxes (a vertical wall is size[0]=length + yaw=90°).
                yaw = pose[5] if len(pose) > 5 else 0.0
                hx, hy = size[0] / 2, size[1] / 2
                ax = abs(hx * math.cos(yaw)) + abs(hy * math.sin(yaw))
                ay = abs(hx * math.sin(yaw)) + abs(hy * math.cos(yaw))
                xs += [pose[0] - ax, pose[0] + ax]
                ys += [pose[1] - ay, pose[1] + ay]
        models.append(entry)

    world: dict = {"models": models}
    if xs:
        world["bounds"] = {"x": [round(min(xs), 2), round(max(xs), 2)],
                           "y": [round(min(ys), 2), round(max(ys), 2)]}
    return world


def _scenarios(project_dir: str, m: dict) -> list[dict]:
    directory = (m.get("scenarios") or {}).get("directory", "simulation/scenarios")
    out = []
    for path in sorted(glob.glob(os.path.join(project_dir, directory, "*.yaml"))):
        try:
            with open(path) as f:
                s = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            continue
        out.append({
            "name": s.get("name") or os.path.splitext(os.path.basename(path))[0],
            "description": " ".join((s.get("description") or "").split()),
            "assertions": [a.get("type") for a in s.get("assertions", [])],
        })
    return out
