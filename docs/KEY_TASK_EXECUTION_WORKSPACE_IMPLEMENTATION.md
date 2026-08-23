# Key Task / Initiative Execution Workspace

## Scope and compatibility

The business hierarchy remains `Project → Workstream → Key Task`.  An Execution
Plan is internal to a Key Task; it is not a fourth project hierarchy level.
Existing physical names (`subtasks`, `execution_schedules`, `subtask_id`) and
legacy endpoints remain available for compatibility.  The workspace uses the
new `/api/key-tasks/{id}/execution-workspace` read contract.

## Data model

- `SubTask` continues to mean Key Task and now carries structured
  `collaborator_ids`, `start_date`, `due_kind`, `due_date`, `due_label`, and
  `due_reference_date`.
- `ExecutionSchedule` continues to mean Execution Plan and retains its
  existing `collaborator_ids`.  It now supports `due_kind`, `due_label`,
  `due_reference_date`, and `is_archived`.
- `due_kind=exact` requires `due_date`; `fuzzy` preserves the entered
  `due_label` and may have a reference date only for sort/reminders; `unknown`
  stores no due values and renders as “暂未确定”.
- `key_task_execution_events` is an append-only projection/index.  Its source
  facts remain submissions, approved meeting writebacks, achievements, issues,
  execution plans, and manual Key Task actions.  It includes source identity,
  a unique dedupe key, authority, occurred/confirmed/effective timestamps, and
  `affects_current_progress`.

## Progress and meeting authority

Current Progress is the newest confirmed event with
`affects_current_progress=true`, ordered by `effective_at DESC, id DESC`.
Changing a Key Task status is neither required nor sufficient for an event to
affect Current Progress.

Publishing a meeting never creates a formal execution event.  Only the chain
`meeting fact → owner review/edit → approval → successful source writeback →
confirmed execution event` can do so.  AI candidates and unconfirmed meeting
content remain outside both Current Progress and the formal timeline.

## Completion rule

Effective plans are linked, not deleted, not archived, and not cancelled.  No
plans means `no_execution_plan`, never automatic completion.  When all
effective plans are complete, the Key Task becomes `eligible`; its owner (or
authorized operator) must explicitly confirm completion.  A completed Key
Task must be reopened with a reason before creating another effective plan.
No completion percentage is generated.

## UI

`KeyTaskExecutionWorkspace` is shared by My Tasks and Task Management.  It
shows the execution state first (header, confirmed current progress, execution
plans) and the historical state below (Key Task context, outcomes, issues,
timeline).  The plan table has no operation column; clicking a row opens a
`DetailDrawer`-based plan detail.  The timeline is sourced only from the
workspace execution-event DTO.

## Migration and rollback

Alembic revisions `e6f7a8b9c0d1` and `b0c1d2e3f4a5` are additive and
reversible one at a time. They were verified on a temporary SQLite database
with upgrade, downgrade, and re-upgrade. They do not alter the protected repository
database.  Roll back application code first if needed, then downgrade this
single revision only after taking the normal production backup.
