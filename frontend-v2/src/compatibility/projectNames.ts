import type { Project } from '../types'
import { getProjectById, getProjectIdFromRecord } from '../domain/projectIdentity'

type ProjectRecord = Record<string, unknown>
type ProjectSummary = Pick<Project, 'id' | 'name'>

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function firstText(source: ProjectRecord, keys: string[]): string {
  for (const key of keys) {
    const value = text(source[key])
    if (value) return value
  }
  return ''
}

const currentProjectKey = (projectId: number) => `project:${projectId}`
const historicalProjectKey = (name: string) => `compat-name:${name}`

export function getProjectDisplayName(
  projects: ReadonlyArray<ProjectSummary>,
  record?: ProjectRecord | null,
  fallback = '',
): string {
  const data = record ?? {}
  const projectId = getProjectIdFromRecord(data)
  if (projectId != null) {
    const matched = getProjectById(projects, projectId)
    if (matched) return matched.name
  }

  return firstText(data, [
    'special_project',
    'related_special_project',
    'project_name',
    'projectName',
    'parent_special_project',
  ]) || fallback
}

export function getProjectGroupKey(
  projects: ReadonlyArray<ProjectSummary>,
  record?: ProjectRecord | null,
  fallback = '',
): string {
  const projectId = getProjectIdFromRecord(record)
  if (projectId != null) return currentProjectKey(projectId)
  return historicalProjectKey(getProjectDisplayName(projects, record, fallback))
}

export function getProjectNameFromGroupKey(
  projects: ReadonlyArray<ProjectSummary>,
  key: string,
  records: ReadonlyArray<ProjectRecord>,
  fallback = '',
): string {
  if (key.startsWith('project:')) {
    const projectId = Number(key.slice('project:'.length))
    if (Number.isFinite(projectId)) {
      const matched = getProjectById(projects, projectId)
      if (matched) return matched.name
    }
  }
  if (key.startsWith('compat-name:')) return key.slice('compat-name:'.length) || fallback
  return getProjectDisplayName(projects, records[0], fallback)
}
