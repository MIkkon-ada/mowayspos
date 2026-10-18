export function parseWorkProgressProjectId(searchParams: URLSearchParams): number | null {
  const raw = searchParams.get('projectId')
  if (raw === null || !/^\d+$/.test(raw)) return null
  const projectId = Number(raw)
  return Number.isSafeInteger(projectId) && projectId > 0 ? projectId : null
}

export function updateWorkProgressProjectQuery(searchParams: URLSearchParams, selectedProject: string): URLSearchParams {
  const next = new URLSearchParams(searchParams)
  const projectId = Number(selectedProject)
  if (selectedProject && Number.isSafeInteger(projectId) && projectId > 0) next.set('projectId', String(projectId))
  else next.delete('projectId')
  return next
}
