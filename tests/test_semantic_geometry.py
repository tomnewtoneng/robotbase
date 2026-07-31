import pytest

from robotbase.robotspec.semantic import (
    Box,
    Cylinder,
    Sphere,
    geometry_from_spec,
    inertial_for,
)
from robotbase.robotspec.ir import ShapeSizeError


def test_box_inertia_matches_legacy_formula():
    g = Box([0.4, 0.3, 0.2])
    m = 5.0
    inr = inertial_for(g, m)
    assert inr.ixx == pytest.approx(m * (0.3**2 + 0.2**2) / 12)
    assert inr.iyy == pytest.approx(m * (0.4**2 + 0.2**2) / 12)
    assert inr.izz == pytest.approx(m * (0.4**2 + 0.3**2) / 12)


def test_cylinder_and_sphere_inertia():
    c = inertial_for(Cylinder(0.05, 0.1), 0.5)
    assert c.izz == pytest.approx(0.5 * 0.05**2 / 2)
    s = inertial_for(Sphere(0.05), 0.1)
    assert s.ixx == pytest.approx(2 * 0.1 * 0.05**2 / 5)


def test_geometry_from_spec_validates_length():
    assert isinstance(geometry_from_spec("box", [1, 2, 3]), Box)
    with pytest.raises(ShapeSizeError):
        geometry_from_spec("box", [1, 2])
