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
