# -*- coding: utf-8 -*-
"""按用户提供的推进表导入：1个项目「AI升级计划」，下设6个重点工作，共22个关键任务"""
import os
import re
import sys
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard/bowei_ai_dashboard.db",
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Person, Project, Task, SubTask

YEAR = 2026

db = SessionLocal()
people = {p.name: p.id for p in db.query(Person).all()}


def parse_md(s):
    """解析「7月3日」格式"""
    m = re.match(r"(\d{1,2})月(\d{1,2})日", (s or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def fmt_time(s, e):
    """把起止时间转成「7.3-7.10」"""
    a, b = parse_md(s), parse_md(e)
    if a and b:
        return f"{a[0]}.{a[1]}-{b[0]}.{b[1]}"
    if a:
        return f"{a[0]}.{a[1]}"
    return ""


def split_names(s):
    """按常见分隔符拆分人名，空/无/暂无返回空列表"""
    if not s or s.strip() in ("无", "暂无"):
        return []
    return [x.strip() for x in re.split(r"[/,、\\]+", s) if x.strip()]


def resolve_owner(s):
    """
    解析责任人：
    - 「项目经理」保持字面，id 为空
    - 多人以「、」分隔时，第一人作为主责任人，其余放入协同人
    """
    if not s or s.strip() == "项目经理":
        return "项目经理", None, []
    names = split_names(s)
    if not names:
        return "项目经理", None, []
    primary = names[0]
    rest = names[1:]
    return primary, people.get(primary), rest


def build_task_plan_time(subtasks):
    """根据子任务最早开始、最晚结束生成重点工作计划时间"""
    starts = []
    ends = []
    for st in subtasks:
        sd = parse_md(st.get("start"))
        ed = parse_md(st.get("end"))
        if sd:
            starts.append(sd)
        if ed:
            ends.append(ed)
    if starts and ends:
        return f"{starts[0][0]}.{starts[0][1]}-{ends[-1][0]}.{ends[-1][1]}"
    if starts:
        return f"{starts[0][0]}.{starts[0][1]}"
    return ""


# ---- 数据结构：6 个重点工作 + 22 个关键任务 ----
DATA = [
    {
        "key_task": "一、联合腾讯 WorkBuddy 开拓 AI 相关业务",
        "completion_standard": "1. AI相关业务收入占比达到10%；\n2. 形成联合拓客机制；\n3. 达成阶段性客户转化目标。",
        "subtasks": [
            {"seq": 1, "title": "明确联合拓展方案与目标客户范围", "owner": "杨宇帆", "start": "7月3日", "end": "7月10日", "collab": "邹奇敏"},
            {"seq": 2, "title": "策划并执行联合市场活动", "owner": "邹奇敏", "start": "7月3日", "end": "持续（3场以上）", "collab": "杨宇帆/温会林"},
            {"seq": 3, "title": "跟进重点客户转化与签约", "owner": "邹奇敏", "start": "7月3日", "end": "持续", "collab": "大侠（专业支持）/全员（客户）"},
        ],
    },
    {
        "key_task": "二、打造 AI 应用标杆案例",
        "completion_standard": "1. 形成2-3个可对外展示的标杆案例；\n2. 形成销售工具包；\n3. 可支撑市场推广与客户转化。",
        "subtasks": [
            {"seq": 4, "title": "选择标杆客户与高价值场景", "owner": "刘万超", "start": "7月10日", "end": "7月13日", "collab": ""},
            {"seq": 5, "title": "推进试点应用落地并形成结果", "owner": "项目经理", "start": "", "end": "", "collab": ""},
            {"seq": 6, "title": "提炼案例成果、方法与客户价值", "owner": "项目经理", "start": "", "end": "", "collab": ""},
            {"seq": 7, "title": "沉淀销售工具包", "owner": "项目经理", "start": "", "end": "", "collab": ""},
        ],
    },
    {
        "key_task": "三、开发并应用项目运营系统，形成 AI 驱动的项目执行体系",
        "completion_standard": "1. 项目运营系统覆盖率达到80%；\n2. 至少2个项目跑通闭环；\n3. 形成标准项目执行模板并在项目中应用。",
        "subtasks": [
            {"seq": 8, "title": "完成系统模块梳理与迭代", "owner": "吴肖、郭熠彬", "start": "7月3日", "end": "7月10日", "collab": "无"},
            {"seq": 9, "title": "选择现有项目导入系统运行", "owner": "刘万超", "start": "7月13日", "end": "", "collab": ""},
            {"seq": 10, "title": "梳理目标、任务、执行、反馈、复盘流程", "owner": "项目经理", "start": "", "end": "", "collab": ""},
        ],
    },
    {
        "key_task": "四、推进 AI 组织建设，形成组织运行机制",
        "completion_standard": "1. 形成AI项目运行单元；\n2. 建立人机协同、项目运营、AI治理三类机制；\n3. 可在项目中稳定运行。",
        "subtasks": [
            {"seq": 11, "title": "明确AI项目运行团队角色与分工", "owner": "温会林", "start": "7月3日", "end": "7月10日", "collab": ""},
            {"seq": 12, "title": "建立人机任务分配与协同机制", "owner": "温会林", "start": "7月3日", "end": "需完成场景、岗位的AI Agent的构建运作，提取方法论形成（7月底前在基于现在对claude、ChatGPT、workbuddy的知识、语料的使用方式上，整理出相关内容）", "collab": ""},
            {"seq": 13, "title": "建立知识调用、反馈与复盘闭环", "owner": "刘万超", "start": "7月10日", "end": "", "collab": ""},
            {"seq": 14, "title": "建立Agent与知识库治理机制", "owner": "刘万超", "start": "7月10日", "end": "", "collab": ""},
        ],
    },
    {
        "key_task": "五、建设知识库，形成知识资产与方法论体系",
        "completion_standard": "1. 知识库V1.0建成并可调用；\n2. 核心方法论、模板、案例完成首批入库；\n3. 在多个项目中实际调用。",
        "subtasks": [
            {"seq": 15, "title": "梳理知识目录结构与入库标准", "owner": "杨宇帆", "start": "7月7日", "end": "7月10日", "collab": ""},
            {"seq": 16, "title": "萃取资深顾问知识与项目案例", "owner": "杨宇帆", "start": "7月13日", "end": "逐个项目进行，计划先从魏都项目、云宏项目开始，后续再安排", "collab": "暂无"},
            {"seq": 17, "title": "完成方法论、模板、案例首批入库", "owner": "刘万超", "start": "7月13日", "end": "", "collab": ""},
            {"seq": 18, "title": "在项目中测试调用并持续更新", "owner": "郭熠彬", "start": "7月6日", "end": "7月10日", "collab": "暂无"},
        ],
    },
    {
        "key_task": "六、开发 Skill、Agent 与数字分身，形成可复用的 AI 能力体系",
        "completion_standard": "1. Skill体系初步形成；\n2. 开发高频Agent；\n3. 数字分身进入试点；\n4. 在项目中实现实际应用与迭代优化。",
        "subtasks": [
            {"seq": 19, "title": "识别高价值场景，并设计、开发与测试Skill", "owner": "许明良", "start": "7月6日", "end": "梳理清单后，进行任务分配，根据场景和agent及skill需求，完成工作任务。计划7月份基本成型（基本成型=有成功案例+建造的流程标准化指导+覆盖部分核心场景）", "collab": "吴肖、郭熠彬"},
            {"seq": 20, "title": "梳理AI First工作流，设计、开发与测试Agent", "owner": "许明良", "start": "7月6日", "end": "", "collab": "吴肖、郭熠彬"},
            {"seq": 21, "title": "选择专家角色试点数字分身", "owner": "刘万超", "start": "7月22日", "end": "10月1日", "collab": ""},
            {"seq": 22, "title": "在项目中应用并迭代优化", "owner": "项目经理", "start": "", "end": "", "collab": ""},
        ],
    },
]

# ---- 查找/创建项目 ----
proj = db.query(Project).filter(Project.name == "AI升级计划").first()
if not proj:
    proj = Project(
        name="AI升级计划",
        description="AI升级转型 2026年下半年目标与重点工作计划",
        status="active",
        start_date="2026-07-01",
        end_date="2026-12-31",
        owners="冯海林",
        is_active=True,
    )
    db.add(proj)
    db.flush()
    print(f"[CREATE] Project: AI升级计划 (id={proj.id})")
else:
    print(f"[EXIST] Project: AI升级计划 (id={proj.id})")

# ---- 清空旧的 tasks / subtasks ----
deleted_subs = db.query(SubTask).filter(SubTask.task_id.in_(
    db.query(Task.id).filter(Task.project_id == proj.id)
)).delete(synchronize_session=False)
deleted_tasks = db.query(Task).filter(Task.project_id == proj.id).delete(synchronize_session=False)
print(f"[CLEAN] 删除旧数据: {deleted_tasks} 个重点工作, {deleted_subs} 个关键任务")

counts = {"tasks": 0, "subtasks": 0}

for item in DATA:
    # 收集协同人（去重，排除主责任人）
    all_collabs = set()
    primary_owners = set()
    for st in item["subtasks"]:
        owner_name, _, owner_rest = resolve_owner(st["owner"])
        primary_owners.add(owner_name)
        for r in owner_rest:
            all_collabs.add(r)
        for c in split_names(st["collab"]):
            all_collabs.add(c)
    # 仅保留系统里存在的人员作为正式协同人字段
    known_collabs = sorted([c for c in all_collabs if c in people and c not in primary_owners])
    # 任务负责人取第一个子任务主责任人
    first_owner_name, first_owner_id, _ = resolve_owner(item["subtasks"][0]["owner"])

    task = Task(
        project_id=proj.id,
        special_project="AI升级计划",
        key_task=item["key_task"],
        completion_standard=item["completion_standard"],
        owner=first_owner_name,
        owner_id=first_owner_id,
        collaborators="、".join(known_collabs),
        plan_time=build_task_plan_time(item["subtasks"]),
        status="进行中",
        source_type="批量导入",
    )
    db.add(task)
    db.flush()
    counts["tasks"] += 1
    print(f"[CREATE] 重点工作: {item['key_task']} ({first_owner_name})")

    for st in item["subtasks"]:
        owner_name, owner_id, owner_rest = resolve_owner(st["owner"])
        plan_time = fmt_time(st["start"], st["end"])

        # 结束时间如果不是纯日期，作为完成说明保存
        completion_note = ""
        if st["end"] and not parse_md(st["end"]):
            completion_note = st["end"]

        # 构建 notes：先写原始协同人/多责任人信息，便于前端展示
        notes_lines = []
        # 责任人含多人时，其余人写进备注
        if st["owner"] and "、" in st["owner"] and owner_rest:
            notes_lines.append("协同人：" + "、".join(owner_rest))
        # 原始协同人（含系统外角色如「大侠」）保留展示
        if st["collab"] and st["collab"].strip() not in ("", "无", "暂无"):
            notes_lines.append("协同人：" + st["collab"].strip())
        if st["owner"] and st["owner"].strip() == "项目经理":
            notes_lines.append("责任人：项目经理（待指定）")

        sub = SubTask(
            task_id=task.id,
            title=f"{st['seq']}. {st['title']}",
            assignee=owner_name,
            assignee_id=owner_id,
            plan_time=plan_time,
            status="未开始",
            completion_criteria=completion_note,
            notes="\n".join(notes_lines),
        )
        db.add(sub)
        counts["subtasks"] += 1
        print(f"  [CREATE] 关键任务: {st['seq']}. {st['title']} ({owner_name}, {plan_time or '无日期'})")

db.commit()

# ---- 验证 ----
print(f"\n--- 验证 ---")
proj = db.query(Project).filter(Project.name == "AI升级计划").first()
tasks = db.query(Task).filter(Task.project_id == proj.id).order_by(Task.id).all()
print(f"项目: {proj.name}")
print(f"重点工作: {len(tasks)}")
total_sub = 0
for t in tasks:
    n = db.query(SubTask).filter(SubTask.task_id == t.id).count()
    total_sub += n
    print(f"  - {t.key_task}: {n} 个关键任务")
print(f"关键任务总计: {total_sub}")
print(f"本次新增: {counts['tasks']} 重点工作, {counts['subtasks']} 关键任务")
db.close()
print("DONE")
