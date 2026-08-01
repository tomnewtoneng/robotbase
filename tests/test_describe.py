import os

import robotbase
from robotbase.describe import describe

TEMPLATES = os.path.join(os.path.dirname(robotbase.__file__), "templates")


def test_describe_differential_drive():
    d = describe(os.path.join(TEMPLATES, "differential-drive"))
    assert d["robot"]["template"] == "differential-drive"
    assert d["robot"]["fixed_base"] is False
    assert d["robot"]["dimensions"]["body_x"] == 0.35
    assert d["robot"]["dimensions"]["body_y"] == 0.30
    # arena bounds come from the walls, not the (much larger) ground plane
    assert d["world"]["bounds"] == {"x": [-4.05, 4.05], "y": [-4.05, 4.05]}
    names = {s["name"] for s in d["scenarios"]}
    assert {"drive-forward", "stop-before-obstacle", "reach-goal", "turn-around"} <= names
    turn = next(s for s in d["scenarios"] if s["name"] == "turn-around")
    assert "minimum_path_length" in turn["assertions"]
    assert "diff-drive" in {c["kind"] for c in d["robot"]["controllers"]}   # control config is surfaced


def test_describe_arm():
    d = describe(os.path.join(TEMPLATES, "arm"))
    assert d["robot"]["fixed_base"] is True
    joints = {j["name"]: j for j in d["robot"]["joints"]}
    assert joints["shoulder_joint"]["type"] == "revolute"
    assert joints["shoulder_joint"]["limits"] == [-3.14, 3.14]
    assert d["ready_topics"] == ["/joint_states"]
    assert d["command_joints"]["shoulder"]["command_topic"] == "/shoulder_cmd"
    assert d["scenarios"][0]["name"] == "reach-configuration"
    # the compiled joint-position controllers + their tunable gains are surfaced as ground truth
    ctrl = {c["joint"]: c["params"] for c in d["robot"]["controllers"] if c["kind"] == "joint-position"}
    assert ctrl["shoulder_joint"]["p_gain"] == "80" and ctrl["elbow_joint"]["p_gain"] == "60"
