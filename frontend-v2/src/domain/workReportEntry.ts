export type WorkReportEntryIntent = 'report' | 'issue' | 'achievement'

export function buildWorkReportEntryUrl(
  projectId: number,
  subtaskId: number,
  entryIntent: WorkReportEntryIntent,
) {
  const params = new URLSearchParams({
    projectId: String(projectId),
    subtaskId: String(subtaskId),
    entryIntent,
  })
  return `/work/submit?${params.toString()}`
}
