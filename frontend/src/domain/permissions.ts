import type { CurrentUser } from '../types'

export type ProjectRole = 'owner' | 'member' | 'coordinator' | 'project_ceo'

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
  return hasProjectAccess(user, roles)
}

export function canSubmitUpdate(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'owner') || hasProjectRole(roles, 'member') || hasProjectRole(roles, 'coordinator')
}

export function canWriteProjectMainData(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'owner')
}

export function canViewOwnerConfirmCenter(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'owner')
}

export function canViewConfirmCenter(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return (
    canViewOwnerConfirmCenter(user, roles) ||
    canViewCoordinatorReview(user, roles) ||
    canViewCeoDecision(user, roles)
  )
}

export function canViewCoordinatorReview(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'coordinator')
}

export function canViewCeoDecision(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
  return isSuperAdmin(user) || hasProjectRole(roles, 'project_ceo')
}

export function canManageProjects(user: CurrentUserLike, roles?: readonly string[] | null): boolean {
  return isSuperAdmin(user) || Boolean(user?.is_ceo) || hasProjectRole(roles, 'project_ceo')
}

/**
 * 是否可进入「项目管理」页面（角色化视图入口）。
 * 管理员 / CEO / 企业教练 / 负责人 均可进入，但可见范围与操作权限在页面内进一步区分。
 * 注意：这只是「进入页面」的门槛，不等于拥有完整管理权限。
 */
export function canViewProjectManagement(user: CurrentUserLike, roles?: readonly string[] | null): boolean {
  return canManageProjects(user, roles) || hasProjectRole(roles, 'owner')
}

export function canManageProjectMembers(user: CurrentUserLike): boolean {
  return isSuperAdmin(user) || Boolean(user?.is_ceo)
}

export function canViewGlobalOverview(user: CurrentUserLike): boolean {
  return isSuperAdmin(user)
}
