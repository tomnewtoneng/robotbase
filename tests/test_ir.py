import math
import pytest
from robotbase.robotspec.ir import Fragment, LinkIR, UnknownShape, link_from_shape


def test_box_link_has_geometry_and_computed_inertia():
    link = link_from_shape("base_link", "box", [0.4, 0.2, 0.1], 6.0)
    assert isinstance(link, LinkIR) and link.name == "base_link"
    assert '<box size="0.4 0.2 0.1"/>' in link.xml
    # box ixx = m*(y^2+z^2)/12 = 6*(0.04+0.01)/12 = 0.025
    assert 'ixx="0.025"' in link.xml
    assert "<visual>" in link.xml and "<collision>" in link.xml and "<inertial>" in link.xml


def test_cylinder_and_sphere_shapes():
    cyl = link_from_shape("mast", "cylinder", [0.03, 0.5], 0.2)
    assert '<cylinder radius="0.03" length="0.5"/>' in cyl.xml
    sph = link_from_shape("ball", "sphere", [0.05], 0.1)
    assert '<sphere radius="0.05"/>' in sph.xml
    # sphere inertia = 2/5 m r^2 = 0.4*0.1*0.0025 = 0.0001
    assert 'ixx="0.0001"' in sph.xml


def test_unknown_shape_raises():
    with pytest.raises(UnknownShape):
        link_from_shape("x", "torus", [1], 1.0)


def test_fragment_defaults_are_independent():
    a, b = Fragment(), Fragment()
    a.links.append(LinkIR("l", "<link/>"))
    assert b.links == []          # default_factory, not a shared mutable
