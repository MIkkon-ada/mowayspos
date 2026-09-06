export const aiDocumentFormats = {
  meeting: ['.docx', '.txt', '.xlsx'],
  workReport: ['.docx', '.pdf', '.xlsx', '.pptx'],
  taskPlan: ['.docx', '.xlsx', '.txt'],
  projectInit: ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt'],
} as const

export type AiDocumentFormatTarget = keyof typeof aiDocumentFormats

export function acceptedDocumentTypes(target: AiDocumentFormatTarget): string {
  return aiDocumentFormats[target].join(',')
}
