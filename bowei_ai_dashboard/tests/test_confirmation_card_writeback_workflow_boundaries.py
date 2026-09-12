from __future__ import annotations

import json

from app import models, schemas
from tests.test_confirmation_card_coach_flow import _seed_card_coach_team
from tests.test_confirmation_card_coordinator_flow import _make_card_submission
from tests.test_execution_submission_to_work_progress_flow import _make_session


def test_confirm_task_card_service_writes_only_the_selected_card():
    from app.services import confirmation_card_writeback_workflow as workflow

    db = _make_session()
    team = _seed_card_coach_team(db)
    row = _make_card_submission(db, statuses=("", ""))
    data = json.loads(row.human_result_json)
    data["task_reports"][0].update(
        {
            "result_type": "subtask_progress",
            "type": "progress",
            "matched_subtask_id": team["subtask"].id,
            "completed": "写回服务测试进展",
            "achievements": [{"name": "写回服务成果"}],
            "subtask_issues": [{"description": "写回服务问题"}],
        }
    )
    row.human_result_json = json.dumps(data, ensure_ascii=False)
    db.commit()

    result = workflow.confirm_task_card(
        submission_id=row.id,
        card_index=0,
        payload=schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )

    reports = json.loads(result["submission"]["human_result_json"])["task_reports"]
    assert reports[0]["confirmation_status"] == "confirmed"
    assert not reports[1].get("confirmation_status")
    achievement = db.query(models.Achievement).filter_by(source_submission_id=row.id).one()
    issue = db.query(models.Issue).filter_by(source_submission_id=row.id).one()
    assert achievement.related_subtask_id == team["subtask"].id
    assert issue.related_subtask_id == team["subtask"].id
