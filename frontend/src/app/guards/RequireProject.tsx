import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useProject } from '../../context/ProjectContext'
import { canAccessProjectRoute } from '../../domain/authFlow'

type RequireProjectProps = {
  children: ReactNode
}

export function RequireProject({ children }: RequireProjectProps) {
  const { currentProjectId, currentUser, projects } = useProject()

  if (currentProjectId === null) {
    return <Navigate to="/no-access" replace />
  }

  if (!canAccessProjectRoute(currentUser, currentProjectId, projects)) {
    return <Navigate to="/no-access" replace />
  }

  return <>{children}</>
}
