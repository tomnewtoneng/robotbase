"""The declarative robot spec and its compiler (see docs/design/robot-spec.md).

A `robot.yaml` describes a robot as *intent*; `compile_robot` turns it into a URDF, the
launch bridge wiring, the world systems it needs, and the manifest fields — so an agent
authors robots without touching XML.
"""
from robotbase.robotspec.compile import CompiledRobot, compile_robot  # noqa: F401
from robotbase.robotspec.schema import RobotSpec  # noqa: F401
