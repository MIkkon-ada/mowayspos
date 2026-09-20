import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('meeting progress review UI', () => {
  it('exposes analysis, evidence, confirmation, and ignore actions', () => {
    const source = fs.readFileSync('src/features/meeting/MeetingProgressReviewSection.tsx', 'utf8')
    expect(source).toContain('确认并写回')
    expect(source).toContain('忽略')
    expect(source).toContain('evidence_quote')
  })
})
