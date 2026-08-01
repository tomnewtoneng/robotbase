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
        # Keep the imported URDF pristine and separate from the compiled output: robot.yaml
        # points at `.imported.urdf`, and the compiler writes the runnable `.urdf.xacro`
        # (imported body + any sensors the author later adds). This keeps recompiles idempotent —
        # the pristine source is re-read each time, never mutated.
        shutil.copyfile(from_urdf, os.path.join(urdf_dir, f"{snake}.imported.urdf"))
        with open(os.path.join(dest, "robot.yaml"), "w", encoding="utf-8") as fh:
            fh.write(f"version: 1\nname: {snake}\n"
                     "parts:\n  - use: custom\n"
                     f"    urdf: src/{snake}_description/urdf/{snake}.imported.urdf\n"
                     "sensors: []\n")

    _compile_specs(dest, snake)
    return dest


def recompile_project(project_dir: str) -> bool:
    """Recompile an existing project's robot.yaml/world.yaml into its description package.

    This is what closes the authoring loop: an agent edits a spec, rebuilds, and the change
    takes effect. Returns True if a recompile ran (a robot.yaml was found)."""
    snake = _project_snake(project_dir)
    if not snake or not os.path.exists(os.path.join(project_dir, "robot.yaml")):
        return False
    _compile_specs(project_dir, snake)
    return True


def _project_snake(project_dir: str) -> str | None:
    """The project's package prefix (``<snake>_description``), from the manifest or the tree."""
    manifest = os.path.join(project_dir, "robotbase.yaml")
    if os.path.exists(manifest):
        from robotbase.schema import Manifest, ManifestError
        try:
            return Manifest.from_yaml(manifest).launch_package.removesuffix("_bringup")
        except ManifestError:
            pass
    src = os.path.join(project_dir, "src")
    if os.path.isdir(src):
        for d in sorted(os.listdir(src)):
            if d.endswith("_description"):
                return d[: -len("_description")]
    return None


# Runtime essentials every robot needs regardless of archetype: control in, sim clock out. A
# `differential-drive` base emits /cmd_vel itself (deduped below); a `use: custom` import gets its
# drivetrain from the imported URDF's own plugin, so the compiler wouldn't otherwise bridge /cmd_vel.
_ESSENTIAL_BRIDGES = [
    {"arg": "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist", "remap": None},
    {"arg": "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock", "remap": None},
]


def _bridge_list(compiled_bridges) -> list[dict]:
    """Serialize compiled bridges + merge the runtime essentials (deduped by ROS topic)."""
    out, seen = [], set()
    for b in compiled_bridges:
        out.append({"arg": b.arg, "remap": list(b.remap) if b.remap else None})
        seen.add(b.arg.split("@", 1)[0])
    for e in _ESSENTIAL_BRIDGES:
        if e["arg"].split("@", 1)[0] not in seen:
            out.append(e)
    return out


def _sync_manifest(dest: str, compiled, world_name: str) -> None:
    """Keep the manifest's spec-derived fields in sync with the compiled robot: the model name,
    the world name, and the sensor list. Only rewrites when something actually changed, so a
    stable project keeps its manifest (and comments) untouched. Runtime-critical values (spawn
    name, bridges) are already in launch_config.json/bridges.json; this keeps the manifest — which
    Runtime and `describe` read — accurate after an edit that renamed the robot or changed sensors."""
    import yaml
    path = os.path.join(dest, "robotbase.yaml")
    if not os.path.exists(path):
        return
    try:
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except yaml.YAMLError:
        return
    # Only the runtime-relevant identity fields, so the common case (names unchanged) does not
    # rewrite the manifest and lose its comments; the sensor list is already authoritative in
    # bridges.json / the compiled URDF.
    robot = data.setdefault("robot", {})
    sim = data.setdefault("simulation", {})
    if robot.get("name") == compiled.name and sim.get("world_name") == world_name:
        return
    robot["name"] = compiled.name
    sim["world_name"] = world_name
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(yaml.safe_dump(data, sort_keys=False))


def _with_source_map(urdf: str, spec) -> str:
    """Prepend a source map to the generated URDF: which spec declaration produced each element,
    so reading the raw file is traceable (the same data `robotbase explain` reports). Best-effort.

    Skipped for a `use: custom` import — an imported URDF is preserved verbatim (best-effort import
    guarantee); use `robotbase explain` for its provenance instead."""
    if any(p.use == "custom" for p in spec.parts):
        return urdf
    try:
        from robotbase.robotspec.explain import explain_robot
        lines = []
        for e in explain_robot(spec).get("produced", []):
            bits = []
            if e.get("links"):
                bits.append("links: " + ", ".join(e["links"]))
            if e.get("ros_topics"):
                bits.append("topics: " + ", ".join(e["ros_topics"]))
            lines.append(f"       {e['source']}  ->  {'; '.join(bits) or e.get('note', '')}")
        comment = ("<!-- Source map (robotbase explain) - which spec declaration made each element:\n"
                   + "\n".join(lines) + "\n-->\n")
        return urdf.replace("<robot", comment + "<robot", 1)
    except Exception:
        return urdf


def _compile_specs(dest: str, snake: str) -> None:
    """Compile the project's robot.yaml/world.yaml into the description package.

    Always writes the runnable ``<snake>.urdf.xacro``. For a `use: custom` import the compiler
    reads the pristine ``.imported.urdf`` and returns the imported body plus any sensors the
    author added, so writing it here is idempotent (the pristine source is never mutated). The
    world SDF is regenerated with the robot's sensor-derived gz systems so imported/added
    LiDAR/IMU/contact/camera actually publish.
    """
    robot_yaml = os.path.join(dest, "robot.yaml")
    if not os.path.exists(robot_yaml):
        return
    from robotbase.robotspec.compile import compile_robot
    from robotbase.robotspec.schema import RobotSpec

    spec = RobotSpec.from_yaml(robot_yaml)
    for p in spec.parts:                       # resolve project-relative import paths
        if p.use == "custom" and p.urdf and not os.path.isabs(p.urdf):
            p.urdf = os.path.join(dest, p.urdf)
    compiled = compile_robot(spec)

    urdf_dir = os.path.join(dest, "src", f"{snake}_description", "urdf")
    if os.path.isdir(urdf_dir):
        with open(os.path.join(urdf_dir, f"{snake}.urdf.xacro"), "w", encoding="utf-8") as fh:
            fh.write(_with_source_map(compiled.urdf, spec))
        # Compile the ROS<->gz bridge list from the robot's actual sensors so the launch bridges
        # exactly what was authored (an added camera/depth is exposed to ROS, not just rendered in
        # gz). Installed alongside the URDF; the launch reads it. See docs/STRATEGY.md P2.
        import json
        with open(os.path.join(urdf_dir, "bridges.json"), "w", encoding="utf-8") as fh:
            json.dump(_bridge_list(compiled.bridges), fh, indent=2)
        # Compile the launch config from the specs so the launch is NOT coupled to the project
        # name: the model spawns under the robot.yaml `name` (matching the sensor bridges' scoped
        # topics + the interface contract), and the launch reads the world name from world.yaml.
        world_name = "warehouse"
        _wy = os.path.join(dest, "world.yaml")
        if os.path.exists(_wy):
            from robotbase.worldspec.schema import WorldSpec
            world_name = WorldSpec.from_yaml(_wy).name
        with open(os.path.join(urdf_dir, "launch_config.json"), "w", encoding="utf-8") as fh:
            json.dump({"robot_name": compiled.name, "world_name": world_name,
                       "spawn_z": compiled.spawn_z,
                       "fixed_base": bool(compiled.manifest.get("fixed_base"))}, fh, indent=2)
        _sync_manifest(dest, compiled, world_name)

    # Generate the launch file so the whole runtime is compiler-owned (P2): one data-driven launch
    # that reads bridges.json/launch_config.json, regenerated on every create + recompile so it can
    # never drift from the specs (the arm/drone launches had drifted — stale hardcoded bridges +
    # spawn name). render_launch is archetype-neutral; all variation lives in the compiled config.
    launch_dir = os.path.join(dest, "src", f"{snake}_bringup", "launch")
    if os.path.isdir(launch_dir):
        from robotbase.robotspec.project import render_launch
        with open(os.path.join(launch_dir, "simulation.launch.py"), "w", encoding="utf-8") as fh:
            fh.write(render_launch(snake))

    world_yaml = os.path.join(dest, "world.yaml")
    world_dir = os.path.join(dest, "src", f"{snake}_description", "worlds")
    if os.path.exists(world_yaml) and os.path.isdir(world_dir):
        from robotbase.worldspec.compile import compile_world
        from robotbase.worldspec.schema import WorldSpec
        sdf, _ = compile_world(WorldSpec.from_yaml(world_yaml), robot_systems=compiled.world_systems)
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
