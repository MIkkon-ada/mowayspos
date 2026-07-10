import json
import logging
import os
import re
from datetime import date

logger = logging.getLogger("bowei.extractor")

from ..domain import issue_type as IT

USE_LLM = os.getenv("BOWEI_USE_LLM", "false").lower() == "true"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
# 单次 LLM 调用最长等待秒数，可通过环境变量覆盖
_LLM_TIMEOUT = int(os.getenv("LLM_CALL_TIMEOUT", "45"))

# 规则引擎项目名精确匹配列表（LLM 可用时不走此路径）
# 如需精确匹配，可在运行时通过 extract_update(project_names=...) 传入 DB 数据
PROJECTS: list[str] = []
PROJECT_ALIASES = {
    "知识库": "知识资产AI化",
    "知识资产": "知识资产AI化",
    "知识问答": "知识资产AI化",
    "顾问": "顾问作业AI化",
    "质检": "顾问作业AI化",
    "prompt": "顾问作业AI化",
    "交付": "交付流程AI化",
    "流程": "交付流程AI化",
    "产品化": "咨询服务产品化",
    "训练营": "咨询服务产品化",
    "销售材料": "咨询服务产品化",
    "平台": "技术底座与平台预研",
    "底座": "技术底座与平台预研",
    "agent": "技术底座与平台预研",
}

ACHIEVEMENT_TYPES = [
    "方案",
    "表格",
    "模板",
    "SOP",
    "Prompt",
    "Agent原型",
    "会议纪要",
    "复盘报告",
    "案例包",
    "产品材料",
]
REUSE_TAGS = ["内部使用", "项目复用", "产品材料", "客户交付"]
ISSUE_TYPES = ["问题", "风险", "待协调", "需决策"]
STATUS_VALUES = ["未开始", "进行中", "已完成", "延期", "暂缓"]

_EXTRACT_PROMPT_TMPL = """你是博维AI升级项目的结构化提取助手。今天是 {today}。请从进度汇报文本中提取结构化信息，只输出 JSON，不要输出解释。

{subtasks_section}

文本：
```
{text}
```

要求：
1. `special_project`：如实提取文本中明确提到的专项名称；若没有明确说明则留空，不要猜测
2. `related_task`：对**本次主要工作内容**的简短概括（10-25字），不要写下周计划
3. `completed_items`：本次已完成的具体事项列表
4. `achievements`：只记录已明确产出的可交付实体成果（方案文档/模板/SOP/Prompt/Agent原型/会议纪要/复盘报告/案例包/产品材料）；过程性描述不是成果
5. `issues`：将文本中所有需要处理的事项**逐条独立列出**，一段话里有多个事项就拆成多条，每条用一句话说清楚是什么需处理，**不要对事项分类（不填 issue_type）**，分类由负责人在确认环节定性，不要合并、不要遗漏
   - 只有明确出现卡住、阻塞、延期、风险、无法推进、缺少、未确认导致影响、需要负责人确认/协调/决策/拍板等情况，才进入 issues/key_task_issues/subtask_issues
   - “正在推进/目前正在做/继续推进/下周/下一步/计划/确认/完善/补充”属于正常进展或计划，不要提取成问题；例如“正在推进标签体系和权限规则”不能生成“标签体系和权限规则需要推进”
   - “可能需要某人协调”若没有说明已受阻或无法推进，只作为后续提醒，不要提取成问题/风险
6. `next_steps`：下周/后续计划列表
7. `task_reports`：将文本**按子任务维度**解析，每条回答四个问题：①完成了什么 ②形成了什么成果 ③当前有什么问题 ④下周做什么
   - type "progress"：汇报某个已有子任务的进展；matched_subtask_id 尝试匹配用户现有子任务ID，匹配不到则 null
   - type "new_task"：用户明确提出要新增一项任务（含"添加""新增""帮我建"等意图词）
   - achievements 只填已产出的可交付实体成果（文档/模板/SOP/Prompt等），过程性描述不是成果
   - subtask_issues 只填与这个子任务执行直接相关的问题；不确定属于哪个子任务的问题，放 key_task_issues
   - 时间转换（今天={today}）："约两周"=+14天，"一个月"=+30天，"下个月"=下月1日~末日，"本月底"=本月最后一日，未提及则 plan_end=plan_start+14天
   - plan_start/plan_end 必须是精确日期 YYYY-MM-DD
8. `key_task_issues`：不属于某个具体子任务、但影响整体关键任务交付的需处理事项；特定子任务的执行阻塞 → 放 subtask_issues；**不要填 issue_type**，由负责人定性
9. 没提到的信息填空字符串或空数组，不要编造
10. `summary`：一句话概括（不超过60字）

输出格式：
{{
  "summary": "",
  "special_project": "",
  "related_task": "",
  "completed_items": [""],
  "achievements": [
    {{
      "name": "",
      "achievement_type": "方案/表格/模板/SOP/Prompt/Agent原型/会议纪要/复盘报告/案例包/产品材料",
      "special_project": "",
      "owner": "",
      "version": "V0.1",
      "file_link": "",
      "scenario": "",
      "reuse_tag": "内部使用/项目复用/产品材料/客户交付",
      "status": "草稿/可复用"
    }}
  ],
  "issues": [
    {{
      "description": "一句话说清楚是什么问题",
      "priority": "高/中/低"
    }}
  ],
  "next_steps": [""],
  "task_reports": [
    {{
      "type": "progress",
      "matched_subtask_id": null,
      "matched_subtask_title": "",
      "completed": "本周在这个子任务上完成了什么（未提及则空）",
      "achievements": [{{"name": "已产出的实体成果名称", "achievement_type": "方案/模板/SOP/Prompt/Agent原型/会议纪要/复盘报告/案例包/产品材料"}}],
      "subtask_issues": ["和这个子任务直接相关的具体问题或风险（不确定属于哪个子任务则不填）"],
      "next_steps": ["下周在这个子任务上计划做什么"],
      "status_update": "进行中/已完成/延期"
    }},
    {{
      "type": "new_task",
      "title": "新任务名称（10-30字）",
      "assignee": "执行人，未提及则填提交人",
      "plan_start": "YYYY-MM-DD",
      "plan_end": "YYYY-MM-DD",
      "completed": null,
      "achievements": [],
      "subtask_issues": [],
      "next_steps": ["新任务的具体计划内容"]
    }}
  ],
  "key_task_issues": [
    {{
      "key_task_title": "归属的关键任务名称（从用户子任务推断，不确定则填专项名）",
      "description": "需处理事项描述（一句话，不要带问题/风险前缀）",
      "need_coordination": ["可能需要协调的人名，不确定可不填"],
      "priority": "高/中/低"
    }}
  ],
  "status_suggestion": "未开始/进行中/已完成/延期/暂缓"
}}
"""


def _build_subtasks_section(user_subtasks: list[dict] | None) -> str:
    if not user_subtasks:
        return "（用户暂无活跃子任务，文本中提及的新工作均提取为 new_task 类型）"
    lines = ["用户当前活跃子任务（请将进展描述尽量匹配到对应子任务）："]
    for st in user_subtasks[:20]:
        line = f"- [ID:{st.get('id')}] {st.get('title', '')}（{st.get('status', '')}）"
        if st.get("parent_key_task"):
            line += f" — 关键任务：{st['parent_key_task']}"
        lines.append(line)
    return "\n".join(lines)


def _build_extract_prompt(text: str, user_subtasks: list[dict] | None) -> str:
    today = str(date.today())
    return _EXTRACT_PROMPT_TMPL.format(
        today=today,
        subtasks_section=_build_subtasks_section(user_subtasks),
        text=text,
    )


def _get_cfg(provider: str) -> dict:
    from ..llm_config import get_provider_config

    cfg = get_provider_config(provider)
    if not cfg.get("api_key"):
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "dashscope": "DASHSCOPE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "glm": "ZHIPUAI_API_KEY",
        }
        cfg["api_key"] = os.getenv(env_map.get(provider, ""), "")
    return cfg


def _extract_json_blob(raw: str) -> dict:
    match = re.search(r"\{[\s\S]+\}", raw.strip())
    if not match:
        raise ValueError("LLM did not return valid JSON")
    return json.loads(match.group())


def _call_anthropic(text: str, user_subtasks: list[dict] | None = None) -> dict:
    import anthropic

    cfg = _get_cfg("anthropic")
    if not cfg.get("api_key"):
        raise ValueError("Claude API Key not configured")
    client = anthropic.Anthropic(api_key=cfg["api_key"], timeout=_LLM_TIMEOUT)
    prompt = _build_extract_prompt(text, user_subtasks)
    resp = client.messages.create(
        model=cfg["model"],
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json_blob(resp.content[0].text)


def _call_openai_compat(text: str, provider: str, user_subtasks: list[dict] | None = None) -> dict:
    from openai import OpenAI

    cfg = _get_cfg(provider)
    if not cfg.get("api_key"):
        raise ValueError(f"{provider} API Key not configured")
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=_LLM_TIMEOUT)
    prompt = _build_extract_prompt(text, user_subtasks)
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
    )
    return _extract_json_blob(resp.choices[0].message.content or "")


def _extract_with_llm(text: str, provider: str, user_subtasks: list[dict] | None = None) -> dict | None:
    try:
        data = (
            _call_anthropic(text, user_subtasks)
            if provider == "anthropic"
            else _call_openai_compat(text, provider, user_subtasks)
        )
        logger.info("LLM extract success provider=%s project=%s", provider, data.get("special_project"))
        return data
    except Exception as exc:
        logger.warning("LLM extract failed provider=%s: %s", provider, exc)
        return None


def _clean_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？；;\n]+", _clean_text(text))
    return [part.strip(" ，。；;") for part in parts if part.strip(" ，。；;")]


def _contains_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word.lower() in lowered for word in words)


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def _pick_project(text: str) -> str:
    for project in PROJECTS:
        if project and project in text:
            return project
    lowered = text.lower()
    for alias, project in PROJECT_ALIASES.items():
        if alias in lowered:
            return project
    return ""


def _take_sentences(text: str, include: list[str], exclude: list[str] | None = None, limit: int = 5) -> list[str]:
    exclude = exclude or []
    rows = []
    for sentence in _sentences(text):
        if _contains_any(sentence, include) and not _contains_any(sentence, exclude):
            rows.append(sentence)
    return _dedupe(rows)[:limit]


_SOFT_PROGRESS_OR_PLAN_WORDS = [
    "正在推进",
    "目前正在",
    "继续推进",
    "需要推进",
    "推进",
    "下周",
    "下一步",
    "后续",
    "计划",
    "准备",
    "确认",
    "完善",
    "补充",
]

_HARD_ISSUE_WORDS = [
    "问题",
    "风险",
    "卡点",
    "卡住",
    "阻塞",
    "延期",
    "受阻",
    "无法",
    "不能",
    "缺少",
    "未确认",
    "未到位",
    "不明确",
    "冲突",
    "报错",
    "失败",
    "影响",
    "等待",
    "依赖不到位",
    "需要负责人确认",
    "需要确认",
    "还需要确认",
    "待确认",
    "需要决策",
    "需要拍板",
]


def _is_soft_progress_or_plan(text: str) -> bool:
    """Return True when a row is normal progress/plan, not a blocker."""
    t = (text or "").strip()
    if not t:
        return False
    if _contains_any(t, _HARD_ISSUE_WORDS):
        return False
    return _contains_any(t, _SOFT_PROGRESS_OR_PLAN_WORDS)


def _filter_soft_issue_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if not _is_soft_progress_or_plan(row.get("description", ""))]


def _status(text: str) -> str:
    if _contains_any(text, ["延期", "阻塞", "卡点", "风险", "受阻"]):
        return "延期"
    if _contains_any(text, ["暂停", "暂缓", "先放一放"]):
        return "暂缓"
    if _contains_any(text, ["计划", "准备", "开始", "启动", "推进", "下周", "下一步", "后续"]):
        return "进行中"
    if _contains_any(text, ["完成", "已完成", "交付", "上线", "收尾", "验收通过"]):
        return "已完成"
    return "进行中"


def _achievement_type(name: str) -> str:
    upper = name.upper()
    if "SOP" in upper:
        return "SOP"
    if "PROMPT" in upper or "提示词" in name:
        return "Prompt"
    if "AGENT" in upper or "原型" in name:
        return "Agent原型"
    if "模板" in name:
        return "模板"
    if "表" in name or "清单" in name:
        return "表格"
    if "复盘" in name or "报告" in name:
        return "复盘报告"
    if "案例" in name:
        return "案例包"
    if "纪要" in name:
        return "会议纪要"
    if "产品" in name or "销售" in name or "物料" in name:
        return "产品材料"
    return "方案"


def _achievement_rows(text: str, project: str, submitter: str | None) -> list[dict]:
    lines = _take_sentences(
        text,
        ["形成", "产出", "输出", "沉淀", "完成", "报告", "方案", "模板", "SOP", "Prompt", "Agent", "清单", "纪要", "工具包", "手册"],
        ["问题", "风险", "下周", "下一步"],
        limit=6,
    )
    rows = []
    for line in lines:
        if not _contains_any(line, ["报告", "方案", "模板", "SOP", "Prompt", "Agent", "清单", "纪要", "工具包", "文档", "手册", "案例", "机制"]):
            continue
        rows.append(
            {
                "name": line[:80],
                "achievement_type": _achievement_type(line),
                "special_project": project,
                "owner": submitter or "",
                "version": "V0.1",
                "file_link": "",
                "scenario": "项目推进复用",
                "reuse_tag": "项目复用",
                "status": "可复用" if _contains_any(line, ["完成", "已完成", "输出", "交付"]) else "草稿",
            }
        )
    return rows


def _issue_type(line: str) -> str:
    if _contains_any(line, ["决策", "拍板", "审批"]):
        return "决策"
    if _contains_any(line, ["风险", "延期", "阻塞", "受阻"]):
        return "风险"
    if _contains_any(line, ["协调", "支持", "依赖", "权限"]):
        return "待协调"
    return "问题"


_SUBTASK_ISSUE_PREFIXES: list[tuple[tuple[str, ...], str]] = [
    (("风险：", "风险:"), "风险"),
    (("需决策：", "需决策:", "决策：", "决策:"), "需决策"),
    (("待协调：", "待协调:", "协调：", "协调:"), "待协调"),
    (("问题：", "问题:"), "问题"),
]


def _classify_issue_text(text: str) -> dict:
    """Convert a plain-string subtask issue into a typed dict {issue_type, description, priority}."""
    for prefixes, itype in _SUBTASK_ISSUE_PREFIXES:
        for prefix in prefixes:
            if text.startswith(prefix):
                return {"issue_type": itype, "description": text[len(prefix):].strip(), "priority": "中"}
    return {"issue_type": "问题", "description": text, "priority": "中"}


def _issue_priority(line: str) -> str:
    if _contains_any(line, ["风险", "阻塞", "延期", "拍板", "决策", "权限", "卡住"]):
        return "高"
    if _contains_any(line, ["关注", "跟进", "协调"]):
        return "中"
    return "低"


def _decision_owner(line: str, ceo_name: str = "") -> str:
    if _contains_any(line, ["海总", "组长", "拍板", "决策", "审批"]):
        return ceo_name
    if ceo_name and _contains_any(line, [ceo_name]):
        return ceo_name
    return ""


def _issue_rows(text: str, project: str, submitter: str | None, ceo_name: str = "") -> list[dict]:
    lines = _take_sentences(
        text,
        ["问题", "风险", "卡点", "阻塞", "延期", "决策", "拍板", "协调", "依赖", "权限", "需要"],
        ["完成", "已完成"],
        limit=5,
    )
    rows = []
    for line in lines:
        if _is_soft_progress_or_plan(line):
            continue
        issue_type = _issue_type(line)
        rows.append(
            {
                "issue_type": issue_type,
                "description": line,
                "owner": submitter or "",
                "helper": ceo_name if ceo_name and _contains_any(line, ([ceo_name] if ceo_name else []) + ["海总", "协调"]) else "",
                "priority": _issue_priority(line),
                "status": "待处理",
                "need_decision_by": _decision_owner(line, ceo_name) if IT.is_decision(issue_type) else "",
                "expected_resolve_time": "",
                "resolution": "",
                "special_project": project,
            }
        )
    return rows


def _find_subtask_by_title(title: str, user_subtasks: list[dict]) -> dict | None:
    """Return the first user_subtask whose title exactly or near-exactly matches `title`."""
    if not title or not user_subtasks:
        return None
    t = title.strip()
    for sub in user_subtasks:
        if sub.get("title", "").strip() == t:
            return sub
    for sub in user_subtasks:
        st = sub.get("title", "").strip()
        if st and len(min(t, st, key=len)) >= 5 and (st in t or t in st):
            return sub
    return None


def _subtasks_ordered_by_transcript(user_subtasks: list[dict], transcript_text: str) -> list[dict]:
    """Return user_subtasks with transcript-mentioned ones first (deterministic ordering)."""
    if not transcript_text:
        return user_subtasks
    mentioned, rest = [], []
    for sub in user_subtasks:
        title = (sub.get("title") or "").strip()
        if title and len(title) >= 4 and title in transcript_text:
            mentioned.append(sub)
        else:
            rest.append(sub)
    return mentioned + rest


def _normalize_task_reports(
    raw: list,
    submitter: str | None,
    user_subtasks: list[dict] | None = None,
    transcript_text: str | None = None,
) -> list[dict]:
    from datetime import timedelta
    today = str(date.today())
    default_end = str(date.today() + timedelta(days=14))
    _user_subtasks = user_subtasks or []
    # Transcript-mentioned subtasks come first so title matching hits them before
    # less relevant candidates — gives deterministic priority when titles overlap.
    _ordered_subtasks = _subtasks_ordered_by_transcript(_user_subtasks, transcript_text or "")
    subtask_by_id: dict[int, dict] = {s["id"]: s for s in _user_subtasks if "id" in s}
    result = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        rtype = r.get("type", "progress")
        achievements = [
            {"name": a.get("name", ""), "achievement_type": a.get("achievement_type", "方案")}
            for a in (r.get("achievements") or [])
            if isinstance(a, dict) and (a.get("name") or "").strip()
        ]
        subtask_issues = []
        for _si in (r.get("subtask_issues") or []):
            if isinstance(_si, dict):
                _desc = (_si.get("description") or "").strip()
                if _desc and not _is_soft_progress_or_plan(_desc):
                    subtask_issues.append({
                        "issue_type": _si.get("issue_type") or "问题",
                        "description": _desc,
                        "priority": _si.get("priority") or "中",
                    })
            elif isinstance(_si, str) and _si.strip() and not _is_soft_progress_or_plan(_si):
                subtask_issues.append(_classify_issue_text(_si.strip()))
        next_steps = [s for s in (r.get("next_steps") or []) if isinstance(s, str) and s.strip()]
        if rtype == "progress":
            matched_id = r.get("matched_subtask_id")
            status_update = (r.get("status_update") or "进行中").strip()
            if matched_id is not None:
                # Matched to an existing subtask — fill parent fields from user_subtasks lookup
                sub_info = subtask_by_id.get(int(matched_id), {})
                if status_update == "已完成":
                    item_result_type = "subtask_complete"
                else:
                    item_result_type = "subtask_progress"
                result.append({
                    "type": "progress",
                    "result_type": item_result_type,
                    "matched_subtask_id": matched_id,
                    "matched_subtask_title": (r.get("matched_subtask_title") or "").strip(),
                    "parent_task_id": sub_info.get("parent_task_id"),
                    "parent_key_task": sub_info.get("parent_key_task", ""),
                    "completed": (r.get("completed") or "").strip(),
                    "achievements": achievements,
                    "subtask_issues": subtask_issues,
                    "next_steps": next_steps,
                    "status_update": status_update,
                })
            else:
                # Try title-based fallback: transcript-mentioned subtasks searched first
                candidate = (r.get("matched_subtask_title") or r.get("completed") or "").strip()[:60]
                found = _find_subtask_by_title(candidate, _ordered_subtasks)
                if found:
                    rt2 = "subtask_complete" if status_update == "已完成" else "subtask_progress"
                    result.append({
                        "type": "progress",
                        "result_type": rt2,
                        "matched_subtask_id": found["id"],
                        "matched_subtask_title": found.get("title", ""),
                        "parent_task_id": found.get("parent_task_id"),
                        "parent_key_task": found.get("parent_key_task", ""),
                        "completed": (r.get("completed") or "").strip(),
                        "achievements": achievements,
                        "subtask_issues": subtask_issues,
                        "next_steps": next_steps,
                        "status_update": status_update,
                    })
                else:
                    # Truly unmatched → suggest new subtask
                    title = candidate or "待负责人确定的子任务"
                    result.append({
                        "type": "suggest_new_subtask",
                        "result_type": "suggest_new_subtask",
                        "title": title[:200],
                        "assignee": (submitter or "").strip(),
                        "parent_task_id": None,
                        "parent_key_task": "",
                        "completed": (r.get("completed") or "").strip(),
                        "achievements": achievements,
                        "subtask_issues": subtask_issues,
                        "next_steps": next_steps,
                    })
        elif rtype == "new_task":
            title = (r.get("title") or "").strip()
            if not title:
                continue
            # Try title match before converting to suggestion; transcript hits first
            found = _find_subtask_by_title(title, _ordered_subtasks)
            if found:
                status_update_nt = "进行中"
                result.append({
                    "type": "progress",
                    "result_type": "subtask_progress",
                    "matched_subtask_id": found["id"],
                    "matched_subtask_title": found.get("title", ""),
                    "parent_task_id": found.get("parent_task_id"),
                    "parent_key_task": found.get("parent_key_task", ""),
                    "completed": (r.get("completed") or "").strip() or None,
                    "achievements": achievements,
                    "subtask_issues": subtask_issues,
                    "next_steps": next_steps,
                    "status_update": status_update_nt,
                })
            else:
                # new_task → suggest_new_subtask (owner must choose parent task)
                result.append({
                    "type": "suggest_new_subtask",
                    "result_type": "suggest_new_subtask",
                    "title": title,
                    "assignee": (r.get("assignee") or submitter or "").strip(),
                    "plan_start": r.get("plan_start") or today,
                    "plan_end": r.get("plan_end") or default_end,
                    "parent_task_id": None,
                    "parent_key_task": "",
                    "completed": None,
                    "achievements": achievements,
                    "subtask_issues": subtask_issues,
                    "next_steps": next_steps,
                })
    return result


def _normalize_key_task_issues(raw: list, submitter: str | None) -> list[dict]:
    # issue_type intentionally omitted here: reviewer assigns it in the confirm center.
    # Kept as "问题" default only for backward compat with old records that have it.
    from ..domain import issue_flow as IF
    result = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        desc = (r.get("description") or "").strip()
        if not desc or _is_soft_progress_or_plan(desc):
            continue
        result.append({
            "key_task_title": (r.get("key_task_title") or "").strip(),
            "issue_type": IF.normalize_type(r.get("issue_type")),  # "问题" when absent
            "description": desc,
            "need_coordination": [s for s in (r.get("need_coordination") or []) if isinstance(s, str) and s.strip()],
            "priority": r.get("priority") or "中",
        })
    return result


_PENDING_NOISE_PREFIXES: tuple[str, ...] = (
    "问题：", "问题:", "风险：", "风险:", "需决策：", "需决策:", "待协调：", "待协调:",
    "需要负责人决策", "需要负责人确认", "决策：", "决策:", "风险提示：", "风险提示:",
)


def _normalize_pending_text(text: str) -> str:
    """Strip noise prefixes/punctuation for dedup key comparison."""
    t = (text or "").strip()
    for p in _PENDING_NOISE_PREFIXES:
        if t.startswith(p):
            t = t[len(p):].strip()
            break
    t = re.sub(r"[\s，。、；：！？,.;:!?]+", "", t)
    return t.lower()


def _build_pending_items(
    issues: list[dict],
    key_task_issues: list[dict],
    task_reports: list[dict],
) -> list[dict]:
    """Merge all need-to-handle items from every source into a deduplicated list.

    Dedup is text-based (after stripping noise prefixes and punctuation) so that
    "风险：脱敏数据提供偏慢" and "脱敏数据提供偏慢，影响接入" are treated as distinct
    while exact or near-exact duplicates are collapsed.
    """
    seen: set[str] = set()
    result: list[dict] = []

    def _add(description: str, priority: str, related_task_title: str = "", related_subtask_title: str = "") -> None:
        description = (description or "").strip()
        if not description:
            return
        key = _normalize_pending_text(description)
        if not key or key in seen:
            return
        seen.add(key)
        item: dict = {"description": description, "priority": priority or "中"}
        if related_task_title:
            item["related_task_title"] = related_task_title
        if related_subtask_title:
            item["related_subtask_title"] = related_subtask_title
        result.append(item)

    for iss in issues:
        _add(iss.get("description", ""), iss.get("priority", "中"))

    for ki in key_task_issues:
        _add(ki.get("description", ""), ki.get("priority", "中"), related_task_title=ki.get("key_task_title", ""))

    for r in task_reports:
        subtask_title = r.get("matched_subtask_title", "")
        for si in r.get("subtask_issues") or []:
            if isinstance(si, dict):
                _add(si.get("description", ""), si.get("priority", "中"), related_subtask_title=subtask_title)
            elif isinstance(si, str) and si.strip():
                # plain string: strip any leading type prefix before dedup
                raw = si.strip()
                for p in _PENDING_NOISE_PREFIXES:
                    if raw.startswith(p):
                        raw = raw[len(p):].strip()
                        break
                _add(raw, "中", related_subtask_title=subtask_title)

    return result


def _normalize_llm_result(llm_data: dict, source_type: str, text: str, submitter: str | None, ceo_name: str = "", user_subtasks: list[dict] | None = None) -> dict:
    from ..domain import source_type as ST
    from ..domain import issue_flow as IF
    # LLM 提取的 special_project 仅作展示用，不再用关键词猜测兜底
    project = (llm_data.get("special_project") or "").strip()
    completed = _dedupe(list(llm_data.get("completed_items") or []))
    next_steps = _dedupe(list(llm_data.get("next_steps") or []))
    achievements = list(llm_data.get("achievements") or [])
    issues = _filter_soft_issue_rows([row for row in list(llm_data.get("issues") or []) if isinstance(row, dict)])

    for row in achievements:
        row["name"] = row.get("name", "")
        row["achievement_type"] = row.get("achievement_type") or _achievement_type(row["name"])
        row["special_project"] = row.get("special_project") or project
        row["owner"] = row.get("owner") or (submitter or "")
        row["version"] = row.get("version") or "V0.1"
        row["file_link"] = row.get("file_link") or ""
        row["scenario"] = row.get("scenario") or "项目推进复用"
        row["reuse_tag"] = row.get("reuse_tag") or "项目复用"
        row["status"] = row.get("status") or "草稿"

    for row in issues:
        # Keep issue_type only as a backward-compat default ("问题"); the reviewer
        # selects the real type in the confirm center via pending_items.
        row["issue_type"] = IF.normalize_type(row.get("issue_type"))  # resolves None → "问题"
        row["owner"] = row.get("owner") or (submitter or "")
        row["helper"] = row.get("helper") or ""
        row["priority"] = row.get("priority") or "中"
        row["status"] = IF.normalize_status(row.get("status")) if row.get("status") else "待处理"
        row["need_decision_by"] = row.get("need_decision_by") or ""
        row["expected_resolve_time"] = row.get("expected_resolve_time") or ""
        row["resolution"] = row.get("resolution") or ""
        row["special_project"] = row.get("special_project") or project

    related_task = llm_data.get("related_task") or (completed[0] if completed else (next_steps[0] if next_steps else "持续推进专项工作"))
    summary = (llm_data.get("summary") or "").strip() or _clean_text(text)[:180]
    raw_proposed = list(llm_data.get("proposed_subtasks") or [])
    proposed_subtasks = []
    for ps in raw_proposed:
        if isinstance(ps, dict) and ps.get("title", "").strip():
            proposed_subtasks.append({
                "title": ps["title"].strip(),
                "assignee": ps.get("assignee") or (submitter or ""),
                "plan_time": ps.get("plan_time") or "",
            })
    task_reports = _normalize_task_reports(list(llm_data.get("task_reports") or []), submitter, user_subtasks, text)
    key_task_issues = _normalize_key_task_issues(list(llm_data.get("key_task_issues") or []), submitter)
    pending_items = _build_pending_items(issues, key_task_issues, task_reports)
    # Top-level result_type: only set for old-format submissions without task_reports.
    # When task_reports is present, each item carries its own result_type.
    if not task_reports:
        _has_ach = bool([a for a in achievements if a.get("name")])
        _has_iss = bool([i for i in issues if i.get("description")])
        if _has_ach and not _has_iss:
            _top_rt = "achievement"
        elif _has_iss and not _has_ach:
            _top_rt = "task_issue"
        else:
            _top_rt = "unknown"
    else:
        _top_rt = "unknown"  # defer to per-item result_type in task_reports

    result = {
        "summary": summary,
        "special_project": project,
        "related_task": related_task,
        "completed_items": completed,
        "achievements": achievements,
        "issues": issues,
        "next_steps": next_steps,
        "proposed_subtasks": proposed_subtasks,
        "task_reports": task_reports,
        "key_task_issues": key_task_issues,
        "pending_items": pending_items,
        "result_type": _top_rt,
        "decision_items": [],  # no longer auto-classified; reviewer assigns in confirm center
        "status_suggestion": llm_data.get("status_suggestion") or _status(text),
        "need_coordination": _dedupe(list(llm_data.get("need_coordination") or [])),
        "confidence": 0.93,
        "raw_type": source_type,
        "task": {
            "special_project": project,
            "key_task": related_task,
            "key_achievement": achievements[0]["name"] if achievements else "",
            "completion_standard": "负责人确认关键产出可复用，相关问题完成闭环。",
            "coordinator": "",
            "owner": submitter or "",
            "collaborators": "",
            "plan_time": str(date.today())[:7],
            "status": llm_data.get("status_suggestion") or _status(text),
            "problem_note": "；".join([row["description"] for row in issues]),
            "achievement_links": "",
        },
    }
    if ST.is_meeting(source_type):
        result["meeting"] = {
            "title": f"{project or '专项'}会议纪要",
            "date": str(date.today()),
            "participants": [submitter or ""],
            "discussion_points": completed,
            "task_items": next_steps,
            "decision_items": result["decision_items"],
            "risk_items": [row["description"] for row in issues if row["issue_type"] == "风险"],
            "next_focus": next_steps,
        }
    return result


def _rule_extract(source_type: str, text: str, submitter: str | None, ceo_name: str = "") -> dict:
    from ..domain import source_type as ST
    from ..domain import issue_flow as IF
    clean_text = _clean_text(text)
    project = _pick_project(clean_text)
    completed = _take_sentences(
        clean_text,
        ["完成", "已完成", "产出", "形成", "输出", "交付", "上线", "沉淀", "整理好"],
        ["问题", "风险", "下周", "下一步"],
        limit=5,
    )
    next_steps = _take_sentences(
        clean_text,
        ["下周", "下一步", "计划", "准备", "继续", "后续"],
        ["已完成"],
        limit=5,
    )
    achievements = _achievement_rows(clean_text, project, submitter)
    issues = _issue_rows(clean_text, project, submitter, ceo_name)
    for row in issues:
        row["issue_type"] = IF.normalize_type(row.get("issue_type"))
        if not row.get("status"):
            row["status"] = "待处理"

    if not achievements and completed:
        achievements.append(
            {
                "name": completed[0][:80],
                "achievement_type": _achievement_type(completed[0]),
                "special_project": project,
                "owner": submitter or "",
                "version": "V0.1",
                "file_link": "",
                "scenario": "项目推进复用",
                "reuse_tag": "内部使用",
                "status": "草稿",
            }
        )

    related_task = completed[0] if completed else (next_steps[0] if next_steps else "持续推进专项工作")
    proposed_subtasks = [{"title": s, "assignee": submitter or "", "plan_time": ""} for s in next_steps]
    _has_ach = bool([a for a in achievements if a.get("name")])
    _has_iss = bool([i for i in issues if i.get("description")])
    if _has_ach and not _has_iss:
        _top_rt = "achievement"
    elif _has_iss and not _has_ach:
        _top_rt = "task_issue"
    else:
        _top_rt = "unknown"
    rule_pending_items = _build_pending_items(issues, [], [])
    result = {
        "summary": clean_text[:180],
        "special_project": project,
        "related_task": related_task,
        "completed_items": completed,
        "achievements": achievements,
        "issues": issues,
        "next_steps": next_steps,
        "proposed_subtasks": proposed_subtasks,
        "task_reports": [],
        "key_task_issues": [],
        "pending_items": rule_pending_items,
        "result_type": _top_rt,
        "decision_items": [],
        "status_suggestion": _status(clean_text),
        "need_coordination": [],
        "confidence": 0.84 if len(clean_text) >= 60 else 0.62,
        "raw_type": source_type,
        "task": {
            "special_project": project,
            "key_task": related_task,
            "key_achievement": achievements[0]["name"] if achievements else "",
            "completion_standard": "负责人确认关键产出可复用，相关问题完成闭环。",
            "coordinator": "",
            "owner": submitter or "",
            "collaborators": "",
            "plan_time": str(date.today())[:7],
            "status": _status(clean_text),
            "problem_note": "；".join([row["description"] for row in issues]),
            "achievement_links": "",
        },
    }
    if ST.is_meeting(source_type):
        result["meeting"] = {
            "title": f"{project or '专项'}会议纪要",
            "date": str(date.today()),
            "participants": [submitter or ""],
            "discussion_points": completed,
            "task_items": next_steps,
            "decision_items": result["decision_items"],
            "risk_items": [row["description"] for row in issues if row["issue_type"] == "风险"],
            "next_focus": next_steps,
        }
    return result


def _with_meta(result: dict, provider: str, used_llm: bool, fallback_reason: str = "") -> dict:
    labels = {
        "rules": "规则引擎",
        "anthropic": "Claude",
        "dashscope": "通义千问",
        "deepseek": "DeepSeek",
        "glm": "智谱GLM",
    }
    result["engine"] = provider
    result["engine_label"] = labels.get(provider, provider)
    result["pipeline"] = "llm_extract" if used_llm else "rule_extract"
    result["llm_used"] = used_llm
    result["fallback_reason"] = fallback_reason
    result["generated_at"] = str(date.today())
    return result


_TASK_OUTLINE_PROMPT = """你是项目管理助手。从下面的大纲或计划文本中提取关键任务列表，只输出 JSON，不要解释。

当前年份：{current_year}

文本：
```
{text}
```

要求：
1. `project_guess`：从文本内容推断这批任务所属的项目或专项名称（用文本中出现的原词或最接近的概念，不确定则留空）
2. 每条任务：key_task（任务名称，10-30字）、owner（负责人姓名，未提及则空）、coordinator（统筹人姓名，未提及则空）、collaborators（协作人，多人用逗号分隔，未提及则空）、plan_time（格式 YYYY-MM 或 YYYY-MM~YYYY-MM，未提及则空；文本中只写了月份未写年份时，用当前年份 {current_year} 补全）、status（默认"未开始"）、key_achievement（期望成果，未提及则空）、completion_standard（完成标准，未提及则空）
3. 最多提取 20 条，按文本顺序排列
4. 只提取明确的任务，不要推断或发明

输出格式：
{{
  "project_guess": "",
  "tasks": [
    {{
      "key_task": "",
      "owner": "",
      "coordinator": "",
      "collaborators": "",
      "plan_time": "",
      "status": "未开始",
      "key_achievement": "",
      "completion_standard": ""
    }}
  ]
}}
"""


def _fix_past_year(plan_time: str) -> str:
    """把 plan_time 里所有早于今年的 YYYY 替换成今年。"""
    if not plan_time:
        return plan_time
    current_year = date.today().year
    def _replace(m: re.Match) -> str:
        y = int(m.group())
        return str(current_year) if y < current_year else m.group()
    return re.sub(r'\d{4}', _replace, plan_time)


def _match_project(guess: str, project_names: list[str]) -> tuple[str, float]:
    """将 AI 猜测的项目名与候选列表做模糊匹配，返回 (最佳匹配名, 置信度)。"""
    if not guess or not project_names:
        return ("", 0.0)
    guess_lower = guess.lower()
    # 精确包含匹配
    for name in project_names:
        if name == guess or name in guess or guess in name:
            return (name, 0.95)
    # 中文关键词（2字以上）或英文单词（3字以上）匹配
    for name in project_names:
        keywords = re.findall(r'[一-鿿]{2,}|[a-zA-Z]{3,}', name.lower())
        for kw in keywords:
            if kw in guess_lower:
                return (name, 0.75)
    return ("", 0.0)


def extract_tasks(text: str, provider: str | None = None, project_names: list[str] | None = None) -> dict:
    """从大纲文本提取关键任务列表（LLM only），失败抛 RuntimeError。
    返回 {tasks, project_guess, suggested_project, confidence}。
    """
    clean = _clean_text(text)
    if not clean:
        return {"tasks": [], "project_guess": "", "suggested_project": "", "confidence": 0.0}

    effective_provider: str | None = None
    if provider and provider != "rules":
        effective_provider = provider
    elif USE_LLM:
        effective_provider = LLM_PROVIDER

    if not effective_provider:
        raise RuntimeError("未配置可用AI引擎，请在系统设置中配置API Key")

    prompt = _TASK_OUTLINE_PROMPT.format(text=clean, current_year=date.today().year)
    try:
        if effective_provider == "anthropic":
            import anthropic
            cfg = _get_cfg("anthropic")
            if not cfg.get("api_key"):
                raise ValueError("Claude API Key not configured")
            client = anthropic.Anthropic(api_key=cfg["api_key"], timeout=_LLM_TIMEOUT)
            resp = client.messages.create(
                model=cfg["model"], max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            data = _extract_json_blob(resp.content[0].text)
        else:
            from openai import OpenAI
            cfg = _get_cfg(effective_provider)
            if not cfg.get("api_key"):
                raise ValueError(f"{effective_provider} API Key not configured")
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=_LLM_TIMEOUT)
            resp = client.chat.completions.create(
                model=cfg["model"], max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            data = _extract_json_blob(resp.choices[0].message.content or "")

        tasks = list(data.get("tasks") or [])
        for t in tasks:
            t.setdefault("key_task", "")
            t.setdefault("owner", "")
            t.setdefault("coordinator", "")
            t.setdefault("collaborators", "")
            t.setdefault("plan_time", "")
            t.setdefault("status", "未开始")
            t.setdefault("key_achievement", "")
            t.setdefault("completion_standard", "")
            t["plan_time"] = _fix_past_year(t["plan_time"])
        tasks = [t for t in tasks if t.get("key_task")]

        project_guess = (data.get("project_guess") or "").strip()
        suggested_project, confidence = _match_project(project_guess, project_names or [])

        return {
            "tasks": tasks,
            "project_guess": project_guess,
            "suggested_project": suggested_project,
            "confidence": confidence,
        }
    except Exception as exc:
        logger.warning("extract_tasks failed provider=%s: %s", effective_provider, exc)
        raise RuntimeError(f"AI引擎（{effective_provider}）提取任务失败：{exc}") from exc


def extract_update(
    source_type: str,
    transcript_text: str,
    submitter: str | None = None,
    provider: str | None = None,
    ceo_name: str = "",
    *,
    require_llm: bool = False,
    user_subtasks: list[dict] | None = None,
) -> dict:
    text = _clean_text(transcript_text)
    if not text:
        return _with_meta({
            "summary": "",
            "special_project": "",
            "related_task": "",
            "completed_items": [],
            "achievements": [],
            "issues": [],
            "next_steps": [],
            "task_reports": [],
            "decision_items": [],
            "status_suggestion": "进行中",
            "need_coordination": [],
            "confidence": 0.0,
            "raw_type": source_type,
            "task": {
                "special_project": "",
                "key_task": "",
                "key_achievement": "",
                "completion_standard": "",
                "coordinator": "",
                "owner": submitter or "",
                "collaborators": "",
                "plan_time": str(date.today())[:7],
                "status": "进行中",
                "problem_note": "",
                "achievement_links": "",
            },
        }, provider or "rules", False, "")

    effective_provider = None
    if provider and provider != "rules":
        effective_provider = provider
    elif USE_LLM:
        effective_provider = LLM_PROVIDER

    if effective_provider:
        llm_data = _extract_with_llm(text, effective_provider, user_subtasks)
        if llm_data is not None:
            return _with_meta(_normalize_llm_result(llm_data, source_type, text, submitter, ceo_name, user_subtasks), effective_provider, True, "")
        if require_llm:
            raise RuntimeError(f"AI引擎（{effective_provider}）调用失败，请检查API Key配置后重试，或联系管理员")
        logger.info("LLM extract fell back to rule engine")
        return _with_meta(_rule_extract(source_type, text, submitter, ceo_name), "rules", False, f"{effective_provider} 调用失败，已回退到规则提取")

    if require_llm:
        raise RuntimeError("未配置可用AI引擎，请在系统设置中配置API Key")
    return _with_meta(_rule_extract(source_type, text, submitter, ceo_name), "rules", False, "")
