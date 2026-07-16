export type ProjectCloseRoles = {
  isSuperAdmin: boolean
  isCompanyCeo: boolean
  isRealProjectCeo: boolean
  isRealOwner: boolean
}

export type ProjectCloseAction = 'workProgress' | 'closeRequest' | 'closeReview' | 'closeArchiveView' | 'viewDetail'

export function getProjectCloseMainAction(status: string, roles: ProjectCloseRoles): { type: ProjectCloseAction; label: string } | null {
  if (status === 'active') return { type: 'workProgress', label: '进入工作推进表' }
  if (status === 'pending_close') return { type: 'closeReview', label: roles.isSuperAdmin || roles.isRealProjectCeo ? '审核结束申请' : '查看结束申请' }
  if (status === 'ended') return { type: 'closeArchiveView', label: '查看结束档案' }
  if (status === 'archived') return { type: 'closeArchiveView', label: '查看归档档案' }
  return null
}

export function canCreateProjectCloseRequest(status: string, roles: ProjectCloseRoles): boolean {
  return status === 'active' && (roles.isRealOwner || roles.isSuperAdmin)
}

export function canReviewProjectCloseRequest(status: string, roles: ProjectCloseRoles): boolean {
  return status === 'pending_close' && (roles.isRealProjectCeo || roles.isSuperAdmin)
}

export function canEditProjectCloseRequest(status: string, requesterPersonId: number | null, currentPersonId: number | null, roles: ProjectCloseRoles): boolean {
  return status === 'pending_close' && (roles.isSuperAdmin || (requesterPersonId !== null && requesterPersonId === currentPersonId && roles.isRealOwner))
}
