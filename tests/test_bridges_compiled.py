"""The ROS<->gz bridge list is compiled from the robot's actual sensors (urdf/bridges.json), so an
authored camera is bridged to ROS, not just rendered in gz. Regression for the two-sensor task."""
import json
import os
import tempfile

from robotbase.generator import create_project, recompile_project, template_dir


def _bridges(project_dir, snake):
    path = os.path.join(project_dir, "src", f"{snake}_description", "urdf", "bridges.json")
    return [b["arg"] for b in json.load(open(path, encoding="utf-8"))]


def test_authored_camera_is_bridged_to_ros():
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("robot", tmp, template_dir("differential-drive"))
        open(os.path.join(dest, "robot.yaml"), "w").write(
            "version: 1\nname: robot\nbase: differential-drive\n"
            "sensors:\n  - {type: lidar}\n  - {type: camera}\n")
        assert recompile_project(dest) is True
        args = _bridges(dest, "robot")
        assert any("/scan@" in a for a in args)                      # lidar still bridged
        assert any("/image@" in a and "Image" in a for a in args)    # authored camera now bridged
        assert any("/cmd_vel@" in a for a in args)                   # drivetrain bridged
        assert sum("/cmd_vel@" in a for a in args) == 1              # essential not duplicated


def test_custom_import_still_bridges_cmd_vel():
    # A custom import gets its drivetrain from the imported URDF's plugin, so the compiler emits no
    # /cmd_vel bridge — the essentials merge must still expose it or the controller cannot drive.
    with tempfile.TemporaryDirectory() as tmp:
        vendor = os.path.join(tmp, "vendor.urdf")
        open(vendor, "w").write(
            '<?xml version="1.0"?>\n<robot name="robot"><link name="base_link"/></robot>\n')
        dest = create_project("robot", tmp, template_dir("differential-drive"), from_urdf=vendor)
        open(os.path.join(dest, "robot.yaml"), "w").write(
            "version: 1\nname: robot\nparts:\n  - use: custom\n"
            "    urdf: src/robot_description/urdf/robot.imported.urdf\n"
            "sensors:\n  - {type: lidar}\n")
        assert recompile_project(dest) is True
        args = _bridges(dest, "robot")
        assert any("/scan@" in a for a in args)                      # added lidar bridged
        assert any("/cmd_vel@" in a for a in args)                   # essential merged in
