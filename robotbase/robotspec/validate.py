"""Static physical validation — catch dangerous physics BEFORE launching the sim.

"A compiler that generates invalid physics faster is worthless." The renderer already refuses
structurally-broken robots (unknown keys, wrong-length sizes, orphan links). This stage goes one
level deeper: it parses the *compiled* URDF and flags physically-suspect values — non-positive
mass or inertia, wildly disparate masses (numerically unstable), and inverted joint limits — that
would otherwise only surface as a silently-wrong or exploding simulation.

Findings are structured (severity/code/message) so they render in `describe`, gate `validate`,
and read cleanly to an agent. Errors mean "this will not simulate correctly"; warnings mean "this
is probably a mistake." Massless *frame* links (e.g. `base_footprint`, an arm `tip`) are expected
and ignored — only links that declare an `<inertial>` are physically checked.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

MASS_RATIO_WARN = 1000.0   # heaviest / lightest link above this risks solver instability


@dataclass(frozen=True)
class Finding:
    severity: str   # "error" | "warning"
    code: str
    message: str


def validate_urdf(urdf: str) -> list[Finding]:
    """Physically validate a compiled URDF string."""
    findings: list[Finding] = []
    try:
        root = ET.fromstring(urdf)
    except ET.ParseError as e:
        return [Finding("error", "unparseable-urdf", f"generated URDF is not valid XML: {e}")]

    masses: dict[str, float] = {}
    for link in root.findall("link"):
        name = link.get("name", "?")
        inertial = link.find("inertial")
        if inertial is None:
            continue  # a massless frame link (base_footprint, tip) — expected, not physical
        mass_el = inertial.find("mass")
        mass = float(mass_el.get("value")) if mass_el is not None else 0.0
        if mass <= 0:
            findings.append(Finding("error", "non-positive-mass",
                                    f"link '{name}' has non-positive mass ({mass}) — it will not "
                                    "behave under physics"))
        else:
            masses[name] = mass
        inertia = inertial.find("inertia")
        if inertia is not None:
            for ax in ("ixx", "iyy", "izz"):
                v = float(inertia.get(ax, "0"))
                if v <= 0:
                    findings.append(Finding("error", "non-positive-inertia",
                                            f"link '{name}' has non-positive {ax} ({v}) — an "
                                            "invalid inertia tensor"))

    if len(masses) >= 2:
        heavy_name, heavy = max(masses.items(), key=lambda kv: kv[1])
        light_name, light = min(masses.items(), key=lambda kv: kv[1])
        ratio = heavy / light
        if ratio > MASS_RATIO_WARN:
            findings.append(Finding("warning", "mass-ratio",
                                    f"mass ratio {ratio:.0f}:1 between '{heavy_name}' ({heavy} kg) "
                                    f"and '{light_name}' ({light} kg) — large ratios make the "
                                    "physics solver unstable"))

    for joint in root.findall("joint"):
        name = joint.get("name", "?")
        limit = joint.find("limit")
        if limit is not None and limit.get("lower") is not None and limit.get("upper") is not None:
            lo, hi = float(limit.get("lower")), float(limit.get("upper"))
            if lo >= hi:
                findings.append(Finding("error", "inverted-joint-limit",
                                        f"joint '{name}' has lower limit {lo} >= upper {hi} — it "
                                        "cannot move"))
    return findings


def validate_robot(spec) -> list[Finding]:
    """Compile `spec` and physically validate the result (raises the usual compile errors first)."""
    from robotbase.robotspec.compile import compile_robot
    return validate_urdf(compile_robot(spec).urdf)


def summarize(findings: list[Finding]) -> dict:
    """A JSON-friendly report: ok flag + counts + the findings."""
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    return {
        "ok": not errors,
        "errors": len(errors),
        "warnings": len(warnings),
        "findings": [{"severity": f.severity, "code": f.code, "message": f.message}
                     for f in findings],
    }
