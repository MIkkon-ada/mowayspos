from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import database, models
from app.services.asr_context import build_work_report_asr_context


@pytest.fixture()
def isolated_db(tmp_path: Path) -> Session:
    database_path = tmp_path / "asr-context.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    models.Base.metadata.create_all(engine)
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
        selected_task_id=task.id,
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
    isolated_db.add(
        models.SubTask(
            task_id=other_task.id,
            title="其他项目关键任务",
            assignee="王小明",
            is_deleted=False,
        )
    )
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user="reporter",
            project_id=selected_project.id,
            selected_task_id=other_task.id,
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
    isolated_db.add(
        models.SubTask(
            task_id=task.id,
            title="没有分配给该成员的关键任务",
            assignee="关键任务负责人",
            is_deleted=False,
        )
    )
    isolated_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        build_work_report_asr_context(
            current_user="member",
            project_id=project.id,
            selected_task_id=task.id,
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
    isolated_db.add(
        models.SubTask(
            task_id=task.id,
            title="调研甲，验证乙",
            assignee=reporter.name,
            is_deleted=False,
        )
    )
    isolated_db.commit()

    context = build_work_report_asr_context(
        current_user="owner",
        project_id=project.id,
        selected_task_id=task.id,
        db=isolated_db,
    )

    assert context.splitlines()[0] == "当前关键任务：调研甲，验证乙"


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
        system_role="super_admin",
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
            selected_task_id = task.id
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
