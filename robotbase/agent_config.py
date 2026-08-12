"""Emit correct MCP-server config for coding agents. The generated `.mcp.json` must launch the
interpreter Robotbase is actually installed under — a bare `python3` fails once an agent runs
outside the activated venv (system python3 has no robotbase). `interpreter()` is that path."""
from __future__ import annotations

import json
import os
import sys


def interpreter() -> str:
    return sys.executable


def mcp_server_entry(project_dir: str, interp: str | None = None) -> dict:
    return {
        "command": interp or interpreter(),
        "args": ["-m", "robotbase.mcp_server"],
        "env": {"ROBOTBASE_PROJECT_DIR": os.path.abspath(project_dir)},
    }


def fix_mcp_interpreter(project_dir: str, interp: str | None = None) -> str | None:
    """Rewrite an existing project .mcp.json's robotbase `command` to the real interpreter,
    preserving its args/env. Returns the path, or None if there is no .mcp.json."""
    path = os.path.join(project_dir, ".mcp.json")
    if not os.path.exists(path):
        return None
    try:
        data = json.load(open(path))
    except (OSError, json.JSONDecodeError):
        return None
    srv = (data.get("mcpServers") or {}).get("robotbase")
    if isinstance(srv, dict):
        srv["command"] = interp or interpreter()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def write_project_mcp_json(project_dir: str, interp: str | None = None) -> str:
    """Write a correct project .mcp.json (used by `robotbase agent configure`)."""
    path = os.path.join(project_dir, ".mcp.json")
    data = {"mcpServers": {"robotbase": mcp_server_entry(project_dir, interp)}}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def codex_toml_snippet(project_dir: str, interp: str | None = None) -> str:
    e = mcp_server_entry(project_dir, interp)
    return (
        "[mcp_servers.robotbase]\n"
        f'command = "{e["command"]}"\n'
        'args = ["-m", "robotbase.mcp_server"]\n'
        f'env = {{ ROBOTBASE_PROJECT_DIR = "{e["env"]["ROBOTBASE_PROJECT_DIR"]}" }}\n'
    )
