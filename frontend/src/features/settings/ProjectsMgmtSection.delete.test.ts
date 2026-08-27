import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('project management permanent deletion UI', () => {
  it('uses the draft-only policy and exact-name confirmation dialog', () => {
    const source = fs.readFileSync('src/features/settings/ProjectsMgmtSection.tsx', 'utf8')

    expect(source).toContain('canPermanentlyDeleteDraftProject')
    expect(source).toContain('isProjectDeletionConfirmed')
    expect(source).toContain('永久删除项目')
    expect(source).toContain('请输入项目名称以确认')
    expect(source).toContain('deleteDraftProject')
    expect(source).toContain("toast.success('项目已永久删除')")
  })
})
