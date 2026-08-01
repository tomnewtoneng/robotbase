import os

import pytest

from robotbase.generator import create_project


def _make_template(tmp_path):
    t = tmp_path / "template"
    (t / "src" / "warehouse_bot" / "warehouse_bot").mkdir(parents=True)
    (t / "src" / "warehouse_bot" / "package.xml").write_text("<name>warehouse_bot</name>")
    (t / "src" / "warehouse_bot" / "resource").mkdir()
    (t / "src" / "warehouse_bot" / "resource" / "warehouse_bot").write_text("")
    (t / "src" / "warehouse_bot" / "warehouse_bot" / "ctrl.py").write_text("# warehouse_bot node")
    (t / "robotbase.yaml").write_text(
        "project:\n  name: warehouse-bot\nrobot:\n  name: warehouse_bot\n"
        "launch:\n  package: warehouse_bot_bringup\n"
        "simulation:\n  world_name: warehouse\n"
    )
    (t / "scripts").mkdir()
    (t / "scripts" / "metrics_collector.py").write_text("# keep me")
    (t / "scripts" / "probe.sh").write_text("echo throwaway")
    (t / "build").mkdir()
    (t / "build" / "junk").write_text("x")
    return str(t)


def test_create_renames_and_replaces(tmp_path):
    template = _make_template(tmp_path)
    dest = create_project("obstacle-bot", str(tmp_path / "out"), template)

    assert dest.endswith("obstacle-bot")
    # package directories (including the nested one and the resource marker) renamed
    assert os.path.isdir(os.path.join(dest, "src", "obstacle_bot", "obstacle_bot"))
    assert os.path.isfile(os.path.join(dest, "src", "obstacle_bot", "resource", "obstacle_bot"))
    # file contents rewritten, no template identifier left behind
    pkg = open(os.path.join(dest, "src", "obstacle_bot", "package.xml")).read()
    assert "obstacle_bot" in pkg and "warehouse_bot" not in pkg
    manifest = open(os.path.join(dest, "robotbase.yaml")).read()
    assert "name: obstacle-bot" in manifest
    assert "obstacle_bot_bringup" in manifest
    # the bare world name "warehouse" is preserved (not part of the robot identifier)
    assert "world_name: warehouse" in manifest
    # build artifacts skipped, throwaway probe skipped, metrics_collector kept
    assert not os.path.exists(os.path.join(dest, "build"))
    assert not os.path.exists(os.path.join(dest, "scripts", "probe.sh"))
    assert os.path.isfile(os.path.join(dest, "scripts", "metrics_collector.py"))


def test_create_rejects_existing(tmp_path):
    template = _make_template(tmp_path)
    create_project("obstacle-bot", str(tmp_path / "out"), template)
    with pytest.raises(FileExistsError):
        create_project("obstacle-bot", str(tmp_path / "out"), template)


def test_bridge_list_omits_cmd_vel_for_non_mobile_robots():
    # a joint-controlled arm must not get a spurious idle /cmd_vel bridge; /clock stays essential
    from robotbase.generator import _bridge_list
    from robotbase.robotspec.ir import Bridge
    arm_bridges = [Bridge("/shoulder_cmd@std_msgs/msg/Float64]gz.msgs.Double"),
                   Bridge("/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model"),
                   Bridge("/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock")]
    args = [b["arg"].split("@")[0] for b in _bridge_list(arm_bridges, {"joint_command_topics": ["/shoulder_cmd"]})]
    assert "/cmd_vel" not in args and "/clock" in args


def test_bridge_list_adds_cmd_vel_for_a_cmd_vel_driven_robot():
    # a custom import is driven by /cmd_vel (control) but the compiler didn't bridge it -> fallback adds it
    from robotbase.generator import _bridge_list
    from robotbase.robotspec.ir import Bridge
    out = _bridge_list([Bridge("/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock")], {"velocity_topic": "/cmd_vel"})
    assert "/cmd_vel" in [b["arg"].split("@")[0] for b in out]


def test_created_project_generates_a_data_driven_launch(tmp_path):
    # a real template compiles specs on create; the launch is generated (P2), package-scoped,
    # data-driven, and the compiled launch_config carries the spawn name + fixed_base flag.
    import ast
    import json
    from robotbase.generator import template_dir

    dest = create_project("coolbot", str(tmp_path / "out"), template_dir("differential-drive"))
    launch = os.path.join(dest, "src", "coolbot_bringup", "launch", "simulation.launch.py")
    src = open(launch, encoding="utf-8").read()
    ast.parse(src)                                                       # valid Python
    assert 'get_package_share_directory("coolbot_description")' in src   # package-scoped, not template
    assert "bridges.json" in src and "launch_config.json" in src        # data-driven
    cfg = json.load(open(os.path.join(dest, "src", "coolbot_description", "urdf", "launch_config.json")))
    assert cfg["robot_name"] == "coolbot" and "fixed_base" in cfg and "spawn_z" in cfg
