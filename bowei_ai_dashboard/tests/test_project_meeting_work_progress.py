from app.services.project_meeting_work_progress import build_word_work_progress_preview


def _fact(fact_id: str, fact_type: str, content: str) -> dict:
    return {
        "fact_id": fact_id,
        "fact_type": fact_type,
        "content": content,
        "meeting_evidence": [{"quote": content, "char_start": 0, "char_end": len(content)}],
        "confidence": 0.9,
        "validation": {"state": "ready", "errors": []},
    }


def _match(fact_id: str, key_task_id: int = 20) -> dict:
    return {
        "match_id": f"M{fact_id[1:]}",
        "fact_id": fact_id,
        "target": {"target_type": "key_task", "target_id": key_task_id, "workstream_id": 10, "key_task_id": key_task_id},
        "confidence": 0.88,
        "reasons": ["标题与关键任务一致"],
        "validation": {"state": "ready", "errors": []},
    }


def _delta(fact_id: str, delta_type: str) -> dict:
    return {
        "delta_id": f"D{fact_id[1:]}", "source_fact_id": fact_id,
        "source_match_id": f"M{fact_id[1:]}", "delta_type": delta_type,
        "reasoning": "会议有新的执行安排", "validation": {"state": "ready", "errors": []},
    }


def test_word_preview_maps_exact_action_and_tracking_progress_to_one_key_task():
    action = "完成客户清单第二批"
    tracking = "客户清单第一批"
    progress = "第一批已交付客户审核"
    snapshot = {"project_id": 1, "workstreams": [{"id": 10, "key_task": "客户清单", "key_tasks": [
        {"id": 20, "title": "梳理客户清单", "status": "进行中", "execution_schedules": []},
    ]}]}
    result = {
        "meeting_facts": [_fact("F001", "action_item", action), _fact("F002", "progress", tracking)],
        "project_matches": [_match("F001"), _match("F002")],
        "project_deltas": [_delta("F001", "NEW_EXECUTION_SCHEDULE"), _delta("F002", "PROGRESS_UPDATE")],
        "prior_action_tracking": [{"content": tracking, "progress_note": progress,
                                   "evidence": [{"quote": progress, "char_start": 30, "char_end": 30 + len(progress)}]}],
        "unmatched_items": [], "needs_confirmation": [],
    }

    preview = build_word_work_progress_preview(result, snapshot)

    assert len(preview["rows"]) == 1
    row = preview["rows"][0]
    assert row["key_task_id"] == 20
    assert row["proposed"] == {"progress_summary": progress, "next_step": action}
    assert row["field_fact_ids"] == {"progress_summary": ["F002"], "next_step": ["F001"]}
    assert {item["fact_id"] for item in row["related_facts"]} == {"F001", "F002"}
    assert {item["quote"] for item in row["evidence"]} == {action, tracking, progress}


def test_word_preview_keeps_decisions_in_minutes_and_explains_unlinked_actions():
    snapshot = {"project_id": 1, "workstreams": [{"id": 10, "key_task": "客户清单", "key_tasks": [
        {"id": 20, "title": "梳理客户清单", "execution_schedules": []},
    ]}]}
    decision = _fact("F001", "decision", "后续采用统一客户模板")
    ambiguous = _fact("F002", "action_item", "整理内部知识库")
    ambiguous["reason"] = "客户清单与知识库两个任务都可能相关"
    result = {
        "meeting_facts": [decision], "project_matches": [_match("F001")],
        "project_deltas": [_delta("F001", "PROGRESS_UPDATE")],
        "prior_action_tracking": [], "unmatched_items": [], "needs_confirmation": [ambiguous],
    }

    preview = build_word_work_progress_preview(result, snapshot)

    assert preview["rows"] == []
    assert decision["fact_id"] not in {
        item["fact_id"] for item in preview["unlinked_facts"]
    }
    assert preview["unlinked_facts"] == [{
        "fact_id": "F002", "content": "整理内部知识库", "fact_type": "action_item",
        "reason": "客户清单与知识库两个任务都可能相关", "disposition": "needs_confirmation",
    }]
