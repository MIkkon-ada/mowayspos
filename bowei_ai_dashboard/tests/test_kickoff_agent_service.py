from app.services.kickoff_agent import normalize_agent_result


def test_no_change_result_still_creates_a_reviewable_conclusion():
    result = normalize_agent_result({"summary": "按原计划执行", "proposals": []}, {"tasks": []})

    assert result["start_conclusion"] == "no_change"
    assert result["proposals"] == [{"proposal_type": "no_change", "evidence": []}]
