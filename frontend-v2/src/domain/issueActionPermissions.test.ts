import { describe, expect, it } from 'vitest'
import { getIssueActionPermissions } from './issueActionPermissions'

describe('issue action permissions', () => {
  it('does not show coordinator opinion controls to an owner for a normal issue', () => {
    expect(getIssueActionPermissions({ roles: ['owner'], issueType: '问题', status: '待协调' })).toMatchObject({
      canManage: true,
      canAssignHelper: true,
      canRequestDecision: true,
      canSubmitOpinion: false,
      canResolve: true,
      canClose: true,
    })
  })

  it('allows the project coach to submit an opinion only for a pending decision', () => {
    expect(getIssueActionPermissions({ roles: ['project_ceo'], issueType: '需决策', status: '待决策' })).toMatchObject({
      canManage: true,
      canSubmitOpinion: true,
      canAssignHelper: false,
      canResolve: false,
      canClose: false,
    })
    expect(getIssueActionPermissions({ roles: ['project_ceo'], issueType: '问题', status: '待协调' }).canSubmitOpinion).toBe(false)
  })

  it('allows a coordinator to submit opinions for coordination items but not resolve them', () => {
    expect(getIssueActionPermissions({ roles: ['coordinator'], issueType: '待协调', status: '待协调' })).toMatchObject({
      canManage: true,
      canSubmitOpinion: true,
      canRequestDecision: true,
      canAssignHelper: false,
      canResolve: false,
      canClose: false,
    })
  })
})
