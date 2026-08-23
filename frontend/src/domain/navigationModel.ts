import type { AppPage, CurrentUser, Project } from '../types'
import { canViewMeetings } from './permissions'
import { isProjectActive } from './projectLifecycleStatus'
import { AI_CONFIRM_CENTER_LABEL } from './displayNames'

export type NavigationIcon = 'home' | 'table' | 'confirm' | 'voice' | 'meeting' | 'archive' | 'issues' | 'org' | 'projects' | 'bell' | 'settings' | 'mytasks'

export type NavigationEntry = { page: AppPage; label: string; icon: NavigationIcon; badge?: number }

export function getNavigationEntries(currentUser: CurrentUser | null, globalUserRoles: string[], projects: Project[], confirmBadge = 0): NavigationEntry[] {
  const isPrivileged = Boolean(currentUser?.is_tech_admin || currentUser?.is_ceo || globalUserRoles.some((role) => ['owner', 'coordinator', 'project_ceo'].includes(role)))
  const showParticipantModules = !(currentUser?.is_ceo && !globalUserRoles.some((role) => ['owner', 'coordinator', 'project_ceo', 'member'].includes(role)))
  const hasActiveProject = projects.some(isProjectActive)
  return [
    ...(isPrivileged ? [{ page: 'dashboard' as const, label: '驾驶舱', icon: 'home' as const }] : []),
    ...(showParticipantModules && hasActiveProject ? [{ page: 'table' as const, label: '工作推进表', icon: 'table' as const }] : []),
    ...(showParticipantModules ? [{ page: 'mytasks' as const, label: '我的任务', icon: 'mytasks' as const }] : []),
    ...(showParticipantModules && isPrivileged ? [{ page: 'confirm' as const, label: AI_CONFIRM_CENTER_LABEL, icon: 'confirm' as const, badge: confirmBadge || undefined }] : []),
    ...(showParticipantModules ? [{ page: 'voice' as const, label: '工作汇报', icon: 'voice' as const }] : []),
    ...(canViewMeetings(currentUser, globalUserRoles) ? [{ page: 'meeting' as const, label: '会议纪要', icon: 'meeting' as const }] : []),
    { page: 'achievements' as const, label: '成果库', icon: 'archive' as const },
    { page: 'issues' as const, label: '问题中心', icon: 'issues' as const },
    { page: 'coordinate' as const, label: '组织管理', icon: 'org' as const },
    ...((currentUser?.is_tech_admin || currentUser?.is_ceo || globalUserRoles.includes('project_ceo') || globalUserRoles.includes('owner')) ? [{ page: 'projects-mgmt' as const, label: '项目管理', icon: 'projects' as const }] : []),
    { page: 'notifications' as const, label: '通知中心', icon: 'bell' as const },
    ...(currentUser?.is_tech_admin ? [{ page: 'settings' as const, label: '系统设置', icon: 'settings' as const }] : []),
  ]
}
