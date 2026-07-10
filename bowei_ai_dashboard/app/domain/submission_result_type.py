"""
Constants for UpdateSubmission.ai_result_json result_type field.

Used to categorise incoming submissions so the confirmation centre
and downstream handlers can route each item correctly.
"""

# Assignee submits an in-progress update that matches an existing subtask
TYPE_SUBTASK_PROGRESS = "subtask_progress"

# Assignee claims an existing subtask is complete (requires owner confirmation)
TYPE_SUBTASK_COMPLETE = "subtask_complete"

# Assignee requests a status change on a subtask via the confirmation centre
# (written by patch_subtask_status when the caller is assignee-only)
TYPE_SUBTASK_STATUS_UPDATE = "subtask_status_update"

# AI extracted what looks like a concrete execution action but could not match
# it to an existing subtask.  Must NOT be turned into a formal subtask until
# the project owner confirms.
TYPE_SUGGEST_NEW_SUBTASK = "suggest_new_subtask"

# A problem that belongs at the key-task level
TYPE_TASK_ISSUE = "task_issue"

# A problem that belongs at the project level
TYPE_PROJECT_ISSUE = "project_issue"

# A deliverable / achievement
TYPE_ACHIEVEMENT = "achievement"

# The AI could not determine what this item is; escalate to the owner
TYPE_UNKNOWN = "unknown"
