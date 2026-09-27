import { describe, expect, it } from 'vitest'
import type { ProjectInitAiProjectProfile } from '../../api/projectInitAi'
import { applyProjectProfileDecisions, buildProjectProfileMergePreview } from './projectInitProfileDraft'

const evidence = [{
  attachment_id: 1 as any,
  file_name: '项目方案.xlsx',
  location: '概况!A1:B8',
  excerpt: '项目目标：提升复用率',
}]

function suggestion(overrides: Partial<ProjectInitAiProjectProfile> = {}): ProjectInitAiProjectProfile {
  return {
    name: '岗位 AI 应用优化',
    background: '岗位知识分散',
    objectives: '提升复用率',
    expected_outcomes: '形成案例库',
    start_date: '2026-07-01',
    end_date: '2026-09-30',
    description: '',
    confidence: 0.9,
    evidence,
    warnings: [],
    ...overrides,
  }
}

function currentProfile(overrides: Record<string, string> = {}) {
  const profile = suggestion()
  return {
    name: profile.name,
    background: profile.background,
    objectives: profile.objectives,
    expected_outcomes: profile.expected_outcomes,
    start_date: profile.start_date,
    end_date: profile.end_date,
    description: profile.description,
    ...overrides,
  }
}

describe('projectInitProfileDraft', () => {
  it('marks an empty existing field as a safe supplement', () => {
    const preview = buildProjectProfileMergePreview(
      currentProfile({ objectives: '' }),
      suggestion(),
    )

    expect(preview.fields.objectives.status).toBe('supplement')
    expect(applyProjectProfileDecisions(preview, {})).toEqual({ objectives: '提升复用率' })
  })

  it('keeps a non-empty conflicting value until the user explicitly applies it', () => {
    const preview = buildProjectProfileMergePreview(
      currentProfile({ objectives: '旧目标' }),
      suggestion(),
    )

    expect(preview.fields.objectives.status).toBe('change')
    expect(applyProjectProfileDecisions(preview, {})).toEqual({})
    expect(applyProjectProfileDecisions(preview, { objectives: 'apply' })).toEqual({ objectives: '提升复用率' })
  })

  it('does not expose an unverified suggestion for application', () => {
    const preview = buildProjectProfileMergePreview(
      currentProfile({ background: '' }),
      suggestion({ evidence: [] }),
    )

    expect(preview.fields.background.status).toBe('unverified')
    expect(applyProjectProfileDecisions(preview, { background: 'apply' })).toEqual({})
  })
})
