type PermissionInput = {
  isTechAdmin?: boolean
  projectRoles?: string[]
  globalRoles?: string[]
}

type SubTaskPermissionInput = PermissionInput & {
  currentUserName?: string | null
  assignee?: string | null
}

function hasAnyRole(roles: string[] | undefined, allowed: string[]) {
  return (roles ?? []).some((role) => allowed.includes(role))
}

export function canManageProjectWork({ isTechAdmin, projectRoles }: PermissionInput) {
  return !!(isTechAdmin || hasAnyRole(projectRoles, ['owner', 'coordinator']))
}

export function canManageProjectTrash({ isTechAdmin, projectRoles }: PermissionInput) {
  return !!(isTechAdmin || hasAnyRole(projectRoles, ['owner']))
}

export function canEditSubTaskStatus({
  isTechAdmin,
  projectRoles,
  currentUserName,
  assignee,
}: SubTaskPermissionInput) {
  return !!(
    canManageProjectWork({ isTechAdmin, projectRoles }) ||
    (currentUserName && assignee && currentUserName === assignee)
  )
}
