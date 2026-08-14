from __future__ import annotations

from copy import deepcopy

from app.services.project_meeting_agent_contracts import MeetingAgentFinal
from app.services.project_meeting_minutes import normalize_project_meeting_agent_result


DOCUMENT = "客户清单已经完成，计划仍在进行中，截止日期为2026年8月20日，开始日期为2026-08-21。"


def _span(quote: str) -> dict:
    start = DOCUMENT.index(quote)
    return {"quote": quote, "char_start": start, "char_end": start + len(quote)}


def _snapshot() -> dict:
    return {
        "project_id": 1,
        "members": [],
        "workstreams": [
            {
                "id": 10,
                "key_task": "交付",
                "key_tasks": [
                    {
                        "id": 20,
                        "title": "客户清单",
                        "status": "in_progress",
                        "execution_schedules": [
                            {"id": 30, "title": "客户清单第一版", "status": "in_progress", "due_date": "2026-08-20"}
                        ],
                    }
                ],
            }
        ],
    }


def _payload(**overrides) -> dict:
    fact = {
        "fact_id": "F001", "fact_type": "completion", "content": "客户清单已经完成",
        "fields": {
            "status": {
                "value": "completed", "raw_text": "已经完成", "evidence": [_span("已经完成")],
                "provenance": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"},
            }
        },
        "meeting_evidence": [_span("客户清单已经完成")], "confidence": 0.9, "needs_confirmation": False,
    }
    match = {
        "match_id": "M001", "fact_id": "F001", "target_type": "execution_schedule", "target_id": 30,
        "workstream_id": 10, "key_task_id": 20, "confidence": 0.9, "reasons": ["标题匹配"],
        "project_evidence": [{"source_object": "execution_schedule:30", "field": "title", "value": "客户清单第一版"}],
    }
    delta = {"delta_id": "D001", "source_fact_id": "F001", "source_match_id": "M001", "delta_type": "PROGRESS_UPDATE", "reasoning": "项目基线仍为进行中"}
    change = {
        "change_id": "C001", "source_fact_id": "F001", "source_match_id": "M001", "source_delta_id": "D001",
        "action": "update_execution_schedule", "target": {"project_id": 1, "workstream_id": 10, "key_task_id": 20, "execution_schedule_id": 30},
        "before": {"status": "in_progress"}, "proposed": {"status": "completed"},
        "field_sources": {"status": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"}},
        "requires_confirmation": True,
    }
    payload = {
        "meeting_info": {"title": "", "meeting_date": "", "meeting_type": "", "location": "", "host": "", "participants": [], "organizer": "", "copied_to": []},
        "meeting_info_evidence": {}, "summary": "", "summary_evidence": [], "agenda_items": [], "decisions": [],
        "completed_items": [], "next_steps": [], "risks": [], "open_questions": [], "task_updates": [],
        "meeting_facts": [fact], "project_matches": [match], "project_deltas": [delta], "proposed_changes": [change],
        "unmatched_items": [], "needs_confirmation": [],
    }
    payload.update(overrides)
    return payload


def _normalize(**overrides) -> dict:
    return normalize_project_meeting_agent_result(MeetingAgentFinal.model_validate(_payload(**overrides)), DOCUMENT, _snapshot())


def test_normalize_uses_field_level_word_evidence_and_deterministic_status_date_rules():
    payload = _payload()
    fact = payload["meeting_facts"][0]
    fact["fields"]["due_date"] = {
        "value": "2026-08-20", "raw_text": "2026年8月20日", "evidence": [_span("2026年8月20日")],
        "provenance": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"},
    }
    fact["fields"]["assignee"] = {
        "value": "张三", "raw_text": "张三", "evidence": [_span("已经完成")],
        "provenance": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"},
    }
    fact["fields"]["start_date"] = {
        "value": "2026-08-21", "raw_text": "2026-08-21", "evidence": [_span("2026-08-21")],
        "provenance": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"},
    }

    result = _normalize(meeting_facts=payload["meeting_facts"])

    fields = result["meeting_facts"][0]["fields"]
    assert fields["status"]["value"] == "completed"
    assert fields["due_date"]["value"] == "2026-08-20"
    assert fields["start_date"]["value"] == "2026-08-21"
    assert fields["assignee"]["validation"]["state"] == "blocked"
    assert "raw_text" in fields["assignee"]["validation"]["errors"][0]


def test_normalize_allows_inference_delta_without_fabricated_word_reasoning():
    result = _normalize()

    assert result["project_deltas"][0]["validation"]["state"] == "ready"
    assert result["project_deltas"][0]["reasoning"] == "项目基线仍为进行中"
    assert result["execution_schedule_changes"][0]["validation"]["state"] == "ready"


def test_normalize_rejects_snapshot_external_targets_and_project_evidence():
    payload = _payload()
    payload["project_matches"][0]["target_id"] = 999
    result = _normalize(project_matches=payload["project_matches"])
    assert result["project_matches"][0]["validation"]["state"] == "blocked"

    payload = _payload()
    payload["project_matches"][0]["project_evidence"][0]["value"] = "伪造标题"
    result = _normalize(project_matches=payload["project_matches"])
    assert result["project_matches"][0]["validation"]["state"] == "blocked"


def test_normalize_rejects_snapshot_target_with_wrong_existing_parent():
    snapshot = _snapshot()
    snapshot["workstreams"].append({"id": 11, "key_task": "其他工作", "key_tasks": [{"id": 21, "title": "其他任务", "execution_schedules": []}]})
    payload = _payload()
    payload["project_matches"][0]["workstream_id"] = 11
    payload["proposed_changes"][0]["target"]["workstream_id"] = 11

    result = normalize_project_meeting_agent_result(MeetingAgentFinal.model_validate(payload), DOCUMENT, snapshot)

    assert result["project_matches"][0]["validation"]["state"] == "blocked"
    assert result["proposed_changes"][0]["validation"]["state"] == "blocked"


def test_normalize_rejects_change_target_that_differs_from_matched_schedule():
    snapshot = _snapshot()
    snapshot["workstreams"][0]["key_tasks"][0]["execution_schedules"].append(
        {"id": 31, "title": "客户清单第二批", "status": "in_progress"}
    )
    payload = _payload()
    payload["proposed_changes"][0]["target"]["execution_schedule_id"] = 31

    result = normalize_project_meeting_agent_result(MeetingAgentFinal.model_validate(payload), DOCUMENT, snapshot)

    assert result["project_matches"][0]["validation"]["state"] == "ready"
    assert result["proposed_changes"][0]["validation"]["state"] == "blocked"
    assert any(
        "does not match project match target" in error
        for error in result["proposed_changes"][0]["validation"]["errors"]
    )


def test_ambiguous_delta_cannot_project_a_writable_legacy_change():
    payload = _payload()
    payload["project_deltas"][0]["delta_type"] = "AMBIGUOUS"

    result = _normalize(project_deltas=payload["project_deltas"])

    assert result["proposed_changes"][0]["validation"]["state"] == "blocked"
    assert result["execution_schedule_changes"] == []


def test_baseline_provenance_must_exactly_reference_snapshot_field():
    payload = _payload()
    change = payload["proposed_changes"][0]
    change["proposed"] = {"due_date": "2026-08-20"}
    change["field_sources"] = {
        "due_date": {"source_type": "project_baseline", "source_object": "execution_schedule:30", "source_field": "due_date", "usage": "inherit"}
    }
    result = _normalize(proposed_changes=[change])
    assert result["proposed_changes"][0]["validation"]["state"] == "ready"

    invalid = deepcopy(change)
    invalid["field_sources"]["due_date"]["source_field"] = "status"
    result = _normalize(proposed_changes=[invalid])
    assert result["proposed_changes"][0]["validation"]["state"] == "blocked"
