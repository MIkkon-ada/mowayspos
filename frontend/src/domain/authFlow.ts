import type { CurrentUser, Project } from '../types'

type ApiLikeError = {
  status?: number
  message?: string
}

type ProjectRef = {
  id: number
}

type ProjectAccessRef = number | string | { id?: number; name?: string }

function hasMessage(error: unknown, pattern: RegExp): boolean {
  return pattern.test(String((error as ApiLikeError | undefined)?.message ?? ''))
}

export function normalizeLoginError(error: unknown): string {
  const status = (error as ApiLikeError | undefined)?.status
  // 后端 must_change_password 中间件返回 403 + detail="must_change_password"，非账号禁用
  const detail = (error as { body?: { detail?: string } } | undefined)?.body?.detail
  if (status === 403 && detail === 'must_change_password') return '请先修改初始密码'
  if (status === 401) return '账号或密码错误'
  if (status === 403) return '账号已禁用，请联系管理员'
  if (status === 423) return '密码错误次数过多，请稍后再试'
  if (status && status >= 500) return '服务器异常，请查看后端日志'
  if (hasMessage(error, /Failed to fetch|NetworkError|Network request failed|Load failed/i)) {
    return '无法连接服务器，请确认后端服务已启动'
  }
  const message = String((error as ApiLikeError | undefined)?.message ?? '')
  if (message) return message
  return '登录失败，请稍后重试'
}


function getLegacyPostLoginDestination(projects: ProjectRef[], preferredProjectId: number | null): string {
  if (projects.length === 0) return '/home'
  if (projects.length === 1) return `/project/${projects[0].id}`
  if (preferredProjectId !== null && projects.some((p) => p.id === preferredProjectId)) {
    return `/project/${preferredProjectId}`
  }
  return '/home'
}

function getFirstProjectId(projects: ProjectRef[]): number | null {
  return projects[0]?.id ?? null
}

export function getPostLoginDestination(
  currentUserOrProjects: Pick<CurrentUser, 'is_tech_admin' | 'is_ceo' | 'can_view_all' | 'must_change_password'> | ProjectRef[] | null | undefined,
  projectsOrPreferred: ProjectRef[] | number | null,
  preferredProjectId?: number | null,
): string {
  if (Array.isArray(currentUserOrProjects)) {
    return getLegacyPostLoginDestination(currentUserOrProjects, projectsOrPreferred as number | null)
  }

  const currentUser = currentUserOrProjects
  // 强制改密码优先级最高，跳过项目列表加载（后端中间件会 403 拦截）
  if (currentUser?.must_change_password) return '/change-password'
  const projects = Array.isArray(projectsOrPreferred) ? projectsOrPreferred : []
  if (projects.length === 0) return '/home/dashboard'
  if (currentUser?.is_tech_admin || currentUser?.is_ceo || currentUser?.can_view_all) return '/home/dashboard'

  const preferred = preferredProjectId ?? null
  return '/member/projects'
}

export function getProjectsLandingDestination(projects: ProjectRef[]): string {
  return projects.length === 1 ? `/project/${projects[0].id}` : '/home'
}

function matchesProjectAccessRef(ref: ProjectAccessRef, projectId: number, projectName?: string): boolean {
  if (typeof ref === 'number') return ref === projectId
  if (typeof ref === 'string') {
    return ref === String(projectId) || (projectName ? ref === projectName : false)
  }
  if (!ref || typeof ref !== 'object') return false
  if (typeof ref.id === 'number' && ref.id === projectId) return true
  if (projectName && typeof ref.name === 'string' && ref.name === projectName) return true
  return false
}

export function canAccessTechAdminRoute(user: Pick<CurrentUser, 'is_tech_admin'> | null | undefined): boolean {
  return Boolean(user?.is_tech_admin)
}

export function canAccessProjectRoute(
  user: Pick<CurrentUser, 'is_tech_admin' | 'is_ceo' | 'projects' | 'visible_projects'> | null | undefined,
  projectId: number,
  projects: Project[],
): boolean {
  if (!user) return false
  if (user.is_tech_admin || user.is_ceo) return true

  const project = projects.find((item) => item.id === projectId)
  const refs = [
    ...(Array.isArray(user.projects) ? user.projects : []),
    ...(Array.isArray(user.visible_projects) ? user.visible_projects : []),
  ] as ProjectAccessRef[]

  return refs.some((ref) => matchesProjectAccessRef(ref, projectId, project?.name))
}

export function canPreviewClientRoute(
  user: Pick<CurrentUser, 'capabilities'> | null | undefined,
): boolean {
  return Boolean(user?.capabilities?.canPreviewClientView)
}

export function getProjectScopedNavigationDestination(
  page: string,
  currentProjectId: number | null,
  projects: ProjectRef[],
): string {
  const workspacePages: Record<string, string> = {
    dashboard: '/home/dashboard',
    voice: '/work/submit',
    confirm: '/work/confirmations',
    confirmations: '/work/confirmations',
    table: '/work/tasks',
    achievements: '/work/achievements',
    issues: '/work/issues',
    coordinate: '/work/org',
    decisions: '/work/decisions',
    meetings: '/work/meetings',
    meeting: '/work/meetings',
    notifications: '/home/notifications',
    settings: '/home/settings',
    'projects-mgmt': '/home/projects',
    mytasks: '/member/projects',
  }

  const workspaceDestination = workspacePages[page]
  if (workspaceDestination) return workspaceDestination

  return currentProjectId !== null ? `/project/${currentProjectId}` : '/home'
}


