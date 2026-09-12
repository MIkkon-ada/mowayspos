import type { Project } from '../types'

type ProjectRecord = Record<string, unknown>
type ProjectSummary = Pick<Project, 'id' | 'name'>

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function asRecord(value: unknown): ProjectRecord {
  return typeof value === 'object' && value !== null ? (value as ProjectRecord) : {}
}

export function getProjectById<T extends ProjectSummary>(projects: ReadonlyArray<T>, projectId: number | null | undefined): T | null {
  if (projectId == null) return null
  return projects.find((project) => project.id === projectId) ?? null
}

export function getProjectIdFromRecord(record: ProjectRecord | null | undefined): number | null {
  const data = record ?? {}
  const direct = toNumber(data.project_id)
  if (direct != null) return direct
  const alias = toNumber(data.projectId)
  if (alias != null) return alias
  const parent = toNumber(data.parent_project_id)
  if (parent != null) return parent

  const nestedParent = asRecord(data.parent_task)
  const nested = toNumber(nestedParent.project_id) ?? toNumber(nestedParent.projectId) ?? toNumber(nestedParent.parent_project_id)
  if (nested != null) return nested

  return null
}

export function isSameProjectById(record: ProjectRecord | null | undefined, projectId: number | null | undefined): boolean {
  const resolved = getProjectIdFromRecord(record)
  return resolved != null && projectId != null && resolved === projectId
}
