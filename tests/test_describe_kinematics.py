import tempfile

from robotbase.describe import describe
from robotbase.generator import create_project, template_dir


def _describe(tmpl):
    tmp = tempfile.mkdtemp()
    return describe(create_project("k", tmp, template_dir(tmpl)))


def test_arm_kinematic_tree():
    d = _describe("arm")
    joints = {j["name"]: j for j in d["robot"]["joints"]}
    sh = joints["shoulder_joint"]
    assert sh["type"] == "revolute" and sh["parent"] == "arm_base_link" and sh["child"] == "upper_arm"
    assert sh["origin_xyz"] == [0.0, 0.0, 0.05] and sh["axis"] == [0.0, 1.0, 0.0]
    assert "origin_rpy" in sh and len(sh["origin_rpy"]) == 3
    for link in d["robot"]["links"]:
        assert "visual_origin_xyz" in link and len(link["visual_origin_xyz"]) == 3


def test_diff_drive_tree_has_parent_child():
    d = _describe("differential-drive")
    joints = {j["name"]: j for j in d["robot"]["joints"]}
    assert joints["base_joint"]["parent"] == "base_footprint" and joints["base_joint"]["child"] == "base_link"
    assert joints["lidar_joint"]["parent"] == "base_link"
