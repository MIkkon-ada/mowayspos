export function canPermanentlyDeleteDraftProject(status: string, isSuperAdmin: boolean): boolean {
  return isSuperAdmin && status === 'draft'
}

export function isProjectDeletionConfirmed(projectName: string, confirmation: string): boolean {
  return projectName === confirmation
}
