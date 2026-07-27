from robotbase.robotbench.records import TrialRecord
from robotbase.robotbench.report import compare, render_markdown


def _rec(arm, solved, claimed, edits=3, turns=5, stop="end_turn"):
    return TrialRecord(task_id="diff/reach-goal", arm=arm, model="claude-sonnet-5", trial=0,
                       seed=0, solved=solved, robustness=1.0 if solved else 0.0,
                       claimed_solved=claimed, controller_edits=edits, agent_turns=turns,
                       wall_clock_s=10.0, stop_reason=stop)


def test_compare_computes_rates_per_arm():
    recs = [_rec("with", True, True), _rec("with", True, True),
            _rec("without", False, True), _rec("without", True, True)]
    c = compare(recs)
    assert c["by_arm"]["with"]["solved_rate"] == 1.0
    assert c["by_arm"]["with"]["self_verification_accuracy"] == 1.0   # both claims matched judge
    assert c["by_arm"]["without"]["solved_rate"] == 0.5
    assert c["by_arm"]["without"]["false_positive_rate"] == 0.5       # one claimed-but-unsolved of two
    assert c["by_arm"]["with"]["n"] == 2 and c["model"] == "claude-sonnet-5"


def test_capped_runs_excluded_from_self_verification():
    # A capped run that solved-but-didn't-claim must NOT count as a self-verification error:
    # the agent was cut off ("not finished"), not mis-verifying. It DOES count toward capped_rate.
    recs = [_rec("without", solved=True, claimed=False, stop="turns_cap"),  # capped: excluded from SV
            _rec("without", solved=True, claimed=True, stop="end_turn")]    # concluded: counts
    s = compare(recs)["by_arm"]["without"]
    assert s["capped_rate"] == 0.5
    assert s["concluded_n"] == 1
    assert s["self_verification_accuracy"] == 1.0   # the one concluded run matched
    assert s["false_negative_rate"] == 0.0          # the solved-but-unclaimed run was capped, not counted


def test_false_negative_tracked_for_concluded_runs():
    # A run that concluded on its own, solved, but claimed NOT_SOLVED IS a self-verification error.
    s = compare([_rec("without", solved=True, claimed=False, stop="end_turn")])["by_arm"]["without"]
    assert s["self_verification_accuracy"] == 0.0
    assert s["false_negative_rate"] == 1.0 and s["false_positive_rate"] == 0.0


def test_render_markdown_has_headline_sections():
    md = render_markdown([_rec("with", True, True), _rec("without", False, True, stop="turns_cap")])
    assert "with" in md.lower() and "without" in md.lower()
    assert "self-verify" in md.lower() and "capped" in md.lower()   # the refined headline metrics
    assert "solved" in md.lower()
