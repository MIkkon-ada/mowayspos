/**
 * TaskItem 业务语义：重点工作 / Workstream（三层结构第二层）
 *
 * 物理表：tasks
 * 前端展示：重点工作 / Workstream
 * 子层级：SubTask(KeyTask) 实体
 * special_project：项目名镜像字段，非重点工作名
 */
export type TaskItem = {
  id: number
  project_id?: number | null
  /** 项目名镜像字段（非重点工作名），由后端从 project_id 自动回填 */
  special_project: string
  /** 重点工作名称（三层结构第二层，对应文档"重点工作"） */
  key_task: string
  key_achievement: string
  completion_standard: string
  coordinator: string
  owner: string
  collaborators: string
  plan_time: string
  status: string
  problem_note: string
  achievement_links: string
  source_type: string
  submitter?: string
  confirmed_by?: string
  confirmed_at?: string | null
  edit_count?: number
  is_deleted?: boolean
  deleted_at?: string | null
  deleted_by?: string
  delete_reason?: string
  delete_batch_id?: string
  created_at?: string
  updated_at?: string
}

/** alias：TaskItem 即 WorkstreamItem */
export type WorkstreamItem = TaskItem

export type TaskFilters = {
  query: string
  project: string
  status: string
  month: string
}

export type TaskStatItem = {
  label: string
  value: number
  tone: 'total' | 'notstart' | 'progress' | 'done' | 'delayed' | 'paused'
}

export type AppPage = 'dashboard' | 'voice' | 'meeting' | 'confirm' | 'table' | 'achievements' | 'issues' | 'coordinate' | 'settings' | 'mytasks' | 'notifications' | 'projects-mgmt'

// ── 项目化地基类型（P0-1）──────────────────────────────────

// GET /api/auth/me 返回（仅声明本批会用到的字段，其余字段后端仍返回）
export type CurrentUser = {
  account_id?: number | null
  person_id?: number | null
  username?: string
  account_status?: 'active' | 'disabled'
  default_route?: string
  locked_until?: string | null
  is_locked?: boolean
  projects?: Array<number | string | { id?: number; name?: string }>
  capabilities?: {
    canPreviewClientView?: boolean
    [key: string]: boolean | undefined
  }
  name: string
  system_role: string
  system_role_label?: string
  is_tech_admin: boolean
  is_ceo: boolean
  is_coordinator: boolean
  can_view_all: boolean
  can_confirm_all: boolean
  visible_projects: string[]
  project_roles: Record<string, string>
  must_change_password?: boolean
}

// GET /api/projects 列表项
export type Project = {
  id: number
  name: string
  code: string
  description: string
  status: string
  is_active: boolean
  start_date?: string
  end_date?: string
  coordinator?: string
  owners?: string[]
  collaborators?: string[]
  user_roles: string[]           // 当前用户在该项目的角色：owner/coordinator/member/project_ceo/super_admin
  member_counts: Record<string, number>
  // 立项扩展字段
  project_type?: string
  client_name?: string
  background?: string
  objectives?: string
  expected_outcomes?: string
  lifecycle_status?: string
  kickoff_date?: string
  kickoff_by?: string
  initiated_by?: string
}

// GET /api/projects/{id}/capabilities
export type ProjectCapabilities = {
  roles: string[]
  canSubmit: boolean
  canConfirm: boolean
  canCoordinate: boolean
  canEscalateToCEO: boolean
  canCeoDecide: boolean
  canViewCenter: boolean
  pendingCount: number
}

// GET /api/projects/{id}/members
export type ProjectMember = {
  id: number
  project_id: number
  person_id: number
  person_name_snapshot: string
  role: string
  note: string
  joined_at: string | null
}

// GET/POST /api/projects/{id}/member-change-requests
export type MemberChangeRequest = {
  id: number
  project_id: number
  project_name?: string
  requester_person_id: number | null
  requester_name: string
  target_person_id: number
  target_person_name: string
  action: string
  from_role?: string
  to_role: string
  to_role_label?: string
  reason: string
  status: string  // pending / approved / rejected
  reviewer_person_id: number | null
  reviewer_name: string
  review_comment: string
  created_at: string | null
  reviewed_at: string | null
  new_member?: ProjectMember
}

// ── P0-2：主链路 API 类型 ──────────────────────────────────

// GET /api/dashboard/overview?project_id=X（项目模式，字段做兜底容错）
export type DashboardOverview = {
  project?: { id: number | null; name: string }
  task_stats?: {
    total_tasks?: number
    not_started?: number
    in_progress?: number
    completed?: number
    delayed?: number
    paused?: number
  }
  achievement_stats?: { total_achievements?: number; recent_achievements?: unknown[] }
  issue_stats?: {
    total_issues?: number
    open_issues?: number
    high_priority_issues?: number
    waiting_ceo_decision?: number
  }
  submission_stats?: {
    total_submissions?: number
    pending_owner_confirmation?: number | null
    returned_submissions?: number | null
    confirmed_submissions?: number
  }
  ceo_decision_stats?: { pending_ceo_decisions?: number; ceo_decided_awaiting_owner?: number }
  recent?: {
    submissions?: Array<Record<string, unknown>>
    tasks?: Array<Record<string, unknown>>
    issues?: Array<Record<string, unknown>>
  }
  [key: string]: unknown
}

// GET /api/people 列表项（人员选择器用）
export type Person = {
  id: number
  name: string
  system_role?: string
  department?: string
  contact?: string
  is_active?: boolean
  special_project_duty?: string
  [key: string]: unknown
}

// GET /api/achievements?project_id=X 列表项
export type AchievementItem = {
  id: number
  project_id: number | null
  name?: string
  achievement_type?: string
  special_project?: string
  related_task_id?: number | null
  related_subtask_id?: number | null
  owner?: string
  version?: string
  file_link?: string
  scenario?: string
  reuse_tag?: string
  status?: string
  confirmed_by?: string
  confirmed_at?: string | null
  source_submission_id?: number | null
  source_achievement_submission_id?: number | null
  created_at?: string
  updated_at?: string
  [key: string]: unknown
}

// GET /api/achievement-submissions
export type AchievementSubmissionItem = {
  id: number
  project_id: number | null
  special_project?: string
  related_task_id?: number | null
  related_subtask_id?: number | null
  submitter?: string
  name: string
  achievement_type?: string
  version?: string
  file_link?: string
  scenario?: string
  reuse_tag?: string
  status: string  // 待确认 / 已确认 / 已退回 / 已撤回
  reviewer?: string
  reviewed_at?: string | null
  reject_reason?: string
  source_type?: string
  created_at?: string
  updated_at?: string
  [key: string]: unknown
}

// GET /api/issues?project_id=X 列表项
export type IssueItem = {
  id: number
  project_id: number | null
  issue_type?: string
  description?: string
  owner?: string
  helper?: string
  priority?: string
  status?: string
  need_decision_by?: string
  expected_resolve_time?: string
  resolution?: string
  handler_reply?: string
  reporter?: string
  related_task_id?: number | null
  related_subtask_id?: number | null
  special_project?: string
  created_at?: string
  updated_at?: string
  [key: string]: unknown
}

// GET /api/meetings?project_id=X 列表项（Meeting 模型字段，做兜底容错）
export type MeetingItem = {
  id: number
  project_id: number | null
  related_special_project?: string
  meeting_type?: string
  title?: string
  meeting_date?: string
  host?: string
  participants?: string
  summary?: string
  task_list_json?: string
  decision_items_json?: string
  risk_items_json?: string
  publish_status?: string
  created_at?: string
  updated_at?: string
  [key: string]: unknown
}

/**
 * SubTaskItem 业务语义：关键任务 / KeyTask（三层结构第三层）
 *
 * 物理表：subtasks
 * 前端展示：关键任务 / KeyTask
 * 父层级：Task(Workstream) 实体
 */
// GET /api/tasks/{id}/subtasks 关键任务列表项
export type SubTaskItem = {
  id: number
  /** 关联的上级重点工作(Workstream) ID */
  task_id: number
  title: string
  assignee: string
  plan_time: string
  status: string
  completion_criteria?: string
  notes?: string
  source_submission_id?: number | null
  is_deleted?: boolean
  deleted_at?: string | null
  deleted_by?: string
  delete_reason?: string
  delete_batch_id?: string
  deleted_by_parent_id?: number | null
  created_at?: string
  updated_at?: string
}

/** alias：SubTaskItem 即 KeyTaskItem */
export type KeyTaskItem = SubTaskItem

// GET /api/confirmations/pending?project_id=X 列表项（crud.to_dict + 注入字段）
export type ConfirmationItem = {
  id: number
  project_id: number | null
  submitter: string
  source_type: string
  title: string
  confirm_status: string
  confidence: number
  special_project?: string
  related_task?: string
  created_at?: string
  updated_at?: string
  reject_reason?: string
  coordinator_note?: string
  ceo_note?: string
  ceo_decision_scope?: 'submission' | 'card'
  pending_ceo_card_indices?: number[]
  [key: string]: unknown
}
