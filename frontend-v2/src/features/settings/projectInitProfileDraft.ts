import type { ProjectInitAiProjectProfile } from '../../api/projectInitAi'

export const PROJECT_PROFILE_FIELDS = [
  'name',
  'background',
  'objectives',
  'expected_outcomes',
  'start_date',
  'end_date',
  'description',
] as const

export type ProjectProfileField = typeof PROJECT_PROFILE_FIELDS[number]
export type ProjectProfileValues = Partial<Record<ProjectProfileField, string>>
export type ProjectProfileFieldStatus = 'empty' | 'same' | 'supplement' | 'change' | 'unverified'
export type ProjectProfileDecision = 'apply' | 'keep'

export type ProjectProfileMergeField = {
  current: string
  suggested: string
  status: ProjectProfileFieldStatus
}

export type ProjectProfileMergePreview = {
  fields: Record<ProjectProfileField, ProjectProfileMergeField>
  suggestion: ProjectInitAiProjectProfile
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

export function buildProjectProfileMergePreview(
  current: ProjectProfileValues,
  suggestion: ProjectInitAiProjectProfile,
): ProjectProfileMergePreview {
  const evidenceVerified = suggestion.evidence.length > 0
  const fields = {} as Record<ProjectProfileField, ProjectProfileMergeField>
  PROJECT_PROFILE_FIELDS.forEach((field) => {
    const currentValue = text(current[field])
    const suggestedValue = text(suggestion[field])
    let status: ProjectProfileFieldStatus = 'empty'
    if (suggestedValue) {
      if (!evidenceVerified) status = 'unverified'
      else if (!currentValue) status = 'supplement'
      else if (currentValue === suggestedValue) status = 'same'
      else status = 'change'
    }
    fields[field] = { current: currentValue, suggested: suggestedValue, status }
  })
  return { fields, suggestion }
}

export function applyProjectProfileDecisions(
  preview: ProjectProfileMergePreview,
  decisions: Partial<Record<ProjectProfileField, ProjectProfileDecision>>,
): ProjectProfileValues {
  const result: ProjectProfileValues = {}
  PROJECT_PROFILE_FIELDS.forEach((field) => {
    const item = preview.fields[field]
    if (!item.suggested || item.status === 'unverified' || item.status === 'same' || item.status === 'empty') return
    if (item.status === 'supplement' || decisions[field] === 'apply') result[field] = item.suggested
  })
  return result
}
