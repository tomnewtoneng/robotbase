"""`robotbase describe` — surface a project's robot / world / scenario facts as structured
data, so an agent can query ground truth instead of reading files or trusting numbers
restated in prose. Pure host-side parsing of the manifest, the robot URDF (xacro properties
+ literal joints), the world SDF (models + arena bounds), and the scenarios — no container.
"""
from __future__ import annotations

import glob
import os
import xml.etree.ElementTree as ET

import yaml


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
        "control": m.get("control", {}),
        "command_joints": m.get("joints", {}),  # arm: joint -> command topic
        "ready_topics": (m.get("runtime") or {}).get("ready_topics", ["/scan", "/odom"]),
        "world": _world(project_dir, m),
        "scenarios": _scenarios(project_dir, m),
    }


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

    # xacro properties = the robot's parameters/dimensions (literal numeric ones only).
    dims: dict[str, float] = {}
    joints: list[dict] = []
    for el in root.iter():
        tag = _local(el.tag)
        if tag == "property" and el.get("name") and el.get("value") is not None:
            try:
                dims[el.get("name")] = float(el.get("value"))
            except ValueError:
                pass
        elif tag == "joint" and el.get("name") and "${" not in el.get("name"):
            # literal (non-macro) joints, with axis / limits where present
            j = {"name": el.get("name"), "type": el.get("type")}
            for child in el:
                ct = _local(child.tag)
                if ct == "axis" and child.get("xyz"):
                    j["axis"] = _floats(child.get("xyz"))
                elif ct == "limit" and child.get("lower") and child.get("upper"):
                    j["limits"] = [float(child.get("lower")), float(child.get("upper"))]
            joints.append(j)
    if dims:
        info["dimensions"] = dims
    if joints:
        info["joints"] = joints
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
            if static:  # track arena extent from static box models (walls)
                xs += [pose[0] - size[0] / 2, pose[0] + size[0] / 2]
                ys += [pose[1] - size[1] / 2, pose[1] + size[1] / 2]
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
