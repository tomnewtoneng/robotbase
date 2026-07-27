"""Load the Anthropic API key for RobotBench: env var first, else the gitignored
.robotbench_key file (raw key OR an `ANTHROPIC_API_KEY=...` dotenv line). Loading in Python
sidesteps the wsl-shell env/quoting problems. NEVER log the key value."""
from __future__ import annotations

import os
import pathlib


def _read_key_file(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    raw = path.read_text().strip()
    if not raw:
        return None
    if raw.startswith("ANTHROPIC_API_KEY="):
        raw = raw.split("=", 1)[1].strip()
    return raw or None


def ensure_api_key() -> None:
    """Ensure os.environ['ANTHROPIC_API_KEY'] is set; raise a clear error if it can't be found."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    candidates = [pathlib.Path.cwd() / ".robotbench_key",
                  pathlib.Path.home() / "robotbase" / ".robotbench_key"]
    for p in candidates:
        key = _read_key_file(p)
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            return
    raise RuntimeError(
        "No Anthropic API key: set ANTHROPIC_API_KEY or put it in a .robotbench_key file "
        "(repo root or ~/robotbase/). See docs/design/robotbench-validation.md.")
