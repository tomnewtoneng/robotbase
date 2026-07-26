import pytest
from robotbase.robotbench.arms import build_task_prompt, without_orientation, arm_context

TASK = {"id": "diff/reach-goal", "template": "differential-drive", "scenario": "reach-goal",
        "robot": "mobile-base", "skill": "pose goal-seeking (odometry)"}


def test_task_prompt_is_neutral_and_shared():
    p = build_task_prompt(TASK)
    assert "reach-goal" in p
    assert "only edit the controller" in p.lower()
    assert "not claim success" in p.lower() or "verify" in p.lower()


def test_both_arms_share_the_same_task_prompt():
    with_p = arm_context("with", "/proj", TASK)
    without_p = arm_context("without", "/proj", TASK)
    assert build_task_prompt(TASK) in with_p["prompt"]
    assert build_task_prompt(TASK) in without_p["prompt"]


def test_arm_tool_sets_differ_correctly():
    w = arm_context("with", "/proj", TASK)
    wo = arm_context("without", "/proj", TASK)
    assert w["tools"] == ["robotbase-mcp"] and "AGENTS.md" in w["docs"]
    assert wo["tools"] == ["bash"] and wo["docs"] == []
    # only the WITHOUT arm gets the raw-ROS orientation; WITH relies on the tools/AGENTS.md
    assert "controller" in wo["prompt"].lower() and "topic" in wo["prompt"].lower()


def test_unknown_arm_raises():
    with pytest.raises(ValueError):
        arm_context("cheating", "/proj", TASK)
