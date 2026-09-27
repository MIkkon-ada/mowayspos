import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import type { AppPage } from '../types'
import { useProject } from '../context/ProjectContext'

type AppShellProps = {
  children: ReactNode
  activePage: AppPage
  onNavigate: (page: AppPage) => void
}

export function AppShell({ children, activePage, onNavigate }: AppShellProps) {
  const { currentUser, globalUserRoles } = useProject()
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar activePage={activePage} onNavigate={onNavigate} currentUser={currentUser} globalUserRoles={globalUserRoles} />
      <div style={{ flex: 1, overflow: 'hidden' }}>{children}</div>
    </div>
  )
}
