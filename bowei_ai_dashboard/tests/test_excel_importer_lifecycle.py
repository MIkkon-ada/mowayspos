from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.excel_importer import import_projects


class _AssignmentsReader:
    def rows(self, sheet_name: str) -> list[list[str]]:
        assert sheet_name == "组织与分工"
        return [
            ["成员", "角色定位"],
            ["专项", "统筹人", "负责人", "协同人"],
            ["历史执行项目", "统筹人", "负责人", "协同人"],
        ]


def test_excel_imported_project_keeps_active_status_and_legacy_flag_in_sync():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    assert import_projects(db, _AssignmentsReader()) == 1
    project = db.query(models.Project).filter_by(name="历史执行项目").one()

    assert project.status == "active"
    assert project.is_active is True
