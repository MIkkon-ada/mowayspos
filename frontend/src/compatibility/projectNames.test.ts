import { describe, expect, it } from 'vitest'
import * as projectDisplay from '../domain/projectDisplay'

const projects = [{ id: 7, name: '当前项目' }] as any
const getProjectGroupKey = (projectDisplay as Record<string, unknown>).getProjectGroupKey as
  | ((projects: typeof projects, record: Record<string, unknown>, fallback?: string) => string)
  | undefined

describe('project name compatibility', () => {
  it('prefers a resolved project_id over a stale historical name', () => {
    expect(projectDisplay.getProjectDisplayName(projects, { project_id: 7, special_project: '旧名称' })).toBe('当前项目')
    expect(getProjectGroupKey?.(projects, { project_id: 7, special_project: '旧名称' })).toBe('project:7')
  })

  it('uses a historical name only when no current project id resolves', () => {
    expect(projectDisplay.getProjectDisplayName(projects, { related_special_project: '历史会议项目' })).toBe('历史会议项目')
    expect(getProjectGroupKey?.(projects, { special_project: '历史任务项目' })).toContain('历史任务项目')
  })

  it('uses the supplied fallback for records with no project data', () => {
    expect(projectDisplay.getProjectDisplayName(projects, {}, '（未分类）')).toBe('（未分类）')
  })
})
