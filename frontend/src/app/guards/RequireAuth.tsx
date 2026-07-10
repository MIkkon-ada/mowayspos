import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useProject } from '../../context/ProjectContext'
import { CenterMessage } from '../../layouts/AppLayout'

type RequireAuthProps = {
  children: ReactNode
}

export function RequireAuth({ children }: RequireAuthProps) {
  const { authState, currentUser } = useProject()
  const location = useLocation()

  if (authState === 'loading') {
    return <CenterMessage title="加载中..." />
  }

  if (authState === 'unauthenticated') {
    return <Navigate to="/login?reason=session_expired" replace />
  }

  if (currentUser?.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }

  return <>{children}</>
}
