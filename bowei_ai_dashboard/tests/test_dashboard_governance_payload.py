from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain import submission_status as SS
from app.routers import dashboard


def record(**values):
    return SimpleNamespace(**values)


def governance_fixture():
    workstream = record(
        id=10,
        project_id=7,
        special_project="示例项目",
        key_task="AI升级计划",
        owner="杨宇帆",
        plan_time="2026-08",
        status="进行中",
    )
    key_task = record(
        id=101,
        task_id=10,
        title="试点升级",
        assignee="杨宇帆",
        assignee_id=1,
        collaborator_ids=[2, 3],
        due_date=date(2026, 8, 29),
        due_label="试点上线",
        plan_time="2026-08",
        status="进行中",
    )
    decision = record(
        id=201,
        project_id=7,
        description="确认预算方案",
        issue_type="需决策",
        need_decision_by="企业教练",
        status="待决策",
        priority="高",
        expected_resolve_time="2026-08-28",
        updated_at=datetime(2026, 8, 20, 9, 0, 0),
        related_task_id=10,
        related_subtask_id=101,
    )
    coordination = record(
        id=202,
        project_id=7,
        description="补齐业务验收确认",
        issue_type="问题",
        need_decision_by="",
        status="待协调",
        priority="中",
        expected_resolve_time="2026-08-27",
        updated_at=datetime(2026, 8, 21, 9, 0, 0),
        related_task_id=10,
        related_subtask_id=101,
    )
    confirmed = record(
        id=301,
        project_id=7,
        title="已确认的试点进展",
        submitter="刘万超",
        confirm_status=SS.S_CONFIRMED,
        related_task_id=10,
        related_subtask_id=101,
        created_at=datetime(2026, 8, 21, 9, 0, 0),
    )
    pending_owner = record(
        id=302,
        project_id=7,
        title="等待负责人确认的试点进展",
        submitter="吴肖",
        confirm_status=SS.S_PENDING_OWNER,
        related_task_id=10,
        related_subtask_id=101,
        created_at=datetime(2026, 8, 22, 9, 0, 0),
    )
    people = {2: record(id=2, name="刘万超"), 3: record(id=3, name="吴肖")}
    return workstream, key_task, decision, coordination, confirmed, pending_owner, people


def test_governance_payload_prioritizes_actions_and_exposes_keytask_signals():
    builder = getattr(dashboard, "_build_governance_payload", None)
    assert callable(builder), "dashboard governance payload builder is required"

    workstream, key_task, decision, coordination, confirmed, pending_owner, people = governance_fixture()
    payload = builder(
        workstreams=[workstream],
        key_tasks=[key_task],
        issues=[decision, coordination],
        submissions=[confirmed, pending_owner],
        people_by_id=people,
        can_view_decisions=True,
        can_view_risks=True,
        can_view_submissions=True,
    )

    assert payload["signals"] == {
        "pending_decisions": 1,
        "pending_coordination": 1,
        "pending_owner_confirmation": 1,
    }
    assert [action["kind"] for action in payload["actions"]] == [
        "decision",
        "coordination",
        "owner_confirmation",
    ]
    initiative = payload["initiatives"][0]
    assert initiative["key_task_id"] == 101
    assert initiative["workstream_id"] == 10
    assert initiative["workstream_title"] == "AI升级计划"
    assert initiative["accountable_owner"] == "杨宇帆"
    assert initiative["collaborators"] == [{"id": 2, "name": "刘万超"}, {"id": 3, "name": "吴肖"}]
    assert initiative["next_milestone"] == "试点上线"
    assert initiative["next_milestone_at"] == "2026-08-29"
    assert initiative["evidence_confirmed"] == 1
    assert initiative["evidence_total"] == 2
    assert initiative["health"] == "watch"


def test_governance_payload_hides_restricted_decision_and_evidence_signals():
    builder = getattr(dashboard, "_build_governance_payload", None)
    assert callable(builder), "dashboard governance payload builder is required"

    workstream, key_task, decision, coordination, confirmed, pending_owner, people = governance_fixture()
    payload = builder(
        workstreams=[workstream],
        key_tasks=[key_task],
        issues=[decision, coordination],
        submissions=[confirmed, pending_owner],
        people_by_id=people,
        can_view_decisions=False,
        can_view_risks=False,
        can_view_submissions=False,
    )

    assert payload["signals"] == {
        "pending_decisions": 0,
        "pending_coordination": 0,
        "pending_owner_confirmation": 0,
    }
    assert payload["actions"] == []
    assert payload["initiatives"][0]["evidence_confirmed"] == 0
    assert payload["initiatives"][0]["evidence_total"] == 0


def test_all_dashboard_overview_paths_include_governance_contract():
    source = (BACKEND_ROOT / "app" / "routers" / "dashboard.py").read_text(encoding="utf-8")

    assert source.count('"governance":') >= 3
    assert source.count("governance = _build_governance_payload(") == 2
    assert source.count('"governance":         governance') == 1
    assert source.count('"governance":        governance') == 1
