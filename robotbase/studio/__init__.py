"""Robotbase Studio — a local web control panel (a client of the core CLI/runtime).

Behind the `studio` optional extra. `robotbase studio` imports this lazily; if fastapi/uvicorn
are missing the import fails and the CLI prints an install hint."""
from __future__ import annotations


def run_server(project_dir: str, port: int = 8080, open_browser: bool = True) -> None:
    """Start the Studio web server (blocking). Implemented in server.py."""
    from robotbase.studio.server import run_server as _run
    _run(project_dir, port, open_browser)
