"""Static physical validation: clean robots pass; physically-suspect ones are flagged (not silently
compiled into a broken sim)."""
from robotbase.robotspec.schema import RobotSpec
from robotbase.robotspec.validate import summarize, validate_robot, validate_urdf


def test_compiled_diff_drive_robot_is_physically_clean():
    spec = RobotSpec.model_validate({"name": "robot", "base": "differential-drive",
                                     "sensors": [{"type": "lidar"}]})
    findings = validate_robot(spec)
    assert [f for f in findings if f.severity == "error"] == []
    assert summarize(findings)["ok"] is True


def test_non_positive_mass_is_an_error():
    urdf = ('<robot name="r"><link name="a"><inertial><mass value="0"/>'
            '<inertia ixx="1" iyy="1" izz="1"/></inertial></link></robot>')
    f = validate_urdf(urdf)
    assert any(x.code == "non-positive-mass" and x.severity == "error" for x in f)


def test_non_positive_inertia_is_an_error():
    urdf = ('<robot name="r"><link name="a"><inertial><mass value="1"/>'
            '<inertia ixx="1" iyy="0" izz="1"/></inertial></link></robot>')
    f = validate_urdf(urdf)
    assert any(x.code == "non-positive-inertia" for x in f)


def test_extreme_mass_ratio_is_a_warning():
    urdf = ('<robot name="r">'
            '<link name="heavy"><inertial><mass value="5000"/><inertia ixx="1" iyy="1" izz="1"/></inertial></link>'
            '<link name="light"><inertial><mass value="0.001"/><inertia ixx="1" iyy="1" izz="1"/></inertial></link>'
            '</robot>')
    f = validate_urdf(urdf)
    assert any(x.code == "mass-ratio" and x.severity == "warning" for x in f)


def test_inverted_joint_limit_is_an_error():
    urdf = ('<robot name="r"><link name="a"/><link name="b"/>'
            '<joint name="j" type="revolute"><parent link="a"/><child link="b"/>'
            '<limit lower="1.0" upper="-1.0"/></joint></robot>')
    f = validate_urdf(urdf)
    assert any(x.code == "inverted-joint-limit" for x in f)


def test_massless_frame_links_are_not_flagged():
    # base_footprint / tip have no <inertial> — expected, must not error.
    urdf = '<robot name="r"><link name="base_footprint"/></robot>'
    assert validate_urdf(urdf) == []


def test_validate_model_reads_typed_fields_no_xml():
    # the physical checks now run over a typed RobotModel, not parsed XML
    from robotbase.robotspec.semantic import RobotModel, RigidBody, Inertial, Joint
    from robotbase.robotspec.validate import validate_model
    model = RobotModel(name="r", root="a", bodies=[
        RigidBody("base_footprint"),                                   # frame link -> ignored
        RigidBody("a", ("box", [1, 1, 1]), inertia=Inertial(0.0, 1, 1, 1)),   # zero mass
        RigidBody("b", ("box", [1, 1, 1]), mass=2.0),                  # fine
    ], joints=[Joint("j", "revolute", "a", "b", limit=("1.0", "-1.0", "10", "1"))])
    codes = {f.code for f in validate_model(model)}
    assert "non-positive-mass" in codes
    assert "inverted-joint-limit" in codes


def test_compile_model_returns_a_robot_model():
    from robotbase.robotspec.compile import compile_model
    from robotbase.robotspec.semantic import RobotModel
    model = compile_model(RobotSpec.model_validate(
        {"name": "robot", "base": "differential-drive", "sensors": [{"type": "lidar"}]}))
    assert isinstance(model, RobotModel)
    assert {b.name for b in model.bodies} >= {"base_footprint", "base_link", "left_wheel", "lidar_link"}
