from __future__ import annotations

import json

from app import models
from app.services.escalation import escalate_card_to_issue
from tests.test_confirmation_card_coach_flow import _seed_card_coach_team, _submit
from tests.test_execution_submission_to_work_progress_flow import _make_session


def test_escalated_issue_keeps_project_task_and_key_task_source_links():
    db = _make_session()
    team = _seed_card_coach_team(db)
    submission_id = _submit(db, team)
    submission = db.get(models.UpdateSubmission, submission_id)
    report_data = json.loads(submission.human_result_json)
    report_data["task_reports"][0]["plan_end"] = "2026-11-30"
    submission.human_result_json = json.dumps(report_data, ensure_ascii=False)

    issue = escalate_card_to_issue(
        db=db,
        submission=submission,
        card_index=0,
        target="coordinator",
        note="请协助排查",
        caller_username="owner",
        caller_name="项目负责人",
        project_id=team["project"].id,
        decision_by_username="统筹人",
    )

    assert issue.project_id == team["project"].id
    assert issue.source_submission_id == submission_id
    assert issue.source_card_index == 0
    assert issue.related_task_id == team["task"].id
    assert issue.related_subtask_id == team["subtask"].id
    assert issue.expected_resolve_time == "2026-11-30"
