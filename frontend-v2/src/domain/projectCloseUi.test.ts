import { describe, expect, it } from 'vitest'
import {
  canCreateProjectCloseRequest,
  canEditProjectCloseRequest,
  canReviewProjectCloseRequest,
  getProjectCloseMainAction,
} from './projectCloseUi'

const owner = { isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true }
const coach = { isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: true, isRealOwner: false }

describe('project close UI compatibility', () => {
  it('keeps the current lifecycle action labels', () => {
    expect(getProjectCloseMainAction('active', owner)).toEqual({ type: 'workProgress', label: '进入工作推进表' })
    expect(getProjectCloseMainAction('pending_close', coach)).toEqual({ type: 'closeReview', label: '审核结束申请' })
    expect(getProjectCloseMainAction('archived', owner)).toEqual({ type: 'projectArchive', label: '查看项目档案' })
  })

  it('delegates create, edit and review permission without widening roles', () => {
    expect(canCreateProjectCloseRequest('active', owner)).toBe(true)
    expect(canEditProjectCloseRequest('pending_close', 7, 7, owner)).toBe(true)
    expect(canReviewProjectCloseRequest('pending_close', coach)).toBe(true)
    expect(canReviewProjectCloseRequest('pending_close', owner)).toBe(false)
  })
})
