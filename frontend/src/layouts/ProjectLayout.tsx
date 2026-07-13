import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Sidebar } from '../components/Sidebar'
import { PageTransition } from '../components/PageTransition'
import { useProject } from '../context/ProjectContext'
import { getPlatformSettings } from '../api/platformSettings'
import { getProjectScopedNavigationDestination } from '../domain/authFlow'
import type { AppPage } from '../types'

type PageSegment =
  | 'dashboard'
  | 'tasks'
  | 'achievements'
  | 'issues'
  | 'confirm'
  | 'confirmations'
  | 'coordinate'
  | 'org'
  | 'submit'
  | 'meeting'
  | 'settings'
  | 'mytasks'
  | 'notifications'
  | 'projects'

const PATH_TO_PAGE: Record<PageSegment, AppPage> = {
  dashboard: 'dashboard',
  tasks: 'table',
  achievements: 'achievements',
  issues: 'issues',
  confirm: 'confirm',
  confirmations: 'confirm',
  coordinate: 'coordinate',
  org: 'coordinate',
  submit: 'voice',
  meeting: 'meeting',
  settings: 'settings',
  mytasks: 'mytasks',
  notifications: 'notifications',
  projects: 'projects-mgmt',
}

export function NoProjectHome({ isAdmin }: { isAdmin: boolean }) {
  const navigate = useNavigate()

  return (
    <div className="flex-1 flex items-center justify-center" style={{ background: '#F1F5F9' }}>
      <div className="flex flex-col items-center gap-4 text-center">
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg,#0EA5E9,#0369A1)' }}
        >
          <svg style={{ width: 30, height: 30, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <div>
          <div className="text-slate-700 font-semibold text-base">欢迎使用博维 AI 驾驶舱</div>
          <div className="text-slate-400 text-sm mt-1">
            {isAdmin ? '请前往项目管理创建项目并配置项目人员' : '请等待管理员为您分配项目'}
          </div>
        </div>
        {isAdmin && (
          <button
            onClick={() => navigate('/home/projects')}
            className="px-5 py-2 rounded-xl text-white text-sm font-semibold"
            style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
          >
            前往项目管理
          </button>
        )}
      </div>
    </div>
  )
}

function getActivePage(pathname: string, defaultPage: AppPage): AppPage {
  const parts = pathname.split('/').filter(Boolean)
  const group = parts[0] ?? ''
  if (group === 'member') return 'mytasks'

  const segment =
    group === 'home' || group === 'work'
      ? (parts[1] ?? '')
      : group === 'project'
        ? (parts[2] ?? 'dashboard')
        : ''

  if (!segment) return defaultPage
  const mapped = PATH_TO_PAGE[segment as PageSegment]
  return mapped ?? defaultPage
}

export function ProjectLayout() {
  const { currentProjectId, currentUser, globalUserRoles, logout, projects, reloadProjects } = useProject()
  const location = useLocation()
  const navigate = useNavigate()

  const [logoUrl, setLogoUrl] = useState<string | null>(null)
  const [platformName, setPlatformName] = useState<string | undefined>(undefined)

  useEffect(() => {
    getPlatformSettings()
      .then((d) => {
        setLogoUrl(d.logo_url)
        setPlatformName(d.platform_name)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (currentProjectId !== null) {
      reloadProjects().catch(() => {})
    }
  }, [currentProjectId, reloadProjects])

  const isPrivileged = !!(
    currentUser?.is_tech_admin ||
    globalUserRoles.some((r) => ['owner', 'coordinator', 'project_ceo'].includes(r))
  )
  const defaultPage: AppPage = isPrivileged ? 'dashboard' : 'mytasks'
  const activePage = getActivePage(location.pathname, defaultPage)

  const handleNavigate = (page: AppPage) => {
    navigate(getProjectScopedNavigationDestination(page, currentProjectId, projects))
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        activePage={activePage}
        onNavigate={handleNavigate}
        currentUser={currentUser}
        globalUserRoles={globalUserRoles}
        onLogout={logout}
        logoUrl={logoUrl}
        platformName={platformName}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <PageTransition />
      </div>
    </div>
  )
}
