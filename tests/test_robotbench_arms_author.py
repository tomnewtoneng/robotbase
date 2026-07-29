from robotbase.robotbench.arms import build_author_prompt, arm_context

T = {"id": "author/diff-lidar-world", "kind": "author", "model_name": "robot",
     "prompt": "Build a diff-drive robot with a LiDAR."}


def test_prompt_is_identical_task_text_both_arms():
    w = build_author_prompt(T, "with")
    wo = build_author_prompt(T, "without")
    assert T["prompt"] in w and T["prompt"] in wo


def test_prompt_forbids_editing_controller_and_states_contract():
    p = build_author_prompt(T, "with").lower()
    assert "do not modify" in p and "/cmd_vel" in p and "/scan" in p and "model" in p


def test_bringup_command_differs_by_arm():
    assert "robotbase up" in build_author_prompt(T, "with")
    assert "ros2 launch" in build_author_prompt(T, "without")


def test_arm_context_wires_tools_and_docs():
    assert arm_context("with", "/p", T)["tools"] == ["robotbase-mcp"]
    ctx = arm_context("without", "/p", T)
    assert "bash" in ctx["tools"] and ctx["docs"] == ["RAW-ROS-ORIENTATION.md"]
