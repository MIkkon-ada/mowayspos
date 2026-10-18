from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services.task_assignee_audit import audit_unbound_task_assignees


def test_audit_classifies_unique_ambiguous_and_unmatched_without_writes():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add_all([
            models.Person(id=1, name="唯一人员", system_role="normal_member", is_active=True),
            models.Person(id=2, name="重名", system_role="normal_member", is_active=True),
            models.Person(id=3, name="重名", system_role="normal_member", is_active=True),
            models.Project(id=10, name="项目", status="active", is_active=True),
        ])
        for task_id, title, assignee in [
            (100, "唯一匹配", "唯一人员"),
            (101, "重名待核对", "重名"),
            (102, "找不到人员", "已离职人员"),
        ]:
            db.add(models.Task(id=task_id, project_id=10, key_task=f"重点工作 {task_id}"))
            db.flush()
            db.add(models.SubTask(
                id=task_id,
                task_id=task_id,
                title=title,
                assignee=assignee,
                assignee_id=None,
            ))
        db.commit()

        writes = []

        def reject_writes(_conn, _cursor, statement, *_args):
            operation = statement.lstrip().split(None, 1)[0].upper()
            if operation in {"INSERT", "UPDATE", "DELETE", "REPLACE"}:
                writes.append(statement)
                raise AssertionError("audit must be read-only")

        event.listen(engine, "before_cursor_execute", reject_writes)
        rows = audit_unbound_task_assignees(db)
        event.remove(engine, "before_cursor_execute", reject_writes)

        assert [(row["subtask_id"], row["classification"]) for row in rows] == [
            (100, "unique_candidate"),
            (101, "ambiguous"),
            (102, "unmatched"),
        ]
        assert rows[0]["candidate_person_ids"] == [1]
        assert rows[1]["candidate_person_ids"] == [2, 3]
        assert rows[2]["candidate_person_ids"] == []
        assert writes == []
