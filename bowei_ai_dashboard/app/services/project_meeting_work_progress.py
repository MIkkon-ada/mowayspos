"""Project exact Word facts onto the existing work-progress hierarchy."""

from __future__ import annotations

from typing import Any


def build_word_work_progress_preview(result: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep each Word action row intact and propose only supported task updates.

    Decisions, discussion, and risks remain in the meeting minutes and never
    become work-progress rows or writeback proposals.
    """
    key_tasks: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for workstream in snapshot.get("workstreams", []):
        if not isinstance(workstream, dict):
            continue
        for key_task in workstream.get("key_tasks", []):
            if isinstance(key_task, dict) and isinstance(key_task.get("id"), int):
                key_tasks[key_task["id"]] = (workstream, key_task)

    facts = {
        item["fact_id"]: item for item in result.get("meeting_facts", [])
        if isinstance(item, dict) and isinstance(item.get("fact_id"), str)
        and item.get("validation", {}).get("state") == "ready"
    }
    all_facts = {
        item["fact_id"]: item
        for group in ("meeting_facts", "unmatched_items", "needs_confirmation")
        for item in result.get(group, [])
        if isinstance(item, dict) and isinstance(item.get("fact_id"), str)
        and item.get("fact_type") == "action_item"
    }
    matches_by_fact = {
        item["fact_id"]: item for item in result.get("project_matches", [])
        if isinstance(item, dict) and isinstance(item.get("fact_id"), str)
        and item.get("validation", {}).get("state") == "ready"
    }
    deltas = {
        item["source_fact_id"]: item for item in result.get("project_deltas", [])
        if isinstance(item, dict) and isinstance(item.get("source_fact_id"), str)
        and item.get("validation", {}).get("state") == "ready"
    }
    tracking_by_content = {
        item["content"]: item for item in result.get("prior_action_tracking", [])
        if isinstance(item, dict) and isinstance(item.get("content"), str)
    }
    rows: dict[int, dict[str, Any]] = {}
    for match in result.get("project_matches", []):
        if not isinstance(match, dict) or match.get("validation", {}).get("state") != "ready":
            continue
        fact = facts.get(match.get("fact_id"))
        target = match.get("target") if isinstance(match.get("target"), dict) else {}
        key_task_id = target.get("key_task_id")
        if not fact or key_task_id not in key_tasks:
            continue
        workstream, key_task = key_tasks[key_task_id]
        if target.get("workstream_id") != workstream.get("id"):
            continue
        fact_type = str(fact.get("fact_type") or "")
        if fact_type not in {"action_item", "progress", "completion", "output"}:
            continue
        if fact_type == "action_item" and float(match.get("confidence") or 0) < 0.75:
            continue
        row = rows.setdefault(key_task_id, {
            "workstream_id": workstream["id"],
            "workstream_title": str(workstream.get("key_task") or ""),
            "key_task_id": key_task_id,
            "key_task_title": str(key_task.get("title") or ""),
            "key_task_status": str(key_task.get("status") or ""),
            "related_facts": [],
            "proposed": {},
            "field_fact_ids": {},
            "evidence": [],
            "confidence": 1.0,
        })
        delta = deltas.get(fact["fact_id"], {})
        content = str(fact.get("content") or "").strip()
        row["related_facts"].append({
            "fact_id": fact["fact_id"], "fact_type": fact_type, "content": content,
            "delta_type": str(delta.get("delta_type") or ""),
            "reason": str(delta.get("reasoning") or (match.get("reasons") or [""])[0]),
        })
        row["confidence"] = min(row["confidence"], float(match.get("confidence") or 0))

        field_name = None
        value = content
        if delta.get("delta_type") not in {None, "", "NO_CHANGE"}:
            if fact_type == "action_item":
                field_name = "next_step"
            elif fact_type in {"progress", "completion", "output"}:
                tracked = tracking_by_content.get(content)
                if tracked is not None:
                    value = str(tracked.get("progress_note") or "").strip()
                if value:
                    field_name = "progress_summary"
        if not field_name or not value:
            continue
        if value not in row["proposed"].get(field_name, "").split("\n"):
            row["proposed"][field_name] = "\n".join(filter(None, (row["proposed"].get(field_name), value)))
        row["field_fact_ids"].setdefault(field_name, []).append(fact["fact_id"])
        evidence = list(fact.get("meeting_evidence") or [])
        if field_name == "progress_summary" and value != content:
            evidence.extend(
                span for span in tracking_by_content[content].get("evidence", [])
                if isinstance(span, dict) and span.get("quote") == value
            )
        seen = {(span.get("quote"), span.get("char_start"), span.get("char_end")) for span in row["evidence"]}
        for span in evidence:
            if not isinstance(span, dict):
                continue
            key = (span.get("quote"), span.get("char_start"), span.get("char_end"))
            if key not in seen:
                row["evidence"].append(span)
                seen.add(key)

    unlinked_facts = []
    for disposition in ("unmatched_items", "needs_confirmation"):
        for fact in result.get(disposition, []):
            if not isinstance(fact, dict) or fact.get("fact_type") != "action_item":
                continue
            unlinked_facts.append({
                "fact_id": str(fact.get("fact_id") or ""),
                "content": str(fact.get("content") or ""),
                "fact_type": str(fact.get("fact_type") or ""),
                "reason": str(fact.get("reason") or "当前没有足够信息确定对应的关键任务"),
                "disposition": "needs_confirmation" if disposition == "needs_confirmation" else "unmatched",
            })
    for match in matches_by_fact.values():
        fact = all_facts.get(match["fact_id"])
        if not fact or float(match.get("confidence") or 0) >= 0.75:
            continue
        unlinked_facts.append({
            "fact_id": fact["fact_id"], "content": str(fact.get("content") or ""),
            "fact_type": "action_item", "reason": "现有任务匹配依据不足，请核对任务归属",
            "disposition": "needs_confirmation",
            "suggested_key_task_id": match.get("target", {}).get("key_task_id"),
        })

    action_rows = []
    available_by_content: dict[str, list[dict[str, Any]]] = {}
    for fact in all_facts.values():
        available_by_content.setdefault(str(fact.get("content") or "").strip(), []).append(fact)
    for item in result.get("next_stage_work", []):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        candidates = available_by_content.get(content, [])
        fact = candidates.pop(0) if candidates else None
        match = matches_by_fact.get(fact["fact_id"]) if fact else None
        target = match.get("target", {}) if match else {}
        key_task_id = target.get("key_task_id")
        workstream, key_task = key_tasks[key_task_id] if key_task_id in key_tasks else ({}, {})
        confident = bool(match and float(match.get("confidence") or 0) >= 0.75
                         and target.get("workstream_id") == workstream.get("id"))
        action_rows.append({
            "fact_id": fact["fact_id"] if fact else "",
            "code": str(item.get("code") or ""), "content": content,
            "owner": str(item.get("owner") or ""), "tracker": str(item.get("tracker") or ""),
            "due_date": str(item.get("due_date") or ""),
            "match_state": "matched" if confident else "needs_review",
            "key_task_id": key_task_id if confident else None,
            "key_task_title": str(key_task.get("title") or "") if confident else "",
            "workstream_id": workstream.get("id") if confident else None,
            "suggested_key_task_id": key_task_id if match and not confident else None,
            "confidence": float(match.get("confidence") or 0) if match else None,
        })
    return {"rows": list(rows.values()), "action_rows": action_rows, "unlinked_facts": unlinked_facts}
