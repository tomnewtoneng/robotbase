from robotbase.robotspec.ir import Fragment, SHAPE_SIZE, body_xyz, _fmt
from robotbase.robotspec.semantic import RigidBody


def test_fragment_defaults_are_independent():
    a, b = Fragment(), Fragment()
    a.links.append(RigidBody("l"))
    assert b.links == []          # default_factory, not a shared mutable


def test_shape_size_is_the_single_source_of_truth():
    assert SHAPE_SIZE["box"][0] == 3
    assert SHAPE_SIZE["cylinder"][0] == 2
    assert SHAPE_SIZE["sphere"][0] == 1


def test_body_xyz_bounds_for_each_shape():
    assert body_xyz([0.4, 0.2, 0.1], "box") == [0.4, 0.2, 0.1]
    assert body_xyz([0.05, 0.1], "cylinder") == [0.1, 0.1, 0.1]   # 2r, 2r, h
    assert body_xyz([0.05], "sphere") == [0.1, 0.1, 0.1]          # 2r each way
    assert body_xyz([1], "box") == [0.35, 0.30, 0.15]             # bad length -> safe default


def test_fmt_trims_trailing_zeros():
    assert _fmt(0.025) == "0.025"
    assert _fmt(10.0) == "10"
    assert _fmt(0.10) == "0.1"
