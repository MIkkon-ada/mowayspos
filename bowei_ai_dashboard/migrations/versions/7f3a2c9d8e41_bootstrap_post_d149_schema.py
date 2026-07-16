"""Bootstrap the proven post-d149, pre-4bf schema for empty databases.

The schema in this revision is a static transcription of app/models.py from
Git commit d5b89b874c3547caf13eed80cff47541d38f1fbc.  Python-side defaults are
intentionally not represented as server defaults.

Revision ID: 7f3a2c9d8e41
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f3a2c9d8e41"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BOOTSTRAP_MARKER_TABLE = "_moways_migration_bootstrap"
BOOTSTRAP_MARKER_TOKEN = "POST_D149_PRE_4BF_BOOTSTRAP_V1"


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_session_id", "auth_sessions", ["session_id"])
    op.create_index(
        "ix_auth_sessions_session_token_hash",
        "auth_sessions",
        ["session_token_hash"],
        unique=True,
    )
    op.create_index("ix_auth_sessions_username", "auth_sessions", ["username"])

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("failure_reason", sa.String(length=80), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"])
    op.create_index("ix_login_attempts_id", "login_attempts", ["id"])
    op.create_index("ix_login_attempts_success", "login_attempts", ["success"])
    op.create_index("ix_login_attempts_username", "login_attempts", ["username"])

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("operator", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=True),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operation_logs_id", "operation_logs", ["id"])
    op.create_index("ix_operation_logs_project_id", "operation_logs", ["project_id"])

    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=True),
        sa.Column("system_role", sa.String(length=40), nullable=True),
        sa.Column("department", sa.String(length=80), nullable=True),
        sa.Column("special_project_duty", sa.Text(), nullable=True),
        sa.Column("permission", sa.String(length=40), nullable=True),
        sa.Column("contact", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_people_id", "people", ["id"])
    op.create_index("ix_people_name", "people", ["name"])
    op.create_index("ix_people_system_role", "people", ["system_role"])

    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("start_date", sa.String(length=20), nullable=True),
        sa.Column("end_date", sa.String(length=20), nullable=True),
        sa.Column("coordinator", sa.String(length=50), nullable=True),
        sa.Column("owners", sa.String(length=200), nullable=True),
        sa.Column("collaborators", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_name", "projects", ["name"], unique=True)
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("is_tech_admin", sa.Boolean(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("last_password_changed_at", sa.DateTime(), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_id", "accounts", ["id"])
    op.create_index("ix_accounts_is_tech_admin", "accounts", ["is_tech_admin"])
    op.create_index("ix_accounts_person_id", "accounts", ["person_id"])
    op.create_index("ix_accounts_status", "accounts", ["status"])
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)

    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("meeting_type", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("meeting_date", sa.String(length=20), nullable=True),
        sa.Column("host", sa.String(length=50), nullable=True),
        sa.Column("participants", sa.Text(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("task_list_json", sa.Text(), nullable=True),
        sa.Column("decision_items_json", sa.Text(), nullable=True),
        sa.Column("risk_items_json", sa.Text(), nullable=True),
        sa.Column("related_special_project", sa.String(length=80), nullable=True),
        sa.Column("publish_status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meetings_id", "meetings", ["id"])
    op.create_index("ix_meetings_project_id", "meetings", ["project_id"])

    op.create_table(
        "member_change_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("requester_person_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("target_person_id", sa.Integer(), nullable=False),
        sa.Column("target_person_name", sa.String(length=50), nullable=True),
        sa.Column("from_role", sa.String(length=30), nullable=True),
        sa.Column("to_role", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reviewer_person_id", sa.Integer(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["requester_person_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["reviewer_person_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["target_person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_member_change_requests_id", "member_change_requests", ["id"])
    op.create_index(
        "ix_member_change_requests_project_id",
        "member_change_requests",
        ["project_id"],
    )
    op.create_index(
        "ix_member_change_requests_requester_person_id",
        "member_change_requests",
        ["requester_person_id"],
    )
    op.create_index(
        "ix_member_change_requests_status",
        "member_change_requests",
        ["status"],
    )
    op.create_index(
        "ix_member_change_requests_target_person_id",
        "member_change_requests",
        ["target_person_id"],
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipient", sa.String(length=50), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=300), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["recipient_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_id", "notifications", ["id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_recipient", "notifications", ["recipient"])
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])

    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("person_name_snapshot", sa.String(length=50), nullable=True),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "person_id",
            "role",
            name="uq_project_member_role",
        ),
    )
    op.create_index("ix_project_members_id", "project_members", ["id"])
    op.create_index("ix_project_members_person_id", "project_members", ["person_id"])
    op.create_index(
        "ix_project_members_person_name_snapshot",
        "project_members",
        ["person_name_snapshot"],
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_index("ix_project_members_role", "project_members", ["role"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("special_project", sa.String(length=80), nullable=True),
        sa.Column("key_task", sa.String(length=200), nullable=False),
        sa.Column("key_achievement", sa.String(length=200), nullable=True),
        sa.Column("completion_standard", sa.Text(), nullable=True),
        sa.Column("coordinator", sa.String(length=50), nullable=True),
        sa.Column("owner", sa.String(length=50), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("collaborators", sa.String(length=200), nullable=True),
        sa.Column("plan_time", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("problem_note", sa.Text(), nullable=True),
        sa.Column("achievement_links", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("submitter", sa.String(length=50), nullable=True),
        sa.Column("confirmed_by", sa.String(length=50), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("source_submission_id", sa.Integer(), nullable=True),
        sa.Column("edit_count", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(length=50), nullable=True),
        sa.Column("delete_reason", sa.Text(), nullable=True),
        sa.Column("delete_batch_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_delete_batch_id", "tasks", ["delete_batch_id"])
    op.create_index("ix_tasks_id", "tasks", ["id"])
    op.create_index("ix_tasks_is_deleted", "tasks", ["is_deleted"])
    op.create_index("ix_tasks_owner", "tasks", ["owner"])
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])
    op.create_index("ix_tasks_plan_time", "tasks", ["plan_time"])
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_source_submission_id", "tasks", ["source_submission_id"])
    op.create_index("ix_tasks_special_project", "tasks", ["special_project"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "achievement_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("special_project", sa.String(length=80), nullable=True),
        sa.Column("related_task_id", sa.Integer(), nullable=True),
        sa.Column("related_subtask_id", sa.Integer(), nullable=True),
        sa.Column("submitter", sa.String(length=50), nullable=True),
        sa.Column("submitter_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("achievement_type", sa.String(length=40), nullable=True),
        sa.Column("version", sa.String(length=30), nullable=True),
        sa.Column("file_link", sa.Text(), nullable=True),
        sa.Column("scenario", sa.Text(), nullable=True),
        sa.Column("reuse_tag", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("reviewer", sa.String(length=50), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["related_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["submitter_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_achievement_submissions_achievement_type",
        "achievement_submissions",
        ["achievement_type"],
    )
    op.create_index("ix_achievement_submissions_id", "achievement_submissions", ["id"])
    op.create_index(
        "ix_achievement_submissions_project_id",
        "achievement_submissions",
        ["project_id"],
    )
    op.create_index(
        "ix_achievement_submissions_special_project",
        "achievement_submissions",
        ["special_project"],
    )
    op.create_index(
        "ix_achievement_submissions_status",
        "achievement_submissions",
        ["status"],
    )
    op.create_index(
        "ix_achievement_submissions_submitter",
        "achievement_submissions",
        ["submitter"],
    )
    op.create_index(
        "ix_achievement_submissions_submitter_id",
        "achievement_submissions",
        ["submitter_id"],
    )

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("achievement_type", sa.String(length=40), nullable=True),
        sa.Column("special_project", sa.String(length=80), nullable=True),
        sa.Column("related_task_id", sa.Integer(), nullable=True),
        sa.Column("owner", sa.String(length=50), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.String(length=30), nullable=True),
        sa.Column("file_link", sa.Text(), nullable=True),
        sa.Column("scenario", sa.Text(), nullable=True),
        sa.Column("reuse_tag", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("confirmed_by", sa.String(length=50), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("source_submission_id", sa.Integer(), nullable=True),
        sa.Column("source_achievement_submission_id", sa.Integer(), nullable=True),
        sa.Column("edit_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["related_task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_achievements_achievement_type", "achievements", ["achievement_type"])
    op.create_index("ix_achievements_id", "achievements", ["id"])
    op.create_index("ix_achievements_owner", "achievements", ["owner"])
    op.create_index("ix_achievements_owner_id", "achievements", ["owner_id"])
    op.create_index("ix_achievements_project_id", "achievements", ["project_id"])
    op.create_index(
        "ix_achievements_source_achievement_submission_id",
        "achievements",
        ["source_achievement_submission_id"],
    )
    op.create_index(
        "ix_achievements_source_submission_id",
        "achievements",
        ["source_submission_id"],
    )
    op.create_index("ix_achievements_special_project", "achievements", ["special_project"])
    op.create_index("ix_achievements_status", "achievements", ["status"])

    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("issue_type", sa.String(length=40), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=50), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("helper", sa.String(length=100), nullable=True),
        sa.Column("priority", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("need_decision_by", sa.String(length=50), nullable=True),
        sa.Column("expected_resolve_time", sa.String(length=20), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("related_task_id", sa.Integer(), nullable=True),
        sa.Column("special_project", sa.String(length=80), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("confirmed_by", sa.String(length=50), nullable=True),
        sa.Column("source_submission_id", sa.Integer(), nullable=True),
        sa.Column("edit_count", sa.Integer(), nullable=True),
        sa.Column("reporter", sa.String(length=50), nullable=True),
        sa.Column("handler_reply", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["related_task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_issues_id", "issues", ["id"])
    op.create_index("ix_issues_issue_type", "issues", ["issue_type"])
    op.create_index("ix_issues_owner", "issues", ["owner"])
    op.create_index("ix_issues_owner_id", "issues", ["owner_id"])
    op.create_index("ix_issues_priority", "issues", ["priority"])
    op.create_index("ix_issues_project_id", "issues", ["project_id"])
    op.create_index("ix_issues_reporter", "issues", ["reporter"])
    op.create_index("ix_issues_source_submission_id", "issues", ["source_submission_id"])
    op.create_index("ix_issues_special_project", "issues", ["special_project"])
    op.create_index("ix_issues_status", "issues", ["status"])

    op.create_table(
        "subtask_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("parent_task_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("proposer", sa.String(length=50), nullable=False),
        sa.Column("assignee", sa.String(length=50), nullable=True),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("plan_time", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("source_submission_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["assignee_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subtask_drafts_assignee", "subtask_drafts", ["assignee"])
    op.create_index("ix_subtask_drafts_assignee_id", "subtask_drafts", ["assignee_id"])
    op.create_index("ix_subtask_drafts_id", "subtask_drafts", ["id"])
    op.create_index(
        "ix_subtask_drafts_parent_task_id",
        "subtask_drafts",
        ["parent_task_id"],
    )
    op.create_index("ix_subtask_drafts_project_id", "subtask_drafts", ["project_id"])
    op.create_index("ix_subtask_drafts_proposer", "subtask_drafts", ["proposer"])
    op.create_index(
        "ix_subtask_drafts_source_submission_id",
        "subtask_drafts",
        ["source_submission_id"],
    )
    op.create_index("ix_subtask_drafts_status", "subtask_drafts", ["status"])

    op.create_table(
        "subtasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("assignee", sa.String(length=50), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("plan_time", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("completion_criteria", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_submission_id", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(length=50), nullable=True),
        sa.Column("delete_reason", sa.Text(), nullable=True),
        sa.Column("delete_batch_id", sa.String(length=64), nullable=True),
        sa.Column("deleted_by_parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["assignee_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subtasks_assignee", "subtasks", ["assignee"])
    op.create_index("ix_subtasks_assignee_id", "subtasks", ["assignee_id"])
    op.create_index("ix_subtasks_delete_batch_id", "subtasks", ["delete_batch_id"])
    op.create_index(
        "ix_subtasks_deleted_by_parent_id",
        "subtasks",
        ["deleted_by_parent_id"],
    )
    op.create_index("ix_subtasks_id", "subtasks", ["id"])
    op.create_index("ix_subtasks_is_deleted", "subtasks", ["is_deleted"])
    op.create_index("ix_subtasks_source_submission_id", "subtasks", ["source_submission_id"])
    op.create_index("ix_subtasks_status", "subtasks", ["status"])
    op.create_index("ix_subtasks_task_id", "subtasks", ["task_id"])

    op.create_table(
        "update_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("submitter", sa.String(length=50), nullable=True),
        sa.Column("submitter_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("ai_result_json", sa.Text(), nullable=True),
        sa.Column("human_result_json", sa.Text(), nullable=True),
        sa.Column("confirm_status", sa.String(length=20), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("related_task_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_by", sa.String(length=50), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("coordinator_note", sa.Text(), nullable=True),
        sa.Column("ceo_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["related_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["submitter_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_update_submissions_confirm_status",
        "update_submissions",
        ["confirm_status"],
    )
    op.create_index("ix_update_submissions_id", "update_submissions", ["id"])
    op.create_index("ix_update_submissions_project_id", "update_submissions", ["project_id"])
    op.create_index("ix_update_submissions_source_type", "update_submissions", ["source_type"])
    op.create_index("ix_update_submissions_submitter_id", "update_submissions", ["submitter_id"])

    marker = op.create_table(
        BOOTSTRAP_MARKER_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.bulk_insert(
        marker,
        [{"id": 1, "token": BOOTSTRAP_MARKER_TOKEN}],
        multiinsert=False,
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade below d14986ccb2dd is unsupported because the "
        "pre-d149 schema cannot be reconstructed safely."
    )
