from robotbase.robotspec.semantic import Controller, RobotModel
from robotbase.robotspec.ir import Fragment


def test_controller_holds_kind_params_joint():
    c = Controller("joint-position", {"joint_name": "shoulder_joint", "p": 80, "i": 2.0, "d": 8.0},
                   joint="shoulder_joint")
    assert c.kind == "joint-position" and c.joint == "shoulder_joint"
    c.params["p"] = 120                      # params is mutable (overrides update in place)
    assert c.params["p"] == 120


def test_model_and_fragment_default_empty_controllers():
    assert RobotModel(name="r", root="a").controllers == []
    assert Fragment().controllers == []


import pytest
from robotbase.robotspec.schema import RobotSpec
from robotbase.robotspec.compile import compile_model, ControlError


def _ctrl(model, joint):
    return next(c for c in model.controllers if c.joint == joint)


def test_control_overrides_arm_gains():
    spec = RobotSpec.model_validate({"name": "arm", "base": "arm",
        "control": {"joints": {"shoulder_joint": {"p": 120, "d": 10}}}})
    model = compile_model(spec)
    sh = _ctrl(model, "shoulder_joint")
    assert sh.params["p"] == 120 and sh.params["d"] == 10 and sh.params["i"] == 2.0   # i untouched
    assert _ctrl(model, "elbow_joint").params["p"] == 60                              # elbow default


def test_control_overrides_drive_odom_frequency():
    spec = RobotSpec.model_validate({"name": "r", "base": "differential-drive",
        "control": {"base": {"odom_publish_frequency": 50}}})
    model = compile_model(spec)
    diff = next(c for c in model.controllers if c.kind == "diff-drive")
    assert diff.params["odom_publish_frequency"] == 50


def test_control_bad_joint_raises():
    spec = RobotSpec.model_validate({"name": "arm", "base": "arm",
        "control": {"joints": {"wrist_joint": {"p": 1}}}})
    with pytest.raises(ControlError, match="wrist_joint"):
        compile_model(spec)


def test_control_base_without_drive_controller_raises():
    spec = RobotSpec.model_validate({"name": "arm", "base": "arm",
        "control": {"base": {"odom_publish_frequency": 50}}})
    with pytest.raises(ControlError, match="drive"):
        compile_model(spec)


def test_no_control_block_leaves_defaults():
    model = compile_model(RobotSpec.model_validate({"name": "arm", "base": "arm"}))
    assert _ctrl(model, "shoulder_joint").params["p"] == 80
