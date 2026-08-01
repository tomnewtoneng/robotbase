"""P2 — the simulation launch is compiler-generated (render_launch), archetype-neutral and
data-driven (reads the compiled bridges.json / launch_config.json)."""
import ast

from robotbase.robotspec.project import render_launch


def test_render_launch_is_valid_python_and_package_scoped():
    src = render_launch("my_bot")
    ast.parse(src)                                              # syntactically valid
    assert 'get_package_share_directory("my_bot_description")' in src
    assert '"my_bot.urdf.xacro"' in src


def test_render_launch_is_data_driven():
    src = render_launch("warehouse_bot")
    assert "bridges.json" in src and "launch_config.json" in src   # nothing robot-specific inlined
    # a fixed-base robot (arm anchored to world) spawns without a -z drop
    assert 'if not _cfg.get("fixed_base", False):' in src
    assert '"-z"' in src


def test_render_launch_has_the_runtime_nodes():
    src = render_launch("warehouse_bot")
    for tok in ("robot_state_publisher", "parameter_bridge", "ros_gz_sim", "foxglove_bridge",
                'DeclareLaunchArgument("gui"', "headless-rendering"):
        assert tok in src, tok
