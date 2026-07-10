from pathlib import Path

from . import models
from .excel_importer import import_excel_data


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
EXCEL_SEED = WORKSPACE_ROOT / "博维咨询2026升级工作推进计划表_V1.2.xlsx"


def seed(db):
    if db.query(models.Task).count() > 0:
        return
    if EXCEL_SEED.exists():
        import_excel_data(db, EXCEL_SEED, replace=False)
        return

    # Minimal fallback when the Excel seed file is not present.
    db.add(
        models.Person(
            name="冯海林",
            role="组长 / CEO",
            department="管理层",
            special_project_duty="方向判断、项目统筹、重大决策、阶段验收",
            permission="确认",
        )
    )
    db.add(
        models.Task(
            special_project="知识资产AI化",
            key_task="设计知识库框架、目录和管理规则",
            key_achievement="知识库框架、知识资产目录、管理规则",
            completion_standard="明确知识库结构、标签、权限和更新规则",
            coordinator="刘万超",
            owner="杨宇帆",
            collaborators="袁金玉、郭熠彬、吴肖",
            plan_time="2026-05",
            status="未开始",
            source_type="内置兜底数据",
        )
    )
    db.commit()
