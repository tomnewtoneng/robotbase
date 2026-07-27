import pytest
sdk = pytest.importorskip("claude_agent_sdk")
from robotbase.robotbench.real_agent import RealAgent


def test_real_agent_satisfies_protocol():
    a = RealAgent(model="claude-sonnet-5")
    assert hasattr(a, "run") and callable(a.run)
