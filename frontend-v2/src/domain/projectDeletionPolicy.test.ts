import { describe, expect, it } from 'vitest'
import { canPermanentlyDeleteProject, isProjectDeletionConfirmed } from './projectDeletionPolicy'

describe('project deletion policy', () => {
  it('allows only a technical administrator to delete every project lifecycle state', () => {
    for (const status of ['draft', 'dispatched', 'pending_kickoff', 'pending_review', 'returned', 'active', 'pending_close', 'ended', 'archived']) {
      expect(canPermanentlyDeleteProject(status, true)).toBe(true)
      expect(canPermanentlyDeleteProject(status, false)).toBe(false)
    }
  })

  it('requires exact project name and destroy phrase without normalization', () => {
    expect(isProjectDeletionConfirmed('测试项目', '测试项目', '永久删除')).toBe(true)
    expect(isProjectDeletionConfirmed('测试项目', '测试项目 ', '永久删除')).toBe(false)
    expect(isProjectDeletionConfirmed('测试项目', '错误名称', '永久删除')).toBe(false)
    expect(isProjectDeletionConfirmed('测试项目', '测试项目', '删除')).toBe(false)
  })
})
