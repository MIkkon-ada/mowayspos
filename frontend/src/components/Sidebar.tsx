import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { AppPage, CurrentUser } from '../types'
import { useProject } from '../context/ProjectContext'
import { NotificationBell } from './NotificationBell'
import { getConfirmationCounts } from '../api/confirmations'
import { isProjectActive } from '../domain/projectLifecycleStatus'
import { getProjectRoleLabel } from '../domain/roleLabels'
import { systemRoleLabel } from '../domain/roles'
import { SYSTEM_NAME_CN, AI_CONFIRM_CENTER_LABEL } from '../domain/displayNames'

type SidebarProps = {
  activePage: AppPage
  onNavigate: (page: AppPage) => void
  currentUser: CurrentUser | null
  globalUserRoles: string[]
  onLogout?: () => void
  logoUrl?: string | null
  platformName?: string
}

type NavItem = {
  page: AppPage
  label: string
  icon: React.ReactNode
  badge?: number
}

type SectionSeparator = {
  kind: 'separator'
}

type NavEntry = NavItem | SectionSeparator

export function Sidebar({ activePage, onNavigate, currentUser, globalUserRoles, onLogout, logoUrl, platformName }: SidebarProps) {
  const navigate = useNavigate()
  const { projects } = useProject()
  const userName = currentUser?.name ?? ''
  const rolePriority = ['owner', 'coordinator', 'project_ceo', 'member']
  const highestRole = rolePriority.find((r) => globalUserRoles.includes(r))
  const roleText = highestRole ? getProjectRoleLabel(highestRole) : systemRoleLabel(currentUser?.system_role)
  const avatarChar = userName.slice(0, 1) || '我'

  const isCEO = !!(currentUser?.is_ceo || globalUserRoles.includes('project_ceo'))
  const isCoachDecisionActor = Boolean(
    currentUser?.is_tech_admin ||
    globalUserRoles.includes('project_ceo')
  )
  const isPrivileged = !!(
    currentUser?.is_tech_admin ||
    currentUser?.is_ceo ||
    globalUserRoles.some((r) => ['owner', 'coordinator', 'project_ceo'].includes(r))
  )
  const showParticipantModules = !(
    currentUser?.is_ceo &&
    !globalUserRoles.some((r) => ['owner', 'coordinator', 'member'].includes(r))
  )
  const hasActiveProject = projects.some(isProjectActive)

  const [confirmBadge, setConfirmBadge] = useState(0)

  useEffect(() => {
    if (!isPrivileged) return
    function poll() {
      getConfirmationCounts()
        .then((counts) => setConfirmBadge((counts['待审核'] ?? 0) + (counts.ceo_total ?? counts.ceo ?? 0)))
        .catch(() => {})
    }
    poll()
    const id = setInterval(poll, 30_000)
    return () => clearInterval(id)
  }, [isPrivileged])

  function section(items: NavItem[]): NavEntry[] {
    if (items.length === 0) return []
    return [{ kind: 'separator' as const }, ...items]
  }

  const cockpitItems: NavItem[] = [
    ...(isPrivileged ? [{ page: 'dashboard' as const, label: '驾驶舱', icon: <IconHome /> }] : []),
  ]

  const executionItems: NavItem[] = [
    ...(isPrivileged && hasActiveProject
      ? [{ page: 'table' as const, label: '工作推进表', icon: <IconTable /> }]
      : []),
  ]

  const personalWorkItems: NavItem[] = [
    ...(showParticipantModules ? [{ page: 'mytasks' as const, label: '我的任务', icon: <IconMyTasks /> }] : []),
    ...(showParticipantModules && isPrivileged ? [{ page: 'confirm' as const, label: AI_CONFIRM_CENTER_LABEL, icon: <IconConfirm />, badge: confirmBadge || undefined }] : []),
  ]

  const processInputItems: NavItem[] = [
    ...(showParticipantModules ? [{ page: 'voice' as const, label: '工作汇报', icon: <IconVoice /> }] : []),
    ...(showParticipantModules ? [{ page: 'meeting' as const, label: '会议纪要', icon: <IconDoc /> }] : []),
  ]

  const assetItems: NavItem[] = [
    { page: 'achievements' as const, label: '成果库', icon: <IconArchive /> },
    { page: 'issues' as const, label: '问题中心', icon: <IconAlert /> },
    ...(isCoachDecisionActor ? [{ page: 'decisions' as const, label: '企业教练决策中心', icon: <IconGavel /> }] : []),
  ]

  const collaborationManagementItems: NavItem[] = [
    { page: 'coordinate' as const, label: '组织管理', icon: <IconOrg /> },
    ...((currentUser?.is_tech_admin ||
      currentUser?.is_ceo ||
      globalUserRoles.includes('project_ceo') ||
      globalUserRoles.includes('owner'))
      ? [{ page: 'projects-mgmt' as const, label: '项目管理', icon: <IconProjectMgmt /> }]
      : []),
    { page: 'notifications' as const, label: '通知中心', icon: <IconBell /> },
  ]

  const systemItems: NavItem[] = [
    ...(currentUser?.is_tech_admin ? [{ page: 'settings' as const, label: '系统设置', icon: <IconSettings /> }] : []),
  ]

  const navEntries: NavEntry[] = [
    ...section(cockpitItems),
    ...section(executionItems),
    ...section(personalWorkItems),
    ...section(processInputItems),
    ...section(assetItems),
    ...section(collaborationManagementItems),
    ...section(systemItems),
  ]

  function handleNavigate(page: AppPage) {
    if (page === 'dashboard') {
      navigate('/home/dashboard')
      return
    }
    onNavigate(page)
  }

  return (
    <aside className="w-56 flex-shrink-0 flex flex-col overflow-hidden" style={{ background: '#0F172A' }}>
      <div
        className="flex items-center gap-3 px-5 h-16 flex-shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}
      >
        {logoUrl
          ? <img src={logoUrl} alt="logo" style={{ height: 36, maxWidth: 80, objectFit: 'contain', flexShrink: 0 }} />
          : <div
              className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: 'linear-gradient(135deg,var(--brand-accent,#0EA5E9),var(--brand-primary,#0369A1))' }}
            >
              <svg style={{ width: 18, height: 18, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
        }
        <div className="flex-1 min-w-0">
          <div className="text-white text-sm font-bold tracking-tight leading-none">{platformName }</div>
          <div className="text-slate-500 text-xs mt-0.5">{SYSTEM_NAME_CN}</div>
        </div>
        <NotificationBell />
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navEntries.map((entry, idx) => {
          if ('kind' in entry) {
            return <div key={idx} className="pt-4" />
          }

          const isActive = activePage === entry.page
          return (
            <button
              key={entry.page}
              type="button"
              onClick={() => handleNavigate(entry.page)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '9px 14px',
                borderRadius: 8,
                color: isActive ? '#38BDF8' : '#94A3B8',
                fontSize: 13.5,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.18s',
                textDecoration: 'none',
                borderLeft: isActive ? '2px solid var(--brand-accent, #0EA5E9)' : '2px solid transparent',
                background: isActive ? 'rgba(14,165,233,0.15)' : 'transparent',
                width: '100%',
                textAlign: 'left',
                border: 'none',
                outline: 'none',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
                  e.currentTarget.style.color = '#E2E8F0'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = '#94A3B8'
                }
              }}
            >
              <span style={{ width: 16, height: 16, flexShrink: 0 }}>{entry.icon}</span>
              <span style={{ flex: 1 }}>{entry.label}</span>
              {entry.badge ? (
                <span
                  style={{
                    background: '#EF4444',
                    color: '#fff',
                    borderRadius: 9999,
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '1px 6px',
                    lineHeight: '16px',
                    minWidth: 18,
                    textAlign: 'center',
                    flexShrink: 0,
                  }}
                >
                  {entry.badge > 99 ? '99+' : entry.badge}
                </span>
              ) : null}
            </button>
          )
        })}
      </nav>

      <div
        className="px-4 py-3 flex items-center gap-3 flex-shrink-0"
        style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}
      >
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
          style={{ background: 'linear-gradient(135deg,#3B82F6,var(--brand-primary,#0369A1))' }}
        >
          {avatarChar}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-white text-sm font-semibold truncate">{userName || '未登录'}</div>
          <div className="text-slate-500 text-xs truncate">{roleText || '暂无角色'}</div>
        </div>
        <button
          type="button"
          onClick={() => navigate('/change-password')}
          title="修改密码"
          className="flex-shrink-0 p-1.5 rounded-lg transition-colors hover:bg-white/10"
          style={{ color: '#64748B' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#94A3B8' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = '#64748B' }}
        >
          <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
        </button>
        {onLogout && (
          <button
            type="button"
            onClick={onLogout}
            title="退出登录"
            className="flex-shrink-0 p-1.5 rounded-lg transition-colors hover:bg-white/10"
            style={{ color: '#64748B' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#F87171' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = '#64748B' }}
          >
            <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        )}
      </div>
    </aside>
  )
}

function IconHome() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
    </svg>
  )
}

function IconVoice() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
    </svg>
  )
}

function IconDoc() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
}

function IconConfirm() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function IconBell() {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  )
}

function IconTable() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
    </svg>
  )
}

function IconMyTasks() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  )
}

function IconArchive() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
    </svg>
  )
}

function IconAlert() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  )
}

function IconOrg() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )
}

function IconSettings() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )
}

function IconProjectMgmt() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
    </svg>
  )
}

function IconGavel() {
  return (
    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
    </svg>
  )
}
