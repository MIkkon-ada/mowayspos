import type { CurrentUser } from '../types'

export type ProjectRole = 'owner' | 'member' | 'coordinator' | 'project_ceo'

export type ProjectAction =
  | 'project.view'
  | 'project.create'
  | 'project.batch_import'
  | 'project.edit_source'
  | 'project.manage_members_direct'
  | 'project.request_member_change'
  | 'project.review_member_change'
  | 'project.dispatch'
  | 'project.owner_submit'
  | 'project.review_start'
  | 'project.request_close'
  | 'project.edit_close_request'
  | 'project.cancel_close_request'
  | 'project.review_close_request'
  | 'project.archive'
  | 'project.delete'
  | 'project.technical_kickoff'

export type WorkflowAction =
  | 'confirmation.view'
  | 'confirmation.review'
  | 'confirmation.coordinator_feedback'
  | 'confirmation.escalate'
  | 'confirmation.ceo_decide'
  | 'confirmation.resubmit'
  | 'confirmation.withdraw'
  | 'meeting.view'
  | 'meeting.create'
  | 'meeting.edit'
  | 'meeting.publish'
  | 'meeting.review_changes'
  | 'meeting.apply_changes'
  | 'meeting.progress_review'
  | 'meeting.kickoff_submit'
  | 'meeting.kickoff_decide'

export type ProjectPermissionInput = {
  isTechAdmin?: boolean
  isCompanyCeo?: boolean
  personId?: number | null
  projectRoles?: readonly string[] | null
  lifecycle?: string | null
  requesterPersonId?: number | null
}

export type WorkflowPermissionInput = {
  isTechAdmin?: boolean
  isCompanyCeo?: boolean
  personId?: number | null
  projectRoles?: readonly string[] | null
  submitterPersonId?: number | null
  creatorPersonId?: number | null
}

type CurrentUserLike = Pick<CurrentUser, 'is_tech_admin' | 'is_ceo'> | null | undefined

export function isSuperAdmin(user: CurrentUserLike): boolean {
  return Boolean(user?.is_tech_admin)
}

export function hasProjectRole(roles: readonly string[] | null | undefined, role: ProjectRole): boolean {
  return roles?.includes(role) ?? false
}

function hasAnyProjectRole(roles: readonly string[] | null | undefined): boolean {
  return Boolean(
    roles?.some((role) =>
      role === 'owner' ||
      role === 'member' ||
      role === 'coordinator' ||
      role === 'project_ceo',
    ),
  )
}

function hasProjectAccess(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasAnyProjectRole(roles)
}

export function canProjectAction(action: ProjectAction, input: ProjectPermissionInput): boolean {
  const roles = input.projectRoles ?? []
  const has = (...allowed: ProjectRole[]) => roles.some((role) => allowed.includes(role as ProjectRole))
  const tech = Boolean(input.isTechAdmin)
  const companyCeo = Boolean(input.isCompanyCeo)
  const lifecycle = input.lifecycle ?? ''

  switch (action) {
    case 'project.view':
      return tech || companyCeo || has('owner', 'coordinator', 'member', 'project_ceo')
    case 'project.create':
      return tech || companyCeo
    case 'project.batch_import':
    case 'project.delete':
      return tech
    case 'project.edit_source':
    case 'project.manage_members_direct':
      return tech || (companyCeo && lifecycle === 'draft')
    case 'project.request_member_change':
      return !['draft', 'pending_close', 'ended', 'archived'].includes(lifecycle) && (tech || has('owner', 'project_ceo'))
    case 'project.review_member_change':
      return !['pending_close', 'ended', 'archived'].includes(lifecycle) && (tech || has('project_ceo'))
    case 'project.dispatch':
      return lifecycle === 'draft' && (tech || companyCeo)
    case 'project.owner_submit':
      return ['dispatched', 'returned'].includes(lifecycle) && (tech || has('owner'))
    case 'project.review_start':
      return !['pending_close', 'ended', 'archived'].includes(lifecycle) && (tech || has('project_ceo'))
    case 'project.request_close':
      return lifecycle === 'active' && (tech || has('owner'))
    case 'project.edit_close_request':
    case 'project.cancel_close_request':
      return lifecycle === 'pending_close' && (
        tech || (has('owner') && input.personId != null && input.personId === input.requesterPersonId)
      )
    case 'project.review_close_request':
      return lifecycle === 'pending_close' && (tech || has('project_ceo'))
    case 'project.archive':
      return lifecycle === 'ended' && tech
    case 'project.technical_kickoff':
      return !['pending_close', 'ended', 'archived'].includes(lifecycle) && tech
  }
}

export function canWorkflowAction(action: WorkflowAction, input: WorkflowPermissionInput): boolean {
  const roles = input.projectRoles ?? []
  const has = (...allowed: ProjectRole[]) => roles.some((role) => allowed.includes(role as ProjectRole))
  const tech = Boolean(input.isTechAdmin)
  const companyCeo = Boolean(input.isCompanyCeo)
  const isSubmitter = input.personId != null && input.personId === input.submitterPersonId
  const isCreator = input.personId != null && input.personId === input.creatorPersonId

  if (action === 'confirmation.resubmit') {
    return isSubmitter
  }
  if (tech) {
    return true
  }

  switch (action) {
    case 'confirmation.view':
      return companyCeo || has('owner', 'coordinator', 'project_ceo') || isSubmitter
    case 'confirmation.review':
    case 'confirmation.escalate':
      return has('owner')
    case 'confirmation.coordinator_feedback':
      return has('coordinator')
    case 'confirmation.ceo_decide':
      return has('project_ceo')
    case 'confirmation.withdraw':
      return isSubmitter
    case 'meeting.view':
      return companyCeo || has('owner', 'coordinator', 'member', 'project_ceo')
    case 'meeting.create':
      return has('owner', 'coordinator', 'member')
    case 'meeting.edit':
      return has('owner') || isCreator
    case 'meeting.publish':
    case 'meeting.review_changes':
    case 'meeting.apply_changes':
      return has('owner')
    case 'meeting.progress_review':
      return has('owner', 'coordinator')
    case 'meeting.kickoff_submit':
      return has('owner')
    case 'meeting.kickoff_decide':
      return has('project_ceo')
  }
}

export function canViewProjectDashboard(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return hasProjectAccess(user, roles)
}

export function canViewTasks(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return hasProjectAccess(user, roles)
}

export function canViewAchievements(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return hasProjectAccess(user, roles)
}

export function canViewIssues(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return hasProjectAccess(user, roles)
}

export function canViewMeetings(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return canWorkflowAction('meeting.view', {
    isTechAdmin: user?.is_tech_admin,
    isCompanyCeo: user?.is_ceo,
    projectRoles: roles,
  })
}

export function canSubmitUpdate(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'owner') || hasProjectRole(roles, 'member') || hasProjectRole(roles, 'coordinator')
}

export function canWriteProjectMainData(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return canProjectAction('project.owner_submit', {
    isTechAdmin: user?.is_tech_admin,
    projectRoles: roles,
    lifecycle: 'dispatched',
  })
}

export function canViewOwnerConfirmCenter(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'owner')
}

export function canViewConfirmCenter(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  const canViewCoach = canViewCeoDecision(user, roles)
  return canWorkflowAction('confirmation.view', {
    isTechAdmin: user?.is_tech_admin,
    isCompanyCeo: user?.is_ceo,
    projectRoles: roles,
  }) || canViewCoach
}

export function canViewCoordinatorReview(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'coordinator')
}

export function canViewCeoDecision(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'project_ceo')
}

export function canManageProjects(user: CurrentUserLike, roles?: readonly string[] | null): boolean {
  return canProjectAction('project.create', {
    isTechAdmin: user?.is_tech_admin,
    isCompanyCeo: user?.is_ceo,
    projectRoles: roles,
  }) || hasProjectRole(roles, 'project_ceo')
}

/**
 * 是否可进入项目生命周期页面的查看入口。
 * 真实项目参与人可进入并查看自己可见的项目及结束档案，但这不代表拥有项目管理写权限。
 * 新建、编辑、结束申请、审核和归档仍由页面操作及后端接口分别校验。
 */
export function canViewProjectManagement(user: CurrentUserLike, roles?: readonly string[] | null): boolean {
  return canManageProjects(user, roles) || hasAnyProjectRole(roles)
}

export function canManageProjectMembers(user: CurrentUserLike): boolean {
  return isSuperAdmin(user) || Boolean(user?.is_ceo)
}

export function canViewGlobalOverview(user: CurrentUserLike): boolean {
  return isSuperAdmin(user)
}
