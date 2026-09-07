from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.routers.projects import approve_project, owner_submit_project_profile
from app.services.project_init_ai_agent import generate_project_init_draft
from app.services.project_init_file_parser import parse_project_init_file


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_project_team(db):
    owner = models.Person(id=1, name="Owner Person", system_role="normal_member", is_active=True)
    coach = models.Person(id=2, name="Project Coach", system_role="normal_member", is_active=True)
    member = models.Person(id=3, name="Member Person", system_role="normal_member", is_active=True)
    company_ceo = models.Person(id=4, name="Company CEO", system_role="company_ceo", is_active=True)
    db.add_all(
        [
            owner,
            coach,
            member,
            company_ceo,
            models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"),
            models.Account(username="coach", password_hash="x", person_id=coach.id, status="active"),
            models.Account(username="member", password_hash="x", person_id=member.id, status="active"),
            models.Account(username="company_ceo", password_hash="x", person_id=company_ceo.id, status="active"),
            models.Project(id=1, name="Draft Project", status="dispatched", is_active=False),
            models.ProjectMember(project_id=1, person_id=owner.id, person_name_snapshot=owner.name, role="owner"),
            models.ProjectMember(project_id=1, person_id=coach.id, person_name_snapshot=coach.name, role="project_ceo"),
            models.ProjectMember(project_id=1, person_id=member.id, person_name_snapshot=member.name, role="member"),
        ]
    )
    db.commit()


def _add_people_for_picker(db):
    db.add_all(
        [
            models.Person(id=5, name="New Assignee", system_role="normal_member", is_active=True),
            models.Person(id=6, name="Helper One", system_role="normal_member", is_active=True),
            models.Person(id=7, name="Helper Two", system_role="normal_member", is_active=True),
        ]
    )
    db.commit()


def test_owner_submit_persists_xlsx_ai_draft_with_end_only_month_and_raw_imported_people(tmp_path):
    workbook_path = tmp_path / "六月项目计划.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "六月计划"
    sheet.append(["2026 年 6 月项目计划"])
    sheet.append(["重点工作", "关键任务", "负责人", "协助人", "计划时间"])
    sheet.append(["现场部署", "完成现场部署", "王五", "赵六", "2026-06"])
    workbook.save(workbook_path)

    parsed_chunks = parse_project_init_file(workbook_path, "六月项目计划.xlsx")
    data_chunk = next(chunk for chunk in parsed_chunks if "现场部署" in chunk.text)
    assert "重点工作\t关键任务\t负责人\t协助人\t计划时间" in data_chunk.text
    assert data_chunk.location.endswith("A3:E3")

    def deterministic_llm(prompt: str, _provider: str) -> str:
        assert data_chunk.location in prompt
        return json.dumps(
            {
                "tasks": [
                    {
                        "title": "现场部署",
                        "description": "完成现场部署",
                        "owner_name": "王五",
                        "priority": "high",
                        "status": "not_started",
                        "plan_start": "",
                        "plan_end": "2026-06",
                        "evidence": [
                            {
                                "attachment_id": 42,
                                "file_name": data_chunk.file_name,
                                "location": data_chunk.location,
                            }
                        ],
                        "subtasks": [
                            {
                                "title": "完成现场部署",
                                "assignee_name": "王五",
                                "helper_names": ["赵六"],
                                "priority": "high",
                                "status": "not_started",
                                "plan_start": "",
                                "plan_end": "2026-06",
                                "evaluation_standard": "完成现场部署并验收",
                                "evidence": [
                                    {
                                        "attachment_id": 42,
                                        "file_name": data_chunk.file_name,
                                        "location": data_chunk.location,
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        )

    ai_draft = generate_project_init_draft(
        [
            {
                "attachment_id": 42,
                "file_name": chunk.file_name,
                "location": chunk.location,
                "text": chunk.text,
            }
            for chunk in parsed_chunks
        ],
        [],
        [],
        llm_call=deterministic_llm,
    )
    ai_task = ai_draft.tasks[0]
    ai_subtask = ai_task.subtasks[0]
    assert (ai_task.plan_start, ai_task.plan_end) == ("2026-06-01", "")
    expected_evidence = {
        "attachment_id": 42,
        "file_name": data_chunk.file_name,
        "location": data_chunk.location,
        "excerpt": data_chunk.text.strip()[:300],
    }
    assert ai_task.evidence[0].model_dump() == expected_evidence
    assert ai_subtask.evidence[0].model_dump() == expected_evidence

    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
                schemas.ProjectWorkProgressTaskDraft(
                    title=ai_task.title,
                    description=ai_task.description,
                    goal="现场部署目标",
                    acceptance_criteria="现场部署完成并验收",
                    process="准备 → 部署 → 验收",
                    owner=ai_task.owner_name,
                    plan_start=ai_task.plan_start,
                    plan_end=ai_task.plan_end,
                    subtasks=[
                        schemas.ProjectWorkProgressSubTaskDraft(
                            title=ai_subtask.title,
                            evaluation_standard=ai_subtask.evaluation_standard,
                            assignee=ai_subtask.assignee_name,
                            assignee_id=ai_subtask.assignee_id,
                            helper="、".join(ai_subtask.helper_names),
                            helper_ids=ai_subtask.helper_ids,
                            plan_start=ai_subtask.plan_start,
                            plan_end=ai_subtask.plan_end,
                        )
                    ],
                )
        ]
    )
    db = _make_session()
    _seed_project_team(db)

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    task = db.query(models.Task).filter_by(project_id=1).one()
    subtask = db.query(models.SubTask).filter_by(task_id=task.id).one()
    assignee = db.query(models.Person).filter_by(name="王五").one()
    helper = db.query(models.Person).filter_by(name="赵六").one()
    project_actions = {
        log.action
        for log in db.query(models.OperationLog).filter_by(project_id=1, operator="owner").all()
    }
    all_owner_actions = {log.action for log in db.query(models.OperationLog).filter_by(operator="owner").all()}

    assert task.plan_time == "2026-06-01"
    assert task.key_achievement == "现场部署目标"
    assert task.completion_standard == "现场部署完成并验收"
    assert task.plan_process == "准备 → 部署 → 验收"
    assert subtask.assignee_id == assignee.id
    assert subtask.collaborator_ids == [helper.id]
    assert {
        (member.person_id, member.role)
        for member in db.query(models.ProjectMember).filter_by(project_id=1, role="member")
    } >= {(assignee.id, "member"), (helper.id, "member")}
    assert {
        "auto_create_imported_person",
        "auto_add_imported_project_member",
    } <= project_actions
    assert "owner_submit_project" in all_owner_actions


def test_owner_submit_adds_selected_people_to_project_and_snapshots_names():
    db = _make_session()
    _seed_project_team(db)
    _add_people_for_picker(db)

    owner_submit_project_profile(
        1,
        schemas.ProjectProfilePayload(
            work_progress_draft=[
                schemas.ProjectWorkProgressTaskDraft(
                    title="Selected people task",
                    subtasks=[
                        schemas.ProjectWorkProgressSubTaskDraft(
                            title="Selected key task",
                            assignee_id=5,
                            helper_ids=[6, 7, 6],
                        )
                    ],
                )
            ]
        ),
        current_user="owner",
        db=db,
    )

    members = db.query(models.ProjectMember).filter_by(project_id=1).all()
    subtasks = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).all()
    assert {(m.person_id, m.role) for m in members} >= {(5, "member"), (6, "member"), (7, "member")}
    assert len([m for m in members if m.person_id == 6 and m.role == "member"]) == 1
    assert subtasks[0].assignee == "New Assignee"
    assert subtasks[0].assignee_id == 5
    assert "Helper One" in subtasks[0].notes
    assert "Helper Two" in subtasks[0].notes


def test_owner_submit_rejects_invalid_selected_person_atomically():
    db = _make_session()
    _seed_project_team(db)

    with pytest.raises(HTTPException) as exc:
        owner_submit_project_profile(
            1,
            schemas.ProjectProfilePayload(
                work_progress_draft=[
                    schemas.ProjectWorkProgressTaskDraft(
                        title="Invalid selected people task",
                        subtasks=[
                            schemas.ProjectWorkProgressSubTaskDraft(
                                title="Invalid key task",
                                assignee_id=9999,
                            )
                        ],
                    )
                ]
            ),
            current_user="owner",
            db=db,
        )

    assert exc.value.status_code == 422
    assert db.get(models.Project, 1).status == "dispatched"
    assert db.query(models.Task).filter_by(project_id=1).count() == 0
    assert db.query(models.ProjectMember).filter_by(project_id=1, role="member").count() == 1


def test_owner_submit_reuses_named_active_person_and_adds_project_member():
    db = _make_session()
    _seed_project_team(db)
    existing_assignee = models.Person(id=8, name="张三", system_role="normal_member", is_active=True)
    existing_helper = models.Person(id=9, name="李四", system_role="normal_member", is_active=True)
    db.add_all([existing_assignee, existing_helper])
    db.commit()

    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="导入人员重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="导入人员关键任务",
                        assignee="张三",
                        helper="李四",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    subtask = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).one()
    assert payload.work_progress_draft[0].subtasks[0].assignee_id == existing_assignee.id
    assert payload.work_progress_draft[0].subtasks[0].helper_ids == [existing_helper.id]
    assert subtask.assignee_id == existing_assignee.id
    assert subtask.collaborator_ids == [existing_helper.id]
    assert {
        (member.person_id, member.role)
        for member in db.query(models.ProjectMember).filter_by(project_id=1, role="member")
    } >= {(existing_assignee.id, "member"), (existing_helper.id, "member")}


def test_owner_submit_reuses_existing_non_chinese_assignee_without_rejecting_raw_name():
    db = _make_session()
    _seed_project_team(db)
    existing_assignee = models.Person(id=8, name="mowasyadmin", system_role="normal_member", is_active=True)
    db.add(existing_assignee)
    db.commit()

    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="Imported task",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="Imported key task",
                        assignee="mowasyadmin",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    subtask = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).one()
    assert payload.work_progress_draft[0].subtasks[0].assignee_id == existing_assignee.id
    assert subtask.assignee_id == existing_assignee.id
    assert db.query(models.ProjectMember).filter_by(project_id=1, person_id=existing_assignee.id, role="member").one()


def test_owner_submit_creates_named_people_as_normal_members_without_accounts():
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="新增导入人员重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="新增导入人员关键任务",
                        assignee="王五",
                        helper="赵六",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    assignee = db.query(models.Person).filter_by(name="王五").one()
    helper = db.query(models.Person).filter_by(name="赵六").one()
    subtask = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).one()
    assert (assignee.is_active, assignee.system_role) == (True, "normal_member")
    assert (helper.is_active, helper.system_role) == (True, "normal_member")
    assert db.query(models.Account).filter(models.Account.person_id.in_([assignee.id, helper.id])).count() == 0
    assert payload.work_progress_draft[0].subtasks[0].assignee_id == assignee.id
    assert payload.work_progress_draft[0].subtasks[0].helper_ids == [helper.id]
    assert subtask.assignee_id == assignee.id
    assert subtask.collaborator_ids == [helper.id]
    assert {
        (member.person_id, member.role)
        for member in db.query(models.ProjectMember).filter_by(project_id=1, role="member")
    } >= {(assignee.id, "member"), (helper.id, "member")}


def test_owner_submit_skips_non_person_helper_labels_while_importing_named_people():
    db = _make_session()
    _seed_project_team(db)
    db.add(models.Person(id=8, name="市场部", system_role="normal_member", is_active=True))
    db.commit()
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="Mixed collaborator task",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="Mixed collaborator key task",
                        assignee="王五",
                        helper="赵六、市场部",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    helper = db.query(models.Person).filter_by(name="赵六").one()
    subtask = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).one()
    assert payload.work_progress_draft[0].subtasks[0].helper_ids == [helper.id]
    assert subtask.collaborator_ids == [helper.id]
    assert "市场部" not in subtask.notes
    assert db.query(models.ProjectMember).filter_by(project_id=1, person_id=8, role="member").count() == 0


def test_owner_submit_creates_unmatched_account_style_assignee_as_a_project_member():
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="Account-style imported task",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="Account-style imported key task",
                        assignee="mowasyadmin",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    assignee = db.query(models.Person).filter_by(name="mowasyadmin").one()
    assert (assignee.is_active, assignee.system_role) == (True, "normal_member")
    assert payload.work_progress_draft[0].subtasks[0].assignee_id == assignee.id
    assert db.query(models.ProjectMember).filter_by(project_id=1, person_id=assignee.id, role="member").one()


def test_owner_submit_audits_created_imported_people_and_project_members():
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="审计导入人员重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="审计导入人员关键任务",
                        assignee="王五",
                        helper="赵六",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    logs = db.query(models.OperationLog).filter_by(project_id=1, operator="owner").all()
    created_people = [log for log in logs if log.action == "auto_create_imported_person"]
    added_members = [log for log in logs if log.action == "auto_add_imported_project_member"]

    assert {json.loads(log.after_json)["name"] for log in created_people} == {"王五", "赵六"}
    assert {json.loads(log.after_json)["person_name_snapshot"] for log in added_members} == {"王五", "赵六"}
    assert all(log.target_type == "person" and json.loads(log.before_json) == {} for log in created_people)
    assert all(log.target_type == "project_member" and json.loads(log.before_json) == {} for log in added_members)
    assert all(json.loads(log.after_json)["project_id"] == 1 for log in added_members)


def test_owner_submit_does_not_audit_reused_project_member_as_added():
    db = _make_session()
    _seed_project_team(db)

    owner_submit_project_profile(
        1,
        schemas.ProjectProfilePayload(
            work_progress_draft=[
                schemas.ProjectWorkProgressTaskDraft(
                    title="复用成员重点工作",
                    subtasks=[
                        schemas.ProjectWorkProgressSubTaskDraft(
                            title="复用成员关键任务",
                            assignee_id=3,
                        )
                    ],
                )
            ]
        ),
        current_user="owner",
        db=db,
    )

    actions = {
        log.action
        for log in db.query(models.OperationLog).filter_by(project_id=1, operator="owner").all()
    }
    assert "auto_create_imported_person" not in actions
    assert "auto_add_imported_project_member" not in actions


def test_owner_submit_binds_imported_task_owner_and_adds_project_member():
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="任务级负责人重点工作",
                owner="周七",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="任务级负责人关键任务",
                        assignee_id=1,
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    owner = db.query(models.Person).filter_by(name="周七").one()
    task = db.query(models.Task).filter_by(project_id=1).one()
    assert task.owner == "周七"
    assert task.owner_id == owner.id
    assert db.query(models.ProjectMember).filter_by(project_id=1, person_id=owner.id, role="member").one()


def test_owner_submit_binds_existing_non_chinese_task_owner_with_different_assignee():
    db = _make_session()
    _seed_project_team(db)
    _add_people_for_picker(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="Existing owner task",
                owner="Owner Person",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="Different assignee key task",
                        assignee_id=5,
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    task = db.query(models.Task).filter_by(project_id=1).one()
    assert task.owner_id == 1
    assert db.query(models.ProjectMember).filter_by(project_id=1, person_id=1, role="member").one()


@pytest.mark.parametrize(
    "invalid_name",
    ["项目经理", "研发部", "全体成员", "总经理", "副总裁", "总工程师", "管理层", "研发科", "采购处"],
)
def test_owner_submit_rejects_role_department_and_group_assignees(invalid_name):
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="角色词重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="角色词关键任务",
                        assignee=invalid_name,
                    )
                ],
            )
        ]
    )

    with pytest.raises(HTTPException) as exc:
        owner_submit_project_profile(1, payload, current_user="owner", db=db)

    assert exc.value.status_code == 422
    assert db.query(models.Person).filter_by(name=invalid_name).count() == 0


def test_owner_submit_rolls_back_created_people_when_later_imported_assignee_is_invalid(monkeypatch):
    db = _make_session()
    _seed_project_team(db)
    original_flush = db.flush
    flushed_new_person = False

    def tracking_flush():
        nonlocal flushed_new_person
        original_flush()
        flushed_new_person = flushed_new_person or any(
            isinstance(row, models.Person) and row.name == "王五"
            for row in db.identity_map.values()
        )

    monkeypatch.setattr(db, "flush", tracking_flush)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="先创建后失败重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(title="先创建任务", assignee="王五"),
                    schemas.ProjectWorkProgressSubTaskDraft(title="后失败任务", assignee="项目经理"),
                ],
            )
        ]
    )

    with pytest.raises(HTTPException) as exc:
        owner_submit_project_profile(1, payload, current_user="owner", db=db)

    assert exc.value.status_code == 422
    assert flushed_new_person is True
    assert db.query(models.Person).filter_by(name="王五").count() == 0
    assert db.query(models.Task).filter_by(project_id=1).count() == 0
    assert db.query(models.OperationLog).filter_by(project_id=1, operator="owner").count() == 0
    assert db.get(models.Project, 1).status == "dispatched"


def test_owner_submit_does_not_save_assignee_as_helper():
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="负责人协助人去重重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="负责人协助人去重关键任务",
                        assignee="张三",
                        helper="张三",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    subtask = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).one()
    assert payload.work_progress_draft[0].subtasks[0].helper_ids == []
    assert subtask.collaborator_ids == []
    assert subtask.notes == ""


def test_owner_submit_resolves_raw_helper_after_removing_assignee_helper_id():
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="协助人兜底解析重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="协助人兜底解析关键任务",
                        assignee_id=1,
                        helper_ids=[1],
                        helper="李四",
                    )
                ],
            )
        ]
    )

    owner_submit_project_profile(1, payload, current_user="owner", db=db)

    helper = db.query(models.Person).filter_by(name="李四").one()
    subtask = db.query(models.SubTask).join(models.Task).filter(models.Task.project_id == 1).one()
    assert payload.work_progress_draft[0].subtasks[0].helper_ids == [helper.id]
    assert subtask.collaborator_ids == [helper.id]
    assert subtask.notes == "协助人：李四"


@pytest.mark.parametrize("invalid_name", ["各项目经理", "咨询部"])
def test_owner_submit_rejects_non_person_imported_assignee_without_creating_person(invalid_name):
    db = _make_session()
    _seed_project_team(db)
    payload = schemas.ProjectProfilePayload(
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="无效导入人员重点工作",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="无效导入人员关键任务",
                        assignee=invalid_name,
                    )
                ],
            )
        ]
    )

    with pytest.raises(HTTPException) as exc:
        owner_submit_project_profile(1, payload, current_user="owner", db=db)

    assert exc.value.status_code == 422
    assert db.query(models.Person).filter_by(name=invalid_name).count() == 0
    assert db.get(models.Project, 1).status == "dispatched"
    assert db.query(models.Task).filter_by(project_id=1).count() == 0


def test_owner_submit_saves_work_progress_draft_without_activating_project():
    db = _make_session()
    _seed_project_team(db)

    payload = schemas.ProjectProfilePayload(
        objectives="Launch the pilot",
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="Prepare pilot plan",
                description="Draft the execution plan",
                owner="Owner Person",
                helper="Member Person",
                plan_start="2026-08-01",
                plan_end="2026-08-10",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="Confirm scope",
                        evaluation_standard="Scope signed off",
                        assignee="Owner Person",
                        assignee_id=1,
                        helper="Member Person",
                        plan_start="2026-08-01",
                        plan_end="2026-08-03",
                    )
                ],
            )
        ],
    )

    result = owner_submit_project_profile(1, payload, current_user="owner", db=db)

    project = db.get(models.Project, 1)
    tasks = db.query(models.Task).filter_by(project_id=1).all()
    subtasks = db.query(models.SubTask).join(models.Task, models.SubTask.task_id == models.Task.id).filter(
        models.Task.project_id == 1
    ).all()

    assert result["submitted_for_review"] is True
    assert project.status == "pending_review"
    assert project.is_active is False
    assert len(tasks) == 1
    assert tasks[0].project_id == 1
    assert tasks[0].key_task == "Prepare pilot plan"
    assert tasks[0].completion_standard == "Draft the execution plan"
    assert tasks[0].owner == "Owner Person"
    assert tasks[0].collaborators == "Member Person"
    assert len(subtasks) == 1
    assert subtasks[0].task_id == tasks[0].id
    assert subtasks[0].title == "Confirm scope"
    assert subtasks[0].completion_criteria == "Scope signed off"
    assert subtasks[0].assignee == "Owner Person"
    assert "Member Person" in subtasks[0].notes


def test_non_owner_cannot_submit_project_init_work_progress_draft():
    db = _make_session()
    _seed_project_team(db)

    with pytest.raises(HTTPException) as exc:
        owner_submit_project_profile(
            1,
            schemas.ProjectProfilePayload(
                work_progress_draft=[schemas.ProjectWorkProgressTaskDraft(title="Unauthorized task")]
            ),
            current_user="member",
            db=db,
        )

    assert exc.value.status_code == 403


def test_company_ceo_without_project_coach_role_cannot_approve_project():
    db = _make_session()
    _seed_project_team(db)
    owner_submit_project_profile(
        1,
        schemas.ProjectProfilePayload(
            work_progress_draft=[
                schemas.ProjectWorkProgressTaskDraft(
                    title="Ready for review",
                    subtasks=[
                        schemas.ProjectWorkProgressSubTaskDraft(
                            title="Coach review task",
                            assignee_id=1,
                        )
                    ],
                )
            ]
        ),
        current_user="owner",
        db=db,
    )

    with pytest.raises(HTTPException) as exc:
        approve_project(1, schemas.ProjectProfilePayload(), current_user="company_ceo", db=db)

    assert exc.value.status_code == 403
