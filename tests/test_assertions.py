from robotbase.schema import AssertionSpec
from robotbase.results import Metrics
from robotbase.assertions import evaluate

BASE = dict(collision_count=0, minimum_obstacle_distance_metres=0.4,
            distance_travelled_metres=2.0, final_linear_velocity=0.0,
            final_angular_velocity=0.0, topic_message_counts={"/scan": 20})

def m(**over): return Metrics(**{**BASE, **over})

def test_no_collision_pass_and_fail():
    assert evaluate(AssertionSpec(type="no_collision"), m()).passed is True
    assert evaluate(AssertionSpec(type="no_collision"), m(collision_count=1)).passed is False

def test_min_distance():
    spec = AssertionSpec(type="minimum_obstacle_distance", minimum_metres=0.25)
    assert evaluate(spec, m(minimum_obstacle_distance_metres=0.4)).passed is True
    assert evaluate(spec, m(minimum_obstacle_distance_metres=0.1)).passed is False

def test_robot_stopped():
    spec = AssertionSpec(type="robot_stopped", linear_velocity_tolerance=0.03,
                         angular_velocity_tolerance=0.03)
    assert evaluate(spec, m(final_linear_velocity=0.01, final_angular_velocity=0.0)).passed is True
    assert evaluate(spec, m(final_linear_velocity=0.2)).passed is False

def test_required_topic_messages():
    spec = AssertionSpec(type="required_topic_messages", topic="/scan", minimum_count=5)
    assert evaluate(spec, m(topic_message_counts={"/scan": 20})).passed is True
    assert evaluate(spec, m(topic_message_counts={"/scan": 2})).passed is False

def test_unknown_type_fails():
    assert evaluate(AssertionSpec(type="teleport_check"), m()).passed is False
