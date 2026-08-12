import hashlib
from datetime import date

import pytest

from app.services.meeting_validation import (
    VALIDATION_STATES,
    validate_action_owner,
    validate_candidate,
    validate_candidates,
    resolve_temporal_expression,
    validate_evidence,
)


def test_validation_states_exposes_expected_members():
    assert VALIDATION_STATES == {
        "passed",
        "warning",
        "needs_confirmation",
        "blocked",
    }


def test_validate_evidence_returns_empty_list_for_fully_valid_reference():
    transcript = "会议结论：请在周三前补充材料。"
    quote = transcript[2:6]
    ref = {"start": 2, "end": 6, "quote": quote}

    expected_hash = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    assert validate_evidence(ref, transcript, expected_hash) == []


@pytest.mark.parametrize(
    ("ref", "transcript", "expected_hash"),
    [
        ({"start": -1, "end": 2, "quote": "会议"}, "会议纪要", "sha256:placeholder"),
        ({"start": 1, "end": 100, "quote": "纪要"}, "会议纪要", "sha256:placeholder"),
        ({"start": 0, "end": 2, "quote": "不匹配"}, "会议纪要", "sha256:placeholder"),
    ],
)
def test_validate_evidence_blocks_invalid_span_or_mismatch(ref, transcript, expected_hash):
    result = validate_evidence(ref, transcript, expected_hash)

    assert result
    assert all(item["status"] == "blocked" for item in result)


@pytest.mark.parametrize(
    ("ref", "transcript", "expected_hash"),
    [
        ({"start": 0, "end": 3, "quote": "evi"}, "evidence", None),
        ({"start": 0, "end": 3, "quote": None}, "evidence", "sha256:placeholder"),
        ({"start": True, "end": 4, "quote": "vid"}, "evidence", hashlib.sha256(b"vid").hexdigest()),
        ({"start": 0, "end": False, "quote": ""}, "evidence", hashlib.sha256(b"").hexdigest()),
        ({"start": 0, "end": 3, "quote": "evi"}, None, "sha256:placeholder"),
        (None, "evidence", "sha256:placeholder"),
    ],
)
def test_validate_evidence_blocks_invalid_input_without_raising(ref, transcript, expected_hash):
    result = validate_evidence(ref, transcript, expected_hash)

    assert result
    assert all(item["status"] == "blocked" for item in result)


def test_resolve_temporal_expression_supports_next_week_and_next_wednesday():
    reference_date = date(2026, 8, 3)

    assert resolve_temporal_expression("下周", reference_date) == {
        "expression": "下周",
        "start": "2026-08-10",
        "end": "2026-08-16",
        "status": "passed",
        "reference_date": "2026-08-03",
        "timezone": "Asia/Shanghai",
    }

    assert resolve_temporal_expression("下周三", reference_date) == {
        "expression": "下周三",
        "start": "2026-08-12",
        "end": "2026-08-12",
        "status": "passed",
        "reference_date": "2026-08-03",
        "timezone": "Asia/Shanghai",
    }


def test_resolve_temporal_expression_supports_relative_days_and_this_friday():
    reference_date = date(2026, 8, 3)

    assert resolve_temporal_expression("明天", reference_date)["start"] == "2026-08-04"
    assert resolve_temporal_expression("后天", reference_date)["start"] == "2026-08-05"
    assert resolve_temporal_expression("本周五", reference_date)["start"] == "2026-08-07"


@pytest.mark.parametrize(
    "expression",
    [
        "尽快",
        "近期",
        "过几天",
        "下一阶段",
        "有时间的时候",
        "月底左右",
        "8月3日前",
    ],
)
def test_resolve_temporal_expression_ambiguous_phrases_need_confirmation(expression):
    reference_date = date(2026, 8, 3)

    assert resolve_temporal_expression(expression, reference_date) == {
        "expression": expression,
        "start": None,
        "end": None,
        "status": "needs_confirmation",
        "reference_date": "2026-08-03",
        "timezone": "Asia/Shanghai",
    }


def test_validate_action_owner_needs_confirmation_when_member_exists_but_evidence_is_not_explicit():
    candidate = {
        "owner_person_id": 23,
        "owner_name": "刘万超",
        "evidence": [{"quote": "刘万超提到了下周联调。"}],
    }

    assert validate_action_owner(candidate, {23: "刘万超"}) == [
        "owner is not supported by transcript evidence"
    ]


def test_validate_action_owner_passes_when_member_is_explicitly_named_as_owner():
    candidate = {
        "owner_person_id": 23,
        "owner_name": "刘万超",
        "evidence": [{"quote": "刘万超负责下周联调。"}],
    }

    assert validate_action_owner(candidate, {23: "刘万超"}) == []


def test_validate_candidate_blocks_unproven_acceptance_criteria_and_clears_value():
    candidate = {
        "type": "action_item",
        "owner_person_id": 23,
        "owner_name": "刘万超",
        "content": "刘万超负责下周联调。",
        "acceptance_criteria": "上线后必须补齐验收报告",
        "evidence": [{"quote": "刘万超负责下周联调。"}],
    }

    result = validate_candidate(candidate, {23: "刘万超"})

    assert result["validation_status"] == "blocked"
    assert result["acceptance_criteria"] == ""


def test_validate_candidates_blocks_completed_progress_classified_as_risk_or_decision():
    candidates = [
        {
            "type": "risk",
            "content": "平台版本更新已完成，当前风险已经解除。",
            "evidence": [{"quote": "平台版本更新已完成，当前风险已经解除。"}],
        },
        {
            "type": "decision",
            "content": "平台版本更新已完成，当前风险已经解除。",
            "evidence": [{"quote": "平台版本更新已完成，当前风险已经解除。"}],
        },
    ]

    result = validate_candidates(candidates, {})

    assert [item["validation_status"] for item in result] == ["blocked", "blocked"]
    assert [item["candidate_type"] for item in result] == ["risk", "decision"]


def test_validate_candidate_blocks_question_like_content_when_classified_as_decision():
    candidate = {
        "type": "decision",
        "content": "下周是否继续开评审会？",
        "evidence": [{"quote": "下周是否继续开评审会？"}],
    }

    result = validate_candidate(candidate, {})

    assert result["validation_status"] == "blocked"


def test_validate_candidate_blocks_unknown_candidate_type():
    candidate = {
        "type": "metadata",
        "content": "项目成员名单已更新。",
        "evidence": [{"quote": "项目成员名单已更新。"}],
    }

    result = validate_candidate(candidate, {})

    assert result["validation_status"] == "blocked"
