import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('project management permanent deletion UI', () => {
  it('uses the draft-only policy and exact-name confirmation dialog', () => {
    const source = fs.readFileSync('src/features/settings/ProjectsMgmtSection.tsx', 'utf8')

    expect(source).toContain('canPermanentlyDeleteProject')
    expect(source).toContain('isProjectDeletionConfirmed')
    expect(source).toContain('永久删除项目')
    expect(source).toContain('请输入项目名称以确认')
    expect(source).toContain('请输入“永久删除”以确认')
    expect(source).toContain("const [deletePhrase, setDeletePhrase] = useState('')")
    expect(source).toContain('deleteProject(projectId, deleteConfirmation, deletePhrase)')
    expect(source).toContain("toast.warning('项目数据已删除，附件文件正在等待清理')")
  })
})
