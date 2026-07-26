def test_mobile_manipulator_compiles_to_one_tree():
    from robotbase.robotspec.schema import RobotSpec
    from robotbase.robotspec.compile import compile_robot
    spec = RobotSpec.model_validate({
        "name": "mm_bot",
        "parts": [{"use": "differential-drive"},
                  {"use": "arm", "mount": {"to": "base_link", "xyz": [0, 0, 0.15]}}],
        "sensors": [{"type": "camera", "on": "tip"}],
    })
    urdf = compile_robot(spec).urdf   # must not raise InvalidAssembly
    assert "base_footprint" in urdf and "arm_base_link" in urdf and "tip" in urdf
    assert 'type="camera"' in urdf    # the camera mounted on the arm tip
