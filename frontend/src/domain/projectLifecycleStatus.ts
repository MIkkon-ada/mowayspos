export type ProjectLifecycleStatus =
  | 'draft'
  | 'pending_review'
  | 'returned'
  | 'dispatched'
  | 'active'
  | 'archived'
  | string

export type ProjectLifecycleLike = {
  status?: ProjectLifecycleStatus | null
  lifecycle_status?: ProjectLifecycleStatus | null
  is_active?: boolean | null
}

export type ProjectStatusTone = 'neutral' | 'warning' | 'info' | 'success' | 'danger'

export type ProjectStatusBadge = {
  status: string
  label: string
  tone: ProjectStatusTone
  className: string
}

const STATUS_META: Record<string, ProjectStatusBadge> = {
  draft: {
    status: 'draft',
    label: '草稿',
    tone: 'neutral',
    className: 'bg-slate-100 text-slate-600',
  },
  pending_review: {
    status: 'pending_review',
    label: '待审核',
    tone: 'warning',
    className: 'bg-amber-100 text-amber-700',
  },
  returned: {
    status: 'returned',
    label: '已退回',
    tone: 'danger',
    className: 'bg-orange-100 text-orange-700',
  },
  dispatched: {
    status: 'dispatched',
    label: '已派发',
    tone: 'info',
    className: 'bg-blue-100 text-blue-700',
  },
  active: {
    status: 'active',
    label: '进行中',
    tone: 'success',
    className: 'bg-emerald-100 text-emerald-700',
  },
  archived: {
    status: 'archived',
    label: '已归档',
    tone: 'neutral',
    className: 'bg-slate-200 text-slate-700',
  },
}

function normalizeStatus(value?: string | null): string {
  return (value ?? '').trim()
}

export function getProjectPrimaryStatus(project?: ProjectLifecycleLike | null): string {
  if (!project) return ''
  const status = normalizeStatus(project.status)
  if (status) return status
  const lifecycleStatus = normalizeStatus(project.lifecycle_status)
  if (lifecycleStatus) return lifecycleStatus
  if (project.is_active === true) return 'active'
  if (project.is_active === false) return 'archived'
  return ''
}

export function getProjectStatusBadge(project?: ProjectLifecycleLike | null): ProjectStatusBadge {
  const status = getProjectPrimaryStatus(project)
  return STATUS_META[status] ?? {
    status,
    label: status || '-',
    tone: 'neutral',
    className: 'bg-slate-100 text-slate-600',
  }
}

export function getProjectStatusLabel(project?: ProjectLifecycleLike | null): string {
  return getProjectStatusBadge(project).label
}

export function getProjectStatusTone(project?: ProjectLifecycleLike | null): ProjectStatusTone {
  return getProjectStatusBadge(project).tone
}

export function isProjectArchived(project?: ProjectLifecycleLike | null): boolean {
  if (!project) return false
  if (normalizeStatus(project.status) === 'archived') return true
  if (normalizeStatus(project.lifecycle_status) === 'archived') return true
  return false
}

export function isProjectActive(project?: ProjectLifecycleLike | null): boolean {
  return getProjectPrimaryStatus(project) === 'active'
}

export function canShowProjectStartupAction(project?: ProjectLifecycleLike | null): boolean {
  const status = getProjectPrimaryStatus(project)
  return status === 'dispatched' || status === 'active'
}

export function canShowProjectSubmitAction(project?: ProjectLifecycleLike | null): boolean {
  const status = getProjectPrimaryStatus(project)
  return status === 'draft' || status === 'dispatched' || status === 'returned'
}

export function canShowProjectApproveAction(project?: ProjectLifecycleLike | null): boolean {
  return getProjectPrimaryStatus(project) === 'pending_review'
}
