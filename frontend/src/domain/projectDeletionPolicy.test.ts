import { describe, expect, it } from 'vitest'
import { canPermanentlyDeleteDraftProject, isProjectDeletionConfirmed } from './projectDeletionPolicy'

describe('project deletion policy', () => {
  it('allows only a technical administrator to delete a draft project', () => {
    expect(canPermanentlyDeleteDraftProject('draft', true)).toBe(true)
    expect(canPermanentlyDeleteDraftProject('draft', false)).toBe(false)
    expect(canPermanentlyDeleteDraftProject('active', true)).toBe(false)
  })

  it('requires the exact project name without trimming or case normalization', () => {
    expect(isProjectDeletionConfirmed('测试项目', '测试项目')).toBe(true)
    expect(isProjectDeletionConfirmed('测试项目', '测试项目 ')).toBe(false)
    expect(isProjectDeletionConfirmed('测试项目', '错误名称')).toBe(false)
  })
})
