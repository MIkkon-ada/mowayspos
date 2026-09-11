export type ProjectCloseRoles = {
  isSuperAdmin: boolean
  isCompanyCeo: boolean
  isRealProjectCeo: boolean
  isRealOwner: boolean
}

export type ProjectCloseAction = 'workProgress' | 'closeRequest' | 'closeReview' | 'closeArchiveView' | 'projectArchive' | 'viewDetail'

export function getProjectCloseMainAction(status: string, roles: ProjectCloseRoles): { type: ProjectCloseAction; label: string } | null {
  if (status === 'active') return { type: 'workProgress', label: '进入工作推进表' }
  if (status === 'pending_close') return { type: 'closeReview', label: roles.isSuperAdmin || roles.isRealProjectCeo ? '审核结束申请' : '查看结束申请' }
  if (status === 'ended') return { type: 'closeArchiveView', label: '查看结束档案' }
  if (status === 'archived') return { type: 'projectArchive', label: '查看项目档案' }
  return null
}

export function canCreateProjectCloseRequest(status: string, roles: ProjectCloseRoles): boolean {
  return canProjectAction('project.request_close', {
    isTechAdmin: roles.isSuperAdmin,
    isCompanyCeo: roles.isCompanyCeo,
    projectRoles: roles.isRealOwner ? ['owner'] : [],
    lifecycle: status,
  })
}

export function canReviewProjectCloseRequest(status: string, roles: ProjectCloseRoles): boolean {
  return canProjectAction('project.review_close_request', {
    isTechAdmin: roles.isSuperAdmin,
    isCompanyCeo: roles.isCompanyCeo,
    projectRoles: roles.isRealProjectCeo ? ['project_ceo'] : [],
    lifecycle: status,
  })
}

export function canEditProjectCloseRequest(status: string, requesterPersonId: number | null, currentPersonId: number | null, roles: ProjectCloseRoles): boolean {
  return canProjectAction('project.edit_close_request', {
    isTechAdmin: roles.isSuperAdmin,
    isCompanyCeo: roles.isCompanyCeo,
    personId: currentPersonId,
    projectRoles: roles.isRealOwner ? ['owner'] : [],
    lifecycle: status,
    requesterPersonId,
  })
}
type CloseProjectAction = 'project.request_close' | 'project.edit_close_request' | 'project.review_close_request'

type ClosePermissionInput = {
  isTechAdmin?: boolean
  isCompanyCeo?: boolean
  personId?: number | null
  projectRoles?: readonly string[] | null
  lifecycle?: string | null
  requesterPersonId?: number | null
}

// Kept dependency-free because this pure UI adapter is also loaded standalone by the contract suite.
function canProjectAction(action: CloseProjectAction, input: ClosePermissionInput): boolean {
  const roles = input.projectRoles ?? []
  const hasOwner = roles.includes('owner')
  const hasProjectCeo = roles.includes('project_ceo')
  const tech = Boolean(input.isTechAdmin)
  const lifecycle = input.lifecycle ?? ''

  if (action === 'project.request_close') return lifecycle === 'active' && (tech || hasOwner)
  if (action === 'project.review_close_request') return lifecycle === 'pending_close' && (tech || hasProjectCeo)
  const owned = hasOwner && input.personId != null && input.personId === input.requesterPersonId
  return lifecycle === 'pending_close' && (tech || owned)
}
