from __future__ import annotations
import yaml
from pydantic import BaseModel, ValidationError

SUPPORTED_DISTROS = {"jazzy"}
SUPPORTED_SIMULATORS = {"gazebo-harmonic"}

class ManifestError(ValueError): ...
class ScenarioError(ValueError): ...

class Pose(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0

class Size(BaseModel):
    x: float
    y: float
    z: float

class ObstacleSpec(BaseModel):
    id: str
    type: str = "box"
    pose: Pose
    size: Size

class RobotSetup(BaseModel):
    pose: Pose = Pose()

class SetupSpec(BaseModel):
    reset_world: bool = True
    robot: RobotSetup = RobotSetup()
    obstacles: list[ObstacleSpec] = []

class ActionSpec(BaseModel):
    type: str
    topic: str | None = None
    timeout_seconds: float | None = None
    duration_seconds: float | None = None
    package: str | None = None
    executable: str | None = None

class AssertionSpec(BaseModel):
    type: str
    minimum_metres: float | None = None
    minimum_distance_metres: float | None = None
    linear_velocity_tolerance: float | None = None
    angular_velocity_tolerance: float | None = None
    topic: str | None = None
    minimum_count: int | None = None
    target_x: float | None = None
    target_y: float | None = None
    position_tolerance_metres: float | None = None
    joint_targets: dict[str, float] | None = None
    joint_tolerance: float | None = None

class PoseJitter(BaseModel):
    x: float = 0.0     # ± range (metres) added uniformly
    y: float = 0.0
    yaw: float = 0.0   # ± range (radians)

class RandomizeSpec(BaseModel):
    robot_pose: PoseJitter = PoseJitter()
    obstacles: PoseJitter = PoseJitter()   # applied to each obstacle's x/y

class Scenario(BaseModel):
    version: int
    name: str
    description: str = ""
    timeout_seconds: float = 30
    setup: SetupSpec = SetupSpec()
    actions: list[ActionSpec] = []
    assertions: list[AssertionSpec] = []
    randomize: RandomizeSpec = RandomizeSpec()

    @classmethod
    def from_yaml(cls, path: str) -> "Scenario":
        with open(path) as f:
            data = yaml.safe_load(f)
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise ScenarioError(str(e)) from e

class RecordingSpec(BaseModel):
    enabled: bool = True
    topics: list[str] = []       # [] = record all available topics
    exclude: list[str] = []      # deny-list, e.g. [/image] to skip heavy camera frames
    max_duration_seconds: int = 60

class Manifest(BaseModel):
    project_name: str
    ros_distribution: str
    simulator: str
    launch_package: str
    launch_file: str
    scenarios_dir: str
    mcp_port: int
    world_name: str = "warehouse"
    robot_name: str = "warehouse_bot"
    ready_topics: list[str] = ["/scan", "/odom"]
    fixed_base: bool = False
    recording: RecordingSpec = RecordingSpec()

    @classmethod
    def from_yaml(cls, path: str) -> "Manifest":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            m = cls(
                project_name=data["project"]["name"],
                ros_distribution=data["runtime"]["ros_distribution"],
                simulator=data["runtime"]["simulator"],
                launch_package=data["launch"]["package"],
                launch_file=data["launch"]["file"],
                scenarios_dir=data["scenarios"]["directory"],
                mcp_port=data["agent"]["mcp"]["port"],
                world_name=data.get("simulation", {}).get("world_name", "warehouse"),
                robot_name=data.get("robot", {}).get("name", "warehouse_bot"),
                ready_topics=data.get("runtime", {}).get("ready_topics", ["/scan", "/odom"]),
                fixed_base=data.get("runtime", {}).get("fixed_base", False),
                recording=RecordingSpec(**(data.get("recording") or {})),
            )
        except (KeyError, TypeError, ValidationError) as e:
            raise ManifestError(f"Invalid manifest: {e}") from e
        if data.get("version") != 1:
            raise ManifestError("Unsupported manifest version")
        if m.ros_distribution not in SUPPORTED_DISTROS:
            raise ManifestError(f"Unsupported ROS distribution: {m.ros_distribution}")
        if m.simulator not in SUPPORTED_SIMULATORS:
            raise ManifestError(f"Unsupported simulator: {m.simulator}")
        return m
