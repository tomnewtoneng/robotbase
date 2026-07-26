from robotbase.robotbench.records import TrialRecord, false_confidence, BENCHMARK_VERSION


def test_record_defaults_and_roundtrip():
    r = TrialRecord(task_id="diff/reach-goal", arm="without", model="claude-sonnet-5", trial=0,
                    seed=7, solved=False, robustness=0.33, claimed_solved=True,
                    controller_edits=4, agent_turns=9, wall_clock_s=61.2, stop_reason="declared_done")
    assert r.benchmark_version == BENCHMARK_VERSION
    assert r.tokens is None and r.transcript_path is None
    assert r.model_dump()["arm"] == "without"


def test_false_confidence_flags_claimed_but_unsolved():
    base = dict(task_id="t", arm="without", model="m", trial=0, seed=0, robustness=0.0,
                controller_edits=1, agent_turns=1, wall_clock_s=1.0, stop_reason="timeout")
    assert false_confidence(TrialRecord(solved=False, claimed_solved=True, **base)) is True
    assert false_confidence(TrialRecord(solved=True, claimed_solved=True, **base)) is False
    assert false_confidence(TrialRecord(solved=False, claimed_solved=False, **base)) is False
