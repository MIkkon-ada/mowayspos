from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app import database, models
from app.services.asr_context import _bounded_lines, build_work_report_asr_context


@pytest.fixture()
def isolated_db(tmp_path: Path) -> Session:
    database_path = tmp_path / "asr-context.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    models.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE projects ADD COLUMN lifecycle_status VARCHAR(20)")
        )
    session = sessionmaker(bind=engine)()

    assert Path(session.get_bind().url.database).resolve() == database_path.resolve()
    assert session.get_bind().url.database != database.engine.url.database

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _person_with_account(
    db: Session,
    *,
    name: str,
    username: str,
    system_role: str = "normal_member",
) -> models.Person:
    person = models.Person(
        name=name,
        system_role=system_role,
        is_active=True,
        is_admin=False,
    )
    db.add(person)
    db.flush()
    db.add(
        models.Account(
            username=username,
            password_hash="not-used-in-this-test",
            person_id=person.id,
            status="active",
        )
    )
    db.flush()
    return person


def _active_project(db: Session, name: str) -> models.Project:
    project = models.Project(name=name, status="active", is_active=True)
    db.add(project)
    db.flush()
    return project


def test_context_contains_only_scoped_work_report_terms_and_is_bounded(
    isolated_db: Session,
):
    reporter = _person_with_account(
        isolated_db, name="王小明", username="reporter"
    )
    project = _active_project(isolated_db, "北极星增长项目")
    isolated_db.add(
        models.ProjectMember(
            project_id=project.id,
            person_id=reporter.id,
            person_name_snapshot=reporter.name,
            role="member",
        )
    )
    task = models.Task(
        project_id=project.id,
        special_project=project.name,
        key_task="建设客户成功作战体系",
        key_achievement="不应进入上下文的成果字段",
        owner="李雷",
        coordinator="韩梅梅，王小明",
        collaborators="李雷, Lucy、韩梅梅",
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    subtask = models.SubTask(
        task_id=task.id,
        title="完成首批企业教练访谈",
        assignee="王小明",
        completion_criteria="不应进入上下文的验收标准",
        is_deleted=False,
    )
    isolated_db.add(subtask)
    isolated_db.flush()

    other_project = _active_project(isolated_db, "绝密的其他项目")
    other_task = models.Task(
        project_id=other_project.id,
        key_task="其他项目重点工作",
        owner="无关人员",
        is_deleted=False,
    )
    isolated_db.add(other_task)
    isolated_db.commit()

    context = build_work_report_asr_context(
        current_user="reporter",
        project_id=project.id,
        selected_task_id=subtask.id,
        db=isolated_db,
    )

    assert context.splitlines() == [
        "当前关键任务：完成首批企业教练访谈",
        "当前重点工作：建设客户成功作战体系",
        "当前项目：北极星增长项目",
        "相关人员：王小明、李雷、韩梅梅、Lucy",
        "常用术语：Moways、关键任务、重点工作、成果入库、企业教练、项目统筹人",
    ]
    assert len(context) <= 400
    assert "不应进入上下文" not in context
    assert "绝密的其他项目" not in context
    assert "其他项目重点工作" not in context


def test_selected_task_from_another_project_is_rejected(isolated_db: Session):
    reporter = _person_with_account(
        isolated_db, name="王小明", username="reporter"
    )
    selected_project = _active_project(isolated_db, "允许访问项目")
    other_project = _active_project(isolated_db, "其他项目")
    isolated_db.add(
        models.ProjectMember(
            project_id=selected_project.id,
            person_id=reporter.id,
            person_name_snapshot=reporter.name,
            role="member",
        )
    )
    other_task = models.Task(
        project_id=other_project.id,
        key_task="其他项目重点工作",
        owner="王小明",
        is_deleted=False,
    )
    isolated_db.add(other_task)
    isolated_db.flush()
    other_subtask = models.SubTask(
        task_id=other_task.id,
        title="其他项目关键任务",
        assignee="王小明",
        is_deleted=False,
    )
    isolated_db.add(other_subtask)
    isolated_db.flush()
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user="reporter",
            project_id=selected_project.id,
            selected_task_id=other_subtask.id,
            db=isolated_db,
        )

    assert exc_info.value.status_code == 403


def test_member_without_management_or_assignment_is_rejected(
    isolated_db: Session,
):
    reporter = _person_with_account(
        isolated_db, name="普通成员", username="member"
    )
    project = _active_project(isolated_db, "成员参与项目")
    isolated_db.add(
        models.ProjectMember(
            project_id=project.id,
            person_id=reporter.id,
            person_name_snapshot=reporter.name,
            role="member",
        )
    )
    task = models.Task(
        project_id=project.id,
        key_task="没有分配给该成员的重点工作",
        owner="任务负责人",
        coordinator="项目统筹人",
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    selected_subtask = models.SubTask(
        task_id=task.id,
        title="没有分配给该成员的关键任务",
        assignee="关键任务负责人",
        is_deleted=False,
    )
    isolated_db.add(selected_subtask)
    isolated_db.flush()
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user="member",
            project_id=project.id,
            selected_task_id=selected_subtask.id,
            db=isolated_db,
        )

    assert exc_info.value.status_code == 403


def test_punctuation_inside_subtask_title_is_preserved(isolated_db: Session):
    reporter = _person_with_account(
        isolated_db, name="项目负责人", username="owner"
    )
    project = _active_project(isolated_db, "标题标点项目")
    isolated_db.add(
        models.ProjectMember(
            project_id=project.id,
            person_id=reporter.id,
            person_name_snapshot=reporter.name,
            role="owner",
        )
    )
    task = models.Task(
        project_id=project.id,
        key_task="验证标题原文",
        owner=reporter.name,
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    selected_subtask = models.SubTask(
        task_id=task.id,
        title="调研甲，验证乙",
        assignee=reporter.name,
        is_deleted=False,
    )
    isolated_db.add(selected_subtask)
    isolated_db.flush()
    isolated_db.commit()

    context = build_work_report_asr_context(
        current_user="owner",
        project_id=project.id,
        selected_task_id=selected_subtask.id,
        db=isolated_db,
    )

    assert context.splitlines()[0] == "当前关键任务：调研甲，验证乙"


def test_context_contains_only_the_selected_subtask(isolated_db: Session):
    reporter = _person_with_account(
        isolated_db, name="项目负责人", username="owner"
    )
    project = _active_project(isolated_db, "单任务上下文项目")
    isolated_db.add(
        models.ProjectMember(
            project_id=project.id,
            person_id=reporter.id,
            person_name_snapshot=reporter.name,
            role="owner",
        )
    )
    task = models.Task(
        project_id=project.id,
        key_task="同一重点工作",
        owner=reporter.name,
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    sibling = models.SubTask(
        task_id=task.id,
        title="不可泄露的兄弟关键任务",
        assignee="兄弟任务负责人",
        is_deleted=False,
    )
    selected = models.SubTask(
        task_id=task.id,
        title="当前选中的关键任务",
        assignee="当前任务负责人",
        is_deleted=False,
    )
    isolated_db.add_all([sibling, selected])
    isolated_db.flush()
    isolated_db.commit()

    context = build_work_report_asr_context(
        current_user="owner",
        project_id=project.id,
        selected_task_id=selected.id,
        db=isolated_db,
    )

    assert "当前关键任务：当前选中的关键任务" in context
    assert sibling.title not in context
    assert sibling.assignee not in context
    assert selected.assignee in context


def test_sibling_assignee_cannot_access_selected_subtask(isolated_db: Session):
    reporter = _person_with_account(
        isolated_db, name="兄弟任务负责人", username="sibling-assignee"
    )
    project = _active_project(isolated_db, "兄弟任务权限项目")
    isolated_db.add(
        models.ProjectMember(
            project_id=project.id,
            person_id=reporter.id,
            person_name_snapshot=reporter.name,
            role="member",
        )
    )
    task = models.Task(
        project_id=project.id,
        key_task="权限隔离重点工作",
        owner="重点工作负责人",
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    sibling = models.SubTask(
        task_id=task.id,
        title="分配给当前用户的兄弟任务",
        assignee=reporter.name,
        is_deleted=False,
    )
    selected = models.SubTask(
        task_id=task.id,
        title="未分配给当前用户的选中任务",
        assignee="其他负责人",
        is_deleted=False,
    )
    isolated_db.add_all([sibling, selected])
    isolated_db.flush()
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user="sibling-assignee",
            project_id=project.id,
            selected_task_id=selected.id,
            db=isolated_db,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize("bound_identity", ["task_owner", "subtask_assignee"])
def test_same_name_member_cannot_impersonate_id_bound_assignee(
    isolated_db: Session,
    bound_identity: str,
):
    victim = _person_with_account(
        isolated_db, name="同名成员", username=f"victim-{bound_identity}"
    )
    attacker = _person_with_account(
        isolated_db, name="同名成员", username=f"attacker-{bound_identity}"
    )
    project = _active_project(isolated_db, f"同名鉴权-{bound_identity}")
    isolated_db.add(
        models.ProjectMember(
            project_id=project.id,
            person_id=attacker.id,
            person_name_snapshot=attacker.name,
            role="member",
        )
    )
    task = models.Task(
        project_id=project.id,
        key_task="同名鉴权重点工作",
        owner="同名成员" if bound_identity == "task_owner" else "其他负责人",
        owner_id=victim.id if bound_identity == "task_owner" else None,
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    selected = models.SubTask(
        task_id=task.id,
        title="同名鉴权关键任务",
        assignee=(
            "同名成员"
            if bound_identity == "subtask_assignee"
            else "其他关键任务负责人"
        ),
        assignee_id=(
            victim.id if bound_identity == "subtask_assignee" else None
        ),
        is_deleted=False,
    )
    isolated_db.add(selected)
    isolated_db.flush()
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user=f"attacker-{bound_identity}",
            project_id=project.id,
            selected_task_id=selected.id,
            db=isolated_db,
        )

    assert exc_info.value.status_code == 403


def test_legacy_null_assignment_ids_fall_back_to_name(isolated_db: Session):
    reporter = _person_with_account(
        isolated_db, name="遗留负责人", username="legacy-assignee"
    )
    project = _active_project(isolated_db, "遗留姓名鉴权项目")
    isolated_db.add(
        models.ProjectMember(
            project_id=project.id,
            person_id=reporter.id,
            person_name_snapshot=reporter.name,
            role="member",
        )
    )
    task = models.Task(
        project_id=project.id,
        key_task="遗留重点工作",
        owner="其他负责人",
        owner_id=None,
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    selected = models.SubTask(
        task_id=task.id,
        title="遗留关键任务",
        assignee=reporter.name,
        assignee_id=None,
        is_deleted=False,
    )
    isolated_db.add(selected)
    isolated_db.flush()
    isolated_db.commit()

    context = build_work_report_asr_context(
        current_user="legacy-assignee",
        project_id=project.id,
        selected_task_id=selected.id,
        db=isolated_db,
    )

    assert "当前关键任务：遗留关键任务" in context


def test_legacy_name_assignment_rejects_duplicate_project_member_names(
    isolated_db: Session,
):
    reporter = _person_with_account(
        isolated_db,
        name="同名遗留成员",
        username="legacy-duplicate",
    )
    duplicate = _person_with_account(
        isolated_db,
        name="同名遗留成员",
        username="legacy-duplicate-other",
    )
    project = _active_project(isolated_db, "同名遗留授权项目")
    isolated_db.add_all(
        [
            models.ProjectMember(
                project_id=project.id,
                person_id=reporter.id,
                person_name_snapshot=reporter.name,
                role="member",
            ),
            models.ProjectMember(
                project_id=project.id,
                person_id=duplicate.id,
                person_name_snapshot=duplicate.name,
                role="member",
            ),
        ]
    )
    task = models.Task(
        project_id=project.id,
        key_task="遗留姓名重点工作",
        owner="其他负责人",
        owner_id=None,
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    selected = models.SubTask(
        task_id=task.id,
        title="遗留姓名关键任务",
        assignee=reporter.name,
        assignee_id=None,
        is_deleted=False,
    )
    isolated_db.add(selected)
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user="legacy-duplicate",
            project_id=project.id,
            selected_task_id=selected.id,
            db=isolated_db,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    ("project_state", "project_id"),
    [("active", 1), ("inactive", 1), ("missing", 98765)],
)
def test_non_member_cannot_enumerate_project_existence_or_lifecycle(
    isolated_db: Session,
    project_state: str,
    project_id: int,
):
    attacker = _person_with_account(
        isolated_db, name="项目外攻击者", username=f"outsider-{project_state}"
    )
    if project_state != "missing":
        project = models.Project(
            name=f"不可枚举项目-{project_state}",
            status="active" if project_state == "active" else "draft",
            is_active=project_state == "active",
        )
        isolated_db.add(project)
        isolated_db.flush()
        assert project.id == project_id
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user=f"outsider-{project_state}",
            project_id=project_id,
            selected_task_id=98765,
            db=isolated_db,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    ("status", "lifecycle_status"),
    [("active", "draft"), ("draft", "active")],
)
def test_project_is_reportable_when_either_lifecycle_field_is_active(
    isolated_db: Session,
    status: str,
    lifecycle_status: str,
):
    reporter = _person_with_account(
        isolated_db,
        name="生命周期负责人",
        username=f"lifecycle-{status}-{lifecycle_status}",
    )
    project = models.Project(
        name=f"生命周期项目-{status}-{lifecycle_status}",
        status=status,
        is_active=False,
    )
    isolated_db.add(project)
    isolated_db.flush()
    isolated_db.execute(
        text(
            "UPDATE projects SET lifecycle_status=:lifecycle "
            "WHERE id=:project_id"
        ),
        {"lifecycle": lifecycle_status, "project_id": project.id},
    )
    isolated_db.add(
        models.ProjectMember(
            project_id=project.id,
            person_id=reporter.id,
            person_name_snapshot=reporter.name,
            role="owner",
        )
    )
    task = models.Task(
        project_id=project.id,
        key_task="生命周期重点工作",
        owner=reporter.name,
        owner_id=reporter.id,
        is_deleted=False,
    )
    isolated_db.add(task)
    isolated_db.flush()
    selected = models.SubTask(
        task_id=task.id,
        title="生命周期关键任务",
        assignee=reporter.name,
        assignee_id=reporter.id,
        is_deleted=False,
    )
    isolated_db.add(selected)
    isolated_db.flush()
    isolated_db.commit()

    context = build_work_report_asr_context(
        current_user=f"lifecycle-{status}-{lifecycle_status}",
        project_id=project.id,
        selected_task_id=selected.id,
        db=isolated_db,
    )

    assert "当前项目：" in context


def test_bounded_lines_keeps_complete_high_priority_lines():
    exact = "甲" * 400
    assert _bounded_lines([exact]) == exact

    high_priority = "乙" * 390
    too_long_next_line = "丙" * 20
    later_complete_line = "丁" * 5
    bounded = _bounded_lines(
        [high_priority, too_long_next_line, later_complete_line]
    )

    assert bounded == f"{high_priority}\n{later_complete_line}"
    assert len(bounded) <= 400
    assert too_long_next_line not in bounded


@pytest.mark.parametrize(
    ("project_exists", "is_active", "task_exists", "expected_status"),
    [
        (False, True, True, 404),
        (True, False, True, 409),
        (True, True, False, 404),
    ],
)
def test_missing_or_inactive_scope_is_rejected(
    isolated_db: Session,
    project_exists: bool,
    is_active: bool,
    task_exists: bool,
    expected_status: int,
):
    reporter = _person_with_account(
        isolated_db,
        name="项目负责人",
        username="owner",
        system_role="company_ceo",
    )
    project_id = 98765
    if project_exists:
        project = models.Project(
            name=f"状态项目-{is_active}",
            status="active" if is_active else "closed",
            is_active=is_active,
        )
        isolated_db.add(project)
        isolated_db.flush()
        project_id = project.id
        isolated_db.add(
            models.ProjectMember(
                project_id=project.id,
                person_id=reporter.id,
                person_name_snapshot=reporter.name,
                role="owner",
            )
        )
        if task_exists:
            task = models.Task(
                project_id=project.id,
                key_task="状态验证重点工作",
                owner=reporter.name,
                is_deleted=False,
            )
            isolated_db.add(task)
            isolated_db.flush()
            selected_subtask = models.SubTask(
                task_id=task.id,
                title="状态验证关键任务",
                assignee=reporter.name,
                is_deleted=False,
            )
            isolated_db.add(selected_subtask)
            isolated_db.flush()
            selected_task_id = selected_subtask.id
        else:
            selected_task_id = 98765
    else:
        selected_task_id = 98765
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user="owner",
            project_id=project_id,
            selected_task_id=selected_task_id,
            db=isolated_db,
        )

    assert exc_info.value.status_code == expected_status
