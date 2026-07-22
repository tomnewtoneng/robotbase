"""Generate a new Robotbase project from the reference template.

`create_project` copies the template tree, rewrites the `warehouse_bot` /
`warehouse-bot` identifiers to the new project's names, and renames the ROS
package directories. Build artifacts and throwaway probe scripts are excluded.
"""
from __future__ import annotations

import os
import re
import shutil
from importlib import resources

from robotbase.naming import to_snake_identifier

TEMPLATE_SNAKE = "warehouse_bot"
TEMPLATE_KEBAB = "warehouse-bot"

# Directory/file names never copied into a generated project.
_SKIP_NAMES = {"build", "install", "log", ".robotbase", "__pycache__", ".pytest_cache"}
# Text extensions whose contents get identifier rewriting ("" = no extension).
_TEXT_EXT = {".py", ".xml", ".yaml", ".yml", ".sdf", ".xacro", ".json", ".md", ".cfg", ".txt", ".sh", ""}


def _kebab(name: str) -> str:
    kebab = re.sub(r"[\s_]+", "-", name.strip().lower())
    kebab = re.sub(r"[^a-z0-9-]", "", kebab).strip("-")
    if not kebab:
        raise ValueError(f"Cannot derive a project directory name from {name!r}")
    return kebab


def default_template_dir() -> str:
    """The reference project template packaged inside robotbase (ships with pip)."""
    return str(resources.files("robotbase") / "template")


def create_project(name: str, dest_parent: str, template_dir: str) -> str:
    """Create a new project under dest_parent; return its path."""
    snake = to_snake_identifier(name)
    kebab = _kebab(name)
    dest = os.path.join(dest_parent, kebab)
    if os.path.exists(dest):
        raise FileExistsError(f"{dest} already exists")

    os.makedirs(dest_parent, exist_ok=True)

    def _ignore(dirpath: str, names: list[str]) -> set[str]:
        ignored = {n for n in names if n in _SKIP_NAMES or n.endswith(".pyc")}
        if os.path.basename(dirpath) == "scripts":
            ignored |= {n for n in names if n.endswith(".sh")}  # throwaway probes
        return ignored

    shutil.copytree(template_dir, dest, ignore=_ignore)
    _rewrite_contents(dest, snake, kebab)
    _rename_paths(dest, TEMPLATE_SNAKE, snake)
    return dest


def _rewrite_contents(root: str, snake: str, kebab: str) -> None:
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in _TEXT_EXT:
                continue
            path = os.path.join(dirpath, fn)
            try:
                content = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            # Compound token first, then the kebab form; the bare "warehouse"
            # (world name) is never a full match, so it is left untouched.
            new = content.replace(TEMPLATE_SNAKE, snake).replace(TEMPLATE_KEBAB, kebab)
            if new != content:
                open(path, "w", encoding="utf-8").write(new)


def _rename_paths(root: str, old: str, new: str) -> None:
    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        for n in dirnames + filenames:
            if old in n:
                matches.append(os.path.join(dirpath, n))
    # Deepest paths first so renaming a child never invalidates a parent path.
    for path in sorted(matches, key=lambda p: p.count(os.sep), reverse=True):
        newpath = os.path.join(os.path.dirname(path), os.path.basename(path).replace(old, new))
        if path != newpath:
            os.rename(path, newpath)
