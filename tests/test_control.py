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
