import type { Project, TaskItem } from '../../types'
import type { SubTaskWithParent } from '../../api/subtasks'
import { getProjectPrimaryStatus } from '../../domain/projectLifecycleStatus'

export type ProjectWorkbenchOverviewStats = {
  all: number
  toComplete: number
  toApprove: number
  active: number
  archived: number
}

export type ProjectTodoRoles = {
  isSuperAdmin: boolean
  isCompanyCeo: boolean
  isRealProjectCeo: boolean
  isRealOwner: boolean
}

export type ProjectTodoAction = 'edit' | 'ownerSubmit' | 'approvalMaterials'
export type ProjectMaterialKey = 'objectives' | 'period' | 'tasks' | 'subtasks'
export type ProjectMaterialCheck = { key: ProjectMaterialKey; label: string; complete: boolean }

export type ProjectTodo = {
  project: Project
  action: ProjectTodoAction
  actionLabel: string
  title: string
  description: string
  materialChecks: ProjectMaterialCheck[]
}

export type ProjectLifecycleStage = {
  key: 'planning' | 'startup' | 'execution' | 'closing' | 'archive'
  label: string
  activeIndex: number
  detail: string
}

const STAGE_NODES = ['立项准备', '启动', '执行', '结束', '归档'] as const

export function getProjectOverviewStats(projects: readonly Project[]): ProjectWorkbenchOverviewStats {
  return projects.reduce<ProjectWorkbenchOverviewStats>((stats, project) => {
    const status = getProjectPrimaryStatus(project)
    stats.all += 1
    if (status === 'dispatched' || status === 'returned') stats.toComplete += 1
    if (status === 'pending_review') stats.toApprove += 1
    if (status === 'active') stats.active += 1
    if (status === 'archived') stats.archived += 1
    return stats
  }, { all: 0, toComplete: 0, toApprove: 0, active: 0, archived: 0 })
}

export function getProjectMaterialChecklist(
  project: Project,
  tasks: readonly TaskItem[],
  subtasks: readonly SubTaskWithParent[],
): ProjectMaterialCheck[] {
  return [
    { key: 'objectives', label: '项目目标', complete: Boolean(project.objectives?.trim()) },
    { key: 'period', label: '项目周期', complete: Boolean(project.start_date && project.end_date) },
    { key: 'tasks', label: '重点工作', complete: tasks.length > 0 },
    { key: 'subtasks', label: '关键任务', complete: subtasks.length > 0 },
  ]
}

export function getProjectTodo(
  project: Project,
  roles: ProjectTodoRoles,
  tasks: readonly TaskItem[],
  subtasks: readonly SubTaskWithParent[],
): ProjectTodo | null {
  const status = getProjectPrimaryStatus(project)
  const materialChecks = status === 'dispatched' || status === 'returned'
    ? getProjectMaterialChecklist(project, tasks, subtasks)
    : []

  if (status === 'draft' && (roles.isSuperAdmin || roles.isCompanyCeo)) {
    return {
      project,
      action: 'edit',
      actionLabel: '继续完善项目',
      title: '项目尚未下发',
      description: '请继续完善项目信息并完成下发。',
      materialChecks,
    }
  }

  if (status === 'dispatched' && roles.isRealOwner) {
    return {
      project,
      action: 'ownerSubmit',
      actionLabel: '继续完善项目',
      title: '项目已下发，等待您完善项目计划',
      description: '请补充项目目标、项目周期、重点工作和关键任务等信息。',
      materialChecks,
    }
  }

  if (status === 'returned' && roles.isRealOwner) {
    return {
      project,
      action: 'ownerSubmit',
      actionLabel: '修改项目计划',
      title: '项目已被企业教练退回',
      description: '请根据审核意见修改后重新提交。',
      materialChecks,
    }
  }

  if (status === 'pending_review' && (roles.isRealProjectCeo || roles.isSuperAdmin)) {
    return {
      project,
      action: 'approvalMaterials',
      actionLabel: '审核项目',
      title: '负责人已提交项目计划',
      description: '等待您审核。',
      materialChecks,
    }
  }

  return null
}

export function getProjectLifecycleStage(status: string): ProjectLifecycleStage {
  switch (status) {
    case 'active':
      return { key: 'execution', label: '执行阶段', activeIndex: 2, detail: '项目正在执行中。' }
    case 'pending_close':
      return { key: 'closing', label: '结束阶段', activeIndex: 3, detail: '项目结束申请正在审核中。' }
    case 'ended':
      return { key: 'closing', label: '结束完成', activeIndex: 3, detail: '项目已结束，等待归档。' }
    case 'archived':
      return { key: 'archive', label: '归档阶段', activeIndex: 4, detail: '项目已归档，可查看项目档案。' }
    default:
      return { key: 'planning', label: '立项准备阶段', activeIndex: 0, detail: '项目处于立项准备阶段。' }
  }
}

export { STAGE_NODES }
