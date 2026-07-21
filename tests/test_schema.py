import textwrap, pytest
from robotbase.schema import Scenario, Manifest, ManifestError

def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(textwrap.dedent(body))
    return str(p)

def test_scenario_parses(tmp_path):
    path = _write(tmp_path, "s.yaml", """
        version: 1
        name: stop-before-obstacle
        description: stop before the box
        timeout_seconds: 30
        setup:
          reset_world: true
          robot: {pose: {x: 0.0, y: 0.0, yaw: 0.0}}
          obstacles:
            - {id: o1, type: box, pose: {x: 2.0, y: 0.0, z: 0.25}, size: {x: 0.5, y: 1.0, z: 0.5}}
        actions:
          - {type: wait_for_topic, topic: /scan, timeout_seconds: 5}
          - {type: run_node, package: warehouse_bot, executable: obstacle_controller}
          - {type: wait, duration_seconds: 10}
        assertions:
          - {type: no_collision}
          - {type: minimum_obstacle_distance, minimum_metres: 0.25}
          - {type: robot_stopped, linear_velocity_tolerance: 0.03, angular_velocity_tolerance: 0.03}
          - {type: required_topic_messages, topic: /scan, minimum_count: 5}
    """)
    s = Scenario.from_yaml(path)
    assert s.name == "stop-before-obstacle"
    assert s.timeout_seconds == 30
    assert [a.type for a in s.assertions][0] == "no_collision"
    assert s.assertions[1].minimum_metres == 0.25

def test_manifest_rejects_bad_simulator(tmp_path):
    path = _write(tmp_path, "m.yaml", """
        version: 1
        project: {name: warehouse-bot}
        runtime: {ros_distribution: jazzy, simulator: webots}
        launch: {package: warehouse_bot_bringup, file: simulation.launch.py}
        scenarios: {directory: simulation/scenarios}
        agent: {mcp: {enabled: true, port: 4381}}
    """)
    with pytest.raises(ManifestError):
        Manifest.from_yaml(path)
