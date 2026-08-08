from robotbase.schema import Scenario


def test_run_policy_action_parses():
    s = Scenario(**{
        "version": 1, "name": "p",
        "actions": [{"type": "run_policy", "module": "policy", "class_name": "Policy", "rate_hz": 20.0}],
    })
    a = s.actions[0]
    assert a.type == "run_policy" and a.module == "policy"
    assert a.class_name == "Policy" and a.rate_hz == 20.0


def test_run_policy_defaults():
    s = Scenario(**{"version": 1, "name": "p", "actions": [{"type": "run_policy"}]})
    a = s.actions[0]
    assert a.module is None and a.class_name is None and a.rate_hz is None
