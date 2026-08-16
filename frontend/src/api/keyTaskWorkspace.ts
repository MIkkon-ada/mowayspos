import { apiGet, apiPost } from './client'

export type DueKind = 'exact' | 'fuzzy' | 'unknown'

export type WorkspacePerson = {
  id?: number | null
  name: string
}

export type ExecutionPlan = {
  id: number
  title: string
  status: string
  assignee: string
  assignee_id?: number | null
  collaborator_ids: number[]
  collaborators: string[]
  start_date: string | null
  due_kind: DueKind
  due_date: string | null
  due_label: string | null
  due_reference_date: string | null
  expected_output: string
  actual_output: string
  completion_criteria: string
  progress_note: string
  risk_dependency: string
  is_archived: boolean
  latest_progress?: string | null
  updated_at?: string | null
}

export type CurrentProgress = {
  progress_summary: string
  next_step: string
  source_type: string
  source_id: number
  source_label: string
  actor: WorkspacePerson
  occurred_at: string | null
  effective_at: string | null
}

export type ExecutionEvent = {
  id: number
  event_type: string
  source_type: string
  source_id: number
  source_label: string
  execution_plan_id: number | null
  actor: WorkspacePerson
  occurred_at: string | null
  confirmed_at: string | null
  effective_at: string | null
  affects_current_progress: boolean
  status_before: string
  status_after: string
  progress_summary: string
  next_step: string
  display_payload: Record<string, unknown>
}

export type KeyTaskWorkspace = {
  key_task: {
    id: number
    title: string
    status: string
    owner: WorkspacePerson
    collaborators: WorkspacePerson[]
    start_date: string | null
    due_kind: DueKind
    due_date: string | null
    due_label: string | null
    due_reference_date: string | null
    plan_time: string
    completion_definition: string
    created_at: string | null
    source_type: string
  }
  project: { id: number; name: string } | null
  workstream: { id: number; name: string } | null
  current_progress: CurrentProgress | null
  completion_eligibility: {
    state: 'no_execution_plan' | 'in_progress' | 'eligible'
    effective_plan_count: number
    completed_plan_count: number
    requires_owner_confirmation: boolean
  }
  plan_summary: { total: number; completed: number; in_progress: number; not_started: number }
  execution_plans: ExecutionPlan[]
  achievements: Array<{ id: number; name: string; achievement_type: string; status: string; owner: string; version: string; created_at: string | null }>
  issues: Array<{ id: number; description: string; issue_type: string; status: string; priority: string; owner: string; updated_at: string | null }>
  timeline: ExecutionEvent[]
  permissions: { can_view: boolean; can_operate: boolean; can_submit_update: boolean; can_confirm_completion: boolean }
}

export const fetchKeyTaskExecutionWorkspace = (keyTaskId: number) =>
  apiGet<KeyTaskWorkspace>(`/api/key-tasks/${keyTaskId}/execution-workspace`)

export const confirmKeyTaskCompletion = (keyTaskId: number) =>
  apiPost(`/api/key-tasks/${keyTaskId}/confirm-completion`, {})

export const reopenKeyTask = (keyTaskId: number, reason: string) =>
  apiPost(`/api/key-tasks/${keyTaskId}/reopen`, { reason })
