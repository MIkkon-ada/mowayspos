import { describe, expect, it } from 'vitest'
import { canEditProjectInit, canShowProjectSubmitAction, getProjectInitEditNotice } from './projectLifecycleStatus'

describe('canShowProjectSubmitAction', () => {
  it('allows owner submission only after dispatch or return', () => {
    expect(canShowProjectSubmitAction({ status: 'draft' })).toBe(false)
    expect(canShowProjectSubmitAction({ status: 'dispatched' })).toBe(true)
    expect(canShowProjectSubmitAction({ status: 'returned' })).toBe(true)
  })
})

describe('project-init editability', () => {
  it('allows editing only for dispatched and returned projects', () => {
    expect(canEditProjectInit({ status: 'draft' })).toBe(false)
    expect(canEditProjectInit({ status: 'pending_review' })).toBe(false)
    expect(canEditProjectInit({ status: 'dispatched' })).toBe(true)
    expect(canEditProjectInit({ status: 'returned' })).toBe(true)
    expect(canEditProjectInit({ status: 'active' })).toBe(false)
  })

  it('explains why a pending review project is read-only', () => {
    expect(getProjectInitEditNotice({ status: 'pending_review' })).toBe('项目已提交审核，当前只能查看，需审核退回后才能继续完善。')
    expect(getProjectInitEditNotice({ status: 'active' })).toContain('进行中')
  })
})
