import pytest

from robotbase.mcp_server import validate_scenario_name


def test_known_name_ok():
    validate_scenario_name("drive-forward", ["drive-forward", "stop-before-obstacle"])


def test_unknown_name_raises():
    with pytest.raises(ValueError):
        validate_scenario_name("teleport", ["drive-forward"])
