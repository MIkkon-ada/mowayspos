import type { CurrentUser } from '../types'
import {
  canSubmitUpdate as canSubmitUpdatePermission,
  canWriteProjectMainData,
  hasProjectRole,
  isSuperAdmin as isSuperAdminPermission,
} from '../domain/permissions'

// 兼容旧页面的角色 helper，底层已统一到 domain/permissions.ts
export function isOwner(roles: string[]): boolean {
  return hasProjectRole(roles, 'owner')
}

export function isMember(roles: string[]): boolean {
  return hasProjectRole(roles, 'member')
}

export function isCoordinator(roles: string[]): boolean {
  return hasProjectRole(roles, 'coordinator')
}

export function isProjectCeo(roles: string[]): boolean {
  return hasProjectRole(roles, 'project_ceo')
}

export function isProjectCoach(roles: string[]): boolean {
  return hasProjectRole(roles, 'project_ceo')
}

export function isSuperAdmin(user: CurrentUser | null | undefined): boolean {
  return isSuperAdminPermission(user)
}

export function canWrite(roles: string[]): boolean {
  return canWriteProjectMainData(null, roles)
}

export function canSubmitUpdate(roles: string[]): boolean {
  return canSubmitUpdatePermission(null, roles)
}
