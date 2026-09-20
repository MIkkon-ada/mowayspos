export function projectOwnerSubmitPath(projectId: number): string {
  return `/home/projects/${projectId}/owner-submit`
}

export function projectEditPath(projectId: number): string {
  return `/home/projects?edit=${projectId}`
}
