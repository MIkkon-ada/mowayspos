export function canPermanentlyDeleteProject(_status: string, isSuperAdmin: boolean): boolean {
  return isSuperAdmin
}

export function isProjectDeletionConfirmed(projectName: string, confirmation: string, phrase: string): boolean {
  return projectName === confirmation && phrase === '永久删除'
}
