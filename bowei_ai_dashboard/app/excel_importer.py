import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from sqlalchemy.orm import Session

from . import models
from .permissions import ROLE_CEO

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

PROJECT_MAP = {
    "知识资产AI化专项": "知识资产AI化",
    "顾问作业AI化专项": "顾问作业AI化",
    "交付流程AI化专项": "交付流程AI化",
    "咨询服务产品化专项": "咨询服务产品化",
    "技术底座与平台预研专项": "技术底座与平台预研",
}

STATUS_MAP = {
    "未启动": "未开始",
    "进行中": "推进中",
    "已完成": "已完成",
    "延期": "延期",
    "暂缓": "暂缓",
}


def normalize_project(value: str) -> str:
    value = (value or "").strip()
    return PROJECT_MAP.get(value, value)


def normalize_status(value: str) -> str:
    value = (value or "").strip()
    return STATUS_MAP.get(value, value or "未开始")


def normalize_month(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    match = re.search(r"(\d{1,2})", value)
    if match:
        month = max(1, min(12, int(match.group(1))))
        return f"2026-{month:02d}"
    return value


class XlsxReader:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.zip = zipfile.ZipFile(self.path)
        self.shared_strings = self._read_shared_strings()
        self.sheet_paths = self._read_sheet_paths()

    def _read_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self.zip.namelist():
            return []
        root = ET.fromstring(self.zip.read("xl/sharedStrings.xml"))
        return ["".join(t.text or "" for t in item.findall(".//a:t", NS)) for item in root.findall("a:si", NS)]

    def _read_sheet_paths(self) -> dict[str, str]:
        workbook = ET.fromstring(self.zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self.zip.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        paths = {}
        for sheet in workbook.findall("a:sheets/a:sheet", NS):
            name = sheet.attrib["name"]
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_map[rid].lstrip("/")
            paths[name] = "xl/" + target if not target.startswith("xl/") else target
        return paths

    def _cell_value(self, cell) -> str:
        cell_type = cell.attrib.get("t")
        value = cell.find("a:v", NS)
        inline = cell.find("a:is", NS)
        if cell_type == "s" and value is not None:
            return self.shared_strings[int(value.text)]
        if cell_type == "inlineStr" and inline is not None:
            return "".join(t.text or "" for t in inline.findall(".//a:t", NS))
        return value.text if value is not None else ""

    def rows(self, sheet_name: str) -> list[list[str]]:
        root = ET.fromstring(self.zip.read(self.sheet_paths[sheet_name]))
        result = []
        for row in root.findall("a:sheetData/a:row", NS):
            cells = {}
            max_col = 0
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "")
                col_idx = column_index(re.sub(r"\d", "", ref))
                max_col = max(max_col, col_idx)
                cells[col_idx] = self._cell_value(cell).strip()
            result.append([cells.get(i, "") for i in range(1, max_col + 1)])
        return result


def column_index(letters: str) -> int:
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - 64
    return index


def as_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    return {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}


def import_excel_data(db: Session, excel_path: Path, replace: bool = False) -> dict[str, int]:
    reader = XlsxReader(excel_path)
    if replace:
        for model in (models.OperationLog, models.UpdateSubmission, models.Issue,
                      models.Achievement, models.Task, models.Person, models.Project):
            db.query(model).delete()
        db.commit()

    project_count = import_projects(db, reader)
    people_count = import_people(db, reader)
    task_count, achievement_count = import_tasks_and_planned_achievements(db, reader)
    issue_count = import_monthly_review_issues(db, reader)
    db.commit()
    return {"projects": project_count, "people": people_count,
            "tasks": task_count, "achievements": achievement_count, "issues": issue_count}


def import_projects(db: Session, reader: XlsxReader) -> int:
    """从"组织与分工" sheet 下半段提取专项列表存入 projects 表。"""
    assignments = _read_raw_project_assignments(reader)
    count = 0
    for idx, a in enumerate(assignments):
        name = a["special_project"]
        if not name:
            continue
        existing = db.query(models.Project).filter_by(name=name).first()
        if existing:
            existing.coordinator = a["coordinator"]
            existing.owners = a["owner"]
            existing.collaborators = a["collaborators"]
            existing.sort_order = idx
        else:
            db.add(models.Project(
                name=name,
                coordinator=a["coordinator"],
                owners=a["owner"],
                collaborators=a["collaborators"],
                sort_order=idx,
                is_active=True,
            ))
            count += 1
    return count


def _build_person_project_map(reader: XlsxReader) -> dict[str, list[str]]:
    """返回 {人名: [专项名, ...]} 映射，基于 Excel 项目分配表。"""
    assignments = _read_raw_project_assignments(reader)
    person_projects: dict[str, set[str]] = {}

    def add(name: str, project: str):
        name = name.strip()
        if not name:
            return
        for n in re.split(r"[,，、/]", name):
            n = n.strip()
            if n:
                person_projects.setdefault(n, set()).add(project)

    for a in assignments:
        proj = a["special_project"]
        add(a["coordinator"], proj)
        add(a["owner"], proj)
        for c in re.split(r"[,，、/]", a["collaborators"]):
            add(c, proj)

    return {k: sorted(v) for k, v in person_projects.items()}


def import_people(db: Session, reader: XlsxReader) -> int:
    rows = reader.rows("组织与分工")
    headers = rows[0]
    person_projects = _build_person_project_map(reader)
    count = 0
    for row in rows[1:]:
        first_cell = row[0] if row else ""
        if not first_cell or first_cell == "专项":
            break
        item = as_dict(headers, row)
        name = item.get("成员", "")
        if not name:
            continue
        projects = person_projects.get(name, [])
        special_project_duty = "、".join(projects) if projects else item.get("核心职责", "")
        role = item.get("角色定位", "")
        is_admin = "工程师" in role or "技术" in role
        existing = db.query(models.Person).filter_by(name=name).first()
        if existing:
            existing.role = role
            existing.special_project_duty = special_project_duty
            existing.permission = permission_from_role(role)
            existing.is_admin = is_admin
            existing.is_active = True
        else:
            db.add(models.Person(
                name=name,
                role=role,
                department="",
                special_project_duty=special_project_duty,
                permission=permission_from_role(role),
                contact="",
                is_active=True,
                is_admin=is_admin,
            ))
            count += 1
    return count


def _read_raw_project_assignments(reader: XlsxReader) -> list[dict[str, str]]:
    rows = reader.rows("组织与分工")
    start = None
    for idx, row in enumerate(rows):
        if row and row[0] == "专项":
            start = idx + 1
            break
    if start is None:
        return []
    assignments = []
    for row in rows[start:]:
        if not row or not row[0]:
            continue
        assignments.append({
            "special_project": normalize_project(row[0]),
            "coordinator": row[1] if len(row) > 1 else "",
            "owner": row[2] if len(row) > 2 else "",
            "collaborators": row[3] if len(row) > 3 else "",
        })
    return assignments


def read_project_assignments(excel_path: Path) -> list[dict[str, str]]:
    reader = XlsxReader(excel_path)
    return _read_raw_project_assignments(reader)


def permission_from_role(role: str) -> str:
    if "CEO" in role or "组长" in role:
        return "确认"
    if "负责人" in role or "统筹" in role:
        return "维护"
    return "查看"


def import_tasks_and_planned_achievements(db: Session, reader: XlsxReader) -> tuple[int, int]:
    """从 Excel「工作推进总表」sheet 导入重点工作(Task)和预定成果(Achievement)。

    列映射（语义对齐）：
      Excel 列「关键任务」→ Task.key_task（物理字段名，业务语义：重点工作名称）
      Excel 列「关键成果」→ Task.key_achievement + Achievement.name
      Excel 列「专项」   → Task.special_project（项目名镜像）
      Excel 列「负责人」 → Task.owner
    """
    rows = reader.rows("工作推进总表")
    headers = rows[0]
    task_count = 0
    achievement_count = 0
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        item = as_dict(headers, row)
        key_task = item.get("关键任务", "")  # Excel 列名「关键任务」，映射到 Task.key_task（重点工作名称）
        if not key_task:
            continue
        project = normalize_project(item.get("专项", ""))
        task = models.Task(
            special_project=project,
            key_task=key_task,
            key_achievement=item.get("关键成果", ""),
            completion_standard=item.get("完成标准", ""),
            coordinator=item.get("统筹人", ""),
            owner=item.get("负责人", ""),
            collaborators=item.get("协同/人员", ""),
            plan_time=normalize_month(item.get("计划时间", "")),
            status=normalize_status(item.get("当前状态", "")),
            problem_note=item.get("问题与需协调事项", ""),
            achievement_links="",
            source_type="Excel导入",
        )
        db.add(task)
        db.flush()
        task_count += 1

        achievement_name = item.get("关键成果", "")
        if achievement_name:
            db.add(
                models.Achievement(
                    name=achievement_name,
                    achievement_type=guess_achievement_type(achievement_name),
                    special_project=project,
                    related_task_id=task.id,
                    owner=item.get("负责人", ""),
                    version="",
                    file_link="",
                    scenario=item.get("阶段", "") or project,
                    reuse_tag=guess_reuse_tag(project, achievement_name),
                    status="计划中",
                    source_type="Excel预定成果",
                )
            )
            achievement_count += 1
    return task_count, achievement_count


def guess_achievement_type(name: str) -> str:
    upper_name = name.upper()
    if "SOP" in upper_name:
        return "SOP"
    if "PROMPT" in upper_name or "提示词" in name:
        return "Prompt"
    if "AGENT" in upper_name or "原型" in name:
        return "Agent原型"
    if "纪要" in name:
        return "会议纪要"
    if "复盘" in name:
        return "复盘报告"
    if "案例" in name:
        return "案例包"
    if "产品" in name or "销售" in name:
        return "产品材料"
    if "方案" in name:
        return "方案"
    if "表" in name or "清单" in name:
        return "表格"
    if "模板" in name:
        return "模板"
    if "报告" in name or "简报" in name:
        return "复盘报告"
    return "方案"


def guess_reuse_tag(project: str, name: str) -> str:
    if "客户" in name:
        return "客户交付"
    if "产品" in project or "产品" in name or "销售" in name:
        return "产品材料"
    if "复盘" in name or "项目" in project:
        return "项目复用"
    return "内部使用"


def import_monthly_review_issues(db: Session, reader: XlsxReader) -> int:
    ceo_row = db.query(models.Person).filter_by(system_role=ROLE_CEO, is_active=True).first()
    ceo_name = ceo_row.name if ceo_row else ""
    rows = reader.rows("月度检查与复盘")
    headers = rows[0]
    count = 0
    for row in rows[1:]:
        item = as_dict(headers, row)
        project = normalize_project(item.get("专项", ""))
        month = normalize_month(item.get("月份", ""))
        problem = item.get("主要问题", "")
        decision = item.get("需决策事项", "")
        owner = item.get("负责人", "")
        if problem:
            db.add(
                models.Issue(
                    issue_type="问题",
                    description=problem,
                    owner=owner,
                    helper=item.get("统筹人", ""),
                    priority="中",
                    status=normalize_status(item.get("状态", "未启动")),
                    expected_resolve_time=month,
                    special_project=project,
                    source_type="Excel导入",
                )
            )
            count += 1
        if decision:
            db.add(
                models.Issue(
                    issue_type="决策事项",
                    description=decision,
                    owner=owner,
                    helper=item.get("统筹人", ""),
                    priority="高",
                    status="待处理",
                    need_decision_by=ceo_name,
                    expected_resolve_time=month,
                    special_project=project,
                    source_type="Excel导入",
                )
            )
            count += 1
    return count
