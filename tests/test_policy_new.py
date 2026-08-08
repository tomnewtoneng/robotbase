import tempfile

from robotbase.generator import create_project, template_dir
from robotbase.policy_scaffold import write_policy_starter


def test_writes_velocity_starter():
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("pn", tmp, template_dir("differential-drive"))
        path = write_policy_starter(dest)
        assert path.endswith("policy.py")
        body = open(path).read()
        assert "class Policy" in body and "linear_x" in body and "def act" in body


def test_refuses_to_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("pn2", tmp, template_dir("arm"))
        write_policy_starter(dest)
        try:
            write_policy_starter(dest)
            assert False, "should refuse"
        except FileExistsError:
            pass


def test_arm_starter_uses_joint_keys():
    with tempfile.TemporaryDirectory() as tmp:
        dest = create_project("pn3", tmp, template_dir("arm"))
        body = open(write_policy_starter(dest)).read()
        assert "shoulder_joint" in body and "elbow_joint" in body
