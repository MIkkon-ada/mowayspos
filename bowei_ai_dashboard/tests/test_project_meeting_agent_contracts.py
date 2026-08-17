from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.services.project_meeting_agent_contracts import (
    EvidenceSpan,
    FinalEnvelope,
    FieldProvenance,
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


def _analysis_payload() -> dict:
    return {
        "meeting_facts": [
            {
                "fact_id": "F001",
                "fact_type": "completion",
                "content": "客户清单第一版已经完成",
                "fields": {
                    "status": {
                        "value": "completed",
                        "raw_text": "已经完成",
                        "evidence": [_evidence()],
                        "provenance": {
                            "source_type": "meeting_fact",
                            "source_fact_id": "F001",
                            "usage": "new",
                        },
                    }
                },
                "meeting_evidence": [_evidence()],
                "confidence": 0.9,
                "needs_confirmation": False,
            }
        ],
        "project_matches": [
            {
                "match_id": "M001",
                "fact_id": "F001",
                "target_type": "execution_schedule",
                "target_id": 30,
                "workstream_id": 10,
                "key_task_id": 20,
                "confidence": 0.95,
                "reasons": ["标题一致"],
                "project_evidence": [
                    {
                        "source_object": "execution_schedule:30",
                        "field": "title",
                        "value": "客户清单第一版",
                    }
                ],
            }
        ],
        "project_deltas": [
            {
                "delta_id": "D001",
                "source_fact_id": "F001",
                "source_match_id": "M001",
                "delta_type": "PROGRESS_UPDATE",
                "reasoning": "会议确认完成，项目基线仍为进行中",
            }
        ],
        "proposed_changes": [
            {
                "change_id": "C001",
                "source_fact_id": "F001",
                "source_match_id": "M001",
                "source_delta_id": "D001",
                "action": "update_execution_schedule",
                "target": {
                    "project_id": 1,
                    "workstream_id": 10,
                    "key_task_id": 20,
                    "execution_schedule_id": 30,
                },
                "before": {},
                "proposed": {"status": "completed"},
                "field_sources": {
                    "status": {
                        "source_type": "meeting_fact",
                        "source_fact_id": "F001",
                        "usage": "new",
                    }
                },
                "requires_confirmation": True,
            }
        ],
        "unmatched_items": [],
        "needs_confirmation": [],
    }


def _analysis_final(**overrides) -> dict:
    analysis = _analysis_payload()
    analysis.update(overrides)
    return _final_result(**analysis)


def test_analysis_contract_accepts_complete_fact_match_delta_change_lineage():
    final = MeetingAgentFinal.model_validate(_analysis_final())

    assert final.meeting_facts[0].fact_id == "F001"
    assert final.proposed_changes[0].change_id == "C001"


@pytest.mark.parametrize("prefix", ["F", "M", "D", "C"])
def test_analysis_contract_accepts_three_digit_nonzero_stable_ids(prefix):
    payload = _analysis_final()
    identifiers = {
        "F": ("meeting_facts", "fact_id"),
        "M": ("project_matches", "match_id"),
        "D": ("project_deltas", "delta_id"),
        "C": ("proposed_changes", "change_id"),
    }
    collection, field = identifiers[prefix]
    payload[collection][0][field] = f"{prefix}001"

    assert MeetingAgentFinal.model_validate(payload)


@pytest.mark.parametrize("prefix", ["F", "M", "D", "C"])
def test_analysis_contract_rejects_all_zero_stable_ids(prefix):
    payload = _analysis_final()
    identifiers = {
        "F": ("meeting_facts", "fact_id"),
        "M": ("project_matches", "match_id"),
        "D": ("project_deltas", "delta_id"),
        "C": ("proposed_changes", "change_id"),
    }
    collection, field = identifiers[prefix]
    payload[collection][0][field] = f"{prefix}000"

    with pytest.raises(ValidationError, match=field):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_duplicate_fact_ids():
    payload = _analysis_final()
    payload["meeting_facts"].append(payload["meeting_facts"][0].copy())

    with pytest.raises(ValidationError, match="duplicate fact_id"):
        MeetingAgentFinal.model_validate(payload)


@pytest.mark.parametrize(
    ("collection", "identifier"),
    [
        ("project_matches", "match_id"),
        ("project_deltas", "delta_id"),
        ("proposed_changes", "change_id"),
    ],
)
def test_analysis_contract_rejects_duplicate_lineage_ids(collection, identifier):
    payload = _analysis_final()
    payload[collection].append(payload[collection][0].copy())

    with pytest.raises(ValidationError, match=f"duplicate {identifier}"):
        MeetingAgentFinal.model_validate(payload)


@pytest.mark.parametrize("collection", ["unmatched_items", "needs_confirmation"])
def test_analysis_contract_rejects_fact_ids_reused_across_analysis_collections(collection):
    payload = _analysis_final()
    payload[collection].append(payload["meeting_facts"][0].copy())

    with pytest.raises(ValidationError, match="duplicate fact_id"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_writable_chain_from_unmatched_fact():
    payload = _analysis_final()
    payload["unmatched_items"].append(payload["meeting_facts"].pop())

    with pytest.raises(ValidationError, match="normal meeting_facts"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_broken_delta_to_match_reference():
    payload = _analysis_final()
    payload["project_deltas"][0]["source_match_id"] = "M999"

    with pytest.raises(ValidationError, match="unknown match_id"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_broken_change_to_delta_reference():
    payload = _analysis_final()
    payload["proposed_changes"][0]["source_delta_id"] = "D999"

    with pytest.raises(ValidationError, match="unknown delta_id"):
        MeetingAgentFinal.model_validate(payload)


@pytest.mark.parametrize("source_fact_id", ["F999", "F000"])
def test_analysis_contract_rejects_field_provenance_for_unknown_fact(source_fact_id):
    payload = _analysis_final()
    payload["meeting_facts"][0]["fields"]["status"]["provenance"]["source_fact_id"] = (
        source_fact_id
    )

    with pytest.raises(ValidationError, match="field provenance source_fact_id"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_field_provenance_for_different_known_fact():
    payload = _analysis_final()
    second_fact = payload["meeting_facts"][0].copy()
    second_fact["fact_id"] = "F002"
    second_fact["fields"]["status"]["provenance"]["source_fact_id"] = "F002"
    payload["meeting_facts"].append(second_fact)
    payload["meeting_facts"][0]["fields"]["status"]["provenance"]["source_fact_id"] = "F002"

    with pytest.raises(ValidationError, match="must match enclosing fact_id"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_meeting_fact_change_source_without_same_field():
    payload = _analysis_final()
    payload["meeting_facts"][0]["fields"] = {}

    with pytest.raises(ValidationError, match="does not contain proposed field: status"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_proposed_field_from_different_fact_than_change():
    payload = _analysis_final()
    second_fact = deepcopy(payload["meeting_facts"][0])
    second_fact["fact_id"] = "F002"
    second_fact["fields"]["status"]["provenance"]["source_fact_id"] = "F002"
    payload["meeting_facts"].append(second_fact)
    payload["proposed_changes"][0]["field_sources"]["status"]["source_fact_id"] = "F002"

    with pytest.raises(ValidationError, match="must match proposed change source_fact_id"):
        MeetingAgentFinal.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "source_type": "meeting_fact",
            "source_fact_id": "F001",
            "source_object": "execution_schedule:30",
            "usage": "new",
        },
        {
            "source_type": "project_baseline",
            "source_fact_id": "F001",
            "source_object": "execution_schedule:30",
            "source_field": "status",
            "usage": "inherit",
        },
        {
            "source_type": "human_edit",
            "source_object": "execution_schedule:30",
            "usage": "override",
        },
    ],
)
def test_field_provenance_rejects_irrelevant_source_references(payload):
    with pytest.raises(ValidationError, match="must not include"):
        FieldProvenance.model_validate(payload)


@pytest.mark.parametrize(
    ("source_type", "source_fields", "usage", "message"),
    [
        ("meeting_fact", {"source_fact_id": "F001"}, "inherit", "meeting_fact source"),
        (
            "project_baseline",
            {"source_object": "execution_schedule:30", "source_field": "status"},
            "new",
            "project_baseline source",
        ),
        ("human_edit", {}, "new", "human_edit source"),
    ],
)
def test_field_provenance_rejects_invalid_usage(source_type, source_fields, usage, message):
    payload = _analysis_final()
    source = {
        "source_type": source_type,
        "usage": usage,
        **source_fields,
    }
    payload["meeting_facts"][0]["fields"]["status"]["provenance"] = source

    with pytest.raises(ValidationError, match=message):
        MeetingAgentFinal.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("raw_text", ""), ("evidence", [])],
)
def test_sourced_value_requires_raw_word_expression_and_field_evidence(field, value):
    payload = _analysis_final()
    payload["meeting_facts"][0]["fields"]["status"][field] = value

    with pytest.raises(ValidationError, match=field):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_missing_or_extra_proposed_field_provenance():
    payload = _analysis_final()
    payload["proposed_changes"][0]["field_sources"] = {}

    with pytest.raises(ValidationError, match="field_sources"):
        MeetingAgentFinal.model_validate(payload)

    payload = _analysis_final()
    payload["proposed_changes"][0]["field_sources"]["assignee"] = {
        "source_type": "meeting_fact",
        "source_fact_id": "F001",
        "usage": "new",
    }
    with pytest.raises(ValidationError, match="field_sources"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_invalid_relationships_and_model_human_edits():
    payload = _analysis_final()
    payload["project_matches"][0]["fact_id"] = "F999"
    with pytest.raises(ValidationError, match="unknown fact_id"):
        MeetingAgentFinal.model_validate(payload)

    payload = _analysis_final()
    payload["proposed_changes"][0]["field_sources"]["status"] = {
        "source_type": "human_edit",
        "usage": "override",
    }
    with pytest.raises(ValidationError, match="human_edit"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_inference_as_writable_source():
    payload = _analysis_final()
    payload["proposed_changes"][0]["field_sources"]["status"] = {
        "source_type": "inference",
        "usage": "new",
    }

    with pytest.raises(ValidationError, match="source_type"):
        MeetingAgentFinal.model_validate(payload)


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


def test_action_fact_structured_columns_must_be_grounded_in_its_evidence():
    evidence = [EvidenceSpan(quote="温会林完成计划分解，期限2026-08-03", char_start=0, char_end=20)]
    fact = MeetingFact(
        content="完成计划分解",
        owner="温会林",
        due_date="2026-08-03",
        evidence=evidence,
        confidence=0.9,
        needs_confirmation=False,
    )
    assert fact.owner == "温会林"
    assert fact.due_date == "2026-08-03"

    with pytest.raises(ValidationError):
        MeetingFact(
            content="完成计划分解",
            owner="未在原文出现的人",
            evidence=evidence,
            confidence=0.9,
            needs_confirmation=False,
        )


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


def test_all_task_updates_require_evidence_even_when_confirmation_is_needed():
    with pytest.raises(ValidationError):
        TaskUpdate.model_validate(_task_update(evidence=[]))

    with pytest.raises(ValidationError):
        TaskUpdate.model_validate(
            _task_update(evidence=[], needs_confirmation=True)
        )


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
