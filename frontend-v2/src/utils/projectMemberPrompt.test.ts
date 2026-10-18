import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getProjectMembers } from '../api/projects'
import { promptProjectMember } from './projectMemberPrompt'

vi.mock('../api/projects', () => ({ getProjectMembers: vi.fn() }))

const members = [
  { id: 1, project_id: 7, person_id: 11, person_name_snapshot: '同名成员', role: 'member', note: '', joined_at: null },
  { id: 2, project_id: 7, person_id: 12, person_name_snapshot: '同名成员', role: 'member', note: '', joined_at: null },
]

describe('promptProjectMember', () => {
  beforeEach(() => {
    vi.mocked(getProjectMembers).mockResolvedValue(members)
    vi.stubGlobal('window', { prompt: vi.fn().mockReturnValue('2') })
  })

  it('distinguishes project members with duplicate names by selected list entry', async () => {
    await expect(promptProjectMember(7, '请选择协助人')).resolves.toMatchObject({ person_id: 12 })
    expect(window.prompt).toHaveBeenCalledWith(expect.stringContaining('人员编号 12'))
  })

  it('rejects an invalid list selection', async () => {
    vi.mocked(window.prompt).mockReturnValue('3')
    await expect(promptProjectMember(7, '请选择协助人')).rejects.toThrow('请输入列表中的有效序号')
  })
})
