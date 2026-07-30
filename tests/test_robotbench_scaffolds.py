import pathlib

from robotbase.robotbench.scaffolds import build_scaffold

AUTHOR = {"id": "author/diff-lidar-world", "kind": "author", "controller": "stop_at_1m",
          "model_name": "robot", "prompt": "Build a robot."}
IMPORT = {**AUTHOR, "id": "import/add-sensor", "kind": "import", "import_urdf": "vendor_bot.urdf",
          "prompt": "Import it."}


def _controller_bytes(d):
    return (pathlib.Path(d).rglob("stop_at_1m.py").__next__()).read_bytes()


def test_with_scaffold_is_runnable_robotbase_project(tmp_path):
    d = build_scaffold(AUTHOR, "with", str(tmp_path))
    p = pathlib.Path(d)
    assert p.name == "robot"                                   # spawns as Gazebo model `robot`
    assert (p / "robotbase.yaml").is_file() and (p / "compose.yaml").is_file()
    assert (p / "robot.yaml").is_file() and (p / "world.yaml").is_file()
    # specs are reset to authoring stubs: base only, no sensors, empty world
    assert "lidar" not in (p / "robot.yaml").read_text()
    assert (p / "controllers" / "stop_at_1m.py").is_file()
    assert (p / "TASK.md").read_text().startswith("Build a robot")


def test_without_scaffold_is_empty_colcon_ws_with_orientation(tmp_path):
    d = build_scaffold(AUTHOR, "without", str(tmp_path))
    p = pathlib.Path(d)
    assert (p / "src" / "authored_pkg" / "package.xml").is_file()
    orient = (p / "RAW-ROS-ORIENTATION.md").read_text().lower()
    assert "gazebo harmonic" in orient and "ros_gz_sim create" in orient
    assert "<robot" not in orient and "<sensor" not in orient  # NO templates


def test_controller_is_byte_identical_across_arms(tmp_path):
    w = build_scaffold(AUTHOR, "with", str(tmp_path / "a"))
    wo = build_scaffold(AUTHOR, "without", str(tmp_path / "b"))
    assert _controller_bytes(w) == _controller_bytes(wo)


def test_import_scaffold_ships_vendor_urdf(tmp_path):
    d = build_scaffold(IMPORT, "with", str(tmp_path))
    assert (pathlib.Path(d) / "vendor_bot.urdf").is_file()
