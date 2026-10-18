import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('project team synchronization', () => {
  it('adds replacement roles before removing existing members and reloads current membership', () => {
    const source = fs.readFileSync('src/features/settings/ProjectsMgmtSection.tsx', 'utf8')
    const start = source.indexOf('async function syncProjectMembers(projectId: number, nextTeam: TeamMap)')
    const end = source.indexOf('async function handleSaveProjectEdit()', start)
    expect(start).toBeGreaterThanOrEqual(0)
    expect(end).toBeGreaterThan(start)
    const body = source.slice(start, end)
    expect(body).toContain('const currentMembers = await getProjectMembers(projectId)')
    expect(body.indexOf('addProjectMember(')).toBeLessThan(body.indexOf('removeProjectMember('))
  })
})
