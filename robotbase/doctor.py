"""`robotbase doctor` — check the environment and point at fixes.

Every gotcha we hit while building Robotbase, turned into a check: Docker reachable, compose
present, the runtime image built, port 8765 free (concurrent projects conflict on it),
whether you're in a project, whether its container is up, and optional Python deps. Each
check reports ok / warn / fail with a fix. Host-side; safe to run anytime.
"""
from __future__ import annotations

import os
import subprocess


def _run(cmd: list[str], cwd: str | None = None, timeout: float = 15.0):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _check(name, status, detail, fix=None):
    c = {"check": name, "status": status, "detail": detail}
    if fix:
        c["fix"] = fix
    return c


def overall(checks: list[dict]) -> str:
    """Worst status wins: fail > warn > ok."""
    statuses = {c["status"] for c in checks}
    return "fail" if "fail" in statuses else "warn" if "warn" in statuses else "ok"


# ---- individual checks ------------------------------------------------------

def check_docker() -> dict:
    r = _run(["docker", "ps"])
    if r is None:
        return _check("docker", "fail", "The `docker` command isn't available.",
                      "Install Docker Desktop; on Windows enable WSL integration for this distro.")
    if r.returncode != 0:
        return _check("docker", "fail", "Docker is installed but the daemon isn't reachable.",
                      "Start Docker Desktop (ensure 'Engine running'), and keep Resource Saver "
                      "off so it doesn't stop mid-run.")
    return _check("docker", "ok", "Docker daemon reachable.")


def check_compose() -> dict:
    r = _run(["docker", "compose", "version"])
    if r is None or r.returncode != 0:
        return _check("compose", "fail", "`docker compose` (v2) isn't available.",
                      "Use a Docker version with the Compose v2 plugin.")
    return _check("compose", "ok", "docker compose available.")


def check_runtime_image() -> dict:
    r = _run(["docker", "images", "-q", "robotbase-runtime:latest"])
    if r is None:
        return _check("runtime-image", "warn", "Could not check for the runtime image.")
    if not (r.stdout or "").strip():
        return _check("runtime-image", "warn", "The robotbase-runtime image isn't built yet.",
                      "The first `robotbase up` builds it (~3.6 GB, a few minutes).")
    return _check("runtime-image", "ok", "robotbase-runtime:latest is built.")


def check_port_8765() -> dict:
    r = _run(["docker", "ps", "--format", "{{.Ports}}"])
    if r and "8765" in (r.stdout or ""):
        return _check("port-8765", "warn", "Port 8765 is already published by a running container.",
                      "Concurrent projects conflict on the Foxglove port — run `robotbase down` "
                      "in the other project before using `--gui` here.")
    return _check("port-8765", "ok", "Port 8765 is free.")


def check_project(project_dir: str) -> dict:
    if os.path.exists(os.path.join(project_dir, "robotbase.yaml")):
        return _check("project", "ok", f"In a Robotbase project ({os.path.abspath(project_dir)}).")
    return _check("project", "warn", "No robotbase.yaml here — not inside a project.",
                  "cd into a generated project, or run `robotbase create <name>`.")


def check_container(project_dir: str) -> dict:
    if not os.path.exists(os.path.join(project_dir, "compose.yaml")):
        return _check("container", "warn", "No compose.yaml — can't check the container.")
    r = _run(["docker", "compose", "ps"], cwd=project_dir)
    if r is None or r.returncode != 0:
        return _check("container", "warn", "Could not query the project's container.")
    text = (r.stdout or "")
    if "running" in text or " Up " in text:
        return _check("container", "ok", "The project's container is up.")
    return _check("container", "warn", "The project's container isn't running.",
                  "Run `robotbase up` to start it.")


def check_python_deps() -> dict:
    missing = []
    for mod, why in (("mcap", "MCAP episode attachments"), ("yaml", "manifests"),
                     ("pydantic", "schema")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(f"{mod} ({why})")
    if missing:
        return _check("python-deps", "warn", "Missing optional/required Python packages: "
                      + ", ".join(missing), "pip install -e . (add [sim-mujoco] for MuJoCo).")
    return _check("python-deps", "ok", "Core Python dependencies importable.")


def diagnose_environment(project_dir: str) -> dict:
    checks = [
        check_docker(),
        check_compose(),
        check_runtime_image(),
        check_port_8765(),
        check_project(project_dir),
        check_container(project_dir),
        check_python_deps(),
    ]
    status = overall(checks)
    problems = [c for c in checks if c["status"] != "ok"]
    # A container that isn't up / an image not yet built are the EXPECTED state before the first
    # `robotbase up` — reassure rather than alarm when those are the only non-ok checks.
    expected_pre_up = {"container", "runtime-image"}
    if problems and all(c["check"] in expected_pre_up for c in problems):
        summary = "Ready to go — run `robotbase up` to start the container (it builds on first run)."
    elif status == "ok":
        summary = "Everything looks good."
    else:
        summary = f"{len(problems)} thing(s) need attention — see the fixes above."
    return {"status": status, "summary": summary, "checks": checks}
