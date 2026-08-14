import pytest
from pydantic import ValidationError

from app.services.project_meeting_agent_contracts import (
    EvidenceSpan,
    FinalEnvelope,
    MeetingAgentFinal,
    MeetingFact,
    MeetingInfo,
    TaskTarget,
    TaskUpdate,
    ToolCallEnvelope,
)


def _evidence() -> dict:
    return {
        "quote": "项目负责人确认本周完成需求评审。",
        "char_start": 12,
        "char_end": 29,
    }


def _meeting_info() -> dict:
    return {
        "title": "AI升级项目周会",
        "meeting_date": "2026-07-27",
        "meeting_type": "项目周会",
        "location": "线上会议",
        "host": "杨宇帆",
        "participants": ["杨宇帆", "吴肖"],
        "organizer": "吴肖",
        "copied_to": ["项目组成员"],
    }


def _meeting_info_evidence() -> dict:
    return {field: [_evidence()] for field in _meeting_info()}


def _final_result(**overrides) -> dict:
    result = {
        "meeting_info": _meeting_info(),
        "meeting_info_evidence": _meeting_info_evidence(),
        "summary": "会议确认需求评审已经完成，并安排下周完成开发排期。",
        "summary_evidence": [_evidence()],
        "agenda_items": [],
        "decisions": [],
        "completed_items": [],
        "next_steps": [],
        "risks": [],
        "open_questions": [],
        "task_updates": [],
    }
    result.update(overrides)
    return result


def _task_target(**overrides) -> dict:
    target = {
        "project_id": 1,
        "workstream_id": 2,
        "key_task_id": 3,
        "execution_schedule_id": 4,
    }
    target.update(overrides)
    return target


def _task_update(**overrides) -> dict:
    update = {
        "action": "update_execution_schedule",
        "target": _task_target(),
        "before": {"status": "进行中"},
        "proposed": {"status": "已完成"},
        "evidence": [_evidence()],
        "reason": "会议明确确认该项工作已完成。",
        "confidence": 0.91,
        "needs_confirmation": False,
    }
    update.update(overrides)
    return update


def test_strict_models_forbid_unknown_json_fields():
    with pytest.raises(ValidationError):
        EvidenceSpan.model_validate({**_evidence(), "source": "word"})

    with pytest.raises(ValidationError):
        MeetingInfo.model_validate({**_meeting_info(), "unknown": "不允许"})

    with pytest.raises(ValidationError):
        ToolCallEnvelope.model_validate(
            {"type": "tool_call", "tool": "get_project_context", "arguments": {}, "extra": True}
        )

    with pytest.raises(ValidationError):
        FinalEnvelope.model_validate(
            {"type": "final", "result": _final_result(), "extra": True}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"quote": "", "char_start": 0, "char_end": 1},
        {"quote": "有效证据", "char_start": -1, "char_end": 1},
        {"quote": "有效证据", "char_start": 1, "char_end": 0},
        {"quote": "有效证据", "char_start": 5, "char_end": 5},
        {"quote": "有效证据", "char_start": 5, "char_end": 4},
    ],
)
def test_evidence_span_requires_valid_text_and_offsets(payload):
    with pytest.raises(ValidationError):
        EvidenceSpan.model_validate(payload)


def test_confirmed_meeting_fact_requires_evidence():
    with pytest.raises(ValidationError):
        MeetingFact(
            content="需求评审完成",
            evidence=[],
            confidence=0.9,
            needs_confirmation=False,
        )

    pending = MeetingFact(
        content="可能需要调整开发排期",
        evidence=[],
        confidence=0.5,
        needs_confirmation=True,
    )
    assert pending.needs_confirmation is True


def test_task_target_requires_positive_identifiers_and_forbids_unknown_shape():
    assert TaskTarget.model_validate(_task_target()).key_task_id == 3

    for field in ("project_id", "workstream_id", "key_task_id"):
        with pytest.raises(ValidationError):
            TaskTarget.model_validate(_task_target(**{field: 0}))

    with pytest.raises(ValidationError):
        TaskTarget.model_validate(_task_target(target_name="错误结构"))


def test_task_update_only_allows_execution_schedule_actions_and_matching_targets():
    with pytest.raises(ValidationError):
        TaskUpdate.model_validate(_task_update(action="update_key_task"))

    with pytest.raises(ValidationError):
        TaskUpdate.model_validate(
            _task_update(target=_task_target(execution_schedule_id=None))
        )

    with pytest.raises(ValidationError):
        TaskUpdate.model_validate(
            _task_update(
                action="create_execution_schedule",
                target=_task_target(execution_schedule_id=4),
            )
        )

    created = TaskUpdate.model_validate(
        _task_update(
            action="create_execution_schedule",
            target=_task_target(execution_schedule_id=None),
            before={},
        )
    )
    assert created.target.execution_schedule_id is None


def test_executable_task_update_requires_evidence():
    with pytest.raises(ValidationError):
        TaskUpdate.model_validate(_task_update(evidence=[]))

    pending = TaskUpdate.model_validate(
        _task_update(evidence=[], needs_confirmation=True)
    )
    assert pending.needs_confirmation is True


@pytest.mark.parametrize(
    "field",
    ["title", "meeting_date", "meeting_type", "location", "host", "participants", "organizer", "copied_to"],
)
def test_final_requires_evidence_for_each_nonempty_meeting_info_field(field):
    evidence = _meeting_info_evidence()
    evidence.pop(field)

    with pytest.raises(ValidationError):
        MeetingAgentFinal.model_validate(
            _final_result(meeting_info_evidence=evidence)
        )


def test_final_rejects_unknown_meeting_info_evidence_field():
    evidence = _meeting_info_evidence()
    evidence["unknown_field"] = [_evidence()]

    with pytest.raises(ValidationError):
        MeetingAgentFinal.model_validate(
            _final_result(meeting_info_evidence=evidence)
        )


def test_final_requires_summary_evidence_when_summary_is_present():
    with pytest.raises(ValidationError):
        MeetingAgentFinal.model_validate(_final_result(summary_evidence=[]))

    no_summary = MeetingAgentFinal.model_validate(
        _final_result(summary="", summary_evidence=[])
    )
    assert no_summary.summary == ""


def test_final_and_tool_envelopes_accept_their_exact_shapes():
    final = FinalEnvelope.model_validate({"type": "final", "result": _final_result()})
    tool_call = ToolCallEnvelope.model_validate(
        {
            "type": "tool_call",
            "tool": "get_project_context",
            "arguments": {"project_id": 1},
        }
    )

    assert final.result.meeting_info.title == "AI升级项目周会"
    assert tool_call.tool == "get_project_context"
