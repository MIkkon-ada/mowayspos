import { describe, expect, it } from 'vitest'
import {
  canProjectAction,
  canWorkflowAction,
  type ProjectPermissionInput,
  type WorkflowPermissionInput,
} from './permissions'

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

const workflowInput = (patch: Partial<WorkflowPermissionInput> = {}): WorkflowPermissionInput => ({
  isTechAdmin: false,
  isCompanyCeo: false,
  personId: 7,
  projectRoles: [],
  submitterPersonId: null,
  creatorPersonId: null,
  ...patch,
})

describe('confirmation and meeting workflow permission display matrix', () => {
  it('keeps company management as a reader, not a project coach', () => {
    expect(canWorkflowAction('confirmation.view', workflowInput({ isCompanyCeo: true }))).toBe(true)
    expect(canWorkflowAction('confirmation.ceo_decide', workflowInput({ isCompanyCeo: true }))).toBe(false)
    expect(canWorkflowAction('confirmation.ceo_decide', workflowInput({ projectRoles: ['project_ceo'] }))).toBe(true)
  })

  it('matches meeting create, publish, and progress-review role boundaries', () => {
    expect(canWorkflowAction('meeting.create', workflowInput({ projectRoles: ['member'] }))).toBe(true)
    expect(canWorkflowAction('meeting.publish', workflowInput({ projectRoles: ['coordinator'] }))).toBe(false)
    expect(canWorkflowAction('meeting.progress_review', workflowInput({ projectRoles: ['coordinator'] }))).toBe(true)
    expect(canWorkflowAction('meeting.progress_review', workflowInput({ projectRoles: ['member'] }))).toBe(false)
  })

  it('allows confirmation resubmission only for the original submitter', () => {
    expect(canWorkflowAction('confirmation.resubmit', workflowInput({ submitterPersonId: 7 }))).toBe(true)
    expect(canWorkflowAction('confirmation.resubmit', workflowInput({ submitterPersonId: 8 }))).toBe(false)
  })
})
