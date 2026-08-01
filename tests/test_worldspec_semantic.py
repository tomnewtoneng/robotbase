"""Task 12 — WorldSpec compiles to a typed WorldModel that the SDF backend renders."""
from robotbase.worldspec.schema import WorldSpec
from robotbase.worldspec.compile import build_world_model, compile_world
from robotbase.worldspec.semantic import WorldModel
from robotbase.worldspec.backends.sdf import render_sdf


def _spec():
    return WorldSpec.model_validate({
        "name": "w", "ground": True, "light": "sun",
        "obstacles": [{"shape": "box", "size": [1, 1, 1], "at": [2, 0, 0.5]}],
        "goals": [{"name": "g", "at": [3, 1], "radius": 0.2}],
    })


def test_build_world_model_types_the_parts_in_order():
    model = build_world_model(_spec())
    assert isinstance(model, WorldModel) and model.sun is True
    kinds = [type(m.geometry).__name__ for m in model.models]
    assert kinds == ["Plane", "Box", "Cylinder"]   # ground, obstacle, goal — in emit order
    goal = model.models[-1]
    assert goal.has_collision is False and goal.material is not None   # goal marker: visual-only


def test_compile_world_equals_rendering_the_model():
    spec = _spec()
    sdf, meta = compile_world(spec)
    assert sdf == render_sdf(build_world_model(spec))
    assert '<model name="obstacle_0">' in sdf and '<model name="goal_g">' in sdf
    assert meta["goals"]["g"] == {"at": [3, 1], "radius": 0.2}
