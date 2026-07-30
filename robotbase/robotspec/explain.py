"""Explainability — attribute every compiled artifact back to the spec declaration that produced it.

The vision makes traceability mandatory: an agent (or human) should be able to see WHY the compiled
robot looks the way it does, not just that it compiled. `explain_robot` reports, per source
declaration (`base:`, each `parts[i]`, each `sensors[i]`), the links, joints, ROS topics, and gz
world-systems it contributed — so "what did `sensors[0]` add?" is answerable without reading URDF.

It mirrors `compile_robot`'s assembly; a consistency test asserts the explained links match the
compiled URDF exactly, so the two cannot silently drift.
"""
from __future__ import annotations

from robotbase.robotspec.ir import Fragment, body_xyz
from robotbase.robotspec.modules import MODULES
from robotbase.robotspec.schema import Part, RobotSpec
from robotbase.robotspec.sensors import SENSORS, Ctx, infer_sensors_from_urdf


def _prov(model, field: str) -> str:
    return "authored" if field in model.model_fields_set else "default"


def provenance(spec: RobotSpec) -> list[dict]:
    """Where each key physical value came from — `authored` (in the spec), `default` (the compiler
    filled it), or `inferred` (computed). Surfacing defaults answers "did I forget to set this?" —
    silent physical defaults are dangerous."""
    rows = [{"field": f"body.{f}", "value": getattr(spec.body, f), "source": _prov(spec.body, f)}
            for f in ("shape", "size", "mass")]
    if spec.base == "differential-drive" or any(p.use == "differential-drive" for p in spec.parts):
        rows += [{"field": f"drive.{f}", "value": getattr(spec.drive, f), "source": _prov(spec.drive, f)}
                 for f in ("wheel_radius", "wheel_separation")]
    for i, s in enumerate(spec.sensors):
        rows.append({"field": f"sensors[{i}].mount",
                     "value": s.mount if s.mount is not None else "per-type default",
                     "source": _prov(s, "mount")})
    rows.append({"field": "link inertia", "value": None, "source": "inferred",
                 "note": "auto-computed from shape + mass"})
    return rows


def _summary(source: str, frag: Fragment, note: str = "") -> dict:
    entry = {
        "source": source,
        "links": [l.name for l in frag.links],
        "joints": [j.name for j in frag.joints],
        "ros_topics": sorted({b.arg.split("@", 1)[0] for b in frag.bridges}),
        "gz_world_systems": list(frag.world_systems),
    }
    if note:
        entry["note"] = note
    return entry


def explain_robot(spec: RobotSpec, world_name: str = "warehouse") -> dict:
    """Report, per spec declaration, what it contributed to the compiled robot."""
    parts = list(spec.parts)
    if spec.base:
        parts = [Part(use=spec.base, body=spec.body, drive=spec.drive)] + parts

    custom = next((p for p in parts if p.use == "custom"), None)
    if custom is not None:
        # Imported URDF: report the import + which sensors were recognised vs. author-added.
        produced = [{"source": f"parts: use custom (import {custom.urdf})",
                     "note": "imported URDF body preserved verbatim"}]
        ctx = Ctx(world=world_name, robot_name=spec.name,
                  body_size=body_xyz(spec.body.size, spec.body.shape))
        try:
            imported = infer_sensors_from_urdf(open(custom.urdf, encoding="utf-8").read())
        except OSError:
            imported = []
        for t in imported:
            produced.append(_summary(f"import: existing {t} sensor", SENSORS[t]({}, "base_link", ctx),
                                     "recognised in the URDF — bridged, XML not re-injected"))
        for i, s in enumerate(spec.sensors):
            if s.type in SENSORS:
                produced.append(_summary(f"sensors[{i}]: {s.type} (added)",
                                         SENSORS[s.type](s.model_dump(), s.on or "base_link", ctx),
                                         "injected into the imported URDF"))
        return {"robot": spec.name, "produced": produced, "provenance": provenance(spec)}

    produced, base_link, body_size = [], None, body_xyz(spec.body.size, spec.body.shape)
    for i, part in enumerate(parts):
        is_base = spec.base and i == 0
        if part.use is not None and part.use in MODULES:
            p = {"body": (part.body or spec.body).model_dump(),
                 "drive": (part.drive or spec.drive).model_dump()}
            frag = MODULES[part.use](p, part.mount)
            label = f"base: {part.use}" if is_base else f"parts[{i}]: use {part.use}"
            if base_link is None and frag.exposes:
                base_link = frag.exposes[0]
                b = part.body or spec.body
                body_size = body_xyz(b.size, b.shape)
        else:
            from robotbase.robotspec.compile import _raw_part
            frag = _raw_part(part)
            label = f"parts[{i}]: raw links/joints"
        produced.append(_summary(label, frag))

    base_link = base_link or "base_link"
    ctx = Ctx(world=world_name, robot_name=spec.name, body_size=body_size, base_link=base_link)
    for i, s in enumerate(spec.sensors):
        if s.type in SENSORS:
            on = f" on {s.on}" if s.on else f" on {base_link}"
            produced.append(_summary(f"sensors[{i}]: {s.type}{on}",
                                     SENSORS[s.type](s.model_dump(), s.on or base_link, ctx)))
    return {"robot": spec.name, "produced": produced, "provenance": provenance(spec)}
