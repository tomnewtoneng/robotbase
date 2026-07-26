import os, glob
from robotbase.robotbench.agent import AgentResult, Caps, StubAgent


def _fake_project(tmp_path):
    d = tmp_path / "proj" / "src" / "bot" / "bot"
    d.mkdir(parents=True)
    (d / "controller.py").write_text("# starter\n")
    return str(tmp_path / "proj")


def test_stub_agent_writes_controller_and_reports(tmp_path):
    proj = _fake_project(tmp_path)
    res = StubAgent(solution="# solved\n", claim=True, edits=3, turns=7).run(
        proj, "with", {"scenario": "reach-goal"}, Caps())
    assert isinstance(res, AgentResult)
    assert res.claimed_solved is True and res.controller_edits == 3 and res.agent_turns == 7
    written = glob.glob(os.path.join(proj, "src", "*", "*", "controller.py"))[0]
    assert open(written).read() == "# solved\n"


def test_caps_have_sensible_defaults():
    c = Caps()
    assert c.max_edits == 15 and c.max_turns == 40 and c.timeout_s == 1200
