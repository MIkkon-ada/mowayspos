import type { CurrentUser, AppPage } from '../types'
import {
  canManageProjects,
  canSubmitUpdate,
  canViewAchievements,
  canViewCoordinatorReview,
  canViewIssues,
  canViewMeetings,
  canViewOwnerConfirmCenter,
  canViewProjectDashboard,
  canViewTasks,
} from './permissions'
import { WORK_REPORT_LABEL, AI_CONFIRM_CENTER_LABEL } from './displayNames'

export type SidebarRouteItem = {
  key: AppPage
  label: string
  icon: string
  kind: 'route'
  page: AppPage
  visible: (user: CurrentUser | null, roles: string[]) => boolean
}

export type SidebarLinkItem = {
  key: string
  label: string
  icon: string
  kind: 'link'
  to: string
  visible: (user: CurrentUser | null, roles: string[]) => boolean
}

export type SidebarItem = SidebarRouteItem | SidebarLinkItem

export const SIDEBAR_ITEMS: SidebarItem[] = [
  { key: 'dashboard', label: '首页', icon: 'home', kind: 'route', page: 'dashboard', visible: canViewProjectDashboard },
  { key: 'voice', label: WORK_REPORT_LABEL, icon: 'voice', kind: 'route', page: 'voice', visible: canSubmitUpdate },
  { key: 'meeting', label: '会议纪要', icon: 'doc', kind: 'route', page: 'meeting', visible: canViewMeetings },
  { key: 'confirm', label: AI_CONFIRM_CENTER_LABEL, icon: 'confirm', kind: 'route', page: 'confirm', visible: canViewOwnerConfirmCenter },
  { key: 'table', label: '工作推进表', icon: 'table', kind: 'route', page: 'table', visible: canViewTasks },
  { key: 'achievements', label: '成果库', icon: 'archive', kind: 'route', page: 'achievements', visible: canViewAchievements },
  { key: 'issues', label: '问题与决策', icon: 'alert', kind: 'route', page: 'issues', visible: canViewIssues },
  { key: 'coordinate', label: '统筹建议', icon: 'confirm', kind: 'route', page: 'coordinate', visible: canViewCoordinatorReview },
  { key: 'admin-projects', label: '项目管理', icon: 'settings', kind: 'link', to: '/admin/projects', visible: canManageProjects },
]

export function getVisibleSidebarItems(user: CurrentUser | null, roles: string[]): SidebarItem[] {
  return SIDEBAR_ITEMS.filter((item) => item.visible(user, roles))
}
