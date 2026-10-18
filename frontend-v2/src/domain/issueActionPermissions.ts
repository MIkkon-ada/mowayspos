export type IssueActionPermissionInput = {
  roles: string[]
  isTechAdmin?: boolean
  issueType: string
  status: string
  isOwnerAssignee?: boolean
}

const COORDINATION_TYPES = new Set(['待协调', '需协调', '协调', '协调事项'])
const DECISION_TYPES = new Set(['需决策', '待决策', '决策', '决策事项', '需CEO决策', '待CEO决策'])

export function getIssueActionPermissions({
  roles,
  isTechAdmin = false,
  issueType,
  status,
  isOwnerAssignee = false,
}: IssueActionPermissionInput) {
  const roleSet = new Set(roles)
  const isOwner = roleSet.has('owner')
  const isCoordinator = roleSet.has('coordinator')
  const isProjectCoach = roleSet.has('project_ceo')
  const canManage = isTechAdmin || isOwner || isCoordinator || isProjectCoach
  const isCoordinationOpinion = status === '待协调' && COORDINATION_TYPES.has(issueType)
  const isDecisionOpinion = status === '待决策' && DECISION_TYPES.has(issueType)
  const canSubmitOpinion = (isCoordinationOpinion && (isTechAdmin || isCoordinator))
    || (isDecisionOpinion && (isTechAdmin || isProjectCoach))
  const canOwnerConfirm = status === '待负责人确认' && (isTechAdmin || isOwner || isOwnerAssignee)

  return {
    canManage,
    canAssignHelper: isTechAdmin || isOwner,
    canSubmitOpinion,
    canRequestDecision: (isTechAdmin || isOwner || isCoordinator)
      && status !== '待决策'
      && status !== '待负责人确认',
    canOwnerConfirm,
    canResolve: (isTechAdmin || isOwner) && status !== '待负责人确认',
    canClose: isTechAdmin || isOwner,
  }
}
