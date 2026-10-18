"""Owner plan recovery and stable identity checks; never write execution data on save."""
import json
import re
from fastapi import HTTPException
from .. import models


def actor_key(context, username):
    return f"person:{context['person_id']}" if context.get("person_id") else f"account:{username}"


def split_period(value):
    parts = re.split(r"\s*(?:~|至|到|\s+-\s+)\s*", value or "", maxsplit=1)
    return (parts[0], parts[1] if len(parts) == 2 else "")


def existing_plan(db, project_id):
    tasks = db.query(models.Task).filter_by(project_id=project_id, is_deleted=False).order_by(models.Task.id).all()
    subs = db.query(models.SubTask).filter(models.SubTask.task_id.in_([task.id for task in tasks]), models.SubTask.is_deleted.is_(False)).order_by(models.SubTask.id).all() if tasks else []
    result = []
    for task in tasks:
        start, end = split_period(task.plan_time)
        children = []
        for sub in subs:
            if sub.task_id != task.id:
                continue
            sub_start, sub_end = split_period(sub.plan_time)
            children.append({"id": sub.id, "title": sub.title, "assignee": sub.assignee,
                             "assignee_id": sub.assignee_id, "helper_ids": sub.collaborator_ids or [],
                             "helper": (sub.notes or "").removeprefix("协助人：") if (sub.notes or "").startswith("协助人：") else "",
                             "evaluation_standard": sub.completion_criteria or "",
                             "plan_start": sub.start_date.isoformat() if sub.start_date else sub_start,
                             "plan_end": sub.due_date.isoformat() if sub.due_date else sub_end})
        result.append({"id": task.id, "title": task.key_task, "goal": task.key_achievement or "",
                       "description": task.key_achievement or "", "acceptance_criteria": task.completion_standard or "",
                       "process": task.plan_process or "", "owner": task.owner or "", "helper": task.collaborators or "",
                       "plan_start": start, "plan_end": end, "subtasks": children})
    return result


def return_reason(db, project):
    if project.status != "returned":
        return ""
    log = db.query(models.OperationLog).filter_by(target_type="project", target_id=project.id, action="return_project").order_by(models.OperationLog.id.desc()).first()
    if not log:
        return ""
    try:
        return json.loads(log.before_json or "{}").get("reason", "")
    except (ValueError, AttributeError):
        return ""


def validate_ids(db, project_id, drafts):
    seen_tasks, seen_subtasks = set(), set()
    for draft in drafts:
        task_id = draft.id or draft.task_id
        if draft.id and draft.task_id and draft.id != draft.task_id:
            raise HTTPException(422, "重点工作标识不一致")
        if task_id:
            task = db.get(models.Task, task_id)
            if not task or task.project_id != project_id or task.is_deleted or task_id in seen_tasks:
                raise HTTPException(422, "重点工作不属于当前项目或重复，请刷新方案")
            seen_tasks.add(task_id)
        for sub_draft in draft.subtasks:
            sub_id = sub_draft.id or sub_draft.subtask_id
            if sub_draft.id and sub_draft.subtask_id and sub_draft.id != sub_draft.subtask_id:
                raise HTTPException(422, "关键任务标识不一致")
            if sub_id:
                sub = db.get(models.SubTask, sub_id)
                if not sub or not task_id or sub.task_id != task_id or sub.is_deleted or sub_id in seen_subtasks:
                    raise HTTPException(422, "关键任务不属于当前重点工作或重复，请刷新方案")
                seen_subtasks.add(sub_id)


def reconcile_plan(db, project, kept_task_ids, kept_subtask_ids, username):
    tasks = db.query(models.Task).filter_by(project_id=project.id, is_deleted=False).all()
    task_ids = [task.id for task in tasks]
    subs = db.query(models.SubTask).filter(models.SubTask.task_id.in_(task_ids), models.SubTask.is_deleted.is_(False)).all() if tasks else []
    removed = [sub for sub in subs if sub.id not in kept_subtask_ids]
    for sub in removed:
        linked = any(db.query(model.id).filter(model.related_subtask_id == sub.id).first() for model in
                     [models.UpdateSubmission, models.Achievement, models.AchievementSubmission, models.Issue])
        if linked or sub.source_submission_id or db.query(models.ExecutionSchedule.id).filter_by(subtask_id=sub.id).first() or db.query(models.KeyTaskExecutionEvent.id).filter_by(key_task_id=sub.id).first():
            raise HTTPException(409, "待移除关键任务已有执行记录，请保留该任务并联系管理员核查")
        sub.is_deleted = True
        sub.deleted_by = username
        sub.delete_reason = "立项方案修订移除"
    for task in tasks:
        if task.id not in kept_task_ids:
            linked = any(db.query(model.id).filter(model.related_task_id == task.id).first() for model in
                         [models.UpdateSubmission, models.Achievement, models.AchievementSubmission, models.Issue])
            if linked or task.source_submission_id:
                raise HTTPException(409, "待移除重点工作已有执行记录，请保留该工作")
            task.is_deleted = True
            task.deleted_by = username
            task.delete_reason = "立项方案修订移除"
