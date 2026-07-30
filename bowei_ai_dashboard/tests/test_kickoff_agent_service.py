from app.services.kickoff_agent import normalize_agent_result, run_kickoff_agent


def test_no_change_result_still_creates_a_reviewable_conclusion():
    result = normalize_agent_result({"summary": "按原计划执行", "proposals": []}, {"tasks": []})

    assert result["start_conclusion"] == "no_change"
    assert result["proposals"] == [{"proposal_type": "no_change", "evidence": []}]


def test_agent_result_rejects_proposal_for_a_task_outside_the_frozen_snapshot():
    snapshot = {"tasks": [{"id": 10, "subtasks": []}]}
    result = run_kickoff_agent(
        "会议纪要",
        snapshot,
        lambda _prompt: {"summary": "调整", "proposals": [{"proposal_type": "update", "target_type": "task", "target_id": 99}]},
    )

    assert result["proposals"][0]["validation_errors"] == ["target_id does not belong to the frozen kickoff snapshot"]
