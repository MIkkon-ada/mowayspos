import asyncio
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..domain import task_status as TS
from ..database import get_db
from ..llm_config import get_provider_config

logger = logging.getLogger("bowei.meetings")
from ..permissions import (
    PROJECT_ROLE_COORD_KEY,
    PROJECT_ROLE_MEMBER_KEY,
    PROJECT_ROLE_OWNER_KEY,
    can_view_project,
    get_current_user_name,
    get_user_context_from_db,
    require_login,
    require_project_access,
    require_project_role,
)
from ..services.project_resolution import resolve_project_context
from ..services.project_close import require_project_business_writable

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

# ── 5C 写权限检查 ─────────────────────────────────────────────
def _require_global_read_scope(context: dict) -> None:
    if not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")


def _meeting_project_id_or_raise(row: models.Meeting, context: dict, db: Session) -> int | None:
    project_id = resolve_project_context(
        db,
        project_id=row.project_id,
        related_special_project=row.related_special_project or "",
    )["project_id"]
    if project_id is not None:
        return project_id
    if context.get("is_tech_admin"):
        return None
    raise HTTPException(403, "permission denied")


def _is_meeting_creator(current_user: str, context: dict, row: models.Meeting) -> bool:
    row_host = (row.host or "").strip()
    if not row_host:
        return False
    candidates = {current_user.strip()}
    name = (context.get("name") or "").strip()
    if name:
        candidates.add(name)
    return row_host in candidates


def _row_project_id(row: models.Meeting, db: Session) -> int | None:
    return resolve_project_context(
        db,
        project_id=row.project_id,
        related_special_project=row.related_special_project or "",
    )["project_id"]


@router.get("")
def list_meetings(
    project_id: int | None = None,
    related_special_project: str | None = None,
    meeting_type: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)

    resolution = resolve_project_context(
        db,
        project_id=project_id,
        related_special_project=related_special_project,
    )
    effective_project_id: int | None = resolution["project_id"]
    if project_id is not None and not resolution["is_valid"]:
        raise HTTPException(404, "project not found")
    if project_id is None and related_special_project and effective_project_id is None:
        return []

    if effective_project_id is not None:
        require_project_access(current_user, effective_project_id, db)
    elif not related_special_project:
        _require_global_read_scope(context)

    q = db.query(models.Meeting)
    if effective_project_id is not None:
        q = q.filter(models.Meeting.project_id == effective_project_id)
    if meeting_type:
        q = q.filter(models.Meeting.meeting_type == meeting_type)

    return [
        crud.to_dict(r)
        for r in q.order_by(
            models.Meeting.meeting_date.desc(),
            models.Meeting.updated_at.desc(),
        ).all()
    ]


@router.post("")
def create_meeting(
    payload: schemas.MeetingPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    if payload.project_id is None:
        raise HTTPException(422, "project_id is required")

    require_project_role(
        current_user,
        payload.project_id,
        [
            PROJECT_ROLE_OWNER_KEY,
            PROJECT_ROLE_COORD_KEY,
            PROJECT_ROLE_MEMBER_KEY,
        ],
        db,
    )
    require_project_business_writable(payload.project_id, db)

    project_name = resolve_project_context(
        db,
        project_id=payload.project_id,
        related_special_project=payload.related_special_project,
    )["project_name"] or ""
    data = {
        k: v
        for k, v in payload.model_dump().items()
        if k not in {"project_id", "related_special_project"}
    }
    row = models.Meeting(**data)
    row.project_id = payload.project_id
    if payload.related_special_project:
        row.related_special_project = payload.related_special_project
    elif project_name:
        row.related_special_project = project_name
    db.add(row)
    db.flush()
    crud.log(db, current_user, "meeting_create", "meeting", row.id, {}, crud.to_dict(row))
    db.commit()
    db.refresh(row)
    return crud.to_dict(row)


class MeetingAnalyzeRequest(BaseModel):
    text: str
    project_id: int | None = None


@router.post("/analyze")
async def analyze_meeting(
    payload: MeetingAnalyzeRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    if payload.project_id is not None:
        require_project_access(current_user, payload.project_id, db)

    if not payload.text.strip():
        raise HTTPException(422, "text 不能为空")

    # 如果转写文本里有说话人编号，就使用带成员背景的提示词。
    has_speakers = bool(re.search(r"\d+", payload.text))
    if has_speakers:
        prompt = _PROMPT_REPORT.format(
            member_context="请结合说话人映射与成员背景，分析每位成员的汇报内容。",
            text=payload.text[:10000],
        )
    else:
        prompt = _PROMPT_GENERIC.format(text=payload.text[:8000])

    provider = _pick_provider()
    try:
        result = await asyncio.to_thread(_do_analyze, payload.text, prompt, provider)
    except Exception as exc:
        logger.warning("meeting analyze failed: %s", exc)
        raise HTTPException(500, f"AI analysis failed: {exc}")

    reports = result.get("reports") or []
    decisions = result.get("decisions") or []
    action_items = result.get("action_items") or result.get("task_list") or []

    return {
        "title": result.get("title", ""),
        "meeting_type": result.get("meeting_type", ""),
        "meeting_date": result.get("meeting_date", ""),
        "host": result.get("host", ""),
        "participants": result.get("participants", ""),
        "summary": result.get("summary", ""),
        "reports_json": json.dumps(reports, ensure_ascii=False),
        "task_list_json": json.dumps(action_items, ensure_ascii=False),
        "decision_items_json": json.dumps(decisions, ensure_ascii=False),
        "risk_items_json": json.dumps(result.get("risk_items") or [], ensure_ascii=False),
        "transcript_text": payload.text,
        "has_speakers": has_speakers,
    }


@router.get("/{row_id}")
def get_meeting(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")
    project_id = _row_project_id(row, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    return crud.to_dict(row)


@router.put("/{row_id}")
def update_meeting(
    row_id: int,
    payload: schemas.MeetingPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")

    project_id = _meeting_project_id_or_raise(row, context, db)
    if project_id is not None and not _is_meeting_creator(current_user, context, row):
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY],
            db,
        )

    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    update_data = {
        k: v
        for k, v in payload.model_dump().items()
        if k not in {"project_id", "related_special_project"}
    }
    crud.update_model(row, update_data)
    if context.get("is_tech_admin") and payload.project_id is not None:
        row.project_id = payload.project_id
    if context.get("is_tech_admin") and payload.related_special_project:
        row.related_special_project = payload.related_special_project
    crud.log(db, current_user, "meeting_update", "meeting", row.id, before, payload.model_dump())
    db.commit()
    return crud.to_dict(row)


@router.patch("/{row_id}/status")
def patch_meeting_status(
    row_id: int,
    payload: schemas.MeetingStatusPatch,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")

    project_id = _meeting_project_id_or_raise(row, context, db)
    if project_id is not None:
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY],
            db,
        )

    require_project_business_writable(project_id, db)
    allowed = {"draft", "published", "returned"}
    if payload.publish_status not in allowed:
        raise HTTPException(422, f"publish_status must be one of {allowed}")

    before = {"publish_status": row.publish_status}
    row.publish_status = payload.publish_status
    action = {
        "published": "meeting_publish",
        "returned": "meeting_return",
        "draft": "meeting_save_draft",
    }.get(payload.publish_status, "meeting_update_status")
    crud.log(db, current_user, action, "meeting", row.id, before, {"publish_status": payload.publish_status})

    if payload.publish_status == "published":
        from ..services.notify import send as _notify, person_name_for_account
        import json as _json
        caller_name = person_name_for_account(current_user, db)
        project_id = _row_project_id(row, db)
        try:
            action_items = _json.loads(row.task_list_json or "[]")
        except Exception:
            action_items = []
        from ..services.notify import person_id_for_name as _pid_for_name
        import re as _re
        notified: set[str] = set()
        # 向参会人发送已发布会议通知。
        participant_str = row.participants or ""
        participants = [p.strip() for p in _re.split(r"[,??\n]+", participant_str) if p.strip()]
        for p in participants:
            if p != caller_name and p not in notified:
                notified.add(p)
                _notify(db, recipient_id=_pid_for_name(p, db), recipient=p,
                        ntype="meeting_published",
                        title=f"会议已发布：{row.title or '未命名会议'}",
                        body=f"会议《{row.title or '未命名会议'}》已由 {caller_name} 发布，日期：{row.meeting_date or '未填写'}",
                        link=f"/project/{project_id}/meeting" if project_id else "",
                        project_id=project_id)
        # 向需要执行行动项的成员发送任务通知。
        for item in action_items:
            member = (item.get("member") or "").strip()
            if member and member != caller_name and member not in notified:
                notified.add(member)
                _notify(db, recipient_id=_pid_for_name(member, db), recipient=member,
                        ntype="meeting_action",
                        title=f"会议行动项：{row.title or '未命名会议'}",
                        body=f"请处理事项：{item.get('task', '')}，截止时间：{item.get('deadline') or '未填写'}",
                        link=f"/project/{project_id}/meeting" if project_id else "",
                        project_id=project_id)

    db.commit()
    return crud.to_dict(row)


@router.delete("/{row_id}")
def delete_meeting(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")

    project_id = _meeting_project_id_or_raise(row, context, db)
    if project_id is not None:
        require_project_role(current_user, project_id, [PROJECT_ROLE_OWNER_KEY], db)

    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    crud.log(db, current_user, "meeting_delete", "meeting", row_id, before, {})
    db.delete(row)
    db.commit()
    return {"ok": True}


class GenerateTaskCardsRequest(BaseModel):
    project_id: int
    transcript_text: str
    speaker_map: dict[str, str]


_PROMPT_TASK_CARDS = """你是会议任务卡生成助手。
请根据 speaker_map、tasks_context 和 text 生成任务卡，只输出严格 JSON，不要输出任何解释。

speaker_map:
{speaker_map}

tasks_context:
{tasks_context}

text:
{text}

输出格式：
{
  "task_cards": [
    {
      "action": "create | update_status | add_note",
      "parent_task_id": 123,
      "subtask_id": 456,
      "title": "任务标题",
      "subtask_title": "子任务标题",
      "assignee": "负责人",
      "plan_time": "YYYY-MM-DD 或空字符串",
      "new_status": "状态值",
      "notes": "补充说明",
      "note": "备注",
      "evidence": "原文证据"
    }
  ]
}

要求：
- 只输出 JSON
- 如果没有可执行任务，返回 {"task_cards": []}
- action 只能是 create、update_status、add_note
- 优先匹配 tasks_context 中已有任务和子任务
- evidence 用原文短句支持判断
"""


def _build_tasks_context(project_id: int, db: Session) -> str:
    tasks = (
        db.query(models.Task)
        .filter(
            models.Task.project_id == project_id,
            models.Task.is_deleted.is_(False),
            models.Task.status.notin_([TS.S_COMPLETED, TS.S_ARCHIVED]),
        )
        .order_by(models.Task.id.asc())
        .all()
    )
    lines: list[str] = []
    for task in tasks:
        lines.append(
            f"关键任务 #{task.id}：{task.key_task}"
            f"｜负责人：{task.owner or '未填写'}｜状态：{task.status or '未填写'}"
        )
        subtasks = (
            db.query(models.SubTask)
            .filter(models.SubTask.task_id == task.id, models.SubTask.is_deleted.is_(False))
            .order_by(models.SubTask.id.asc())
            .all()
        )
        for st in subtasks:
            lines.append(
                f"  - 子任务 #{st.id}：{st.title}"
                f"｜状态：{st.status or '未填写'}｜负责人：{st.assignee or '未填写'}"
            )
    return "\n".join(lines) if lines else "暂无可参考的关键任务"


@router.post("/generate-task-cards")
async def generate_task_cards(
    payload: GenerateTaskCardsRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    require_project_role(
        current_user,
        payload.project_id,
        [PROJECT_ROLE_OWNER_KEY, PROJECT_ROLE_COORD_KEY],
        db,
    )

    if not payload.transcript_text.strip():
        raise HTTPException(422, "transcript_text 不能为空")
    if not payload.speaker_map:
        raise HTTPException(422, "speaker_map 不能为空")

    tasks_context = _build_tasks_context(payload.project_id, db)
    speaker_context = "\n".join(
        f"{k} = {v}" for k, v in payload.speaker_map.items()
    )
    prompt = _PROMPT_TASK_CARDS.format(
        speaker_map=speaker_context,
        tasks_context=tasks_context,
        text=payload.transcript_text[:12000],
    )

    provider = _pick_provider()
    try:
        result = await asyncio.to_thread(_do_analyze, payload.transcript_text, prompt, provider)
    except Exception as exc:
        logger.warning("generate_task_cards failed: %s", exc)
        raise HTTPException(500, f"AI analysis failed: {exc}")

    raw_cards = result.get("task_cards") or []
    enriched: list[dict] = []
    for card in raw_cards:
        action = card.get("action")
        if action in ("update_status", "add_note"):
            sid = card.get("subtask_id")
            if sid:
                row = db.get(models.SubTask, sid)
                if row and not getattr(row, "is_deleted", False):
                    card["current_payload"] = {
                        "title": row.title or "",
                        "assignee": row.assignee or "",
                        "plan_time": row.plan_time or "",
                        "status": row.status or "",
                        "completion_criteria": getattr(row, "completion_criteria", "") or "",
                        "notes": getattr(row, "notes", "") or "",
                    }
        enriched.append(card)

    return {"task_cards": enriched}


_PROMPT_GENERIC = """你是一个会议纪要结构化提取助手。请从下面的会议文字中提取结构化信息，只输出 JSON。

会议文字：
```
{text}
```

输出格式（严格 JSON，没有的字段填空字符串或空数组）：
{{
  "title": "根据内容自动生成会议标题",
  "meeting_type": "weekly/monthly/review/special/discuss/kickoff，选最合适的",
  "meeting_date": "YYYY-MM-DD，未提及则空字符串",
  "host": "主持人姓名，未提及则空字符串",
  "participants": "参会人逗号分隔",
  "summary": "100字以内整体摘要",
  "reports": [],
  "decisions": ["决策事项"],
  "action_items": [{{"member": "负责人", "task": "事项", "deadline": "时间或空字符串"}}]
}}
"""

# 项目汇报会提示词（有发言人映射 + 成员上下文时使用）
_PROMPT_REPORT = """你是一个项目推进汇报会的会议纪要提取专家。

【参会人员及背景】
{member_context}

【会议转录文字】
```
{text}
```

【提取要求】
这是一场项目推进汇报会，每位成员依次汇报本期进展，领导进行点评和指导。

对每位汇报人，请提取：
1. 本期完成了什么（结合该成员"上次计划"对比，判断完成情况）
2. 遇到的问题或卡点
3. 请求领导协助或需要决策的事项
4. 领导对该人的反馈（分三类）：
   - 肯定的内容
   - 需要改进的地方
   - 补充提醒（汇报人没提到但领导专门指出的盲点，这个非常重要不能遗漏）
5. 该人宣布的下一步计划（含时间节点）

注意：
- "领导"角色的发言内容是评价和指导，不是汇报，不要给他生成报告条目
- 区分"已完成"和"进行中"，汇报人说"基本完成""差不多了"属于"部分完成"
- 如果汇报人的任务与上次计划对不上，要在 vs_last_plan 中说明

严格输出 JSON，不要任何解释：
{{
  "title": "会议标题",
  "meeting_type": "weekly/monthly/review/special/discuss/kickoff",
  "meeting_date": "YYYY-MM-DD或空字符串",
  "host": "主持人姓名",
  "participants": "参会人逗号分隔",
  "summary": "100字以内整体摘要，概括本次汇报的整体完成情况和核心议题",
  "reports": [
    {{
      "member": "成员姓名",
      "role": "该成员在项目中的角色",
      "completed_items": ["本期完成的事项"],
      "vs_last_plan": "完成/部分完成/未完成/未提及",
      "issues": ["遇到的问题或卡点"],
      "requests": ["请求协助或需要决策的内容"],
      "leader_feedback": {{
        "positive": ["领导肯定的内容"],
        "improve": ["领导指出需要改进的地方"],
        "reminder": ["领导补充提醒但汇报人未提到的重要点"]
      }},
      "next_steps": [{{"task": "事项描述", "deadline": "时间节点或空字符串"}}]
    }}
  ],
  "decisions": ["本次会议整体决策事项"],
  "action_items": [{{"member": "负责人", "task": "事项", "deadline": "时间或空字符串"}}]
}}
"""




def _fetch_member_context(member_name: str, project_id: int, db: Session) -> dict:
    """查询该成员当前任务列表和上次提交的 next_steps。"""
    from sqlalchemy import or_
    from .. import models as m

    tasks = (
        db.query(m.Task)
        .filter(
            m.Task.project_id == project_id,
            or_(m.Task.owner == member_name, m.Task.collaborators.contains(member_name)),
            m.Task.status.notin_(["已完成"]),
        )
        .order_by(m.Task.plan_time)
        .limit(8)
        .all()
    )

    last_sub = (
        db.query(m.UpdateSubmission)
        .filter(
            m.UpdateSubmission.project_id == project_id,
            m.UpdateSubmission.submitter == member_name,
        )
        .order_by(m.UpdateSubmission.created_at.desc())
        .first()
    )

    next_steps: list[str] = []
    if last_sub:
        for field in (last_sub.human_result_json, last_sub.ai_result_json):
            if not field:
                continue
            try:
                data = json.loads(field)
                ns = data.get("next_steps") or []
                next_steps = [str(s) for s in ns if s]
                if next_steps:
                    break
            except Exception:
                pass

    return {
        "name": member_name,
        "tasks": [
            {
                "task": t.key_task,
                "status": t.status,
                "plan_time": t.plan_time or "",
                "problem": t.problem_note or "",
            }
            for t in tasks
        ],
        "last_next_steps": next_steps,
    }


def _build_member_context_text(
    speaker_map: dict[str, str],
    speaker_roles: dict[str, str],
    project_id: int,
    db: Session,
) -> str:
    lines: list[str] = []
    seen: set[str] = set()

    for speaker, name in speaker_map.items():
        role = speaker_roles.get(speaker, "其他")
        label = f"{speaker}（{name}，{role}）" if name else f"{speaker}（{role}）"

        if role == "领导":
            lines.append(f"- {label}：负责对汇报内容进行点评和指导，无需生成汇报条目")
            continue

        if not name or name in seen:
            lines.append(f"- {label}")
            continue
        seen.add(name)

        ctx = _fetch_member_context(name, project_id, db)

        block = [f"- {label}"]
        if ctx["last_next_steps"]:
            block.append(f"  上次计划的下一步：")
            for ns in ctx["last_next_steps"][:5]:
                block.append(f"    · {ns}")
        else:
            block.append(f"  上次计划：（无记录）")

        if ctx["tasks"]:
            block.append(f"  当前进行中任务：")
            for t in ctx["tasks"]:
                status_str = f"[{t['status']}]" if t["status"] else ""
                time_str = f"，计划{t['plan_time']}" if t["plan_time"] else ""
                problem_str = f"，问题：{t['problem']}" if t["problem"] else ""
                block.append(f"    · {t['task']}{status_str}{time_str}{problem_str}")
        lines.extend(block)

    return "\n".join(lines) if lines else "（未提供参会人信息）"


def _do_analyze(text: str, prompt: str, provider: str) -> dict:
    if provider == "anthropic":
        import anthropic
        cfg = get_provider_config("anthropic")
        if not cfg.get("api_key"):
            raise ValueError("未配置 Claude API Key")
        client = anthropic.Anthropic(api_key=cfg["api_key"], timeout=90)
        resp = client.messages.create(
            model=cfg["model"],
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text
    else:
        from openai import OpenAI
        cfg = get_provider_config(provider)
        if not cfg.get("api_key"):
            raise ValueError(f"未配置 {provider} API Key")
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=90)
        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        raw = resp.choices[0].message.content or ""

    match = re.search(r"\{[\s\S]+\}", raw.strip())
    if not match:
        raise ValueError("LLM 未返回有效 JSON")
    return json.loads(match.group())


def _pick_provider() -> str:
    for p in ("anthropic", "dashscope", "deepseek", "glm"):
        cfg = get_provider_config(p)
        if cfg.get("api_key") and cfg.get("enabled", False):
            return p
    for p in ("anthropic", "dashscope", "deepseek", "glm"):
        cfg = get_provider_config(p)
        if cfg.get("api_key"):
            return p
    return "anthropic"


