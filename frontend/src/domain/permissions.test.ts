import { describe, expect, it } from 'vitest'
import { canProjectAction, type ProjectPermissionInput } from './permissions'

const input = (patch: Partial<ProjectPermissionInput> = {}): ProjectPermissionInput => ({
  isTechAdmin: false,
  isCompanyCeo: false,
  personId: 7,
  projectRoles: [],
  lifecycle: 'active',
  requesterPersonId: null,
  ...patch,
})

describe('project permission display matrix', () => {
  it('separates company management from project coach review', () => {
    expect(canProjectAction('project.dispatch', input({ isCompanyCeo: true, lifecycle: 'draft' }))).toBe(true)
    expect(canProjectAction('project.review_start', input({ isCompanyCeo: true }))).toBe(false)
    expect(canProjectAction('project.review_start', input({ projectRoles: ['project_ceo'] }))).toBe(true)
  })

  it('allows only the original owner to edit a close request', () => {
    expect(canProjectAction('project.edit_close_request', input({ projectRoles: ['owner'], lifecycle: 'pending_close', requesterPersonId: 7 }))).toBe(true)
    expect(canProjectAction('project.edit_close_request', input({ projectRoles: ['owner'], lifecycle: 'pending_close', requesterPersonId: 8 }))).toBe(false)
  })

  it('keeps archive and delete technical-admin only', () => {
    expect(canProjectAction('project.archive', input({ isTechAdmin: true, lifecycle: 'ended' }))).toBe(true)
    expect(canProjectAction('project.archive', input({ isCompanyCeo: true, lifecycle: 'ended' }))).toBe(false)
    expect(canProjectAction('project.delete', input({ projectRoles: ['owner'] }))).toBe(false)
  })
})
