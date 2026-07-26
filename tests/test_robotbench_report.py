from robotbase.robotbench.records import TrialRecord
from robotbase.robotbench.report import compare, render_markdown


def _rec(arm, solved, claimed, edits=3, turns=5):
    return TrialRecord(task_id="diff/reach-goal", arm=arm, model="claude-sonnet-5", trial=0,
                       seed=0, solved=solved, robustness=1.0 if solved else 0.0,
                       claimed_solved=claimed, controller_edits=edits, agent_turns=turns,
                       wall_clock_s=10.0, stop_reason="declared_done")


def test_compare_computes_rates_per_arm():
    recs = [_rec("with", True, True), _rec("with", True, True),
            _rec("without", False, True), _rec("without", True, True)]
    c = compare(recs)
    assert c["by_arm"]["with"]["solved_rate"] == 1.0
    assert c["by_arm"]["with"]["false_confidence_rate"] == 0.0
    assert c["by_arm"]["without"]["solved_rate"] == 0.5
    assert c["by_arm"]["without"]["false_confidence_rate"] == 0.5   # one claimed-but-unsolved of two
    assert c["by_arm"]["with"]["n"] == 2 and c["model"] == "claude-sonnet-5"


def test_render_markdown_has_headline_sections():
    md = render_markdown([_rec("with", True, True), _rec("without", False, True)])
    assert "with" in md.lower() and "without" in md.lower()
    assert "false" in md.lower() and "confiden" in md.lower()      # the headline metric
    assert "solved" in md.lower()
