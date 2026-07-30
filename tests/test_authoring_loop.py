"""The authoring loop: editing robot.yaml/world.yaml + rebuilding takes effect (idempotently)."""
import os
import tempfile

from robotbase.generator import create_project, recompile_project, template_dir


def test_recompile_project_applies_edited_robot_yaml():
    # Closing the authoring loop: edit robot.yaml after create, recompile, URDF reflects it.
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("loop-bot", tmp, template_dir("differential-drive"))
        urdf_path = os.path.join(dest, "src", "loop_bot_description", "urdf", "loop_bot.urdf.xacro")
        assert 'type="camera"' not in open(urdf_path, encoding="utf-8").read()
        open(os.path.join(dest, "robot.yaml"), "w").write(          # author adds a camera
            "version: 1\nname: loop_bot\nbase: differential-drive\n"
            "sensors:\n  - {type: lidar}\n  - {type: camera}\n")
        assert recompile_project(dest) is True
        assert 'type="camera"' in open(urdf_path, encoding="utf-8").read()   # edit took effect


def test_recompile_project_applies_edited_world_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("wloop-bot", tmp, template_dir("differential-drive"))
        world_path = os.path.join(dest, "src", "wloop_bot_description", "worlds", "warehouse.sdf")
        open(os.path.join(dest, "world.yaml"), "w").write(
            "version: 1\nname: warehouse\nground: true\n"
            "obstacles:\n  - {shape: box, size: [0.5, 0.5, 0.5], at: [2, 0, 0.25]}\n")
        recompile_project(dest)
        assert "2 0 0.25" in open(world_path, encoding="utf-8").read()   # obstacle authored in


def test_spawn_name_is_compiled_from_robot_yaml_not_project_name():
    # P2: the model spawns under the robot.yaml `name`, decoupled from the project name — so the
    # sensor bridges' scoped topics and the interface contract stay consistent.
    import json
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("projname", tmp, template_dir("differential-drive"))
        open(os.path.join(dest, "robot.yaml"), "w").write(
            "version: 1\nname: myrobot\nbase: differential-drive\nsensors:\n  - {type: lidar}\n")
        assert recompile_project(dest) is True
        cfg = json.load(open(os.path.join(dest, "src", "projname_description", "urdf",
                                          "launch_config.json"), encoding="utf-8"))
        assert cfg["robot_name"] == "myrobot"          # spec name, not "projname"


def test_import_add_sensor_is_idempotent_across_recompiles():
    # import a sensorless URDF, add a lidar, recompile twice -> exactly one injected sensor.
    with tempfile.TemporaryDirectory() as tmp:
        src_urdf = os.path.join(tmp, "v.urdf")
        open(src_urdf, "w").write(
            '<?xml version="1.0"?>\n<robot name="v"><link name="base_link"/></robot>\n')
        dest = create_project("imp3", tmp, template_dir("differential-drive"), from_urdf=src_urdf)
        assert os.path.exists(os.path.join(dest, "src", "imp3_description", "urdf",
                                           "imp3.imported.urdf"))       # pristine kept separate
        open(os.path.join(dest, "robot.yaml"), "w").write(
            "version: 1\nname: imp3\nparts:\n  - use: custom\n"
            "    urdf: src/imp3_description/urdf/imp3.imported.urdf\nsensors:\n  - {type: lidar}\n")
        recompile_project(dest)
        recompile_project(dest)                                         # twice
        urdf = open(os.path.join(dest, "src", "imp3_description", "urdf", "imp3.urdf.xacro"),
                    encoding="utf-8").read()
        assert urdf.count('type="gpu_lidar"') == 1                      # not doubled
        assert '<link name="base_link"/>' in urdf                       # imported body preserved
