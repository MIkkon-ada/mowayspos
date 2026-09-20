import type { BatchImportRow } from '../../api/projects'

export type ProjectPlanImportGroup = {
  key: string
  projectName: string
  workstream: string
  rows: BatchImportRow[]
}

export function groupImportRows(rows: BatchImportRow[]): ProjectPlanImportGroup[] {
  const groups = new Map<string, ProjectPlanImportGroup>()
  for (const row of rows) {
    const projectName = row.project_name.trim()
    const workstream = (row.workstream ?? '').trim()
    const key = `${projectName}::${workstream}`
    const current = groups.get(key)
    if (current) current.rows.push(row)
    else groups.set(key, { key, projectName, workstream, rows: [row] })
  }
  return Array.from(groups.values())
}
