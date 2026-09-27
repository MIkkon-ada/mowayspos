import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useProject } from '../../context/ProjectContext'
import { canAccessTechAdminRoute, canPreviewClientRoute } from '../../domain/authFlow'
import { canManageProjects, canViewProjectManagement } from '../../domain/permissions'

type RequireCapabilityProps = {
  children: ReactNode
  mode: 'tech_admin' | 'project_admin' | 'project_view' | 'client_preview'
}

export function RequireCapability({ children, mode }: RequireCapabilityProps) {
  const { currentUser, globalUserRoles } = useProject()

  const allowed =
    mode === 'tech_admin'
      ? canAccessTechAdminRoute(currentUser)
      : mode === 'project_admin'
        ? canManageProjects(currentUser, globalUserRoles)
        : mode === 'project_view'
          ? canViewProjectManagement(currentUser, globalUserRoles)
          : canPreviewClientRoute(currentUser)

  if (!allowed) {
    return <Navigate to="/no-access" replace />
  }

  return <>{children}</>
}
