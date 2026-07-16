from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from app import models, schemas
from app.database import Base
from app.domain import project_lifecycle as PL


EXPECTED_COLUMNS = {
    "id",
    "project_id",
    "requester_person_id",
    "summary",
    "objective_result",
    "unfinished_items_json",
    "remaining_risks_json",
    "handover_plan",
    "retrospective",
    "status",
    "reviewer_person_id",
    "review_comment",
    "created_at",
    "updated_at",
    "reviewed_at",
    "cancelled_at",
}


def _valid_materials() -> dict:
    return {
        "summary": "项目工作已经完成",
        "objective_result": "目标达到预期",
        "unfinished_items": [],
        "remaining_risks": [],
        "handover_plan": "资料移交项目负责人",
        "retrospective": "按计划推进并完成复盘",
    }


def _residual_item() -> dict:
    return {
        "description": "遗留接口切换",
        "reason": "等待外部窗口",
        "owner": "负责人",
        "handover_to": "运维团队",
        "follow_up_plan": "下周切换",
        "expected_resolution": "2026-08-01",
    }


def test_project_lifecycle_defines_close_states_and_helpers():
    assert PL.ALL_STATUSES == {
        "draft",
        "dispatched",
        "pending_review",
        "returned",
        "active",
        "pending_close",
        "ended",
        "archived",
    }
    assert PL.normalize(" pending_close ") == PL.S_PENDING_CLOSE
    assert PL.normalize("unknown", PL.S_ACTIVE) == PL.S_ACTIVE
    assert PL.is_close_frozen(PL.S_PENDING_CLOSE)
    assert PL.is_close_frozen(PL.S_ENDED)
    assert not PL.is_close_frozen(PL.S_ACTIVE)
    assert PL.is_archived(PL.S_ARCHIVED)


def test_project_close_request_model_has_exact_table_contract():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    mapper_columns = set(models.ProjectCloseRequest.__table__.columns.keys())
    assert models.ProjectCloseRequest.__tablename__ == "project_close_requests"
    assert mapper_columns == EXPECTED_COLUMNS

    db_columns = {row["name"]: row for row in inspect(engine).get_columns("project_close_requests")}
    assert set(db_columns) == EXPECTED_COLUMNS
    assert not db_columns["project_id"]["nullable"]
    assert not db_columns["summary"]["nullable"]
    assert not db_columns["objective_result"]["nullable"]
    assert not db_columns["unfinished_items_json"]["nullable"]
    assert not db_columns["remaining_risks_json"]["nullable"]
    assert not db_columns["handover_plan"]["nullable"]
    assert not db_columns["retrospective"]["nullable"]

    foreign_keys = {
        (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
        for fk in inspect(engine).get_foreign_keys("project_close_requests")
    }
    assert (("project_id",), "projects", ("id",)) in foreign_keys
    assert (("requester_person_id",), "people", ("id",)) in foreign_keys
    assert (("reviewer_person_id",), "people", ("id",)) in foreign_keys

    indexed = {
        tuple(index["column_names"])
        for index in inspect(engine).get_indexes("project_close_requests")
    }
    assert ("project_id",) in indexed
    assert ("requester_person_id",) in indexed
    assert ("reviewer_person_id",) in indexed
    assert ("status",) in indexed


def test_project_close_request_defaults_and_timestamps_are_registered():
    row = models.ProjectCloseRequest(
        project_id=1,
        summary="总结",
        objective_result="目标",
        handover_plan="交接",
        retrospective="复盘",
    )
    assert row.status is None or row.status == "pending"
    assert row.unfinished_items_json is None or row.unfinished_items_json == "[]"
    assert row.remaining_risks_json is None or row.remaining_risks_json == "[]"
    assert "created_at" in models.ProjectCloseRequest.__table__.columns
    assert "updated_at" in models.ProjectCloseRequest.__table__.columns


def test_create_payload_requires_complete_trimmed_materials_and_explicit_arrays():
    payload = schemas.ProjectCloseRequestCreatePayload(**_valid_materials())
    assert payload.summary == "项目工作已经完成"
    assert payload.unfinished_items == []
    assert payload.remaining_risks == []

    for missing in ("unfinished_items", "remaining_risks"):
        body = _valid_materials()
        body.pop(missing)
        with pytest.raises(ValidationError):
            schemas.ProjectCloseRequestCreatePayload(**body)

    for field in ("summary", "objective_result", "handover_plan", "retrospective"):
        body = _valid_materials()
        body[field] = "   "
        with pytest.raises(ValidationError):
            schemas.ProjectCloseRequestCreatePayload(**body)


@pytest.mark.parametrize(
    "field",
    ["description", "reason", "owner", "handover_to", "follow_up_plan", "expected_resolution"],
)
def test_residual_item_requires_all_six_trimmed_fields(field: str):
    item = _residual_item()
    item[field] = "  "
    body = _valid_materials()
    body["unfinished_items"] = [item]
    with pytest.raises(ValidationError):
        schemas.ProjectCloseRequestCreatePayload(**body)


def test_close_payload_keeps_arrays_as_objects_and_does_not_mutate_input():
    item = _residual_item()
    original = json.loads(json.dumps(item, ensure_ascii=False))
    body = _valid_materials()
    body["remaining_risks"] = [item]
    payload = schemas.ProjectCloseRequestCreatePayload(**body)

    assert item == original
    assert payload.remaining_risks[0].model_dump() == original


def test_update_payload_is_partial_and_review_payload_trims_comment():
    update = schemas.ProjectCloseRequestUpdatePayload(summary="  新总结  ")
    review = schemas.ProjectCloseReviewPayload(review_comment="  审核意见  ")

    assert update.summary == "新总结"
    assert update.objective_result is None
    assert review.review_comment == "审核意见"
