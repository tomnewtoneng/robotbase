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


DEFAULT_TEMPLATE = "differential-drive"


def _templates_root():
    return resources.files("robotbase") / "templates"


def list_templates() -> list[str]:
    """Names of the robot templates packaged with robotbase."""
    return sorted(p.name for p in _templates_root().iterdir() if p.is_dir())


def template_dir(name: str = DEFAULT_TEMPLATE) -> str:
    """Resolve a template name to its packaged directory."""
    path = _templates_root() / name
    if not path.is_dir():
        raise ValueError(f"Unknown template {name!r}. Available: {list_templates()}")
    return str(path)


def create_project(name: str, dest_parent: str, template_dir: str, from_urdf: str | None = None) -> str:
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

    if from_urdf is not None:
        urdf_dir = os.path.join(dest, "src", f"{snake}_description", "urdf")
        os.makedirs(urdf_dir, exist_ok=True)
        shutil.copyfile(from_urdf, os.path.join(urdf_dir, f"{snake}.urdf.xacro"))
        with open(os.path.join(dest, "robot.yaml"), "w", encoding="utf-8") as fh:
            fh.write(f"version: 1\nname: {snake}\n"
                     f"parts:\n  - use: custom\n    urdf: src/{snake}_description/urdf/{snake}.urdf.xacro\n"
                     f"sensors: []\n")

    _compile_specs(dest, snake)
    return dest


def _compile_specs(dest: str, snake: str) -> None:
    """If the project carries robot.yaml/world.yaml, compile them into the description package.

    A `use: custom` robot.yaml wraps an already-placed, verbatim imported URDF — its
    `urdf:` path is project-relative, and the imported file is authoritative, so URDF
    compilation is skipped entirely for that case (no relative-path open, no clobbering
    the import). The world is still compiled if `world.yaml` is present.
    """
    robot_yaml = os.path.join(dest, "robot.yaml")
    if not os.path.exists(robot_yaml):
        return
    robot_yaml_text = open(robot_yaml, encoding="utf-8").read()
    is_custom = "use: custom" in robot_yaml_text

    world_systems: list[str] = []
    if not is_custom:
        from robotbase.robotspec.compile import compile_robot
        from robotbase.robotspec.schema import RobotSpec

        compiled = compile_robot(RobotSpec.from_yaml(robot_yaml))
        world_systems = compiled.world_systems
        urdf_dir = os.path.join(dest, "src", f"{snake}_description", "urdf")
        if os.path.isdir(urdf_dir):
            with open(os.path.join(urdf_dir, f"{snake}.urdf.xacro"), "w", encoding="utf-8") as fh:
                fh.write(compiled.urdf)

    world_yaml = os.path.join(dest, "world.yaml")
    world_dir = os.path.join(dest, "src", f"{snake}_description", "worlds")
    if os.path.exists(world_yaml) and os.path.isdir(world_dir):
        from robotbase.worldspec.compile import compile_world
        from robotbase.worldspec.schema import WorldSpec
        sdf, _ = compile_world(WorldSpec.from_yaml(world_yaml), robot_systems=world_systems)
        with open(os.path.join(world_dir, "warehouse.sdf"), "w", encoding="utf-8") as fh:
            fh.write(sdf)


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
